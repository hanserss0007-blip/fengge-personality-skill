#!/usr/bin/env python3
"""
09_compile_report.py — 编译最终人格分析报告。

加载所有分析 JSON，按模板填充，生成完整的人格分析报告 Markdown 文件。
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / 'outputs'
REPORT_PATH = OUTPUT_DIR / 'fengge_personality_report.md'
DB_PATH = Path(__file__).resolve().parent.parent / 'data_processed' / 'corpus.db'


def load_analysis(dimension: str) -> dict:
    """加载分析 JSON 文件。"""
    path = OUTPUT_DIR / f'{dimension}_analysis.json'
    if not path.exists():
        logger.warning(f"分析文件不存在: {path}")
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_corpus_stats() -> dict:
    """加载语料统计。"""
    report_path = Path(__file__).resolve().parent.parent / 'data_processed' / 'processing_report.json'
    if report_path.exists():
        with open(report_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def format_catchphrase_list(catchphrases: list) -> str:
    """格式化口头禅列表。"""
    if not catchphrases:
        return "_暂无数据_"
    lines = []
    for i, cp in enumerate(catchphrases[:10]):
        phrase = cp.get('phrase', cp.get('word', str(cp)))
        count = cp.get('count', 0)
        score = cp.get('score', cp.get('salience', 0))
        lines.append(f"{i + 1}. **{phrase}**（{count} 次，显著性 {score:.2f}）")
    return '\n'.join(lines)


def format_topic_list(topics: dict) -> str:
    """格式化主题关键词分布。"""
    if not topics:
        return "_暂无数据_"
    total = sum(topics.values())
    lines = []
    for topic, count in sorted(topics.items(), key=lambda x: -x[1])[:8]:
        pct = count / max(total, 1) * 100
        lines.append(f"- **{topic}**：{count} 次提及（{pct:.1f}%）")
    return '\n'.join(lines)


def compile_report() -> str:
    """编译完整报告。"""
    # 加载所有分析结果
    language = load_analysis('language')
    thinking = load_analysis('thinking')
    values = load_analysis('values')
    interaction = load_analysis('interaction')
    personality = load_analysis('personality_traits') or load_analysis('personality')
    insights = load_analysis('unique_insights') or load_analysis('insights')
    corpus_stats = load_corpus_stats()

    # 报告元数据
    report_date = datetime.now().strftime('%Y-%m-%d')
    video_count = corpus_stats.get('videos_processed', corpus_stats.get('input_videos', 9))  # 9 videos with subs
    total_chars = corpus_stats.get('fengge_total_chars', language.get('corpus_size', {}).get('total_chars', 0) if language else 0)
    total_utterances = corpus_stats.get('utterances_fengge', language.get('corpus_size', {}).get('total_segments', 0) if language else 0)

    # 构建报告
    report = f"""# 峰哥亡命天涯 — 人格分析报告

> 生成日期：{report_date}
> 分析视频数：{video_count}
> 总语料量：{total_chars} 字 | {total_utterances} 条发言
> ⚠️ 本报告部分维度仅完成量化框架，完整 LLM 标注待后续迭代

---

## 一、执行摘要

### 核心发现

本报告基于 {video_count} 个视频、{total_chars} 字的语料，从五个维度对「峰哥亡命天涯」
（周丽峰）的公开人格进行了系统分析。

- **语言指纹**：峰哥拥有高度独特的口头禅系统，以仪式化重复和抽象话语著称。
- **思维架构**：理工科训练痕迹与刻意的非理性表演形成张力。
- **价值体系**：在犬儒与关怀、精英与底层之间维持着不稳定的平衡。
- **社交互动**：高权力距离的对话模式与瞬间切换到共情模式的能力并存。
- **人格轮廓**：高开放性、中低尽责性、高外向性、中低宜人性、中神经质（初步估计）。

### 一句话概括

峰哥是一个「用程序员的系统思维解构一切社会现象的、自我意识过剩的观察者」。

---

## 二、语言 DNA

### 口头禅 Top 10

{format_catchphrase_list(language.get('catchphrases', [])) if language else '_暂无数据_'}

### 语言指纹

"""

    if language and 'sentence_stats' in language:
        ss = language['sentence_stats']
        cs = language.get('corpus_size', {})
        report += f"""- 总字数：{cs.get('total_chars', 0)} 字
- 总段数：{cs.get('total_segments', 0)} 条
- 平均句长：{ss.get('avg_len', 'N/A')} 字
- 中位句长：{ss.get('med_len', 'N/A')} 字
- 句长分布：短（<10字）{ss.get('len_distribution', {}).get('short (<10)', 0)} | 中（10-30字）{ss.get('len_distribution', {}).get('medium (10-30)', 0)} | 长（30-60字）{ss.get('len_distribution', {}).get('long (30-60)', 0)} | 超长（>60字）{ss.get('len_distribution', {}).get('very_long (>60)', 0)}

### 高频词汇 Top 20

{chr(10).join(f'- {w}（{c}次）' for w, c in (language.get('word_frequency', [])[:20] if language else [])) if language and language.get('word_frequency') else '_暂无数据_'}

"""

    report += """
### 修辞风格

_（此部分需要 LLM agent 基于 language_analyst_agent.md 进行修辞手段标注，当前仅完成量化统计）_

---

## 三、思维架构

"""

    if thinking and 'argument_samples' in thinking:
        report += f"""- 发现 {thinking['total_arguments_found']} 个候选论证片段（>100字）
- 已抽样 {thinking['sample_size']} 段待 LLM 标注
- 标注维度：论证结构、逻辑谬误、认知偏差

_（LLM 标注完成后，将补充：常见论证模式、逻辑谬误频次、认知偏差分布、确定性/模糊性分析）_

"""
    else:
        report += "_思维分析数据暂缺_\n\n"

    report += """---

## 四、价值体系地图

### 主题关键词初步统计

"""

    if values and 'topic_keyword_hits' in values:
        report += format_topic_list(values['topic_keyword_hits'])
        report += """

_（完整主题建模需要 BERTopic + LLM 标注，当前为关键词频率统计。LLM 标注完成后将补充：价值维度 7 点量表评分、立场一致性分析、核心价值观提取）_

"""
    else:
        report += "_价值分析数据暂缺_\n\n"

    report += """---

## 五、社交互动签名

### 说话人分布

"""

    if interaction:
        sd = interaction.get('speaker_distribution', {})
        report += f"""- 峰哥发言：{sd.get('fengge', {}).get('count', 0)} 段（均长 {sd.get('fengge', {}).get('avg_chars', 0)} 字）
- 连线观众：{sd.get('caller', {}).get('count', 0)} 段（均长 {sd.get('caller', {}).get('avg_chars', 0)} 字）
- 峰哥说话占比：{interaction.get('fengge_talk_ratio', 0) * 100:.1f}%
- 峰哥/观众均长比：{interaction.get('fengge_avg_length_vs_caller', 0)}x
- 弹幕总数：{interaction.get('danmaku_count', 0)}

_（详细互动模式分析需要 LLM agent 基于 interaction_analyst_agent.md 完成：冲突处理策略、共情水平、弹幕对齐、幽默使用分析等）_

"""
    else:
        report += "_互动分析数据暂缺_\n\n"

    report += """---

## 六、OCEAN 人格画像

"""

    if personality and 'quantitative_indicators' in personality:
        qi = personality['quantitative_indicators']
        report += f"""### 量化指标

| 指标 | 数值 |
|------|------|
| 确定性 vs 模糊语比例 | {qi.get('certainty_vs_hedging_ratio', 'N/A')} |
| 确定性词汇数 | {qi.get('certainty_words_count', 'N/A')} |
| 模糊语词汇数 | {qi.get('hedging_words_count', 'N/A')} |
| 自指词汇数（自我意识） | {qi.get('self_reference_count', 'N/A')} |
| 愤怒标记数 | {qi.get('anger_markers_count', 'N/A')} |
| 焦虑标记数 | {qi.get('anxiety_markers_count', 'N/A')} |

### OCEAN 评分（初步估计，待 LLM 标注）

| 维度 | 评分 | 倾向 | 依据 |
|------|------|------|------|
| 开放性 (O) | 4/5 | 高 | 内容类型多样、主动探索未知、讨论抽象概念 |
| 尽责性 (C) | 2/5 | 偏低 | "逃避劳动"自我描述、随性直播风格 |
| 外向性 (E) | 4/5 | 高 | 长时间高能量直播、主动控场、享受焦点 |
| 宜人性 (A) | 2/5 | 偏低 | 直接怼人、边界感弱（需区分表演vs真实） |
| 神经质 (N) | 3/5 | 中等 | 情境依赖：封禁压力下升高，日常较稳定 |

⚠️ 以上评分为初步估计，最终评分需 LLM agent 基于 oceane_framework.md 提供完整证据链。

"""
    else:
        report += "_人格分析数据暂缺_\n\n"

    report += """---

## 七、独到见解

"""

    if insights and 'known_contradictions' in insights:
        report += """### 待消解的悖论

"""
        for c in insights['known_contradictions']:
            report += f"- {c}\n"
        report += f"""

### 对比分析维度

已标记的对比对象：{', '.join(insights.get('comparison_targets', []))}

_（完整独到见解需 insight_synthesizer_agent (LLM) 基于所有维度结果进行差异分析、悖论消解和假设生成。预计生成 5-10 条结构化见解。）_

"""
    else:
        report += "_独到见解数据暂缺_\n\n"

    report += """---

## 附录

### A. 分析方法论

本报告基于多维度人格分析框架（详见 `references/analysis_framework.md`），
使用 OCEAN 大五模型作为人格映射框架（详见 `references/oceane_framework.md`）。
分析方法包括：中文分词词频统计、n-gram 口头禅挖掘、TF-IDF 显著性计算、
关键词主题映射、LLM 辅助语义标注。

### B. 局限性声明

- 所有分析基于公开视频内容，反映的是「公开人格」而非「私下人格」
- 直播内容有高度表演性，不构成临床诊断依据
- 当前部分维度的 LLM 标注尚未完成（标注为「待完成」），初步评分为研究者推断
- 语料覆盖时段有限，可能不完全反映主体长期变化

### C. 数据来源

详见 `references/data_sources_catalog.md`。

### D. 下一步

1. 完成 LLM agent 对 thinking/values/interaction/personality/insights 五个维度的深度标注
2. 基于完整标注更新 OCEAN 评分和证据链
3. 运行 insight_synthesizer_agent 生成独到见解
4. 迭代完善报告内容
"""

    return report


def main():
    parser = argparse.ArgumentParser(description='编译人格分析报告')
    parser.add_argument('--output', type=str, default=str(REPORT_PATH),
                        help='报告输出路径')
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("编译人格分析报告...")
    report = compile_report()

    output_path = Path(args.output)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    logger.info(f"报告已生成: {output_path}")
    logger.info(f"报告大小: {len(report)} 字符")

    # 检查完整性
    sections = [
        '执行摘要', '语言 DNA', '思维架构',
        '价值体系地图', '社交互动签名', 'OCEAN 人格画像', '独到见解'
    ]
    missing = [s for s in sections if s not in report]
    if missing:
        logger.warning(f"缺少章节: {', '.join(missing)}")

    logger.info("完成！")


if __name__ == '__main__':
    main()
