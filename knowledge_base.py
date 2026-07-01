"""
素材库 / 知识库模块
- SQLite 存元数据（文件名、上传时间、类型、标签、纯文本内容）
- 本地文件夹存原始文件
- BM25 关键词检索（纯 Python 实现，无需外部依赖）
"""
import os
import sqlite3
import re
import math
import time
from typing import List, Dict, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'kb.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            filetype TEXT,
            category TEXT DEFAULT '通用',
            tags TEXT DEFAULT '',
            content TEXT DEFAULT '',
            size INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT,
            industry TEXT,
            contact TEXT,
            notes TEXT,
            stage TEXT DEFAULT '初次接触',
            last_touch INTEGER,
            created_at INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


init_db()


# ============ 文本抽取 ============
def extract_text(filepath: str, filetype: str) -> str:
    """从文件抽取纯文本"""
    try:
        if filetype in ('txt', 'md', 'csv', 'json', 'log'):
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()[:50000]
        elif filetype == 'pdf':
            try:
                import subprocess
                r = subprocess.run(['pdftotext', filepath, '-'],
                                   capture_output=True, timeout=30)
                return r.stdout.decode('utf-8', errors='ignore')[:50000]
            except Exception:
                return ''
        elif filetype in ('docx', 'doc'):
            try:
                from docx import Document
                doc = Document(filepath)
                return '\n'.join(p.text for p in doc.paragraphs)[:50000]
            except Exception:
                return ''
        else:
            return ''
    except Exception as e:
        return f'[抽取失败: {e}]'


# ============ 简易中英文分词 ============
def tokenize(text: str) -> List[str]:
    """字符级 + 英文单词，简单但足够 Demo 用"""
    text = text.lower()
    tokens = []
    # 英文/数字单词
    tokens.extend(re.findall(r'[a-z0-9]+', text))
    # 中文按字切
    tokens.extend(re.findall(r'[\u4e00-\u9fff]', text))
    return tokens


# ============ BM25 检索 ============
def search(query: str, top_k: int = 5, category: Optional[str] = None) -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    if category:
        cur.execute('SELECT * FROM documents WHERE category=?', (category,))
    else:
        cur.execute('SELECT * FROM documents')
    docs = [dict(r) for r in cur.fetchall()]
    conn.close()

    if not docs:
        return []

    q_tokens = tokenize(query)
    if not q_tokens:
        return docs[:top_k]

    # BM25 参数
    k1, b = 1.5, 0.75
    N = len(docs)
    doc_tokens = [tokenize(d['content'] + ' ' + d['filename'] + ' ' + d['tags']) for d in docs]
    avgdl = sum(len(t) for t in doc_tokens) / max(N, 1)
    # DF
    df = {}
    for tokens in doc_tokens:
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1

    scores = []
    for i, tokens in enumerate(doc_tokens):
        score = 0.0
        dl = len(tokens)
        tf_map = {}
        for t in tokens:
            tf_map[t] = tf_map.get(t, 0) + 1
        for q in q_tokens:
            if q not in tf_map:
                continue
            idf = math.log((N - df.get(q, 0) + 0.5) / (df.get(q, 0) + 0.5) + 1)
            tf = tf_map[q]
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / max(avgdl, 1)))
        scores.append((score, i))

    scores.sort(key=lambda x: -x[0])
    results = []
    for score, i in scores[:top_k]:
        if score <= 0:
            continue
        d = docs[i]
        # 高亮片段
        snippet = d['content'][:300] if d['content'] else ''
        results.append({
            'id': d['id'],
            'filename': d['filename'],
            'category': d['category'],
            'tags': d['tags'],
            'snippet': snippet,
            'score': round(score, 3),
        })
    return results


# ============ 文档 CRUD ============
def add_document(filename: str, filepath: str, filetype: str,
                 category: str = '通用', tags: str = '') -> int:
    content = extract_text(filepath, filetype)
    size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO documents (filename, filepath, filetype, category, tags, content, size, created_at)
        VALUES (?,?,?,?,?,?,?,?)
    ''', (filename, filepath, filetype, category, tags, content, size, int(time.time())))
    doc_id = cur.lastrowid
    conn.commit()
    conn.close()
    return doc_id


def list_documents(category: Optional[str] = None) -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    if category:
        cur.execute('SELECT id, filename, filetype, category, tags, size, created_at FROM documents WHERE category=? ORDER BY id DESC', (category,))
    else:
        cur.execute('SELECT id, filename, filetype, category, tags, size, created_at FROM documents ORDER BY id DESC')
    return [dict(r) for r in cur.fetchall()]


def get_document(doc_id: int) -> Optional[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM documents WHERE id=?', (doc_id,))
    r = cur.fetchone()
    conn.close()
    return dict(r) if r else None


def delete_document(doc_id: int) -> bool:
    d = get_document(doc_id)
    if not d:
        return False
    try:
        if os.path.exists(d['filepath']):
            os.remove(d['filepath'])
    except Exception:
        pass
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM documents WHERE id=?', (doc_id,))
    conn.commit()
    conn.close()
    return True


# ============ 客户 CRUD（销售系统专属） ============
def add_customer(name: str, company: str = '', industry: str = '',
                 contact: str = '', notes: str = '', stage: str = '初次接触') -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO customers (name, company, industry, contact, notes, stage, last_touch, created_at)
        VALUES (?,?,?,?,?,?,?,?)
    ''', (name, company, industry, contact, notes, stage, int(time.time()), int(time.time())))
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid


def list_customers() -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM customers ORDER BY id DESC')
    return [dict(r) for r in cur.fetchall()]


def update_customer_stage(cid: int, stage: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('UPDATE customers SET stage=?, last_touch=? WHERE id=?',
                (stage, int(time.time()), cid))
    conn.commit()
    conn.close()


def delete_customer(cid: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM customers WHERE id=?', (cid,))
    conn.commit()
    conn.close()
