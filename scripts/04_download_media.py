#!/usr/bin/env python3
"""
04_download_media.py — 下载字幕和音频（不下载完整视频）。

使用 yt-dlp 下载：
- 字幕文件（优先选择自动生成的中文字幕）
- 音频流（仅用于无字幕时的 ASR 兜底）
- 默认不下载视频流，节省存储空间
"""

import argparse
import json
import logging
import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.utils.download_manager import DownloadManager, DownloadTask
from scripts.utils.progress_tracker import ProgressTracker

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / 'data_raw'
PLAN_PATH = DATA_DIR / 'metadata' / 'collection_plan.json'
PROGRESS_PATH = DATA_DIR / 'progress.json'
SUBTITLE_DIR = DATA_DIR / 'subtitles'
AUDIO_DIR = DATA_DIR / 'audio'


def check_yt_dlp() -> bool:
    """检查 yt-dlp 是否可用。"""
    try:
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True)
        logger.info(f"yt-dlp 版本: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        logger.error("yt-dlp 未安装，请运行: pip install yt-dlp")
        return False


def extract_subs_with_ytdlp(bvid: str, subtitle_dir: Path, audio_dir: Path) -> bool:
    """使用 yt-dlp 下载 B站视频的字幕和音频。

    Args:
        bvid: BV 号
        subtitle_dir: 字幕输出目录
        audio_dir: 音频输出目录

    Returns:
        是否成功
    """
    url = f'https://www.bilibili.com/video/{bvid}'
    subtitle_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    # 1. 先尝试下载字幕
    sub_output = subtitle_dir / f'{bvid}'
    cmd_subs = [
        'yt-dlp',
        '--skip-download',           # 不下载视频
        '--write-subs',              # 写入字幕
        '--write-auto-subs',         # 包括自动生成字幕
        '--sub-langs', 'zh-Hans,zh,en',  # 优先中文字幕
        '--sub-format', 'srt/vtt/ttml',  # 接受的字幕格式
        '--convert-subs', 'srt',     # 转换为 srt
        '--output', str(sub_output),
        '--no-warnings',
        '--quiet',
        url,
    ]

    try:
        subprocess.run(cmd_subs, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        logger.warning(f"  [{bvid}] 字幕下载超时")
    except Exception as e:
        logger.warning(f"  [{bvid}] 字幕下载异常: {e}")

    # 检查是否成功获取字幕
    subtitle_files = list(subtitle_dir.glob(f'{bvid}*.srt')) + \
                     list(subtitle_dir.glob(f'{bvid}*.vtt'))
    has_subtitles = len(subtitle_files) > 0

    # 2. 下载音频（仅用于无字幕时 ASR）
    if not has_subtitles:
        logger.info(f"  [{bvid}] 无字幕，下载音频用于 ASR")
        audio_output = audio_dir / f'{bvid}'
        cmd_audio = [
            'yt-dlp',
            '-f', 'worstaudio',       # 最低质量音频（够ASR用，节省空间）
            '--output', str(audio_output),
            '--no-warnings',
            '--quiet',
            url,
        ]
        try:
            subprocess.run(cmd_audio, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            logger.warning(f"  [{bvid}] 音频下载超时")
            return False
        except Exception as e:
            logger.warning(f"  [{bvid}] 音频下载异常: {e}")
            return False

    return True


def download_fn(task: DownloadTask, tmp_path: Path) -> bool:
    """下载函数（供 DownloadManager 使用）。"""
    bvid = task.task_id
    # yt-dlp 直接下载到目标目录，tmp 仅用于进度标记
    result = extract_subs_with_ytdlp(bvid, SUBTITLE_DIR, AUDIO_DIR)
    # 写入标记
    tmp_path.write_text(json.dumps({'success': result, 'bvid': bvid}))
    return result


def main():
    parser = argparse.ArgumentParser(description='下载字幕和音频')
    parser.add_argument('--plan', type=str, default=str(PLAN_PATH),
                        help='collection_plan.json 路径')
    parser.add_argument('--no-video', action='store_true', default=True,
                        help='不下载视频（默认开启）')
    parser.add_argument('--video', action='store_true',
                        help='同时下载视频文件（需要50GB+）')
    parser.add_argument('--limit', type=int, default=0,
                        help='限制处理数量（0=全部）')
    parser.add_argument('--threads', type=int, default=2,
                        help='并发下载数（默认2，太高可能被限）')
    args = parser.parse_args()

    if not check_yt_dlp():
        sys.exit(1)

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

    logger.info(f"开始处理 {len(videos)} 个视频")
    logger.info(f"字幕输出: {SUBTITLE_DIR}")
    logger.info(f"音频输出: {AUDIO_DIR}")
    if args.video:
        logger.warning("已启用视频下载模式，需要大量存储空间")

    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    tracker = ProgressTracker(PROGRESS_PATH)
    tracker.start_phase('04_download_media')
    tracker.set_total_items('04_download_media', len(videos))

    manager = DownloadManager(num_threads=args.threads, max_retries=2)

    for video in videos:
        bvid = video['bvid']
        if tracker.is_item_completed('04_download_media', bvid):
            continue
        task = DownloadTask(
            task_id=bvid,
            url=f'https://www.bilibili.com/video/{bvid}',
            dest_path=SUBTITLE_DIR / f'{bvid}.done',
            metadata={'title': video.get('title', ''), 'bvid': bvid},
        )
        manager.add_task(task)

    results = manager.run(download_fn, progress_desc='下载字幕/音频')

    # 统计
    success_count = sum(1 for r in results.values() if r['success'])
    for bvid, r in results.items():
        if r['success']:
            tracker.mark_item_completed('04_download_media', bvid)

    subtitle_count = len(list(SUBTITLE_DIR.glob('*.srt'))) + len(list(SUBTITLE_DIR.glob('*.vtt')))
    audio_count = len(list(AUDIO_DIR.glob('*')))

    tracker.complete_phase('04_download_media')
    tracker.set_phase_data('04_download_media', 'stats', {
        'total': len(videos),
        'success': success_count,
        'subtitle_files': subtitle_count,
        'audio_files': audio_count,
    })

    logger.info(f"下载完成: {success_count}/{len(videos)} 成功")
    logger.info(f"  字幕文件: {subtitle_count}")
    logger.info(f"  音频文件: {audio_count}")


if __name__ == '__main__':
    main()
