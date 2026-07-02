"""
素材库 / 知识库模块（EdgeOne Serverless 部署专用版）
- 与仓库根目录的 knowledge_base.py 逻辑一致
- 唯一区别：数据目录改为 /tmp，因为 Serverless 函数运行环境项目目录只读，
  只有 /tmp 可写。注意：/tmp 在冷启动后可能被清空，数据不做长期持久化承诺，
  仅保证当次运行会话内可用（满足评审 Demo 场景）。

重要加固（修复 500 报错）：
- 之前版本在模块加载时直接 os.makedirs() + init_db()，如果 Serverless 沙箱
  不允许写 /tmp（权限受限/只读），会导致 import 本模块直接抛异常，进而拖垮
  整个 Flask app（因为入口文件顶部 import knowledge_base），表现为所有页面
  （包括首页）都 500，跟有没有用到素材库功能无关。
- 现在把目录创建 + 建库过程做了多级兜底（/tmp 固定目录 → tempfile 临时目录
  → 纯内存 sqlite），且任何一步失败都不会向上抛异常导致 import 失败，只会
  把 KB_AVAILABLE 置为 False，相关 API 优雅降级返回空结果，不会拖垮整个应用。
"""
import os
import sqlite3
import re
import math
import time
import tempfile
from typing import List, Dict, Optional

KB_AVAILABLE = True
DB_PATH = ':memory:'
UPLOAD_DIR = None
_INIT_ERROR = ''

def _setup_storage():
    """多级兜底选出一个可写的数据目录，全部失败则退化为内存库（本次请求内可用，跨请求不保证）"""
    global DB_PATH, UPLOAD_DIR, KB_AVAILABLE, _INIT_ERROR
    candidates = ['/tmp/kb_data_sales', None]  # None 表示走 tempfile 兜底
    for base in candidates:
        try:
            if base is None:
                base = tempfile.mkdtemp(prefix='kb_data_sales_')
            upload_dir = os.path.join(base, 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            db_path = os.path.join(base, 'kb.db')
            # 尝试真实建一次连接验证可写
            conn = sqlite3.connect(db_path)
            conn.execute('CREATE TABLE IF NOT EXISTS _probe (id INTEGER)')
            conn.commit()
            conn.close()
            DB_PATH, UPLOAD_DIR = db_path, upload_dir
            return
        except Exception as e:
            _INIT_ERROR = str(e)
            continue
    # 全部失败，退化为纯内存库（同一进程内的多次请求若复用同一 worker 仍可用）
    DB_PATH, UPLOAD_DIR = ':memory:', tempfile.gettempdir()


_setup_storage()


_conn_singleton = None

def get_conn():
    global _conn_singleton
    if DB_PATH == ':memory:':
        # 内存库必须复用同一个连接，否则每次都是空库
        if _conn_singleton is None:
            _conn_singleton = sqlite3.connect(':memory:', check_same_thread=False)
            _conn_singleton.row_factory = sqlite3.Row
        return _conn_singleton
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_close(conn):
    if DB_PATH != ':memory:':
        conn.close()


def init_db():
    global KB_AVAILABLE, _INIT_ERROR
    try:
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
        _safe_close(conn)
        KB_AVAILABLE = True
    except Exception as e:
        KB_AVAILABLE = False
        _INIT_ERROR = str(e)


init_db()


def get_status() -> Dict:
    """诊断用：返回当前存储层状态"""
    return {
        'kb_available': KB_AVAILABLE,
        'db_path': DB_PATH,
        'upload_dir': UPLOAD_DIR,
        'init_error': _INIT_ERROR or None,
    }


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
    tokens.extend(re.findall(r'[a-z0-9]+', text))
    tokens.extend(re.findall(r'[\u4e00-\u9fff]', text))
    return tokens


# ============ BM25 检索 ============
def search(query: str, top_k: int = 5, category: Optional[str] = None) -> List[Dict]:
    if not KB_AVAILABLE:
        return []
    try:
        conn = get_conn()
        cur = conn.cursor()
        if category:
            cur.execute('SELECT * FROM documents WHERE category=?', (category,))
        else:
            cur.execute('SELECT * FROM documents')
        docs = [dict(r) for r in cur.fetchall()]
        _safe_close(conn)
    except Exception:
        return []

    if not docs:
        return []

    q_tokens = tokenize(query)
    if not q_tokens:
        return docs[:top_k]

    k1, b = 1.5, 0.75
    N = len(docs)
    doc_tokens = [tokenize(d['content'] + ' ' + d['filename'] + ' ' + d['tags']) for d in docs]
    avgdl = sum(len(t) for t in doc_tokens) / max(N, 1)
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
    if not KB_AVAILABLE:
        raise RuntimeError('素材库当前不可用（存储层初始化失败）')
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
    _safe_close(conn)
    return doc_id


def list_documents(category: Optional[str] = None) -> List[Dict]:
    if not KB_AVAILABLE:
        return []
    try:
        conn = get_conn()
        cur = conn.cursor()
        if category:
            cur.execute('SELECT id, filename, filetype, category, tags, size, created_at FROM documents WHERE category=? ORDER BY id DESC', (category,))
        else:
            cur.execute('SELECT id, filename, filetype, category, tags, size, created_at FROM documents ORDER BY id DESC')
        rows = [dict(r) for r in cur.fetchall()]
        _safe_close(conn)
        return rows
    except Exception:
        return []


def get_document(doc_id: int) -> Optional[Dict]:
    if not KB_AVAILABLE:
        return None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT * FROM documents WHERE id=?', (doc_id,))
        r = cur.fetchone()
        _safe_close(conn)
        return dict(r) if r else None
    except Exception:
        return None


def delete_document(doc_id: int) -> bool:
    if not KB_AVAILABLE:
        return False
    d = get_document(doc_id)
    if not d:
        return False
    try:
        if os.path.exists(d['filepath']):
            os.remove(d['filepath'])
    except Exception:
        pass
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('DELETE FROM documents WHERE id=?', (doc_id,))
        conn.commit()
        _safe_close(conn)
        return True
    except Exception:
        return False


# ============ 客户 CRUD（销售系统专属） ============
def add_customer(name: str, company: str = '', industry: str = '',
                 contact: str = '', notes: str = '', stage: str = '初次接触') -> int:
    if not KB_AVAILABLE:
        raise RuntimeError('客户库当前不可用（存储层初始化失败）')
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO customers (name, company, industry, contact, notes, stage, last_touch, created_at)
        VALUES (?,?,?,?,?,?,?,?)
    ''', (name, company, industry, contact, notes, stage, int(time.time()), int(time.time())))
    cid = cur.lastrowid
    conn.commit()
    _safe_close(conn)
    return cid


def list_customers() -> List[Dict]:
    if not KB_AVAILABLE:
        return []
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT * FROM customers ORDER BY id DESC')
        rows = [dict(r) for r in cur.fetchall()]
        _safe_close(conn)
        return rows
    except Exception:
        return []


def update_customer_stage(cid: int, stage: str):
    if not KB_AVAILABLE:
        return
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('UPDATE customers SET stage=?, last_touch=? WHERE id=?',
                    (stage, int(time.time()), cid))
        conn.commit()
        _safe_close(conn)
    except Exception:
        pass


def delete_customer(cid: int):
    if not KB_AVAILABLE:
        return
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('DELETE FROM customers WHERE id=?', (cid,))
        conn.commit()
        _safe_close(conn)
    except Exception:
        pass
