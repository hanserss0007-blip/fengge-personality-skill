#!/usr/bin/env python3
"""
03_download_metadata.py — 拉取弹幕、评论和视频详细信息。

对 collection_plan.json 中的每个视频：
- 获取视频详细信息
- 拉取弹幕数据
- 拉取评论数据
- 保存为 JSON 文件
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.utils.bilibili_client import get_client
from scripts.utils.progress_tracker import ProgressTracker

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / 'data_raw'
PLAN_PATH = DATA_DIR / 'metadata' / 'collection_plan.json'
PROGRESS_PATH = DATA_DIR / 'progress.json'
DANMAKU_DIR = DATA_DIR / 'danmaku'
COMMENTS_DIR = DATA_DIR / 'comments'
METADATA_DIR = DATA_DIR / 'metadata'


async def process_video(client, video: dict, tracker: ProgressTracker) -> dict:
    """处理单个视频：获取元数据、弹幕、评论。"""
    bvid = video['bvid']
    result = {'bvid': bvid, 'success': True, 'errors': []}

    # 跳过已完成的
    if tracker.is_item_completed('03_download_metadata', bvid):
        logger.info(f"  [{bvid}] 已完成，跳过")
        return result

    # 1. 视频详细信息
    try:
        info = await client.get_video_info(bvid)
        meta_path = METADATA_DIR / f'{bvid}_info.json'
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        logger.info(f"  [{bvid}] 视频信息已保存")
    except Exception as e:
        logger.warning(f"  [{bvid}] 获取视频信息失败: {e}")
        result['errors'].append(f'info: {e}')

    # 2. 弹幕
    try:
        danmaku = await client.get_danmakus(bvid)
        danmaku_path = DANMAKU_DIR / f'{bvid}_danmaku.json'
        danmaku_data = [
            {
                'text': str(d.text),
                'send_time': str(d.send_time) if hasattr(d, 'send_time') else '',
                'mode': getattr(d, 'mode', 1),
                'font_size': getattr(d, 'font_size', 25),
                'color': getattr(d, 'color', 16777215),
                'video_ts': getattr(d, 'video_ts', None),
            }
            for d in danmaku
        ]
        with open(danmaku_path, 'w', encoding='utf-8') as f:
            json.dump(danmaku_data, f, ensure_ascii=False, indent=2)
        logger.info(f"  [{bvid}] {len(danmaku_data)} 条弹幕")
    except Exception as e:
        logger.warning(f"  [{bvid}] 获取弹幕失败: {e}")
        result['errors'].append(f'danmaku: {e}')

    # 3. 评论（前5页）
    try:
        all_comments = []
        for page in range(1, 6):
            comments = await client.get_comments(bvid, page=page, sort=2)
            if comments and 'replies' in comments:
                replies = comments['replies']
                if not replies:
                    break
                for r in replies:
                    all_comments.append({
                        'text': r.get('content', {}).get('message', ''),
                        'likes': r.get('like', 0),
                        'replies_count': r.get('rcount', 0),
                        'send_time': r.get('ctime', ''),
                        'user_name': r.get('member', {}).get('uname', ''),
                    })
            await asyncio.sleep(0.5)  # 评论页间延迟

        comments_path = COMMENTS_DIR / f'{bvid}_comments.json'
        with open(comments_path, 'w', encoding='utf-8') as f:
            json.dump(all_comments, f, ensure_ascii=False, indent=2)
        logger.info(f"  [{bvid}] {len(all_comments)} 条评论")
    except Exception as e:
        logger.warning(f"  [{bvid}] 获取评论失败: {e}")
        result['errors'].append(f'comments: {e}')

    tracker.mark_item_completed('03_download_metadata', bvid)
    return result


async def main():
    parser = argparse.ArgumentParser(description='下载视频元数据（弹幕+评论+信息）')
    parser.add_argument('--plan', type=str, default=str(PLAN_PATH),
                        help='collection_plan.json 路径')
    parser.add_argument('--limit', type=int, default=0,
                        help='限制处理数量（0=全部）')
    parser.add_argument('--resume', action='store_true', default=True,
                        help='断点续传（默认开启）')
    args = parser.parse_args()

    # 确保目录存在
    DANMAKU_DIR.mkdir(parents=True, exist_ok=True)
    COMMENTS_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    # 加载采集计划
    plan_path = Path(args.plan)
    if not plan_path.exists():
        logger.error(f"采集计划不存在: {plan_path}，请先运行 02_filter_videos.py")
        sys.exit(1)

    with open(plan_path, 'r', encoding='utf-8') as f:
        plan = json.load(f)

    videos = plan['videos']
    if args.limit > 0:
        videos = videos[:args.limit]

    logger.info(f"开始处理 {len(videos)} 个视频的元数据")

    tracker = ProgressTracker(PROGRESS_PATH)
    tracker.start_phase('03_download_metadata')
    tracker.set_total_items('03_download_metadata', len(videos))

    client = get_client(rate_limit=1.0)

    success_count = 0
    error_count = 0

    for i, video in enumerate(videos):
        bvid = video['bvid']
        logger.info(f"[{i + 1}/{len(videos)}] {bvid} - {video.get('title', '')[:50]}")

        try:
            result = await process_video(client, video, tracker)
            if result['success'] and not result['errors']:
                success_count += 1
            elif result['errors']:
                error_count += 1
                # 部分错误但仍有数据
                if len(result['errors']) < 3:
                    success_count += 1
        except Exception as e:
            logger.error(f"  [{bvid}] 处理异常: {e}")
            error_count += 1

        # 每10个视频保存一次进度
        if (i + 1) % 10 == 0:
            tracker.save()

    tracker.complete_phase('03_download_metadata')
    tracker.set_phase_data('03_download_metadata', 'stats', {
        'total': len(videos),
        'success': success_count,
        'error': error_count,
    })

    logger.info(f"元数据下载完成: {success_count} 成功 / {error_count} 失败")


if __name__ == '__main__':
    asyncio.run(main())
