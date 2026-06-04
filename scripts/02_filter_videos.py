#!/usr/bin/env python3
"""
02_filter_videos.py — 分层抽样选择代表性视频。

从 video_catalog.json 中按内容类型、时间段、热度分层，
选出 100-200 个代表性视频作为分析语料。
"""

import argparse
import json
import logging
import random
import re
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / 'data_raw' / 'metadata'
OUTPUT_PATH = DATA_DIR / 'collection_plan.json'
CATALOG_PATH = DATA_DIR / 'video_catalog.json'

# 内容类型分类规则（关键词匹配）
CATEGORY_RULES = {
    '解答世间万物': ['解答世间万物', '世间万物', '回答问题', '连线', '连麦'],
    '底层纪实': ['三和', '底层', '流浪', '烂尾', '穷', '打工', '日结', '农民工'],
    '冒险旅行': ['俄罗斯', '乌克兰', '缅甸', '泰国', '乞力马扎罗', '旅行', '探险', '亡命'],
    '抽象直播': ['性压抑', '车轱辘', '炒CP', '女主播', '抽象', '荒诞'],
    '争议/时事': ['封禁', '被拒', '争议', '孤烟', '爱国'],
    '日常闲聊': ['吃面', '补时长', '日常', '闲聊', '唠嗑'],
    '带货/商业': ['带货', '外套', '好货', '推荐', '广告'],
    '其他': [],
}


def classify_video(title: str) -> str:
    """根据标题关键词对视频进行内容分类。"""
    title_lower = title.lower()
    for category, keywords in CATEGORY_RULES.items():
        if category == '其他':
            continue
        for kw in keywords:
            if kw.lower() in title_lower:
                return category
    return '其他'


def parse_upload_date(date_str: str) -> datetime:
    """解析上传日期字符串（兼容多种格式）。"""
    date_str = str(date_str)
    # Unix timestamp
    if date_str.isdigit():
        try:
            ts = int(date_str)
            return datetime.fromtimestamp(ts)
        except (ValueError, OSError):
            pass

    # ISO format
    for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y%m%d', '%Y/%m/%d']:
        try:
            return datetime.strptime(date_str[:10], fmt if len(fmt) <= 10 else fmt)
        except ValueError:
            continue

    return datetime(2000, 1, 1)


def parse_duration(duration_str: str) -> int:
    """解析时长字符串为秒数。"""
    if not duration_str:
        return 0
    duration_str = str(duration_str)
    # 格式: "HH:MM:SS" 或 "MM:SS"
    parts = duration_str.split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    # 纯数字秒数
    try:
        return int(duration_str)
    except ValueError:
        return 0


def stratified_sample(videos: list[dict], target_count: int,
                      seed: int = 42) -> list[dict]:
    """分层抽样：按类别比例分配名额，每层内按热度排序后均匀选取。

    Args:
        videos: 视频列表
        target_count: 目标总数
        seed: 随机种子

    Returns:
        选中的视频列表
    """
    random.seed(seed)
    random.shuffle(videos)

    # 按类别分组
    by_category = defaultdict(list)
    for v in videos:
        cat = v.get('category', '其他')
        by_category[cat].append(v)

    # 计算每类配额（按该类别视频数占总体的比例）
    total = len(videos)
    selected = []
    remaining_quota = target_count

    # 先按比例分配（至少每类1个，如果有视频的话）
    category_quotas = {}
    for cat, cat_videos in sorted(by_category.items(), key=lambda x: -len(x[1])):
        proportion = len(cat_videos) / total
        quota = max(1, min(len(cat_videos), round(target_count * proportion)))
        category_quotas[cat] = quota

    # 调整使总和接近 target_count
    total_quota = sum(category_quotas.values())
    while total_quota > target_count:
        # 从配额最多的类别减少
        max_cat = max(category_quotas, key=category_quotas.get)
        if category_quotas[max_cat] > 1:
            category_quotas[max_cat] -= 1
            total_quota -= 1
        else:
            break

    # 每类内部：按热度排序后均匀取样
    for cat, quota in category_quotas.items():
        cat_videos = by_category[cat]
        # 按播放量排序
        cat_videos.sort(key=lambda v: v.get('play_count', 0) or 0, reverse=True)

        if len(cat_videos) <= quota:
            selected.extend(cat_videos)
        else:
            # 均匀取样（热度头部 + 长尾均匀分布）
            step = len(cat_videos) / quota
            for i in range(quota):
                idx = min(int(i * step), len(cat_videos) - 1)
                # 去重
                v = cat_videos[idx]
                if v not in selected:
                    selected.append(v)

    logger.info(f"分层抽样完成: {len(selected)} 个视频")
    for cat, quota in sorted(category_quotas.items()):
        actual = len([v for v in selected if v.get('category') == cat])
        logger.info(f"  {cat}: 配额 {quota}, 实际 {actual}")

    return selected


def main():
    parser = argparse.ArgumentParser(description='筛选代表性视频')
    parser.add_argument('--catalog', type=str, default=str(CATALOG_PATH),
                        help='video_catalog.json 路径')
    parser.add_argument('--target', type=int, default=150,
                        help='目标视频数（默认150）')
    parser.add_argument('--min-duration', type=int, default=60,
                        help='最小时长（秒，默认60）')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    parser.add_argument('--output', type=str, default=str(OUTPUT_PATH),
                        help='输出路径')
    args = parser.parse_args()

    # 加载视频目录
    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        logger.error(f"视频目录不存在: {catalog_path}，请先运行 01_discover_videos.py")
        sys.exit(1)

    with open(catalog_path, 'r', encoding='utf-8') as f:
        catalog = json.load(f)

    videos = catalog.get('videos', [])
    logger.info(f"加载 {len(videos)} 个视频")

    # 分类
    for v in videos:
        v['category'] = classify_video(v.get('title', ''))
        v['duration_sec'] = parse_duration(v.get('duration_str', '0'))

    # 过滤：过短的视频、无标题的视频
    filtered = [
        v for v in videos
        if v.get('title') and v['duration_sec'] >= args.min_duration
    ]
    logger.info(f"过滤后 {len(filtered)} 个视频（剔除时长<{args.min_duration}s）")

    # 分类统计
    by_cat = defaultdict(int)
    for v in filtered:
        by_cat[v['category']] += 1
    logger.info("分类分布:")
    for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
        logger.info(f"  {cat}: {count}")

    # 分层抽样
    target = min(args.target, len(filtered))
    selected = stratified_sample(filtered, target, args.seed)

    # 输出
    output = {
        'total_selected': len(selected),
        'target': target,
        'generated_at': datetime.now().isoformat(),
        'filters': {
            'min_duration_sec': args.min_duration,
            'seed': args.seed,
        },
        'category_distribution': {cat: sum(1 for v in selected if v['category'] == cat)
                                   for cat in sorted(by_cat.keys())},
        'videos': selected,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"筛选完成: {len(selected)} 个视频 → {output_path}")


if __name__ == '__main__':
    main()
