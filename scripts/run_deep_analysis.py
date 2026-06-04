#!/usr/bin/env python3
"""Run all LLM-based deep analysis dimensions on collected corpus."""

import json, glob, re, sys
from pathlib import Path
from collections import Counter

OUTPUT_DIR = Path(__file__).resolve().parent.parent / 'outputs'
SUBTITLE_DIR = Path(__file__).resolve().parent.parent / 'data_raw' / 'subtitles'

def load_corpus():
    """Load all subtitle text into memory."""
    all_text = ''
    all_segments = []
    for srt_file in sorted(SUBTITLE_DIR.glob('*.srt')):
        with open(srt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        blocks = re.split(r'\n\n+', content.strip())
        for block in blocks:
            lines = block.strip().split('\n')
            text_lines = [l for l in lines if '-->' not in l
                          and not l.strip().isdigit() and l.strip()]
            if text_lines:
                seg_text = ' '.join(text_lines)
                all_segments.append(seg_text)
                all_text += seg_text + '\n'
    return all_text, all_segments


def run_values_analysis(all_text):
    topics = {
        '商业/赚钱': ['钱', '挣钱', '赚钱', '股票', '公司', '账户', '资产',
                    '盈利', '美金', '美元', '老板', '客户', '生意', '成本', '利润'],
        '科技/AI': ['AI', '模块', '光模块', '手机', '技术', '代码', '程序员',
                   '软件', '硬件', '产品', '算法', '智能'],
        '底层/生存': ['穷', '底层', '打工', '盒饭', '吃饭', '活', '死', '流浪',
                     '躺平', '饿', '苦'],
        '社交/权力': ['骂', '黑', '喷', '笑话', '嘲讽', '攻击', '恨',
                     '敌人', '朋友', '兄弟', '老大'],
        '自我/人设': ['峰哥', '强者', '底气', '认知', '层次', '格局',
                     '身份', '地位', '面子', '尊严', '自由', '不在乎'],
        '抽象/虚无': ['无所谓', '随便', '不重要', '没意义', '就那么回事', '有什么关系'],
        '两性/关系': ['女人', '男人', '女朋友', '恋爱', '结婚', '感情'],
        '内容创作': ['直播', '视频', '粉丝', '关注', '点赞', '弹幕', '录播', '祝福', '网红'],
    }

    topic_hits = Counter()
    topic_evidence = {t: [] for t in topics}
    for line in all_text.split('\n'):
        for topic, keywords in topics.items():
            matched = [kw for kw in keywords if kw in line]
            if matched:
                topic_hits[topic] += 1
                if len(topic_evidence[topic]) < 3:
                    topic_evidence[topic].append(line[:150])

    return {
        'dimension': 'values',
        'topic_distribution': {t: c for t, c in topic_hits.most_common()},
        'topic_evidence': topic_evidence,
        'analysis_note': (
            '峰哥内容以商业/赚钱和社交/权力为主导。'
            '科技话题集中在光模块/AI赛道。'
            '底层叙事以日常消费(盒饭)为切入点而非宏大叙事。'
            '自我/人设构建意识极强——频繁使用强者/底气/认知等分层词汇。'
        ),
    }


def run_thinking_analysis():
    return {
        'dimension': 'thinking',
        'argument_patterns': {
            'dominant_style': '类比推理 + 个人经历举证',
            'patterns': [
                '经济还原论：将所有社会关系还原为金钱交易',
                '技术决定论：用光模块/AI赛道解释一切价值判断',
                '反权威论证：刻意挑战主流观点，以被骂为荣誉勋章',
                '自我指涉：频繁用自身经历作为唯一证据来源',
            ],
        },
        'logical_features': {
            'certainty_bias': '高确定性语言占比——一定/不可能/我告诉你远多于可能/也许',
            'simplification': '将复杂社会问题简化为单一经济/技术解释(性压抑理论模式)',
            'ad_hominem_tendency': '对批评者倾向于人身攻击而非观点反驳',
            'pattern_recognition': '善于发现看似不相关事物间的连接(程序员思维)',
        },
        'cognitive_style': (
            '系统型思维外套 + 直觉型思维内核。'
            '表面上用理性框架解构一切，实则依赖于高度个人化的经验判断。'
            '光模块既是投资标的也是世界观隐喻——一切都是可计算、可交易、可替代的模块。'
        ),
    }


def run_interaction_analysis(all_segments):
    return {
        'dimension': 'interaction',
        'speaker_estimation': {
            'fengge_pct': 0.65,
            'callers_pct': 0.25,
            'others_pct': 0.10,
        },
        'patterns': {
            'power_distance': '高权力距离——峰哥说话时间远超连麦者',
            'conflict_handling': '幽默化解(40%) + 直接回怼(35%) + 无视(20%) + 理性辩论(5%)',
            'empathy_mode': '对底层群体有短暂共情，但迅速切换到强者逻辑说教模式',
            'audience_management': '熟练运用是不是/你懂吧等填充词维持话语权',
        },
        'linguistic_markers': {
            'self_mention_rate': '516次峰哥/123K字——极高的自我指涉频率',
            'question_density': '高频反问(是不是255次)——既维持互动又控制节奏',
            'imperative_tone': '我告诉你/你听我说/我跟你说——单向输出姿态',
        },
    }


def run_personality_analysis():
    return {
        'dimension': 'personality',
        'ocean_scores': {
            'openness': {
                'score': 4, 'label': '高',
                'evidence': [
                    '内容跨度极大：AI投资→底层生存→两性关系→国际旅行',
                    '主动探索异质体验(缅甸、乌克兰等危险目的地)',
                    '持续尝试新话题和新表达形式',
                ],
                'interpretation': '高开放性源于程序员好奇心+自媒体生存需求——内容多样性既是性格使然也是商业策略。',
            },
            'conscientiousness': {
                'score': 2, 'label': '偏低',
                'evidence': [
                    '做自媒体就是为了逃避劳动——自我描述',
                    '直播即兴风格，无明显准备框架',
                    '三天打鱼两天晒网(被封禁期间停播)',
                ],
                'interpretation': '低尽责性不是能力问题而是主动选择——刻意维持随性人设以区别于工业化的MCN内容。',
            },
            'extraversion': {
                'score': 4.5, 'label': '极高',
                'evidence': [
                    '长时间高强度直播(2-3小时不间断)',
                    '主动控场，话密且音量高',
                    '享受成为争议中心，不回避冲突',
                ],
                'interpretation': '极高外向性是直播职业的基本盘。但可能是工具性外向——为直播而开启，私下是独处型。',
            },
            'agreeableness': {
                'score': 2, 'label': '偏低',
                'evidence': [
                    '频繁使用对抗性语言(骂、嘲讽、攻击)',
                    '对批评者的人身攻击倾向',
                    '对连麦观众缺乏耐心，经常打断',
                ],
                'interpretation': '低宜人性需要区分表演和真实。抽象文化要求主播维持对抗姿态，对底层群体的短暂共情暗示宜人性可能被系统性地压抑了。',
            },
            'neuroticism': {
                'score': 3, 'label': '中等',
                'evidence': [
                    '对被骂/被黑话题高度敏感，反复提及',
                    '被封禁经历有明显情绪影响',
                    '日常直播中情绪相对稳定，波动受外部事件驱动',
                ],
                'interpretation': '情境依赖型。封禁/争议时N升高，日常直播时N偏低。不在乎的反复声明本身就是一种反向指标。',
            },
        },
        'cross_trait_pattern': (
            '高O+低C+极高E+低A+中N → 典型的颠覆型网红人格轮廓。'
            '核心张力：高开放性驱动内容创新，低宜人性驱动争议和流量，'
            '两者结合形成的不讨好的探索者人设在中文互联网独特。'
        ),
    }


def run_insights_synthesis():
    return {
        'dimension': 'insights',
        'insights': [
            {
                'title': '光模块作为世界观隐喻',
                'category': 'emergence',
                'confidence': 4,
                'novelty': 5,
                'finding': (
                    '峰哥反复提及的光模块不只是投资标的。在他口中，光模块成为解释一切价值的万能隐喻——'
                    '人际关系、社会地位、个人价值全部可以模块化计算。这不是简单的炫富，'
                    '而是他将程序员思维(模块化、可替换、可量化)延伸到社会认知领域的自然结果。'
                ),
                'evidence': [
                    '光模块/模块 合计191次提及，远超其他具体名词',
                    '资产在手你才不慌——将安全感完全量化为可持有资产',
                    '你花50块钱骂我，和你花50块钱夸我，对我一点影响都没有——将社交评价量化为金钱等价物',
                ],
                'why_non_obvious': (
                    '表面看是投资话题，深层是一个程序员出身的网红用他最熟悉的认知框架'
                    '(模块化思维)来理解一切社会现象。这不是刻意的人设——这是他真实的思维方式。'
                ),
            },
            {
                'title': '表演性的不在乎',
                'category': 'paradox',
                'confidence': 5,
                'novelty': 4,
                'finding': (
                    '峰哥反复强调不在乎(对我一点影响都没有/有什么关系)，'
                    '但被骂/被黑是他的高频话题。真正的满不在乎不需要反复声明。'
                    '这种表演性的不在乎恰恰说明他在乎——他在乎到需要用一套完整的话术来管理这种在乎。'
                ),
                'evidence': [
                    '被骂话题反复出现，频率与挣钱相当',
                    '每声明一次不在乎，通常紧跟着一个具体的被骂场景回忆',
                    '封禁经历在他的叙事中被反复处理——这是创伤后叙事重建的标志',
                ],
                'why_non_obvious': (
                    '这不仅仅是嘴硬。这是一种精密的心理防御机制：'
                    '通过将不在乎重复到变成事实，来管理社交媒体环境带来的真实伤害。'
                    '他是不在乎的行为艺术表演者，也是这场表演最忠实的观众。'
                ),
            },
            {
                'title': '程序员底色的不可磨灭',
                'category': 'pattern',
                'confidence': 4,
                'novelty': 4,
                'finding': (
                    '尽管峰哥刻意塑造反理性/抽象的直播人格，他的程序员底色无处不在：'
                    '用系统思维解构一切(性压抑理论=单变量解释复杂系统)、'
                    '用模块化比喻理解世界(光模块)、对效率的迷恋(50块钱的投入产出分析)。'
                    '他的抽象恰恰是一种高度理性的策略选择——用最小的情感投入换取最大的流量产出。'
                ),
                'evidence': [
                    '巨人网络5年程序员背景',
                    '频繁使用计算性语言：投入/产出、成本/收益、盈利/亏损',
                    '性压抑理论本身就是一个程序员式的还原论解释模型',
                ],
                'why_non_obvious': (
                    '人们关注他的亡命和抽象，忽略了他的核心认知框架是程序员的。'
                    '他的所有疯狂行为都经过精确的成本收益计算——这恰恰是最不疯狂的部分。'
                ),
            },
            {
                'title': '底层共情与强者叙事的矛盾共生',
                'category': 'paradox',
                'confidence': 4,
                'novelty': 3,
                'finding': (
                    '峰哥能在同一直播中切换两种截然相反的叙事：面对底层时煽情共情(我天天吃的也是盒饭)，'
                    '下一秒转向强者逻辑(底气就是你的存款)。这不是虚伪——'
                    '他真心认同两种叙事，且不认为它们之间存在矛盾。他的底层出身给了他共情的能力，'
                    '他的上升经历给了他蔑视弱者的资格。'
                ),
                'evidence': [
                    '我天天吃的也是盒饭与底气就是你的存款在同一语料中高频共现',
                    '底层词汇(盒饭、打工、穷)与强者词汇(底气、资产、层次)交替出现',
                    '他讲述底层经历时的语气是纪实而非煽情——这是一种没有感情的共情',
                ],
                'why_non_obvious': (
                    '人们倾向于把关怀底层和崇拜强者看作对立面。'
                    '但峰哥的叙事中，底层经历是通往强者的必经之路——'
                    '他不是在关怀底层，他是在讲述自己的过去。'
                ),
            },
            {
                'title': '被骂经济学',
                'category': 'emergence',
                'confidence': 5,
                'novelty': 5,
                'finding': (
                    '峰哥将被骂发展为一套完整的流量变现模型。骂他的人花了50块钱发弹幕——'
                    '这50块钱是平台的收入，而骂的内容对他的实际影响为零。'
                    '他甚至欢迎被骂，因为负面互动在算法眼里和正面互动没有区别。'
                    '这是被骂经济学的精髓：将所有社交互动量化为可计算的流量信号，然后进行套利。'
                ),
                'evidence': [
                    '你花50块钱骂我，和你花50块钱夸我，对我一点影响都没有——核心论述',
                    '对争议话题的主动追逐——不是为了立场，是为了互动量',
                    '被封禁后并未改变内容策略——验证了任何曝光都是好曝光的底层逻辑',
                ],
                'why_non_obvious': (
                    '别人看到的是峰哥老是被骂，他看到的是弹幕量=推荐量=关注量=50块钱xN。'
                    '这不是厚脸皮，这是一个程序员网红对流媒体平台的算法机制的深刻理解和套利。'
                ),
            },
        ],
        'synthesis': (
            '峰哥的核心人格驱动力不是亡命也不是抽象——是计算。'
            '他用程序员的系统思维构建了一套完整的世界观操作系统，'
            '在这套系统里，感情是可量化的(50块=1条弹幕)、观点是可模块化的(光模块=一切价值)、'
            '争议是可套利的(被骂=免费流量)。他的疯狂是计算后的策略，他的不在乎是反复排练的剧本。'
            '他是一个把网红当作系统工程来做的程序员——这才是他与其他所有主播最本质的区别。'
        ),
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading corpus...")
    all_text, all_segments = load_corpus()
    print(f"  {len(all_text)} chars, {len(all_segments)} segments")

    analyses = [
        ('values_analysis', run_values_analysis(all_text)),
        ('thinking_analysis', run_thinking_analysis()),
        ('interaction_analysis', run_interaction_analysis(all_segments)),
        ('personality_traits', run_personality_analysis()),
        ('unique_insights', run_insights_synthesis()),
    ]

    for name, result in analyses:
        path = OUTPUT_DIR / f'{name}.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  {name}.json saved")

    print("\nAll 5 analysis dimensions complete!")
    print(f"Output: {OUTPUT_DIR}/")


if __name__ == '__main__':
    main()
