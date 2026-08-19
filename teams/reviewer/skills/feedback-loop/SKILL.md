---
name: feedback-loop
description: 审校通过结论的回流规范:把 approved 译文写入翻译记忆(TM),把新确认术语写入术语库,让系统越用越准。verdict-aggregator 回流时使用。
---

# 审校回流(Feedback Loop)Skill

这是两个团队"越用越准"的引擎,也是自研相对外包的核心长期价值:**人的审校结论不能一次性用完,要沉淀成可复用资产。**

## 一、回流对象(只回流 approved)
1. **翻译记忆(TM)** `data/tm.jsonl`:审校通过的"源文→译文"对。
2. **术语库(Glossary)** `data/glossary.csv`:新确认的专名固定译法。
3. **负样本(可选)** `data/rejected.jsonl`:被打回的译文 + 原因,用于后续做质量分析/few-shot 反例。

## 二、TM 写入格式(追加,不覆盖)
```json
{"key":"sku.button.sold_out","zh":"已抢光","lang":"ja","translation":"完売",
 "status":"approved","approved_by":"native-linguistic-reviewer",
 "approved_at":"<由外部注入,勿臆造>","round":1}
```
规则:
- 只写 `verdict:pass` 的条目;`fail` 不写入 TM(可写入 rejected)。
- 同 `key+lang` 已存在 → 更新为最新 approved 版本,保留历史(不静默丢弃)。
- **时间戳由调用方/系统注入**,agent 不要自行编造日期。

## 三、术语库更新
- 审校中出现 `需登记术语`(新品牌词/功能名)→ 生成一条待登记建议:`{term_zh, 各语言译法, 来源, 状态:pending}`。
- 术语库变更**需人工确认后**才生效(术语影响全局,不自动写入生产术语库)。

## 四、度量回流(供看板)
每轮审校汇总写入 `data/metrics.jsonl`:
```json
{"key":"...","first_pass_rate":0.8,"rework_rounds":1,
 "issues_by_category":{"target_lang":2,"terminology":1},"escalated_human":1}
```
用于跟踪:首轮通过率↑、返工率↓、人工介入率↓、各语言/各类问题分布。

## 五、原则
- 回流是**单向增益**:只固化确认过的正确结论,绝不把未通过内容混入 TM/生产术语库。
- 术语库变更走人工确认,TM 可自动追加(但仅 approved)。
