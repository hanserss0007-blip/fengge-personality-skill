#!/usr/bin/env python3
"""
01_discover_videos.py — 扫描B站录播频道，生成视频目录。

使用 yt-dlp 获取频道视频列表（比 bilibili-api 更稳定，绕过412风控）。
支持通过 UID 直接拉取，也支持关键词搜索发现新频道。
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.utils.progress_tracker import ProgressTracker

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 已知的录播频道（UID 通过搜索确认）
KNOWN_CHANNELS = [
    {'name': '天涯亡命峰哥', 'uid': 51414558, 'videos_est': 923},
    {'name': '峰哥亡命天涯', 'uid': 35847683, 'videos_est': 664},
    {'name': '゙峰哥亡命天涯', 'uid': 21128578, 'videos_est': 15},
    # 以下需要搜索确认 UID
    {'name': '诸葛黑蛋', 'uid': None, 'keyword': '诸葛黑蛋'},
    {'name': '姜哥滴猜想', 'uid': None, 'keyword': '姜哥滴猜想'},
    {'name': '臭鱼烂虾传媒', 'uid': None, 'keyword': '臭鱼烂虾传媒'},
    {'name': '文工团素材专用号', 'uid': None, 'keyword': '文工团素材专用号'},
    {'name': 'ThreeD幻想亡命天涯', 'uid': None, 'keyword': 'ThreeD幻想亡命天涯'},
    {'name': '小阿峰世间万物', 'uid': None, 'keyword': '小阿峰世间万物'},
]

YT_DLP_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / 'data_raw' / 'metadata'
PROGRESS_PATH = Path(__file__).resolve().parent.parent / 'data_raw' / 'progress.json'


def check_yt_dlp():
    """验证 yt-dlp 可用。"""
    try:
        r = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True)
        logger.info(f"yt-dlp {r.stdout.strip()}")
        return True
    except FileNotFoundError:
        logger.error("yt-dlp 未安装: pip install yt-dlp")
        return False


def get_channel_videos(uid: int, max_videos: int = 0) -> list[dict]:
    """使用 yt-dlp 获取频道视频列表。

    Args:
        uid: B站用户 UID
        max_videos: 最大获取数（0=全部）

    Returns:
        视频元数据列表
    """
    url = f'https://space.bilibili.com/{uid}/video'
    cookie_file = Path(__file__).resolve().parent.parent / 'bilibili_cookies.txt'
    cmd = [
        'yt-dlp',
        '--user-agent', YT_DLP_UA,
        '--flat-playlist',
        '--dump-json',
        '--no-warnings',
        '--socket-timeout', '30',
    ]
    if cookie_file.exists():
        cmd += ['--cookies', str(cookie_file)]
    if max_videos > 0:
        cmd += ['--playlist-end', str(max_videos)]
    cmd.append(url)

    logger.info(f"获取 UID={uid} 的视频列表...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if '412' in stderr:
                logger.warning(f"  UID={uid} 触发B站风控(412)，尝试添加延迟后重试...")
                import time
                time.sleep(10)
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0 or not result.stdout.strip():
            logger.error(f"  UID={uid} 获取失败: {result.stderr[:200] if result.stderr else '无输出'}")
            return []

        videos = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            try:
                v = json.loads(line)
                videos.append({
                    'bvid': v.get('id', ''),
                    'title': v.get('title', ''),
                    'duration_sec': v.get('duration', 0) or 0,
                    'view_count': v.get('view_count', 0) or 0,
                    'upload_date': v.get('upload_date', '') or '',
                    'description': v.get('description', '') or '',
                    'channel_uid': uid,
                    'source': 'yt-dlp',
                })
            except json.JSONDecodeError:
                continue

        logger.info(f"  UID={uid}: 获取 {len(videos)} 个视频")
        return videos

    except subprocess.TimeoutExpired:
        logger.error(f"  UID={uid} 超时")
        return []
    except Exception as e:
        logger.error(f"  UID={uid} 异常: {e}")
        return []


def search_uid_by_keyword(keyword: str) -> list[dict]:
    """通过关键词搜索 UP 主 UID（使用 bilibili-api 搜索）。"""
    import asyncio
    from scripts.utils.bilibili_client import get_client

    async def _search():
        client = get_client(rate_limit=1.0)
        try:
            result = await client.search_user(keyword)
            users = []
            if result and 'result' in result:
                for item in result['result'][:5]:
                    users.append({
                        'uid': item.get('mid'),
                        'name': item.get('uname', ''),
                        'fans': item.get('fans', 0),
                        'videos_count': item.get('videos', 0),
                    })
            return users
        except Exception as e:
            logger.warning(f"搜索 '{keyword}' 失败: {e}")
            return []

    return asyncio.run(_search())


def main():
    parser = argparse.ArgumentParser(description='发现峰哥相关视频')
    parser.add_argument('--max-per-channel', type=int, default=0,
                        help='每个频道最大视频数（0=全部）')
    parser.add_argument('--output', type=str, default=None, help='输出路径')
    parser.add_argument('--channels', type=str, nargs='*',
                        help='指定频道UID（空格分隔），跳过已知列表')
    args = parser.parse_args()

    if not check_yt_dlp():
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else OUTPUT_DIR / 'video_catalog.json'
    tracker = ProgressTracker(PROGRESS_PATH)
    tracker.start_phase('01_discover')

    all_videos = []
    seen_bvids = set()

    # 确定要扫描的频道
    channels_to_scan = []
    if args.channels:
        for uid_str in args.channels:
            channels_to_scan.append({'name': f'UID_{uid_str}', 'uid': int(uid_str)})
    else:
        channels_to_scan = KNOWN_CHANNELS

    # Phase 1: 扫描已知频道
    logger.info(f"=== Phase 1: 扫描 {len(channels_to_scan)} 个频道 ===")

    for ch in channels_to_scan:
        uid = ch.get('uid')
        name = ch.get('name', f'UID_{uid}')

        # 如果 UID 未知，搜索获取
        if uid is None and ch.get('keyword'):
            logger.info(f"搜索 '{name}' 的 UID...")
            search_results = search_uid_by_keyword(ch['keyword'])
            if search_results:
                uid = search_results[0]['uid']
                name = search_results[0]['name']
                logger.info(f"  找到: {name} (UID={uid})")
            else:
                logger.warning(f"  未找到 '{name}'，跳过")
                continue
        elif uid is None:
            logger.warning(f"  '{name}' 无 UID 且无搜索关键词，跳过")
            continue

        # 获取视频列表
        videos = get_channel_videos(uid, max_videos=args.max_per_channel)
        new_count = 0
        for v in videos:
            v['channel_name'] = name
            if v['bvid'] not in seen_bvids:
                seen_bvids.add(v['bvid'])
                all_videos.append(v)
                new_count += 1

        logger.info(f"  {name}: 新增 {new_count} 个视频（累计 {len(all_videos)}）")
        tracker.set_phase_data('01_discover', name, {
            'uid': uid,
            'fetched': len(videos),
            'new': new_count,
        })

        # 频道间延迟
        import time
        time.sleep(3)

    # 输出
    output_data = {
        'total': len(all_videos),
        'generated_at': datetime.now().isoformat(),
        'sources': [{'name': ch.get('name', ''), 'uid': ch.get('uid')} for ch in channels_to_scan],
        'videos': all_videos,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    tracker.complete_phase('01_discover')
    tracker.set_phase_data('01_discover', 'output_path', str(output_path))
    tracker.set_phase_data('01_discover', 'total', len(all_videos))

    logger.info(f"视频目录已保存: {output_path}")
    logger.info(f"共发现 {len(all_videos)} 个视频（去重后）")


if __name__ == '__main__':
    main()
