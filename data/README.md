# data/ — 让 Agent Teams 跑起来的示例数据

这些文件是两个团队(Team A / Team B)共享的"活资产"。有了它们,agent 就能真正做术语查询、记忆复用与回流,而不是空转。

## 文件清单

| 文件 | 谁用 | 作用 |
|---|---|---|
| `glossary.csv` | 全部撰写/审校 agent(`glossary-and-tm` skill) | 术语库:专名固定译法;`do_not_translate=true` 的词原样保留 |
| `tm.jsonl` | 撰写(复用)+ 审校(核对)(`glossary-and-tm` skill) | 翻译记忆:已确认的"源文→译文"对,仅 `approved` 可复用 |
| `sample_submission.json` | 输入 | 一份示例 PM 提交单(3 条,覆盖按钮/Toast/营销 Banner) |
| `rejected.jsonl` | `verdict-aggregator`(`feedback-loop` skill) | 打回记录(负样本),含 1 条示例 |
| `metrics.jsonl` | `verdict-aggregator`(`feedback-loop` skill) | 每批审校指标,含 1 条示例 |

## 用这批数据跑一遍(在 Claude Code 中)

前置:把 `../teams/*/agents/*.md` 放进 `.claude/agents/`,`../teams/*/skills/*` 放进 `.claude/skills/`。

**跑撰写团队:**
```
@ux-writer-lead 处理 localization-agents/data/sample_submission.json 中的 items，
术语库见 data/glossary.csv，翻译记忆见 data/tm.jsonl。逐条输出团队级 JSON 契约。
```
预期能观察到:
- 第 1 条「已抢光」→ TM 精确命中,直接复用 `Sold Out/完売/품절/…`(风险最低)。
- 第 2 条「还剩 {count} 件」→ 走 ICU 复数;德语/阿拉伯语触发复数分类,英文 TM 有参考。
- 第 3 条营销 Banner + 含「薯条」「笔记」→ 命中术语库强制用 `Boost`/`Note`;营销类被标 `escalate_to_human`。

**跑审校团队(接上一步产物):**
```
@review-lead 对上面产出的多语言文案做四维走查，术语库/记忆见 data/。
输出逐语言裁定与回退路由，并把 approved 项回流。
```
预期能观察到:
- 若某语言把「薯条」译成 French Fries → `terminology` 维度 fail → `back_to_localizer`(对照 `rejected.jsonl` 里的负样本)。
- 通过项 → 追加进 `tm.jsonl`(仅 approved),指标写入 `metrics.jsonl`。

## 约定
- **时间戳由系统/人注入**,agent 不自行编造(见 `feedback-loop` skill)。
- **术语库变更需人工确认**后才生效;TM 可自动追加,但仅限 `approved`。
- 生产环境应把这几个文件接到你们自研 Starling 的术语/记忆存储,这里的 CSV/JSONL 只是可跑通的最小实现。
