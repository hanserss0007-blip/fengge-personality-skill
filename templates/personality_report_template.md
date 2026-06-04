# 峰哥亡命天涯 — 人格分析报告

> 生成日期：{{report_date}}
> 分析视频数：{{video_count}}
> 总语料量：{{total_chars}} 字 | {{total_utterances}} 条发言

---

## 一、执行摘要

### 一句话概括
{{one_line_summary}}

### 核心发现
{{#each core_findings}}
- **{{title}}**：{{summary}}
{{/each}}

### 人格速写
| OCEAN维度 | 评分 | 一句话 |
|-----------|------|--------|
| 开放性 (O) | {{o_score}}/5 | {{o_one_liner}} |
| 尽责性 (C) | {{c_score}}/5 | {{c_one_liner}} |
| 外向性 (E) | {{e_score}}/5 | {{e_one_liner}} |
| 宜人性 (A) | {{a_score}}/5 | {{a_one_liner}} |
| 神经质 (N) | {{n_score}}/5 | {{n_one_liner}} |

---

## 二、语言 DNA

### 口头禅 Top 10
{{#each catchphrases_top10}}
{{@index_plus_1}}. **{{phrase}}**（出现 {{count}} 次，TF-IDF 显著性 {{salience}}）
{{/each}}

### 语言指纹
- 平均句长：{{avg_sentence_len}} 字
- 中位句长：{{med_sentence_len}} 字
- 句式分布：陈述 {{pct_declarative}}% | 疑问 {{pct_interrogative}}% | 感叹 {{pct_exclamatory}}% | 祈使 {{pct_imperative}}%
- 粗话/语气词频率：每千字 {{profanity_per_k}} 次
- 程度副词偏好：{{adverb_preference}}

### 修辞风格
{{rhetoric_summary}}

---

## 三、思维架构

### 论证模式
{{argumentation_summary}}

### 逻辑特征
- **论证密度**：每分钟 {{arg_density}} 个独立主张
- **证据引用频率**：每10个主张 {{evidence_rate}} 次引用证据
- **常见逻辑谬误**：
{{#each common_fallacies}}
  - {{type}}：{{count}} 次（{{pct}}%）
{{/each}}

### 认知倾向
{{cognitive_bias_summary}}

### 确定性与模糊性
- 确定性语言比例：{{certainty_pct}}%
- 模糊性语言比例：{{hedging_pct}}%
- 解读：{{certainty_interpretation}}

---

## 四、价值体系地图

### 核心主题分布
{{#each topic_clusters}}
- **{{label}}**（占比 {{pct}}%）：{{description}}
{{/each}}

### 价值维度评分

| 维度 | 倾向 | 强度 | 证据 |
|------|------|------|------|
| 权威 vs 自由 | {{auth_liberty}} | {{auth_liberty_strength}}/5 | {{auth_liberty_evidence}} |
| 传统 vs 进步 | {{trad_prog}} | {{trad_prog_strength}}/5 | {{trad_prog_evidence}} |
| 个人 vs 集体 | {{indiv_collect}} | {{indiv_collect_strength}}/5 | {{indiv_collect_evidence}} |
| 犬儒 vs 理想 | {{cynic_ideal}} | {{cynic_ideal_strength}}/5 | {{cynic_ideal_evidence}} |
| 物质 vs 精神 | {{material_spiritual}} | {{material_spiritual_strength}}/5 | {{material_spiritual_evidence}} |

### 立场一致性
- 跨时间一致性：{{temporal_consistency}}/5
- 跨语境一致性：{{context_consistency}}/5
- 解读：{{consistency_interpretation}}

---

## 五、社交互动签名

### 互动模式矩阵

| 场景 | 风格 | 权力姿态 | 共情水平 | 典型行为 |
|------|------|---------|---------|---------|
| 连麦-普通观众 | {{style_viewer}} | {{power_viewer}} | {{empathy_viewer}} | {{typical_viewer}} |
| 连麦-熟人嘉宾 | {{style_guest}} | {{power_guest}} | {{empathy_guest}} | {{typical_guest}} |
| 弹幕互动 | {{style_danmaku}} | {{power_danmaku}} | {{empathy_danmaku}} | {{typical_danmaku}} |
| 独白输出 | {{style_monologue}} | {{power_monologue}} | {{empathy_monologue}} | {{typical_monologue}} |

### 冲突处理模式
{{conflict_handling_summary}}

### 幽默使用分析
- 自嘲 vs 嘲讽他人比例：{{self_deprecation_ratio}}
- 幽默功能：{{humor_function}}

---

## 六、OCEAN 人格画像

### 开放性 (Openness)：{{o_score}}/5
**证据链**：
{{#each o_evidence}}
- [{{video_id}} @ {{timestamp}}] {{observation}} → {{inference}}
{{/each}}
**解读**：{{o_interpretation}}

### 尽责性 (Conscientiousness)：{{c_score}}/5
**证据链**：
{{#each c_evidence}}
- [{{video_id}} @ {{timestamp}}] {{observation}} → {{inference}}
{{/each}}
**解读**：{{c_interpretation}}

### 外向性 (Extraversion)：{{e_score}}/5
**证据链**：
{{#each e_evidence}}
- [{{video_id}} @ {{timestamp}}] {{observation}} → {{inference}}
{{/each}}
**解读**：{{e_interpretation}}

### 宜人性 (Agreeableness)：{{a_score}}/5
**证据链**：
{{#each a_evidence}}
- [{{video_id}} @ {{timestamp}}] {{observation}} → {{inference}}
{{/each}}
**解读**：{{a_interpretation}}

### 神经质 (Neuroticism)：{{n_score}}/5
**证据链**：
{{#each n_evidence}}
- [{{video_id}} @ {{timestamp}}] {{observation}} → {{inference}}
{{/each}}
**解读**：{{n_interpretation}}

---

## 七、独到见解

{{#each unique_insights}}
### 见解 {{@index_plus_1}}：{{title}}
**类别**：{{category}} | **置信度**：{{confidence}}/5 | **新颖度**：{{novelty}}/5

**发现**：{{finding}}

**证据**：
{{#each evidence}}
- [{{video_id}} @ {{timestamp}}] {{description}}
{{/each}}

**解读**：{{interpretation}}

**为什么这不显而易见**：{{why_non_obvious}}

---
{{/each}}

## 附录

### A. 分析方法论说明
本报告基于 {{video_count}} 个视频、{{total_chars}} 字语料的五维度分析。分析使用 OCEAN 大五模型作为人格框架，结合词频统计、主题建模、LLM 语义标注等方法。详见 `references/analysis_framework.md`。

### B. 局限性声明
- 所有分析基于公开视频内容，反映的是「公开人格」而非「私下人格」
- 直播内容有高度表演性，不构成临床诊断依据
- 部分评分依赖 LLM 主观判断，置信度已标注
- 语料覆盖时段有限，可能不完全反映主体长期变化

### C. 数据来源
详见 `references/data_sources_catalog.md`。
