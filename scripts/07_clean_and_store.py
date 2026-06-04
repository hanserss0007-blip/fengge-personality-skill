#!/usr/bin/env python3
"""
07_clean_and_store.py — 数据清洗和 SQLite 入库。

- 文本正则化、清洗
- jieba 分词 + FTS5 全文索引
- 生成 corpus.db
- 输出语料统计报告
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.utils.db_manager import DatabaseManager
from scripts.utils.text_processor import TextProcessor
from scripts.utils.progress_tracker import ProgressTracker

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / 'data_raw'
PROCESSED_DIR = Path(__file__).resolve().parent.parent / 'data_processed'
SEGMENTS_DIR = PROCESSED_DIR / 'segments'
DB_PATH = PROCESSED_DIR / 'corpus.db'
PROGRESS_PATH = DATA_DIR / 'progress.json'
METADATA_DIR = DATA_DIR / 'metadata'
DANMAKU_DIR = DATA_DIR / 'danmaku'
COMMENTS_DIR = DATA_DIR / 'comments'
TRANSCRIPT_DIR = DATA_DIR / 'transcripts'


def load_segments(bvid: str) -> list[dict]:
    """加载已分段的发言。"""
    seg_path = SEGMENTS_DIR / f'{bvid}_segments.json'
    if not seg_path.exists():
        return []
    with open(seg_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('segments', [])


def load_danmaku(bvid: str) -> list[dict]:
    """加载弹幕数据。"""
    path = DANMAKU_DIR / f'{bvid}_danmaku.json'
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_comments(bvid: str) -> list[dict]:
    """加载评论数据。"""
    path = COMMENTS_DIR / f'{bvid}_comments.json'
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_transcript(bvid: str) -> dict:
    """加载 transcript 获取总时长。"""
    path = TRANSCRIPT_DIR / f'{bvid}_transcript.json'
    if not path.exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description='数据清洗和入库')
    parser.add_argument('--plan', type=str,
                        default=str(DATA_DIR / 'metadata' / 'collection_plan.json'),
                        help='collection_plan.json 路径')
    parser.add_argument('--db', type=str, default=str(DB_PATH), help='数据库路径')
    parser.add_argument('--limit', type=int, default=0, help='限制处理数量')
    args = parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    tracker = ProgressTracker(PROGRESS_PATH)
    tracker.start_phase('07_clean_and_store')

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

    tracker.set_total_items('07_clean_and_store', len(videos))

    # 初始化数据库和文本处理器
    db = DatabaseManager(args.db)
    db.connect()
    processor = TextProcessor()

    logger.info(f"开始清洗 {len(videos)} 个视频的数据并入库")

    # 统计
    stats = {
        'videos_processed': 0,
        'utterances_total': 0,
        'utterances_fengge': 0,
        'danmaku_total': 0,
        'comments_total': 0,
        'fengge_total_chars': 0,
    }

    for i, video in enumerate(videos):
        bvid = video['bvid']
        if tracker.is_item_completed('07_clean_and_store', bvid):
            continue

        logger.info(f"[{i + 1}/{len(videos)}] {bvid}")

        # 1. 插入视频记录
        transcript = load_transcript(bvid)
        duration = transcript.get('segments', [])
        duration_sec = duration[-1]['end'] if duration else 0

        video_id = db.insert_video({
            'bvid': bvid,
            'source': 'bilibili',
            'title': video.get('title', ''),
            'description': video.get('description', ''),
            'duration_sec': duration_sec,
            'upload_date': video.get('upload_date', ''),
            'category': video.get('category', '其他'),
            'url': f'https://www.bilibili.com/video/{bvid}',
            'metadata': video,
        })

        # 2. 插入发言
        segments = load_segments(bvid)
        if segments:
            utterances = []
            for j, seg in enumerate(segments):
                text = processor.clean_for_analysis(processor.normalize(seg['text']))
                if not text:
                    continue
                speaker = seg.get('speaker', 'unknown')
                if len(text) < 2:
                    continue

                utterances.append({
                    'video_id': video_id,
                    'speaker': speaker,
                    'text': text,
                    'start_ts': seg.get('start'),
                    'end_ts': seg.get('end'),
                    'utterance_index': j,
                    'confidence': seg.get('confidence', 1.0),
                    'source_type': transcript.get('source', 'unknown'),
                })

            db.insert_utterances(utterances)
            stats['utterances_total'] += len(utterances)
            stats['utterances_fengge'] += sum(1 for u in utterances if u['speaker'] == 'fengge')
            stats['fengge_total_chars'] += sum(
                len(re.findall(r'[一-鿿]', u['text']))
                for u in utterances if u['speaker'] == 'fengge'
            )

        # 3. 插入弹幕
        danmaku = load_danmaku(bvid)
        if danmaku:
            danmaku_rows = []
            for d in danmaku:
                text = processor.normalize(d.get('text', ''))
                if not text:
                    continue
                danmaku_rows.append({
                    'video_id': video_id,
                    'text': text,
                    'video_ts': d.get('video_ts'),
                    'send_time': d.get('send_time', ''),
                    'mode': d.get('mode', 1),
                    'font_size': d.get('font_size', 25),
                    'color': d.get('color', 16777215),
                    'metadata': d,
                })
            db.insert_danmaku_batch(danmaku_rows)
            stats['danmaku_total'] += len(danmaku_rows)

        # 4. 插入评论
        comments = load_comments(bvid)
        if comments:
            comment_rows = []
            for c in comments:
                text = processor.normalize(c.get('text', ''))
                if not text:
                    continue
                comment_rows.append({
                    'video_id': video_id,
                    'text': text,
                    'likes': c.get('likes', 0),
                    'replies_count': c.get('replies_count', 0),
                    'send_time': c.get('send_time', ''),
                    'user_name': c.get('user_name', ''),
                    'metadata': c,
                })
            db.insert_comments_batch(comment_rows)
            stats['comments_total'] += len(comment_rows)

        stats['videos_processed'] += 1
        tracker.mark_item_completed('07_clean_and_store', bvid)

        # 每10个视频提交一次
        if (i + 1) % 10 == 0:
            db.conn.commit()

    db.conn.commit()

    # 生成语料统计报告
    corpus_stats = db.get_corpus_stats()
    stats.update(corpus_stats)

    report = {
        'generated_at': datetime.now().isoformat(),
        'pipeline_version': '0.1.0',
        'input_videos': len(videos),
        **stats,
    }

    report_path = PROCESSED_DIR / 'processing_report.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    tracker.complete_phase('07_clean_and_store')
    tracker.set_phase_data('07_clean_and_store', 'stats', stats)

    db.close()

    logger.info("=" * 50)
    logger.info("数据清洗入库完成!")
    logger.info(f"  处理视频: {stats['videos_processed']}")
    logger.info(f"  发言总数: {stats['utterances_total']}")
    logger.info(f"  峰哥发言: {stats['utterances_fengge']} ({stats['fengge_total_chars']} 字)")
    logger.info(f"  弹幕总数: {stats['danmaku_total']}")
    logger.info(f"  评论总数: {stats['comments_total']}")
    logger.info(f"  数据库: {args.db}")
    logger.info(f"  报告: {report_path}")


if __name__ == '__main__':
    main()
