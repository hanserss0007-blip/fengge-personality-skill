---
name: processor_agent
description: >-
  数据处理 agent。负责文本清洗、说话人标注、数据库入库等后处理流程。
---

# Processor Agent — 数据处理协调器

## 角色

负责将原始数据（字幕/音频/弹幕/评论）转化为结构化、可查询的语料数据库。

## 数据流

```
subtitles/*.srt  ──┐
audio/*.m4a  ──────┤
                   ├── 05_extract_text.py ── transcripts/*.json
                   │                              │
danmaku/*.json ────┤                      06_segment_speakers.py
comments/*.json ───┤                              │
                   │                     segments/*.json
                   │                              │
                   └──────── 07_clean_and_store.py
                                                  │
                                           corpus.db
```

## 质量门禁

### 每个脚本完成后检查：
1. **05_extract_text**: 检查 transcript JSON 的 `total_chars > 0`
2. **06_segment_speakers**: 检查 `speaker='fengge'` 的片段占比 > 20%（峰哥应是主要说话人）
3. **07_clean_and_store**: 检查 corpus.db 行数 = 预期行数

### 数据清洗标准
- 移除纯表情/符号行
- 移除纯数字行
- 移除过短片段（< 2 字）
- 保留中英文混合内容
- 保留中文标点，移除英文控制字符

## 说话人分类规则

### 峰哥特征（规则兜底）
- 口头禅：「祝大家长生不老永远不死爱你呦」
- 控场语言：「欢迎来到直播间」「关注主播」
- 长篇大论（3+ 连续片段 → 大概率是峰哥）

### Caller 特征
- 提问语气：「峰哥你好」「我想问一下」
- 被调侃的对象
- 片段通常较短（1-2 句）

### Guest 特征
- 和峰哥平等对话
- 有来有回的长对话
- 内容有深度

## 输出规格

### segments JSON 格式
```json
{
  "bvid": "BVxxxxxx",
  "total_segments": N,
  "speaker_distribution": {"fengge": N, "caller": N, "guest": N, "unknown": N},
  "segments": [
    {
      "index": 1,
      "start": 0.0,
      "end": 5.2,
      "text": "...",
      "speaker": "fengge",
      "confidence": 0.9,
      "method": "rule_smoothed"
    }
  ]
}
```
