#!/usr/bin/env python3
"""
05_extract_text.py — 字幕提取 / Whisper ASR 兜底。

对每个视频：
- 如果有字幕文件（.srt/.vtt），直接提取文本
- 如果无字幕但有音频，用 Whisper 转写
- 输出统一的 transcript .json 格式
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.utils.whisper_asr import WhisperASR, get_optimal_model_size
from scripts.utils.text_processor import TextProcessor
from scripts.utils.progress_tracker import ProgressTracker

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / 'data_raw'
SUBTITLE_DIR = DATA_DIR / 'subtitles'
AUDIO_DIR = DATA_DIR / 'audio'
TRANSCRIPT_DIR = DATA_DIR / 'transcripts'
PROGRESS_PATH = DATA_DIR / 'progress.json'


def parse_srt(content: str) -> list[dict]:
    """解析 SRT 字幕格式。

    Args:
        content: SRT 文件内容

    Returns:
        [{'index': int, 'start': float, 'end': float, 'text': str}]
    """
    segments = []
    # 标准 SRT 格式：序号、时间戳、文本
    pattern = re.compile(
        r'(\d+)\s*\n'
        r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*'
        r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*\n'
        r'((?:(?!\n\d+\n).)+)',
        re.MULTILINE | re.DOTALL
    )

    for match in pattern.finditer(content):
        idx = int(match.group(1))
        start_h, start_m, start_s, start_ms = map(int, match.group(2, 3, 4, 5))
        end_h, end_m, end_s, end_ms = map(int, match.group(6, 7, 8, 9))
        text = match.group(10).strip()

        start_sec = start_h * 3600 + start_m * 60 + start_s + start_ms / 1000
        end_sec = end_h * 3600 + end_m * 60 + end_s + end_ms / 1000

        # 清理字幕标签（<font>, <b>, 等）
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\{[^}]+\}', '', text)
        text = text.strip()

        if text:
            segments.append({
                'index': idx,
                'start': start_sec,
                'end': end_sec,
                'text': text,
            })

    return segments


def parse_vtt(content: str) -> list[dict]:
    """解析 WebVTT 字幕格式。"""
    segments = []
    # 去掉 WEBVTT 头部
    content = re.sub(r'^WEBVTT.*?\n\n', '', content, count=1, flags=re.DOTALL)

    # VTT 时间戳格式
    pattern = re.compile(
        r'(\d{2}:)?(\d{2}):(\d{2})\.(\d{3})\s*-->\s*'
        r'(\d{2}:)?(\d{2}):(\d{2})\.(\d{3})\s*\n'
        r'((?:(?!\n\d+\n).)+)',
        re.MULTILINE | re.DOTALL
    )

    for i, match in enumerate(pattern.finditer(content)):
        start_h = int(match.group(1)[:2]) if match.group(1) else 0
        start_m = int(match.group(2))
        start_s = int(match.group(3))
        start_ms = int(match.group(4))

        end_h = int(match.group(5)[:2]) if match.group(5) else 0
        end_m = int(match.group(6))
        end_s = int(match.group(7))
        end_ms = int(match.group(8))

        text = match.group(9).strip()
        text = re.sub(r'<[^>]+>', '', text)

        start_sec = start_h * 3600 + start_m * 60 + start_s + start_ms / 1000
        end_sec = end_h * 3600 + end_m * 60 + end_s + end_ms / 1000

        if text:
            segments.append({
                'index': i + 1,
                'start': start_sec,
                'end': end_sec,
                'text': text,
            })

    return segments


def extract_from_subtitle(bvid: str) -> dict:
    """从字幕文件提取文本。"""
    # 查找字幕文件
    subtitle_files = list(SUBTITLE_DIR.glob(f'{bvid}*.srt')) + \
                     list(SUBTITLE_DIR.glob(f'{bvid}*.vtt')) + \
                     list(SUBTITLE_DIR.glob(f'{bvid}*.ttml'))

    if not subtitle_files:
        return None

    sub_path = subtitle_files[0]
    logger.info(f"  [{bvid}] 找到字幕: {sub_path.name}")
    try:
        content = sub_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        try:
            content = sub_path.read_text(encoding='gbk')
        except UnicodeDecodeError:
            content = sub_path.read_text(encoding='utf-8', errors='replace')

    if sub_path.suffix == '.srt':
        segments = parse_srt(content)
    elif sub_path.suffix == '.vtt':
        segments = parse_vtt(content)
    else:
        # TTML/其他格式：尝试用已知模式
        segments = parse_srt(content)
        if not segments:
            segments = parse_vtt(content)

    if not segments:
        return None

    full_text = '\n'.join(seg['text'] for seg in segments)
    # 合并相邻短片段（可能是同一句话被拆分）
    merged = merge_short_segments(segments)

    return {
        'bvid': bvid,
        'source': 'subtitle',
        'subtitle_file': sub_path.name,
        'full_text': full_text,
        'segments': merged,
        'segment_count': len(merged),
        'total_chars': sum(len(re.findall(r'[一-鿿]', seg['text'])) for seg in merged),
    }


def merge_short_segments(segments: list[dict], max_gap: float = 1.0,
                         max_chars: int = 10) -> list[dict]:
    """合并相邻的短片段（可能属于同一句话）。

    Args:
        segments: 分段列表
        max_gap: 最大合并间隔（秒）
        max_chars: 短片段判定阈值（字）

    Returns:
        合并后的分段列表
    """
    if not segments:
        return []

    merged = []
    current = dict(segments[0])

    for seg in segments[1:]:
        gap = seg['start'] - current['end']
        current_short = len(current['text']) < max_chars

        if gap <= max_gap and current_short:
            # 合并
            current['text'] += ' ' + seg['text']
            current['end'] = seg['end']
        else:
            merged.append(current)
            current = dict(seg)

    merged.append(current)
    # 重新编号
    for i, m in enumerate(merged):
        m['index'] = i + 1

    return merged


def extract_with_whisper(bvid: str, asr: WhisperASR) -> dict:
    """使用 Whisper ASR 转写音频。"""
    # 查找音频文件
    audio_files = list(AUDIO_DIR.glob(f'{bvid}*'))
    if not audio_files:
        logger.warning(f"  [{bvid}] 无字幕且无音频文件，跳过")
        return None

    audio_path = audio_files[0]
    logger.info(f"  [{bvid}] ASR 转写: {audio_path.name}")

    try:
        result = asr.transcribe(audio_path)
        segments = result['segments']

        # 清理文本
        processor = TextProcessor()
        for seg in segments:
            seg['text'] = processor.normalize(seg['text'])
            seg['index'] = segments.index(seg) + 1

        full_text = '\n'.join(seg['text'] for seg in segments)

        return {
            'bvid': bvid,
            'source': 'whisper_asr',
            'whisper_model': asr.model_size,
            'audio_file': audio_path.name,
            'full_text': full_text,
            'segments': segments,
            'segment_count': len(segments),
            'total_chars': sum(len(re.findall(r'[一-鿿]', seg['text'])) for seg in segments),
            'detected_language': result.get('language', 'zh'),
        }
    except Exception as e:
        logger.error(f"  [{bvid}] ASR 转写失败: {e}")
        return {
            'bvid': bvid,
            'source': 'whisper_asr',
            'error': str(e),
            'segments': [],
        }


def main():
    parser = argparse.ArgumentParser(description='提取文本：字幕优先，ASR兜底')
    parser.add_argument('--plan', type=str, default=str(DATA_DIR / 'metadata' / 'collection_plan.json'),
                        help='collection_plan.json 路径')
    parser.add_argument('--whisper-model', type=str, default='small',
                        help='Whisper 模型大小（默认 small）')
    parser.add_argument('--limit', type=int, default=0,
                        help='限制处理数量（0=全部）')
    parser.add_argument('--force-asr', action='store_true',
                        help='强制使用 ASR 重新转写（忽略已有字幕）')
    args = parser.parse_args()

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    tracker = ProgressTracker(PROGRESS_PATH)
    tracker.start_phase('05_extract_text')

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

    tracker.set_total_items('05_extract_text', len(videos))

    # 初始化 Whisper（仅在需要时加载）
    asr = None
    need_asr_count = 0

    logger.info(f"开始处理 {len(videos)} 个视频的文本提取")

    success_count = 0
    subtitle_count = 0
    asr_count = 0
    skip_count = 0

    for i, video in enumerate(videos):
        bvid = video['bvid']
        if tracker.is_item_completed('05_extract_text', bvid):
            skip_count += 1
            continue

        logger.info(f"[{i + 1}/{len(videos)}] {bvid} - {video.get('title', '')[:50]}")

        if args.force_asr:
            transcript = None
        else:
            transcript = extract_from_subtitle(bvid)

        if transcript:
            subtitle_count += 1
            success_count += 1
        else:
            # 尝试 ASR
            if asr is None:
                model_size = args.whisper_model
                logger.info(f"加载 Whisper 模型: {model_size}")
                asr = WhisperASR(model_size=model_size)

            transcript = extract_with_whisper(bvid, asr)
            if transcript and 'error' not in transcript:
                asr_count += 1
                success_count += 1

        if transcript:
            # 保存 transcript
            out_path = TRANSCRIPT_DIR / f'{bvid}_transcript.json'
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(transcript, f, ensure_ascii=False, indent=2)
            tracker.mark_item_completed('05_extract_text', bvid)

    tracker.complete_phase('05_extract_text')
    tracker.set_phase_data('05_extract_text', 'stats', {
        'total': len(videos),
        'success': success_count,
        'from_subtitle': subtitle_count,
        'from_asr': asr_count,
        'skipped': skip_count,
    })

    logger.info(f"文本提取完成: {success_count}/{len(videos)} 成功")
    logger.info(f"  字幕: {subtitle_count} | ASR: {asr_count} | 跳过: {skip_count}")


if __name__ == '__main__':
    main()
