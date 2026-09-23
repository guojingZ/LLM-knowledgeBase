# -*- coding: utf-8 -*-
"""合并场景填充结果，并做 uses 引用完整性校验。"""
import io
import os
from collections import Counter

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "model")
TODAY = "2026-09-23"
FIELDS = ["trigger", "goal", "composition", "inputs", "outputs", "tags"]


def load(p):
    with io.open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def q(v):
    s = str(v)
    if any(c in s for c in ":#-{}[]|>&*!%@`\"'"):
        return '"%s"' % s.replace('"', '\\"')
    return s


def main():
    filled = {}
    for i in range(1, 4):
        p = os.path.join(MODEL, f"_round2_scen_part{i}.yaml")
        if os.path.exists(p):
            for s in (load(p).get("scenarios") or []):
                filled[s["id"]] = s
    print(f"收集到场景填充：{len(filled)}")

    doc = load(os.path.join(MODEL, "scenarios.yaml"))
    cids = {c["id"] for c in load(os.path.join(MODEL, "concepts.yaml"))["concepts"]}
    eids = {e["id"] for e in load(os.path.join(MODEL, "entities.yaml"))["entities"]}

    broken = Counter()
    n = 0
    for s in doc["scenarios"]:
        f = filled.get(s["id"])
        if not f:
            continue
        n += 1
        for k in FIELDS:
            if f.get(k) not in (None, {}, [], ""):
                s[k] = f[k]
        for ph in s.get("composition") or []:
            for u in ph.get("uses") or []:
                if u.startswith("concept://") and u[10:] not in cids:
                    broken[(s["id"], u)] += 1
                elif u.startswith("entity://") and u[9:] not in eids:
                    broken[(s["id"], u)] += 1
    doc["updated_at"] = TODAY

    L = ["# ============================================================",
         "# scenarios.yaml — 场景清单",
         "# 第一轮：骨架（id/sources/define）",
         "# 第二轮：填充 trigger / goal / composition / inputs / outputs / tags",
         f"# 生成：_round2_scen_merge.py 合并 _round2_scen_part1..3.yaml（{TODAY}）",
         "# ============================================================", "",
         'version: "2.0"', f'updated_at: "{TODAY}"', "", "scenarios:", ""]
    for s in doc["scenarios"]:
        L.append(f"  - id: {s['id']}")
        L.append("    sources:")
        for x in s.get("sources") or []:
            L.append(f"      - {x}")
        L.append(f"    define: {q(s.get('define',''))}")
        for k in ["trigger", "goal"]:
            L.append(f"    {k}: {q(s.get(k,''))}" if s.get(k) else f'    {k}: ""  # TODO')
        comp = s.get("composition")
        if comp:
            L.append("    composition:")
            for ph in comp:
                L.append(f"      - phase: {q(ph.get('phase',''))}")
                L.append("        uses:")
                for u in ph.get("uses") or []:
                    L.append(f"          - {u}")
                L.append(f"        rule: {q(ph.get('rule',''))}")
                L.append("        key_points:")
                for kp in ph.get("key_points") or []:
                    L.append(f"          - {q(kp)}")
        else:
            L.append("    composition: []  # TODO")
        for k in ["inputs", "outputs"]:
            v = s.get(k) or []
            L.append(f"    {k}:")
            for x in v:
                L.append(f"      - {q(x)}")
        L.append("    tags: [" + ", ".join(q(t) for t in (s.get("tags") or [])) + "]")
        L.append("")
    io.open(os.path.join(MODEL, "scenarios.yaml"), "w", encoding="utf-8").write("\n".join(L) + "\n")

    ph = [len(s.get("composition") or []) for s in doc["scenarios"]]
    print(f"\n场景：{len(doc['scenarios'])} 条，已填充 {n} 条")
    print(f"composition phase 数：{dict(sorted(Counter(ph).items()))}")
    print(f"失效 uses 引用：{sum(broken.values())} 处")
    for k, v in broken.items():
        print(f"  ✗ {k[0]} → {k[1]}")
    empty = [s["id"] for s in doc["scenarios"] if not s.get("trigger") or not s.get("composition")]
    print(f"仍缺 trigger/composition 的场景：{empty or '无'}")


if __name__ == "__main__":
    main()
