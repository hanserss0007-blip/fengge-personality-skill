#!/usr/bin/env python3
"""
06_segment_speakers.py — LLM辅助说话人分类。

对每个 transcript：
- 将文本段落标注为：fengge / guest / caller / multiple / unknown
- 使用规则 + LLM 相结合的方式
- 输出带说话人标签的分段 JSON
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.utils.progress_tracker import ProgressTracker

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / 'data_raw'
TRANSCRIPT_DIR = DATA_DIR / 'transcripts'
SEGMENTS_DIR = Path(__file__).resolve().parent.parent / 'data_processed' / 'segments'
PROGRESS_PATH = DATA_DIR / 'progress.json'

# 峰哥的语言特征标记（规则兜底）
FENGGE_MARKERS = [
    r'祝大家[！!]',
    r'长生不老',
    r'永远不死',
    r'爱你呦',
    r'解答世间万物',
    r'欢迎.*来到直播间',
    r'我是峰哥',
    r'关注主播',
    r'点赞.*转发',
    r'It\'s not that simple',
    r'That\'s pretty rude',
    r'听我说',
    r'我跟你讲',
    r'我告诉你',
    r"我跟你说",
]

# 观众/Caller 的语言特征标记
CALLER_MARKERS = [
    r'峰哥.*你好',
    r'峰哥.*能不能',
    r'我有一个问题',
    r'我想问',
    r'请问',
    r'我是.*粉丝',
    r'我是.*观众',
    r'能不能连麦',
    r'峰哥.*我',
    r'主播',
]


def rule_based_classify(text: str) -> str:
    """基于规则初步分类。

    Returns:
        'fengge' | 'caller' | 'unknown'
    """
    for pattern in FENGGE_MARKERS:
        if re.search(pattern, text, re.IGNORECASE):
            return 'fengge'

    for pattern in CALLER_MARKERS:
        if re.search(pattern, text, re.IGNORECASE):
            return 'caller'

    return 'unknown'


def build_llm_prompt(segments: list[dict], max_samples: int = 20) -> str:
    """构建发送给 LLM 的分类 prompt。

    Args:
        segments: 前 max_samples 个未分类分段
        max_samples: 最大采样数

    Returns:
        Prompt 文本
    """
    samples = segments[:max_samples]
    samples_text = '\n\n'.join(
        f"[{i}] {seg['text'][:200]}"
        for i, seg in enumerate(samples)
    )

    prompt = f"""你是对话分类助手。请对以下直播转录文本的每个片段进行说话人分类。

片段来自主播「峰哥亡命天涯」的直播。说话人类型：
- fengge: 主播峰哥本人（控制对话节奏、插科打诨、长篇大论、主动提问）
- guest: 连麦嘉宾/熟人（和峰哥有来有往、平等对话）
- caller: 连麦观众（提问者、被峰哥调侃的对象、语气较低姿态）
- multiple: 多人同时说话
- unknown: 无法判断

请按以下 JSON 格式返回分类结果（只返回 JSON，不要其他内容）：
{{"classifications": [{{"index": 0, "speaker": "fengge", "confidence": 0.9}}, ...]}}

以下是待分类的片段：

{samples_text}

请对以上 {len(samples)} 个片段进行分类。"""
    return prompt


def classify_with_rules_only(segments: list[dict]) -> list[dict]:
    """仅用规则分类（不需要 LLM）。"""
    classified = []
    for seg in segments:
        speaker = rule_based_classify(seg['text'])
        confidence = 0.6 if speaker != 'unknown' else 0.3
        classified.append({
            **seg,
            'speaker': speaker,
            'confidence': confidence,
            'method': 'rule',
        })
    return classified


def smooth_classifications(segments: list[dict], window: int = 3) -> list[dict]:
    """平滑分类结果：在同一窗口内，少数服从多数。

    直播对话通常一个人连续说多段话后再换人。
    """
    smoothed = list(segments)
    for i in range(len(smoothed)):
        start = max(0, i - window // 2)
        end = min(len(smoothed), i + window // 2 + 1)
        window_segs = smoothed[start:end]

        # 统计窗口内的说话人
        from collections import Counter
        speaker_counts = Counter(s['speaker'] for s in window_segs if s['speaker'] != 'unknown')
        if speaker_counts:
            majority_speaker = speaker_counts.most_common(1)[0][0]
            if smoothed[i]['speaker'] != majority_speaker and smoothed[i]['confidence'] < 0.7:
                smoothed[i] = {
                    **smoothed[i],
                    'speaker': majority_speaker,
                    'confidence': min(smoothed[i]['confidence'] + 0.1, 0.8),
                    'method': smoothed[i].get('method', 'rule') + '_smoothed',
                }

    return smoothed


def main():
    parser = argparse.ArgumentParser(description='说话人分割')
    parser.add_argument('--plan', type=str,
                        default=str(DATA_DIR / 'metadata' / 'collection_plan.json'),
                        help='collection_plan.json 路径')
    parser.add_argument('--limit', type=int, default=0,
                        help='限制处理数量（0=全部）')
    parser.add_argument('--use-llm', action='store_true',
                        help='使用 LLM 辅助分类（需要 API key）')
    parser.add_argument('--window', type=int, default=3,
                        help='平滑窗口大小（默认3）')
    args = parser.parse_args()

    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    tracker = ProgressTracker(PROGRESS_PATH)
    tracker.start_phase('06_segment_speakers')

    # 加载采集计划
    plan_path = Path(args.plan)
    if not plan_path.exists():
        logger.error(f"采集计划不存在: {plan_path}")
        sys.exit(1)

    with open(plan_path, 'r', encoding='utf-8') as f:
        plan = json.load(f)

    videos = plan['videos']
    if args.limit > 0:
        videos = videos[:args.limit]

    tracker.set_total_items('06_segment_speakers', len(videos))

    logger.info(f"开始说话人分割: {len(videos)} 个视频")
    logger.info(f"方法: {'LLM+规则' if args.use_llm else '仅规则'}, 平滑窗口={args.window}")

    stats = {'total': 0, 'fengge': 0, 'guest': 0, 'caller': 0, 'multiple': 0, 'unknown': 0}
    success_count = 0

    for i, video in enumerate(videos):
        bvid = video['bvid']
        if tracker.is_item_completed('06_segment_speakers', bvid):
            continue

        # 加载 transcript
        transcript_path = TRANSCRIPT_DIR / f'{bvid}_transcript.json'
        if not transcript_path.exists():
            logger.warning(f"  [{bvid}] transcript 不存在，跳过")
            continue

        with open(transcript_path, 'r', encoding='utf-8') as f:
            transcript = json.load(f)

        segments = transcript.get('segments', [])
        if not segments:
            logger.warning(f"  [{bvid}] 无分段数据，跳过")
            continue

        logger.info(f"[{i + 1}/{len(videos)}] {bvid} ({len(segments)} 段)")

        # 分类
        if args.use_llm:
            # TODO: 集成 LLM API 调用
            # 当前回退到仅规则
            logger.info(f"  LLM 模式暂未实现，使用仅规则")
            classified = classify_with_rules_only(segments)
        else:
            classified = classify_with_rules_only(segments)

        # 平滑
        smoothed = smooth_classifications(classified, window=args.window)

        # 统计
        from collections import Counter
        speaker_counts = Counter(s['speaker'] for s in smoothed)
        for speaker in ['fengge', 'guest', 'caller', 'multiple', 'unknown']:
            stats[speaker] += speaker_counts.get(speaker, 0)
        stats['total'] += len(smoothed)

        # 保存
        out_path = SEGMENTS_DIR / f'{bvid}_segments.json'
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({
                'bvid': bvid,
                'title': video.get('title', ''),
                'source_type': transcript.get('source', 'subtitle'),
                'total_segments': len(smoothed),
                'speaker_distribution': dict(speaker_counts),
                'segments': smoothed,
                'classified_at': datetime.now().isoformat(),
            }, f, ensure_ascii=False, indent=2)

        tracker.mark_item_completed('06_segment_speakers', bvid)
        success_count += 1

    tracker.complete_phase('06_segment_speakers')
    tracker.set_phase_data('06_segment_speakers', 'stats', {
        'videos_processed': success_count,
        'total_segments': stats['total'],
        'speaker_distribution': {k: v for k, v in stats.items() if k != 'total'},
    })

    logger.info(f"说话人分割完成: {success_count} 个视频")
    logger.info(f"总分段: {stats['total']}")
    for speaker in ['fengge', 'guest', 'caller', 'multiple', 'unknown']:
        pct = stats[speaker] / max(stats['total'], 1) * 100
        logger.info(f"  {speaker}: {stats[speaker]} ({pct:.1f}%)")


if __name__ == '__main__':
    main()
