# langgraph_impl · 本地化 Agent 编排（LangGraph 实现）

把 `localization-agents/` 的两个 Agent Team 设计,落成一个可运行的 LangGraph 编排:
**Team A(UX Writer)→ Team B(审校)** 端到端。无 API key 时走「桩」验证 wiring,配了 key 就接真实 Claude。

## 快速开始

> ⚠️ 需要 **Python 3.10+**(langgraph 1.0 要求)。本目录已内置 `.venv`(Python 3.12)。
> 系统自带的 `python3` 是 3.9,**不能**直接用。

```bash
cd localization-agents/langgraph_impl

# 无 key:走桩,验证编排 wiring
./.venv/bin/python run_demo.py

# 接真实 Claude
export ANTHROPIC_API_KEY=sk-...
./.venv/bin/python run_demo.py

# 换提交单 / 回流 approved 到 TM
./.venv/bin/python run_demo.py --submission ../data/sample_submission.json
./.venv/bin/python run_demo.py --write-tm
```

若要重建环境:

```bash
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## 图结构

```
START → source_review ─[阻断?]─┬─ abort → END
                               └─ en_copy → localize → team_b_review → verdict → END
```

- **Team A** `source_review`(审中文)→ `en_copy`(写英文 SoT)→ `localize`(逐语言 localizer + 约束校验)
- **Team B** `team_b_review`(逐语言四维走查)→ `verdict`(终裁 + 路由 + 回流候选)
- 源文阻断性问题 → `abort`,回退人工 PM(对应 ux-writer-lead 的中止逻辑)

## LLM vs 程序化护栏(重要设计取舍)

对应 PRODUCT-PLAN §5 R4「程序化护栏用代码校验,不信 LLM 自评」:

| 角色 | 实现 | 说明 |
|---|---|---|
| source-copy-reviewer / en-copywriter / multilingual-localizer | **LLM 或桩** | 创译/判断类,有 key 走 Claude |
| native-linguistic / cultural / visual reviewer | **LLM 或桩** | 主观审校,有 key 走 Claude |
| **constraint-validator**(长度/占位符/RTL) | **始终代码** | 客观可判定,见 `data.py` |
| **terminology-checker**(do_not_translate/TM 冲突) | **始终代码** | 确定性一致性校验 |
| **verdict-aggregator**(终裁/路由/回流) | **始终代码** | 规则化终裁 |

桩模式下,创译类 agent 用**数据驱动**产出:优先命中 `data/tm.jsonl`(approved TM),其次 `data/glossary.csv`(术语库固定译法),再退化为英文 SoT 占位(标 `需确认` 交人工)。

## 文件

| 文件 | 职责 |
|---|---|
| `data.py` | 加载 glossary/TM/提交单;程序化护栏(约束校验/术语校验/终裁) |
| `agents.py` | LLM 客户端 + 各 agent 的 system prompt 加载 + 桩响应 |
| `graph.py` | LangGraph `StateGraph` 节点与边 |
| `run_demo.py` | 入口:逐条跑图,打印链路 trace + 终裁 |
| `requirements.txt` | langgraph / langchain-core / langchain-anthropic |

## 配置

- `ANTHROPIC_API_KEY`:设置后自动切真实 Claude,否则桩。
- `ANTHROPIC_MODEL`:默认 `claude-sonnet-5`;按你的 key 可访问的模型调整。

## 与最终形态的差距(本实现有意从简,对应 P0 原型)

- fan-out 为顺序循环;生产可换 LangGraph `Send` 或 async 真并行。
- 回退路径(back_to_uxwriter/back_to_localizer)只标注不自动重入;生产接反馈循环。
- 结构化输出靠 JSON 提取;生产应上 JSON Schema 强校验 + 重试(R3)。
- `--write-tm` 的时间戳用当天日期占位;生产应注入真实审校时刻(勿臆造)。
