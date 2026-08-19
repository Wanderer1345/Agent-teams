---
name: issue-taxonomy
description: 审校问题的分类体系与回退路由规则。verdict-aggregator 用它把每个问题归类,并决定应回退给 UX Writer 团队还是对应语言的 localizer。对应原流程"中英文问题 / 多语言问题"两条回退线。
---

# 问题分类与回退路由 Skill

对应原流程图中母语 tester 的两条回退线:**中英文问题 → 回源头**,**多语言问题 → 回对应语言**。目的是让每个缺陷都被精确路由,不在团队间空转。

## 一、问题根因分类
| 类别 | 根因位置 | 典型问题 | 回退路径 |
|---|---|---|---|
| `source_zh` | 中文源文 | 原文歧义/表达有误/缺 context | `back_to_uxwriter`(source-copy-reviewer) |
| `source_en` | 英文文案 | 英文本身不地道/语义偏差(作为 SoT 会污染所有语言) | `back_to_uxwriter`(en-copywriter) |
| `target_lang` | 某语言译文 | 该语言翻译错/不地道/语气错 | `back_to_localizer`(对应语言) |
| `terminology` | 术语层 | 未用术语库译法/品牌词误译 | `back_to_localizer` +(必要时)`需登记术语` |
| `constraint` | 约束层 | 超长/占位符丢失/复数错 | `back_to_localizer` |
| `cultural` | 文化合规 | 敏感/禁忌/违规 | `escalate_human`(通常 blocker) |

## 二、路由判定顺序(自上而下)
1. 若问题在**英文 SoT**(`source_en`)或**中文源文**(`source_zh`)→ `back_to_uxwriter`。
   > 关键:源头问题会污染全部语言,必须优先修源头,而不是逐语言打补丁。
2. 否则若是**单一目标语言**的翻译/术语/约束问题 → `back_to_localizer`(标明是哪个语言)。
3. 任何 `cultural blocker` 或 `needs_human` → `escalate_human`,人工介入后再定路由。
4. 无问题 → `approved`。

## 三、一条问题多归因时
- 同时存在源头问题与译文问题 → **先修源头**(标 `back_to_uxwriter`),源头修好后重跑,再看译文层是否仍有独立问题。
- 避免"改了译文但源头还错",导致其他语言反复返工。

## 四、度量(供看板)
每条问题记录:`category`、`route`、`severity`、`round`(第几轮返工)。用于统计:
- **返工率**、**首轮通过率**、各类别占比(定位系统性短板,如某语言 localizer 或某类术语)。
