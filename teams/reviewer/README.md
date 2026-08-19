# Team B · 审校团队

对应原流程 ⑦ :**海外母语 tester 走查 / 验证**。
与 Team A **完全独立**(职责分离),被要求"默认挑错",对多语言产物做把关,并把结论回流成资产。

## 团队编制

| Agent | 职责(单一) | 权限(tools) | 依赖 Skill |
|---|---|---|---|
| `review-lead` | 编排:分派各维度审校、并行 fan-out、汇总裁定 | Read, Task | issue-taxonomy |
| `native-linguistic-reviewer` | 母语语言质量:语法/地道/语气/敬语 | Read | review-rubric |
| `terminology-consistency-checker` | 术语一致性:是否遵守术语库/TM | Read | review-rubric |
| `cultural-compliance-checker` | 文化/宗教/政治/法务/敏感词 | Read | review-rubric |
| `visual-context-checker` | UI 走查:截断、占位符、在真实截图/控件中的合适度 | Read | review-rubric |
| `verdict-aggregator` | 汇总多维裁定 → 分类问题 → 决定回退路径 + 回流 | Read, Write | issue-taxonomy, feedback-loop |

## 编排流程

```
review-lead 对每条译文并行分派:
   native-linguistic-reviewer
   terminology-consistency-checker
   cultural-compliance-checker
   visual-context-checker
        └─ 各自返回 {pass|fail + 问题清单}
verdict-aggregator 汇总:
   - 任一维度 fail → 整条 fail
   - 按 issue-taxonomy 给每个问题打分类标签
   - 决定回退路径:
       · 中英文问题(源文/英文本身)  → 回退 Team A(en-copywriter / source-reviewer)
       · 多语言问题(某语言译文)      → 回退 Team A 的 multilingual-localizer(对应语言)
   - 通过项 → 写入 TM/术语库(feedback-loop skill)
```

## 团队级输出契约

```json
{
  "key": "sku.button.sold_out",
  "reviews": [
    {"lang":"ja","verdict":"pass|fail","dimensions":{
        "linguistic":{"pass":true,"issues":[]},
        "terminology":{"pass":true,"issues":[]},
        "cultural":{"pass":true,"issues":[]},
        "visual":{"pass":false,"issues":["按钮内文本被截断"]}},
     "route":"back_to_localizer|back_to_uxwriter|approved",
     "severity":"blocker|major|minor"}
  ],
  "approved_for_tm": [{"lang":"ko","translation":"품절"}]
}
```

## 设计要点(对抗式验证)
- 审校 agent 被明确要求 **默认怀疑、主动挑错**,不得为 Team A 的产物背书。
- **多维并行**:语言/术语/文化/视觉四个维度各自独立判断,避免单点漏检。
- **问题分类驱动回退**:严格区分"中英文问题"与"多语言问题",分别走不同回退路径(与原流程图一致)。
- **闭环**:approved 结论回流 TM/术语库,系统越用越准。
