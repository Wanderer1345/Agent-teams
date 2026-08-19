#!/usr/bin/env python3
"""端到端 demo：加载提交单，逐条跑 Team A → Team B 编排，打印链路与终裁。

用法：
    python3 run_demo.py                 # 无 key：走桩，验证编排 wiring
    ANTHROPIC_API_KEY=sk-... python3 run_demo.py   # 接真实 Claude
    python3 run_demo.py --submission path/to.json  # 换提交单
    python3 run_demo.py --write-tm                  # 把 approved 项回流到 data/tm.jsonl
"""
from __future__ import annotations

import argparse
import json

import agents as A
import data as D
from graph import build_graph


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission", default=None, help="提交单 JSON 路径，默认 data/sample_submission.json")
    ap.add_argument("--write-tm", action="store_true", help="把 approved 译文追加回流到 data/tm.jsonl")
    args = ap.parse_args()

    refs = D.load_refs()
    sub = D.load_submission(args.submission)
    app = build_graph()

    print(f"运行模式: {A.llm_label()}  (配 key 走真实模型，否则桩)")
    print(f"批次: {sub.get('batch')}   条目数: {len(sub['items'])}")
    print("=" * 72)

    all_approved = []
    for item in sub["items"]:
        final = app.invoke({"item": item, "refs": refs})
        print(f"\n▶ {item['key']}  「{item['zh']}」  控件={item['control']}  目标={item['target_langs']}")
        for line in final.get("trace", []):
            print("    " + line)

        if final.get("team_a", {}).get("aborted"):
            print("    ⛔ 源文阻断，已回退人工 PM")
            continue

        v = final["verdict"]
        for rv in v["reviews"]:
            mark = "✅" if rv["verdict"] == "pass" else "❌"
            hu = "  🙋人工" if rv["escalate_human"] else ""
            print(f"    {mark} {rv['lang']:<3} route={rv['route']}{hu}")
            for iss in rv["issues"]:
                print(f"         - [{iss.get('dimension')}/{iss.get('severity')}] {iss.get('desc')}")
        esc = final.get("escalate_to_human", [])
        if esc:
            print(f"    🙋 需人工终审语言: {esc}")
        all_approved += [dict(key=item["key"], **a) for a in v["approved_for_tm"]]

    print("\n" + "=" * 72)
    print(f"可回流 TM 的 approved 译文: {len(all_approved)} 条")
    if args.write_tm and all_approved:
        # 时间戳由外部注入，不臆造；这里用当天日期占位（真实系统应传审校时刻）。
        import datetime
        ts = datetime.date.today().isoformat()
        tm_path = D.DATA_DIR / "tm.jsonl"
        with open(tm_path, "a", encoding="utf-8") as f:
            for a in all_approved:
                f.write(json.dumps({**a, "status": "approved",
                                    "approved_by": "verdict-aggregator",
                                    "approved_at": ts, "round": 1}, ensure_ascii=False) + "\n")
        print(f"已追加 {len(all_approved)} 条到 {tm_path}")
    elif all_approved:
        print("(dry-run: 未写库；加 --write-tm 落库到 data/tm.jsonl)")


if __name__ == "__main__":
    main()
