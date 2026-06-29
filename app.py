#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI销售获客系统 - 主应用
基于WorkBuddy能力构建的营销获客辅助工具
"""

from flask import Flask, render_template, request, jsonify, session
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'ai-sales-assistant-2024'

# 模拟AI响应函数（实际应调用WorkBuddy API）
def mock_ai_response(module, input_data):
    """模拟AI响应，用于Demo演示"""
    
    if module == 'customer_research':
        company = input_data.get('company', '')
        return {
            'success': True,
            'data': {
                'company_name': company,
                'basic_info': f'{company}是一家专注于技术创新的企业，主营业务包括企业服务、云计算和人工智能解决方案。',
                'recent_news': [
                    '最近完成了B轮融资，估值达到10亿人民币',
                    '发布了新一代AI产品线',
                    '与多家行业龙头企业达成战略合作'
                ],
                'key_contacts': [
                    {'name': '张总', 'position': 'CEO', 'background': '连续创业者，技术背景深厚'},
                    {'name': '李经理', 'position': '技术总监', 'background': '负责技术决策，关注产品稳定性'}
                ],
                'decision_chain': 'CEO(最终决策) ← 技术总监(技术评估) ← 采购经理(预算控制)',
                'pain_points': [
                    '技术团队扩张压力大，需要高效的招聘工具',
                    '现有系统集成度高，对新工具的兼容性要求严格',
                    '预算审批流程较长，需要提前3个月规划'
                ],
                'recommendation': '建议从技术痛点切入，强调产品的集成便捷性和ROI测算。'
            }
        }
    
    elif module == 'outreach_generator':
        customer_info = input_data.get('customer_info', '')
        product = input_data.get('product', '')
        scenario = input_data.get('scenario', 'wechat')
        
        templates = {
            'wechat': {
                'subject': '',
                'content': f'''{customer_info}您好！

我是[你的名字]，来自[公司名称]。

了解到贵公司在{product}方面有较大需求，我们最近帮助多家类似企业：
✅ 提升了30%的工作效率
✅ 节省了20%的运营成本
✅ 实现了系统无缝集成

方便的话，这周或下周我们可以简单交流15分钟，我给您分享一些同行的实践案例。

期待您的回复！
[你的名字]''',
                'tips': '微信消息要简洁，重点突出价值，避免过于销售化的语言。最佳发送时间：工作日上午10-11点。'
            },
            'email': {
                'subject': f'关于{product}解决方案的交流',
                'content': f'''尊敬的{customer_info}：

您好！

我是[公司名称]的[你的名字]。通过调研了解到贵公司在{product}领域有着卓越的表现，同时也关注到这个领域面临的共同挑战。

我们最近为多家类似企业提供了定制化解决方案，帮助他们：
• 提升运营效率30%以上
• 降低系统维护成本20%
• 实现与现有系统的无缝集成

附件是我们为同行业企业提供的解决方案概述，包含具体实施案例和ROI分析。

不知您近期是否方便，我们可以安排一次20-30分钟的线上交流，为您详细介绍这些实践案例。

此致
敬礼！

[你的名字]
[职位]
[公司名称]
[联系方式]''',
                'tips': '邮件需要正式但不过于刻板，附件要有价值，跟进间隔建议3-5天。'
            },
            'phone': {
                'subject': '',
                'content': f'''开场白：
"您好，我是[公司名称]的[你的名字]，打扰您了。我这边关注到贵公司在{product}方面有一些布局，想和您简单交流一下。"

如果对方有兴趣：
"太好了，我们最近帮助多家类似企业解决了[具体痛点]的问题，想和您分享一下我们的实践经验，不知道您这周哪天比较方便，我们可以详细聊聊？"

如果对方说没时间：
"理解您比较忙，那我加您微信/发您邮件，您有空的时候可以看看，到时候再约您时间？"''',
                'tips': '电话开场要快、要轻、要有价值钩子。准备好应对"没兴趣"的话术。'
            }
        }
        
        return {
            'success': True,
            'data': templates.get(scenario, templates['wechat'])
        }
    
    elif module == 'objection_handler':
        objection = input_data.get('objection', '')
        context = input_data.get('context', '')
        
        objection_db = {
            '太贵了': {
                'type': '价格异议',
                'strategy': '转移焦点到价值和ROI',
                'response_framework': [
                    '理解客户的预算考虑',
                    '拆解成本构成，强调长期价值',
                    '提供ROI测算或分期方案',
                    '对比"不行动的隐形成本"'
                ],
                'suggested_script': '我理解您的考虑。其实很多客户一开始也有同样的顾虑。我们可以算一笔账：如果这个解决方案能帮您每年节省20万的人力成本，而我们的产品年费是5万，相当于用5万换20万，而且效果是持续的。您觉得这样的投入产出比可以接受吗？',
                'similar_cases': '某科技公司最初也觉得贵，但使用后6个月就收回成本，现在已续约3年。'
            },
            '我们需要考虑考虑': {
                'type': '拖延异议',
                'strategy': '挖掘真实顾虑，创造紧迫感',
                'response_framework': [
                    '理解客户的谨慎态度',
                    '询问具体需要考虑的方面',
                    '提供补充材料或案例',
                    '设定合理的跟进时间点'
                ],
                'suggested_script': '完全理解，这么重要的决策确实需要慎重考虑。不知道您主要需要考虑哪些方面呢？是功能、价格、还是实施周期？如果有任何疑问，我可以帮您进一步解答，也可以安排技术团队给您做更详细的演示。',
                'similar_cases': '很多客户说需要考虑，其实是还有隐藏顾虑没说出来，需要耐心挖掘。'
            },
            '已经有供应商了': {
                'type': '竞争异议',
                'strategy': '了解现有方案，找到差异化价值',
                'response_framework': [
                    '祝贺客户已有合作方案',
                    '了解现有方案的优缺点',
                    '找到我们的差异化价值点',
                    '建议做对比评估或试点'
                ],
                'suggested_script': '那太好了，说明您已经意识到这个领域的价值。不知道您现在的供应商合作体验如何呢？有没有哪些方面是您希望改进的？我们很多客户都是在原有方案基础上，引入我们的产品作为补充或升级，效果非常不错。要不我给您发一份对比分析，您可以看看？',
                'similar_cases': '某客户已有供应商，但我们在某个细分功能上更优，最终达成合作。'
            }
        }
        
        result = objection_db.get(objection, {
            'type': '其他异议',
            'strategy': '先倾听，理解客户真实意图',
            'response_framework': [
                '感谢客户的反馈',
                '深入询问具体原因',
                '针对性地提供信息或方案',
                '保持友好，为未来留机会'
            ],
            'suggested_script': '我理解您的考虑。能否请教一下，主要是什么方面的原因呢？您的反馈对我们非常重要，可以帮助我们改进产品和服务。',
            'similar_cases': '每个异议背后都有原因，耐心倾听比急于反驳更重要。'
        })
        
        return {
            'success': True,
            'data': result
        }
    
    elif module == 'followup_planner':
        customer_status = input_data.get('status', '')
        last_contact = input_data.get('last_contact', '')
        
        status_plans = {
            '初识阶段': {
                'next_action': '发送价值资料 + 预约演示',
                'timing': '2-3天后',
                'channel': '微信/邮件',
                'script_hint': '发送行业报告或案例，附上简短解读',
                'goal': '建立专业形象，展示价值'
            },
            '需求确认': {
                'next_action': '安排需求深度沟通',
                'timing': '1周内',
                'channel': '电话/视频会议',
                'script_hint': '准备需求调研问卷，引导客户表达痛点',
                'goal': '明确需求，定制方案'
            },
            '方案报价': {
                'next_action': '提交正式方案 + 解读会议',
                'timing': '3-5天后',
                'channel': '邮件 + 视频会议',
                'script_hint': '方案要突出ROI和定制化，报价要透明',
                'goal': '让客户看到方案与需求的匹配度'
            },
            '决策等待': {
                'next_action': '温和跟进 + 提供补充信息',
                'timing': '5-7天后',
                'channel': '微信/邮件',
                'script_hint': '不要催得太紧，提供有价值的信息作为跟进理由',
                'goal': '保持存在感，推动决策'
            },
            '成交后': {
                'next_action': '实施跟进 + 满意度确认',
                'timing': '实施完成后1周',
                'channel': '电话 + 微信',
                'script_hint': '关注实施效果，收集成功案例',
                'goal': '确保客户成功，为复购和转介绍打基础'
            }
        }
        
        plan = status_plans.get(customer_status, status_plans['初识阶段'])
        
        return {
            'success': True,
            'data': {
                'current_status': customer_status,
                'last_contact': last_contact,
                'plan': plan,
                'full_journey': list(status_plans.keys())
            }
        }
    
    elif module == 'sales_review':
        conversation = input_data.get('conversation', '')
        
        # 模拟对话分析
        analysis = {
            'customer_intent': '高',
            'pain_points_identified': [
                '效率提升需求明确',
                '对成本敏感',
                '担心实施周期'
            ],
            'objections_raised': [
                '价格偏高',
                '需要内部审批'
            ],
            'next_steps': [
                '发送详细报价方案',
                '安排技术团队演示',
                '跟进审批进度'
            ],
            'win_probability': '65%',
            'missed_opportunities': [
                '没有及时挖掘预算范围',
                '没有展示同行案例',
                ' closure尝试过早'
            ],
            'improvement_suggestions': [
                '下次先了解客户预算范围再报价',
                '准备2-3个同行业成功案例',
                '多问开放性问题，少急于介绍产品'
            ]
        }
        
        return {
            'success': True,
            'data': analysis
        }
    
    return {'success': False, 'error': '未知模块'}


# 路由定义
@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/customer-research')
def customer_research():
    """客户背景速查页面"""
    return render_template('customer_research.html')


@app.route('/api/customer-research', methods=['POST'])
def api_customer_research():
    """客户背景速查API"""
    data = request.json
    result = mock_ai_response('customer_research', data)
    return jsonify(result)


@app.route('/outreach')
def outreach():
    """触达内容生成页面"""
    return render_template('outreach.html')


@app.route('/api/outreach', methods=['POST'])
def api_outreach():
    """触达内容生成API"""
    data = request.json
    result = mock_ai_response('outreach_generator', data)
    return jsonify(result)


@app.route('/objection')
def objection():
    """异议处理教练页面"""
    return render_template('objection.html')


@app.route('/api/objection', methods=['POST'])
def api_objection():
    """异议处理API"""
    data = request.json
    result = mock_ai_response('objection_handler', data)
    return jsonify(result)


@app.route('/followup')
def followup():
    """跟进节奏管理页面"""
    return render_template('followup.html')


@app.route('/api/followup', methods=['POST'])
def api_followup():
    """跟进计划API"""
    data = request.json
    result = mock_ai_response('followup_planner', data)
    return jsonify(result)


@app.route('/review')
def review():
    """销售过程复盘页面"""
    return render_template('review.html')


@app.route('/api/review', methods=['POST'])
def api_review():
    """销售复盘API"""
    data = request.json
    result = mock_ai_response('sales_review', data)
    return jsonify(result)


@app.route('/about')
def about():
    """关于页面"""
    return render_template('about.html')


if __name__ == '__main__':
    # 创建templates目录
    if not os.path.exists('templates'):
        os.makedirs('templates')
    if not os.path.exists('static'):
        os.makedirs('static')
    
    print("="*60)
    print("AI销售获客系统 启动中...")
    print("访问地址: http://0.0.0.0:8080")
    print("="*60")
    
    app.run(host='0.0.0.0', port=8080, debug=True)
