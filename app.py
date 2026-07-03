"""
AI 销售助理 - 主应用
北极星-炼术师 队伍作品（腾讯 AI 黑客松 - 方向三·营销）

功能模块：
1. 客户背景速查 - 联网调研 + 素材库检索
2. 触达内容生成 - 多渠道模板 + LLM 生成
3. 异议处理教练 - 场景化话术
4. 跟进节奏管理 - 客户库 + 阶段化建议
5. 销售过程复盘 - 对话文本分析
6. 素材库 - 上传文档 + BM25 检索
"""
import os
import json
import time
from flask import Flask, render_template, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename

import llm_client
import knowledge_base as kb

app = Flask(__name__)
app.secret_key = 'polaris-alchemist-sales-2024'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB

ALLOWED_EXT = {'txt', 'md', 'pdf', 'docx', 'doc', 'csv', 'json', 'log'}


# ============ Mock 兜底数据 ============
def mock_research(company):
    return json.dumps({
        'company_name': company or '示例公司',
        'basic_info': f'{company or "示例公司"}是一家专注于技术创新的企业，主营企业服务、云计算和 AI 解决方案。',
        'recent_news': ['完成 B 轮融资，估值 10 亿', '发布新一代 AI 产品线', '与多家龙头企业达成战略合作'],
        'key_contacts': [{'name': '张总', 'position': 'CEO'}, {'name': '李经理', 'position': '技术总监'}],
        'decision_chain': 'CEO ← 技术总监 ← 采购经理',
        'pain_points': ['技术团队扩张压力大', '系统集成要求高', '预算审批周期长'],
        'recommendation': '建议从技术痛点切入，强调集成便捷性和 ROI 测算，先约技术总监做 30 分钟深度沟通。',
    }, ensure_ascii=False, indent=2)


def mock_outreach(scenario, industry):
    templates = {
        'wechat': f'您好！我是北极星 AI 的销售顾问。了解到贵司在{industry or "所在领域"}的布局，我们最近帮 3 家类似企业提升了 30% 的效率。方便这周聊 15 分钟吗？',
        'email': f'主题：关于 AI 销售提效方案的交流\n\n您好：\n\n关注到贵司在{industry or "行业"}的动作，我们最近为多家客户交付了定制化 AI 销售方案，客户平均转化率提升 20%+。\n\n附上一份 2 页速览材料，若感兴趣可约 20 分钟视频会。\n\n祝好',
        'phone': '开场白（20 秒）：\n"您好，是 X 经理吗？我是北极星 AI 的顾问。看到贵司最近在拓展销售团队，我们有个能帮销售把线索转化提升 30% 的工具，方便占用您 3 分钟简单介绍一下吗？"',
    }
    return templates.get(scenario, templates['wechat'])


def mock_objection(objection):
    return json.dumps({
        'type': '价格异议',
        'strategy': '转移焦点到价值和 ROI',
        'response_framework': ['共情理解', '拆解成本', '提供 ROI', '对比隐性成本'],
        'suggested_script': f'针对"{objection}"：\n\n我完全理解您的顾虑。我们算笔账：假设这套方案帮您每年节省 20 万人力成本，年费 5 万，相当于用 5 万换 20 万。而且实施周期只需 2 周，您觉得这样的 ROI 可以接受吗？',
        'similar_cases': '某腰部 SaaS 客户最初也觉得贵，用了 6 个月收回成本，第二年主动续约并增购。',
    }, ensure_ascii=False, indent=2)


def mock_followup(status):
    plans = {
        '初次接触': {'action': '发价值资料 + 预约演示', 'timing': '2-3 天内', 'channel': '微信/邮件', 'goal': '建立专业形象'},
        '需求确认': {'action': '需求深度沟通', 'timing': '1 周内', 'channel': '电话/视频', 'goal': '明确需求，定制方案'},
        '方案报价': {'action': '提交正式方案 + ROI 测算', 'timing': '3-5 天', 'channel': '邮件 + 视频', 'goal': '展示匹配度'},
        '决策等待': {'action': '温和跟进 + 案例故事', 'timing': '5-7 天', 'channel': '微信/邮件', 'goal': '保持存在感'},
        '已成交': {'action': '实施跟进 + NPS 调研', 'timing': '实施后 1 周', 'channel': '电话', 'goal': '客户成功'},
    }
    return json.dumps({'stage': status, 'plan': plans.get(status, plans['初次接触']), 'journey': list(plans.keys())}, ensure_ascii=False, indent=2)


def mock_review():
    return json.dumps({
        'intent': '高',
        'pain_points': ['效率提升需求明确', '成本敏感'],
        'objections': ['价格偏高', '需内部审批'],
        'next_steps': ['发详细报价方案', '安排技术演示'],
        'win_prob': '65%',
        'missed': ['未了解预算范围', '未挖出决策链'],
        'improvements': ['先了解预算再报价', '准备 2-3 个同行业成功案例'],
    }, ensure_ascii=False, indent=2)


# ============ 页面路由 ============
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/customer-research')
def p_research():
    return render_template('customer_research.html')


@app.route('/outreach')
def p_outreach():
    return render_template('outreach.html')


@app.route('/objection')
def p_objection():
    return render_template('objection.html')


@app.route('/followup')
def p_followup():
    return render_template('followup.html')


@app.route('/review')
def p_review():
    return render_template('review.html')


@app.route('/library')
def p_library():
    return render_template('library.html')


@app.route('/customers')
def p_customers():
    return render_template('customers.html')


@app.route('/about')
def about():
    return render_template('about.html')


# ============ API：客户背景速查 ============
@app.route('/api/customer-research', methods=['POST'])
def api_research():
    data = request.json or {}
    company = data.get('company', '').strip()
    context = data.get('context', '').strip()

    # 检索素材库
    hits = kb.search(f'{company} {context}', top_k=3) if company else []
    kb_context = '\n'.join([f"- {h['filename']}: {h['snippet'][:200]}" for h in hits])

    system = '你是一位资深 B2B 销售顾问，擅长客户背景调研。请基于用户提供的信息与内部知识库片段，输出结构化 JSON。'
    user = f"""请调研以下客户，输出 JSON，字段类型要求严格如下：
{{
  "company_name": "字符串，公司名称",
  "basic_info": "字符串（不是对象/数组），一段连续文字描述公司基本情况",
  "recent_news": ["字符串数组，每个元素是一条动态的完整描述，不要嵌套对象"],
  "key_contacts": [{{"name": "字符串，姓名", "position": "字符串，职位"}}],
  "decision_chain": "字符串（不是数组），一段话描述决策链路",
  "pain_points": ["字符串数组，每个元素是一条痛点描述"],
  "recommendation": "字符串（不是数组/对象！），把 3 步切入策略写成一段连续文字，可用「第一步...第二步...第三步...」这种自然语言衔接，禁止返回数组或对象"
}}

公司名：{company}
补充信息：{context or '无'}

内部知识库相关片段：
{kb_context or '（无匹配素材）'}

要求：
1. 严格返回可解析 JSON，不要 markdown 代码块。
2. 每项内容具体、可执行，避免空话套话。
3. 再次强调：basic_info、decision_chain、recommendation 三个字段必须是字符串类型，不能是数组或对象。"""

    r = llm_client.chat(system, user, mock_fn=lambda: mock_research(company))
    parsed = try_parse_json(r['content'])
    return jsonify({'success': True, 'source': r['source'], 'data': parsed, 'raw': r['content'], 'kb_hits': hits})


# ============ API：触达内容生成 ============
@app.route('/api/outreach', methods=['POST'])
def api_outreach():
    data = request.json or {}
    scenario = data.get('scenario', 'wechat')
    industry = data.get('industry', '').strip()
    product = data.get('product', '').strip()
    tone = data.get('tone', '专业友好')
    custom = data.get('custom', '').strip()

    scenario_map = {'wechat': '微信消息', 'email': '邮件', 'phone': '电话开场白', 'linkedin': 'LinkedIn 私信'}
    system = '你是销售触达内容专家，善于写出让人愿意回复的开场白。'
    user = f"""生成一段{scenario_map.get(scenario, '微信消息')}触达内容：

- 目标行业：{industry or '通用'}
- 我方产品：{product or 'AI 销售助理'}
- 语气风格：{tone}
- 补充要求：{custom or '无'}

要求：
1. 不超过 150 字（电话开场白 30 秒可读完）。
2. 前 20 字必须包含价值钩子。
3. 结尾给出低门槛 CTA。
4. 输出正文即可，不要解释。"""

    r = llm_client.chat(system, user, mock_fn=lambda: mock_outreach(scenario, industry), temperature=0.8)
    return jsonify({'success': True, 'source': r['source'], 'content': r['content']})


# ============ API：异议处理 ============
@app.route('/api/objection', methods=['POST'])
def api_objection():
    data = request.json or {}
    objection = data.get('objection', '').strip()
    context = data.get('context', '').strip()

    system = '你是异议处理教练，善于把销售常见异议转化为成交机会。'
    user = f"""客户说："{objection}"

背景：{context or '无'}

请输出 JSON，字段类型要求：
{{
  "type": "字符串，异议类型",
  "strategy": "字符串（不是数组/对象），一句话核心应对策略",
  "response_framework": ["字符串数组，4 步框架的每一步用一个短语描述"],
  "suggested_script": "字符串（不是数组/对象），具体话术全文",
  "similar_cases": "字符串（不是数组/对象），一段同行业成功案例描述"
}}
要求：话术要口语化、有温度、可直接说出口。仅返回 JSON，上述字段不要出现嵌套对象或数组类型错误。"""

    r = llm_client.chat(system, user, mock_fn=lambda: mock_objection(objection))
    parsed = try_parse_json(r['content'])
    return jsonify({'success': True, 'source': r['source'], 'data': parsed, 'raw': r['content']})


# ============ API：跟进节奏 ============
@app.route('/api/followup', methods=['POST'])
def api_followup():
    data = request.json or {}
    status = data.get('status', '初次接触')
    customer = data.get('customer', '').strip()
    last_talk = data.get('last_talk', '').strip()

    system = '你是销售跟进节奏专家，帮助销售在正确时间做正确动作。'
    user = f"""客户当前处于阶段：{status}
客户信息：{customer or '未提供'}
上次沟通记录：{last_talk or '无'}

输出 JSON，字段类型要求：
{{
  "stage": "字符串，当前阶段名",
  "plan": {{"action": "字符串", "timing": "字符串", "channel": "字符串", "goal": "字符串", "script": "字符串（不是数组/对象），一段完整跟进话术"}},
  "journey": ["字符串数组，全部阶段名称，按顺序"],
  "risk": "字符串（不是数组/对象），一句话说明当前阶段最大风险"
}}
仅返回 JSON，plan 内部各字段与 risk 都必须是字符串，不能是数组或嵌套对象。"""

    r = llm_client.chat(system, user, mock_fn=lambda: mock_followup(status))
    parsed = try_parse_json(r['content'])
    return jsonify({'success': True, 'source': r['source'], 'data': parsed, 'raw': r['content']})


# ============ API：销售复盘 ============
@app.route('/api/review', methods=['POST'])
def api_review():
    data = request.json or {}
    transcript = data.get('transcript', '').strip()
    doc_id = data.get('doc_id')

    # 如果传了 doc_id，从素材库拿对话记录
    if doc_id and not transcript:
        doc = kb.get_document(int(doc_id))
        if doc:
            transcript = doc['content'][:8000]

    if not transcript:
        return jsonify({'success': False, 'error': '请提供对话记录或选择素材库文件'})

    system = '你是销售复盘专家，能从对话中挖出机会点与改进项。'
    user = f"""复盘以下销售对话记录，输出 JSON，字段类型要求：
{{
  "intent": "字符串，客户意向度：高/中/低",
  "pain_points": ["字符串数组，挖到的痛点"],
  "objections": ["字符串数组，客户异议"],
  "next_steps": ["字符串数组，后续动作"],
  "win_prob": "字符串，成交概率，如 65%",
  "missed": ["字符串数组，错失机会"],
  "improvements": ["字符串数组，改进建议"],
  "key_moments": ["字符串数组，每个元素是一段带引用原文的关键节点描述"]
}}

对话记录：
\"\"\"
{transcript[:6000]}
\"\"\"

仅返回 JSON，所有数组元素必须是字符串，不能是嵌套对象。"""

    r = llm_client.chat(system, user, mock_fn=mock_review, max_tokens=2000)
    parsed = try_parse_json(r['content'])
    return jsonify({'success': True, 'source': r['source'], 'data': parsed, 'raw': r['content']})


# ============ API：素材库 ============
@app.route('/api/library/upload', methods=['POST'])
def api_upload():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未收到文件'})
    f = request.files['file']
    if not f.filename:
        return jsonify({'success': False, 'error': '文件名为空'})
    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
    if ext not in ALLOWED_EXT:
        return jsonify({'success': False, 'error': f'不支持的类型 .{ext}，允许：{",".join(ALLOWED_EXT)}'})

    filename = secure_filename(f.filename) or f'upload_{int(time.time())}.{ext}'
    save_name = f'{int(time.time()*1000)}_{filename}'
    filepath = os.path.join(kb.UPLOAD_DIR, save_name)
    f.save(filepath)

    category = request.form.get('category', '通用')
    tags = request.form.get('tags', '')
    doc_id = kb.add_document(filename, filepath, ext, category=category, tags=tags)
    return jsonify({'success': True, 'id': doc_id, 'filename': filename})


@app.route('/api/library/list')
def api_list():
    category = request.args.get('category')
    docs = kb.list_documents(category=category)
    return jsonify({'success': True, 'docs': docs})


@app.route('/api/library/search')
def api_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'success': True, 'hits': []})
    hits = kb.search(q, top_k=10)
    return jsonify({'success': True, 'hits': hits})


@app.route('/api/library/delete/<int:doc_id>', methods=['DELETE'])
def api_delete(doc_id):
    ok = kb.delete_document(doc_id)
    return jsonify({'success': ok})


@app.route('/api/library/get/<int:doc_id>')
def api_get_doc(doc_id):
    d = kb.get_document(doc_id)
    if not d:
        return jsonify({'success': False, 'error': '未找到'})
    return jsonify({'success': True, 'doc': d})


# ============ API：客户库 ============
@app.route('/api/customers/list')
def api_c_list():
    return jsonify({'success': True, 'customers': kb.list_customers()})


@app.route('/api/customers/add', methods=['POST'])
def api_c_add():
    d = request.json or {}
    cid = kb.add_customer(
        name=d.get('name', '').strip() or '未命名',
        company=d.get('company', ''),
        industry=d.get('industry', ''),
        contact=d.get('contact', ''),
        notes=d.get('notes', ''),
        stage=d.get('stage', '初次接触'),
    )
    return jsonify({'success': True, 'id': cid})


@app.route('/api/customers/update/<int:cid>', methods=['POST'])
def api_c_update(cid):
    d = request.json or {}
    kb.update_customer_stage(cid, d.get('stage', '初次接触'))
    return jsonify({'success': True})


@app.route('/api/customers/delete/<int:cid>', methods=['DELETE'])
def api_c_delete(cid):
    kb.delete_customer(cid)
    return jsonify({'success': True})


# ============ 系统信息 ============
@app.route('/api/system/info')
def api_info():
    return jsonify({
        'llm_mode': 'real' if llm_client.is_real_llm() else 'mock',
        'model': llm_client.MODEL,
        'team': '北极星 · 炼术师',
    })


# ============ 工具 ============
def try_parse_json(text):
    """尝试从 LLM 返回中解析 JSON"""
    if not text:
        return None
    t = text.strip()
    # 剥 markdown 代码块
    if t.startswith('```'):
        t = t.split('```')[1] if '```' in t[3:] else t
        if t.startswith('json'):
            t = t[4:]
        t = t.strip()
    try:
        return json.loads(t)
    except Exception:
        # 尝试找第一个 { 和最后一个 }
        s, e = t.find('{'), t.rfind('}')
        if s >= 0 and e > s:
            try:
                return json.loads(t[s:e+1])
            except Exception:
                pass
    return None


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print('=' * 60)
    print('🚀 AI Sales Assistant | 北极星·炼术师')
    print(f'LLM Mode: {"real" if llm_client.is_real_llm() else "mock"} | Model: {llm_client.MODEL}')
    print(f'Port: {port}')
    print('=' * 60)
    app.run(host='0.0.0.0', port=port, debug=False)
