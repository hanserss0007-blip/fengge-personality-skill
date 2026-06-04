#!/usr/bin/env python3
"""
08_run_analysis.py — 编排五维度人格分析。

从 corpus.db 加载语料，依次运行各分析维度，输出中间 JSON。
可以指定维度跳过已完成的分析。
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.utils.db_manager import DatabaseManager
from scripts.utils.text_processor import TextProcessor
from scripts.utils.progress_tracker import ProgressTracker

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

PROCESSED_DIR = Path(__file__).resolve().parent.parent / 'data_processed'
OUTPUT_DIR = Path(__file__).resolve().parent.parent / 'outputs'
DB_PATH = PROCESSED_DIR / 'corpus.db'
PROGRESS_PATH = Path(__file__).resolve().parent.parent / 'data_raw' / 'progress.json'

DIMENSIONS = [
    'language',
    'thinking',
    'values',
    'interaction',
    'personality',
    'insights',
]


def run_language_analysis(db, processor, args) -> dict:
    """语言风格分析。"""
    logger.info("=" * 50)
    logger.info("维度 1/6: 语言风格分析")

    texts = db.get_fengge_texts()
    if not texts:
        logger.warning("无峰哥发言数据")
        return {'error': 'no_data', 'word_frequency': [], 'catchphrases': []}

    # 分词+词频
    word_freq = processor.get_word_frequency(texts, top_n=100)

    # 口头禅
    catchphrases = processor.find_catchphrases(texts, n_range=(2, 5), top_n=20)

    # 句子统计
    sentences = []
    for text in texts:
        # 按中文标点分句
        import re
        parts = re.split(r'[。！？\n]', text)
        sentences.extend([p.strip() for p in parts if p.strip()])

    sentence_stats = processor.sentence_stats(sentences)

    result = {
        'dimension': 'language',
        'word_frequency_top100': word_freq,
        'catchphrases_top20': catchphrases,
        'sentence_stats': sentence_stats,
        'corpus_size': {
            'total_utterances': len(texts),
            'total_chars': sum(len(t) for t in texts),
            'unique_words': len(set(processor.tokenize('\n'.join(texts)))),
        },
        'generated_at': datetime.now().isoformat(),
    }

    output_path = OUTPUT_DIR / 'language_analysis.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"语言分析完成 → {output_path}")
    return result


def run_thinking_analysis(db, args) -> dict:
    """思维模式分析（LLM标注需要外部调用）。"""
    logger.info("=" * 50)
    logger.info("维度 2/6: 思维模式分析")

    # 获取较长的峰哥发言（>100 字，更有可能是完整论证）
    rows = db.conn.execute(
        """SELECT text, start_ts, video_id FROM utterances
           WHERE speaker='fengge' AND LENGTH(text) > 100
           ORDER BY video_id, utterance_index"""
    ).fetchall()

    if not rows:
        logger.warning("无符合长度的发言（>100字），尝试降低阈值")
        rows = db.conn.execute(
            """SELECT text, start_ts, video_id FROM utterances
               WHERE speaker='fengge' AND LENGTH(text) > 50
               ORDER BY video_id, utterance_index"""
        ).fetchall()

    # 抽样 50 段
    sample_size = min(50, len(rows))
    if sample_size == 0:
        return {'error': 'no_data', 'argument_samples': []}

    import random
    random.seed(42)
    samples = random.sample(rows, sample_size)

    result = {
        'dimension': 'thinking',
        'total_arguments_found': len(rows),
        'sample_size': sample_size,
        'argument_samples': [
            {
                'video_id': row['video_id'],
                'timestamp': row['start_ts'],
                'text': row['text'][:500],  # 截断长文本
            }
            for row in samples
        ],
        'note': 'LLM标注待完成。需要调用 LLM 对以上 argument_samples 进行论证结构、逻辑谬误、认知偏差标注。',
        'generated_at': datetime.now().isoformat(),
    }

    output_path = OUTPUT_DIR / 'thinking_analysis.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"思维分析框架已准备 → {output_path}")
    return result


def run_values_analysis(db, args) -> dict:
    """价值体系分析框架。"""
    logger.info("=" * 50)
    logger.info("维度 3/6: 价值体系分析")

    texts = db.get_fengge_texts()
    if not texts:
        return {'error': 'no_data'}

    # 简单主题关键词统计（作为 BERTopic 的轻量替代）
    topic_keywords = {
        '底层关怀': ['底层', '打工', '日结', '穷人', '流浪', '三和', '农民工', '活不下去'],
        '商业/赚钱': ['赚钱', '钱', '变现', '流量', '带货', '广告', '商业'],
        '社会批判': ['社会', '国家', '政府', '制度', '不公平', '阶层', '体制'],
        '个人成长': ['改变', '努力', '奋斗', '成功', '失败', '人生', '命运'],
        '两性关系': ['女人', '男人', '恋爱', '结婚', '性', '感情', '男女'],
        '抽象/虚无': ['无所谓', '随便', '反正', '没意义', '不重要', '就那么回事'],
        '自由/旅行': ['自由', '旅行', '世界', '走走', '看看', '体验', '活法'],
        '技术/互联网': ['代码', '程序员', '互联网', '技术', '产品', '算法'],
    }

    from collections import Counter
    topic_counts = Counter()
    for text in texts:
        matched = set()
        for topic, keywords in topic_keywords.items():
            for kw in keywords:
                if kw in text:
                    matched.add(topic)
        for t in matched:
            topic_counts[t] += 1

    result = {
        'dimension': 'values',
        'topic_keyword_hits': dict(topic_counts.most_common()),
        'topic_definitions': topic_keywords,
        'corpus_size': len(texts),
        'note': '这是基于关键词的初步统计，完整主题建模需要 BERTopic + LLM 标注。建议在 LLM agent 中完成价值维度评分。',
        'generated_at': datetime.now().isoformat(),
    }

    output_path = OUTPUT_DIR / 'values_analysis.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"价值分析框架已准备 → {output_path}")
    return result


def run_interaction_analysis(db, args) -> dict:
    """人际互动分析框架。"""
    logger.info("=" * 50)
    logger.info("维度 4/6: 人际互动分析")

    # 各说话人的统计数据
    fengge_count = db.get_utterance_count('fengge')
    caller_count = db.get_utterance_count('caller')
    guest_count = db.get_utterance_count('guest')
    unknown_count = db.get_utterance_count('unknown')

    # 弹幕统计
    danmaku_count = db.conn.execute("SELECT COUNT(*) FROM danmaku").fetchone()[0]

    # 说话人占比
    total_labeled = fengge_count + caller_count + guest_count

    # 峰哥的均段长度 vs 其他人的均段长度
    fengge_avg_len = db.conn.execute(
        "SELECT AVG(LENGTH(text)) FROM utterances WHERE speaker='fengge'"
    ).fetchone()[0] or 0
    caller_avg_len = db.conn.execute(
        "SELECT AVG(LENGTH(text)) FROM utterances WHERE speaker='caller'"
    ).fetchone()[0] or 0

    result = {
        'dimension': 'interaction',
        'speaker_distribution': {
            'fengge': {'count': fengge_count, 'avg_chars': round(fengge_avg_len, 1)},
            'caller': {'count': caller_count, 'avg_chars': round(caller_avg_len, 1)},
            'guest': {'count': guest_count, 'avg_chars': 0},
            'unknown': {'count': unknown_count, 'avg_chars': 0},
        },
        'fengge_talk_ratio': round(fengge_count / max(total_labeled, 1), 3),
        'fengge_avg_length_vs_caller': round(fengge_avg_len / max(caller_avg_len, 1), 1),
        'danmaku_count': danmaku_count,
        'note': '框架数据已准备。详细互动模式（冲突处理、共情分析、弹幕对齐）需 LLM agent 完成。',
        'generated_at': datetime.now().isoformat(),
    }

    output_path = OUTPUT_DIR / 'interaction_analysis.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"互动分析框架已准备 → {output_path}")
    return result


def run_personality_analysis(db, args) -> dict:
    """OCEAN 人格分析框架。"""
    logger.info("=" * 50)
    logger.info("维度 5/6: OCEAN 人格分析")

    texts = db.get_fengge_texts()
    if not texts:
        return {'error': 'no_data'}

    full_corpus = '\n'.join(texts)

    # 基础量化指标（辅助 OCEAN 评分）
    import re

    # 确定性语言 vs 模糊语
    certainty_words = ['一定', '绝对', '肯定', '必须', '毫无疑问', '显然', '毋庸置疑', '当然']
    hedging_words = ['可能', '也许', '大概', '或许', '好像', '似乎', '不太确定', '说不好', '不知道']

    certainty_count = sum(full_corpus.count(w) for w in certainty_words)
    hedging_count = sum(full_corpus.count(w) for w in hedging_words)

    # 自指语言（自我意识程度）
    self_ref_count = sum(full_corpus.count(w) for w in ['我', '我觉得', '我认为', '我的'])

    # 情绪词（神经质指标）
    anger_words = ['操', '妈的', '烦', '气死', '怒', '傻逼', '恶心']
    anxiety_words = ['担心', '害怕', '焦虑', '紧张', '不安']

    anger_count = sum(full_corpus.count(w) for w in anger_words)
    anxiety_count = sum(full_corpus.count(w) for w in anxiety_words)

    result = {
        'dimension': 'personality',
        'corpus_statistics': {
            'total_chars': len(full_corpus),
            'total_texts': len(texts),
        },
        'quantitative_indicators': {
            'certainty_vs_hedging_ratio': round(certainty_count / max(hedging_count, 1), 2),
            'certainty_words_count': certainty_count,
            'hedging_words_count': hedging_count,
            'self_reference_count': self_ref_count,
            'anger_markers_count': anger_count,
            'anxiety_markers_count': anxiety_count,
        },
        'note': '量化指标已统计。OCEAN 评分和证据链需要 LLM agent 基于 oceane_framework.md 完成。',
        'generated_at': datetime.now().isoformat(),
    }

    output_path = OUTPUT_DIR / 'personality_traits.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"人格分析框架已准备 → {output_path}")
    return result


def run_insights_synthesis(all_results: dict, args) -> dict:
    """独到见解合成框架。"""
    logger.info("=" * 50)
    logger.info("维度 6/6: 独到见解合成")

    # 收集各维度的关键发现作为输入
    key_findings = {}

    for dim_name, result in all_results.items():
        if result and 'error' not in result:
            if dim_name == 'language':
                key_findings['language'] = {
                    'catchphrases': result.get('catchphrases_top20', [])[:5],
                    'sentence_stats': result.get('sentence_stats', {}),
                }
            elif dim_name == 'values':
                key_findings['values'] = {
                    'top_topics': result.get('topic_keyword_hits', {}),
                }
            elif dim_name == 'interaction':
                key_findings['interaction'] = {
                    'fengge_talk_ratio': result.get('fengge_talk_ratio', 0),
                }
            elif dim_name == 'personality':
                key_findings['personality'] = result.get('quantitative_indicators', {})

    result = {
        'dimension': 'insights',
        'input_findings': key_findings,
        'known_contradictions': [
            '程序员技术理性 vs 直播荒诞抽象',
            '底层关怀 vs 消费底层',
            'MCN合伙人身份 vs 反劳动人设',
            '极度社交能量 vs 极端个人主义',
            '深度思考能力 vs 刻意回避深度',
        ],
        'comparison_targets': ['童锦程', '辛巴', '李佳琦', '疯狂小杨哥'],
        'note': '框架已准备。独到见解的完整生成需要 insight_synthesizer_agent (LLM) 基于所有维度结果进行差异分析、悖论消解和假设生成。',
        'generated_at': datetime.now().isoformat(),
    }

    output_path = OUTPUT_DIR / 'unique_insights.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"独到见解框架已准备 → {output_path}")
    return result


def main():
    parser = argparse.ArgumentParser(description='运行五维度人格分析')
    parser.add_argument('--db', type=str, default=str(DB_PATH), help='数据库路径')
    parser.add_argument('--dimensions', type=str, default='all',
                        help=f'指定维度，逗号分隔。可选: {",".join(DIMENSIONS)}')
    parser.add_argument('--skip', type=str, default='',
                        help='跳过的维度，逗号分隔')
    args = parser.parse_args()

    # 检查数据库
    db_path = Path(args.db)
    if not db_path.exists():
        logger.error(f"数据库不存在: {db_path}，请先运行 07_clean_and_store.py")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    db = DatabaseManager(db_path)
    db.connect()
    processor = TextProcessor()

    tracker = ProgressTracker(PROGRESS_PATH)

    # 确定要运行的维度
    if args.dimensions == 'all':
        run_dims = DIMENSIONS
    else:
        run_dims = [d.strip() for d in args.dimensions.split(',')]

    skip_dims = set(s.strip() for s in args.skip.split(',')) if args.skip else set()
    run_dims = [d for d in run_dims if d not in skip_dims]

    logger.info(f"将运行维度: {', '.join(run_dims)}")

    # 维度 -> 函数映射
    runners = {
        'language': lambda: run_language_analysis(db, processor, args),
        'thinking': lambda: run_thinking_analysis(db, args),
        'values': lambda: run_values_analysis(db, args),
        'interaction': lambda: run_interaction_analysis(db, args),
        'personality': lambda: run_personality_analysis(db, args),
        'insights': None,  # 最后统一处理
    }

    all_results = {}

    for dim in run_dims:
        if dim == 'insights':
            continue
        if tracker.is_phase_completed(f'08_analysis_{dim}'):
            logger.info(f"维度 {dim} 已完成，跳过")
            # 加载已有结果
            output_path = OUTPUT_DIR / f'{dim}_analysis.json'
            if output_path.exists():
                with open(output_path, 'r', encoding='utf-8') as f:
                    all_results[dim] = json.load(f)
            continue

        tracker.start_phase(f'08_analysis_{dim}')
        try:
            result = runners[dim]()
            all_results[dim] = result
            tracker.complete_phase(f'08_analysis_{dim}')
        except Exception as e:
            logger.error(f"维度 {dim} 分析失败: {e}", exc_info=True)
            tracker.fail_phase(f'08_analysis_{dim}', str(e))

    # insights 在所有维度之后运行
    if 'insights' in run_dims:
        tracker.start_phase('08_analysis_insights')
        try:
            result = run_insights_synthesis(all_results, args)
            all_results['insights'] = result
            tracker.complete_phase('08_analysis_insights')
        except Exception as e:
            logger.error(f"独到见解合成失败: {e}", exc_info=True)
            tracker.fail_phase('08_analysis_insights', str(e))

    db.close()

    # 总结
    logger.info("=" * 50)
    logger.info("分析引擎运行完成")
    logger.info(f"已运行的维度: {list(all_results.keys())}")
    logger.info(f"输出目录: {OUTPUT_DIR}")

    # 检查哪些维度需要 LLM agent 进一步处理
    llm_dimensions = ['thinking', 'values', 'interaction', 'personality', 'insights']
    pending = [d for d in llm_dimensions if d in all_results and 'note' in all_results[d]]
    if pending:
        logger.info("以下维度需要 LLM agent 进一步处理（当前仅完成了量化框架）：")
        for d in pending:
            logger.info(f"  - {d}")


if __name__ == '__main__':
    main()
