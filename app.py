from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)
app.secret_key = 'ai-sales-2024'

def mock_ai(module, data):
    if module == 'research':
        return {'success': True, 'data': {
            'company_name': data.get('company',''),
            'basic_info': '一家专注于技术创新的企业，主营业务包括企业服务、云计算和AI解决方案。',
            'recent_news': ['完成B轮融资，估值10亿', '发布新一代AI产品线', '与多家龙头企业达成战略合作'],
            'key_contacts': [{'name':'张总','position':'CEO'}, {'name':'李经理','position':'技术总监'}],
            'decision_chain': 'CEO <- 技术总监 <- 采购经理',
            'pain_points': ['技术团队扩张压力大', '系统集成要求高', '预算审批周期长'],
            'recommendation': '建议从技术痛点切入，强调集成便捷性和ROI测算。'
        }}
    if module == 'outreach':
        scenario = data.get('scenario','wechat')
        templates = {
            'wechat': {'content': '您好！我是[公司]的[姓名]。了解到贵公司在[领域]的需求，我们帮助多家类似企业提升30%效率。方便这周简单交流15分钟？', 'tips': '微信消息要简洁，最佳发送时间：工作日上午10-11点。'},
            'email': {'subject': '关于[产品]解决方案的交流', 'content': '尊敬的[客户]：我是[公司]的[姓名]。了解到贵公司的需求，我们最近为多家类似企业提供了定制化解决方案。不知近期是否方便安排交流？', 'tips': '邮件需正式但不过刻板，跟进间隔3-5天。'},
            'phone': {'content': '开场白："您好，我是[公司]的[姓名]，打扰了。关注到贵公司在[领域]的布局，想简单交流一下。"', 'tips': '电话开场要快、轻、有价值钩子。'}
        }
        return {'success': True, 'data': templates.get(scenario, templates['wechat'])}
    if module == 'objection':
        return {'success': True, 'data': {
            'type': '价格/拖延/竞争异议',
            'strategy': '转移焦点到价值和ROI',
            'response_framework': ['理解客户考虑', '拆解成本构成', '提供ROI测算', '对比隐形成本'],
            'suggested_script': '我理解您的考虑。我们可以算一笔账：如果这个解决方案能帮您每年节省20万，而年费是5万，相当于用5万换20万。您觉得这样的投入产出比可以接受吗？',
            'similar_cases': '某科技公司最初也觉得贵，但使用后6个月收回成本。'
        }}
    if module == 'followup':
        status = data.get('status','初识阶段')
        plans = {
            '初识阶段': {'next_action': '发送价值资料+预约演示', 'timing': '2-3天后', 'channel': '微信/邮件', 'goal': '建立专业形象'},
            '需求确认': {'next_action': '安排需求深度沟通', 'timing': '1周内', 'channel': '电话/视频', 'goal': '明确需求，定制方案'},
            '方案报价': {'next_action': '提交正式方案', 'timing': '3-5天后', 'channel': '邮件+视频', 'goal': '展示方案匹配度'},
            '决策等待': {'next_action': '温和跟进', 'timing': '5-7天后', 'channel': '微信/邮件', 'goal': '保持存在感'},
            '成交后': {'next_action': '实施跟进+满意度确认', 'timing': '实施后1周', 'channel': '电话+微信', 'goal': '确保客户成功'}
        }
        return {'success': True, 'data': {'current_status': status, 'plan': plans.get(status, plans['初识阶段']), 'full_journey': list(plans.keys())}}
    if module == 'review':
        return {'success': True, 'data': {
            'customer_intent': '高',
            'pain_points_identified': ['效率提升需求明确', '对成本敏感'],
            'objections_raised': ['价格偏高', '需要内部审批'],
            'next_steps': ['发送详细报价方案', '安排技术演示'],
            'win_probability': '65%',
            'missed_opportunities': ['未及时了解预算范围'],
            'improvement_suggestions': ['下次先了解预算再报价', '准备2-3个成功案例']
        }}
    return {'success': False}

@app.route('/')
def index(): return render_template('index.html')

@app.route('/customer-research')
def p1(): return render_template('customer_research.html')

@app.route('/api/customer-research', methods=['POST'])
def a1(): return jsonify(mock_ai('research', request.json))

@app.route('/outreach')
def p2(): return render_template('outreach.html')

@app.route('/api/outreach', methods=['POST'])
def a2(): return jsonify(mock_ai('outreach', request.json))

@app.route('/objection')
def p3(): return render_template('objection.html')

@app.route('/api/objection', methods=['POST'])
def a3(): return jsonify(mock_ai('objection', request.json))

@app.route('/followup')
def p4(): return render_template('followup.html')

@app.route('/api/followup', methods=['POST'])
def a4(): return jsonify(mock_ai('followup', request.json))

@app.route('/review')
def p5(): return render_template('review.html')

@app.route('/api/review', methods=['POST'])
def a5(): return jsonify(mock_ai('review', request.json))

@app.route('/about')
def about(): return render_template('about.html')

if __name__ == '__main__':
    port = 8080
    print('=' * 60)
    print('AI Sales Assistant starting...')
    print('Port:', port)
    print('=' * 60)
    app.run(host='0.0.0.0', port=port, debug=False)