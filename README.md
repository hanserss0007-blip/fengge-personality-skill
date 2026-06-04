# 峰哥亡命天涯 人格分析 Skill

对网红「峰哥亡命天涯」（周丽峰）进行多维度人格深度分析的 Claude Code Skill。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 采集数据（只下载文本，不下载视频）
python scripts/01_discover_videos.py
python scripts/02_filter_videos.py --target 150
python scripts/03_download_metadata.py
python scripts/04_download_media.py --no-video
python scripts/05_extract_text.py --whisper-model small
python scripts/06_segment_speakers.py
python scripts/07_clean_and_store.py

# 3. 运行分析
python scripts/08_run_analysis.py

# 4. 生成报告
python scripts/09_compile_report.py
```

或直接在 Claude Code 中使用 `/fengge` 命令。

## 目录结构

```
fengge-personality-skill/
├── SKILL.md           # Skill 入口定义
├── agents/            # 10 个分析 Agent
├── references/        # 参考文档
├── scripts/           # Python 数据管道
├── templates/         # 输出模板
├── data_raw/          # 原始数据（运行时）
├── data_processed/    # 处理后数据（运行时）
└── outputs/           # 分析输出（运行时）
```

## 依赖

- Python 3.9+
- bilibili-api-python, yt-dlp, openai-whisper, jieba, sentence-transformers
- ffmpeg（Whisper 需要）
