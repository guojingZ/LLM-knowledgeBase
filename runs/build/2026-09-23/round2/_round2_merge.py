# -*- coding: utf-8 -*-
"""第二轮合并：把 _round2_partN.yaml 的填充内容并入 concepts.yaml / entities.yaml，
并做引用完整性全量校验。骨架字段（id/type/category/sources）以骨架为准。"""
import io
import os
import re
from collections import Counter

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "model")
TODAY = "2026-09-23"

FILL_FIELDS = ["define", "ipo", "decomposition", "relations", "children", "tags"]


def load_yaml(p):
    with io.open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_parts():
    filled_c, filled_e = {}, {}
    for i in range(1, 9):
        p = os.path.join(MODEL, f"_round2_part{i}.yaml")
        if not os.path.exists(p):
            print(f"  [缺失] {os.path.basename(p)}")
            continue
        d = load_yaml(p)
        for c in d.get("concepts") or []:
            filled_c[c["id"]] = c
        for e in d.get("entities") or []:
            filled_e[e["id"]] = e
    return filled_c, filled_e


def main():
    fc, fe = collect_parts()
    print(f"收集到填充：概念 {len(fc)} / 实体 {len(fe)}")

    sk_c = load_yaml(os.path.join(MODEL, "concepts.yaml"))
    sk_e = load_yaml(os.path.join(MODEL, "entities.yaml"))

    orphan_c = set(fc) - {c["id"] for c in sk_c["concepts"]}
    orphan_e = set(fe) - {e["id"] for e in sk_e["entities"]}
    if orphan_c:
        print("  [警告] 填充了骨架中不存在的概念:", orphan_c)
    if orphan_e:
        print("  [警告] 填充了骨架中不存在的实体:", orphan_e)

    n_c = n_e = 0
    for c in sk_c["concepts"]:
        f = fc.get(c["id"])
        if not f:
            continue
        n_c += 1
        for k in FILL_FIELDS:
            if f.get(k) not in (None, {}, [], ""):
                c[k] = f[k]
    for e in sk_e["entities"]:
        f = fe.get(e["id"])
        if not f:
            continue
        n_e += 1
        for k in FILL_FIELDS:
            if f.get(k) not in (None, {}, [], ""):
                e[k] = f[k]

    sk_c["updated_at"] = TODAY
    sk_e["updated_at"] = TODAY

    # ---------- 引用完整性校验 ----------
    cids = {c["id"] for c in sk_c["concepts"]}
    eids = {e["id"] for e in sk_e["entities"]}
    broken = Counter()
    ref_count = 0

    def check(rels, owner):
        nonlocal ref_count
        for rtype, targets in (rels or {}).items():
            for t in targets or []:
                ref_count += 1
                if t.startswith("concept://") and t[10:] not in cids:
                    broken[("概念", owner, t)] += 1
                elif t.startswith("entity://") and t[9:] not in eids:
                    broken[("实体", owner, t)] += 1
                elif t.startswith("scenario://"):
                    broken[("非法场景引用", owner, t)] += 1

    for c in sk_c["concepts"]:
        check(c.get("relations"), c["id"])
        for d in c.get("decomposition") or []:
            u = d.get("uses")
            if u:
                ref_count += 1
                if not u.startswith("concept://") or u[10:] not in cids:
                    broken[("分解引用", c["id"], u)] += 1
        for t in ((c.get("ipo") or {}).get("process") or {}).get("tools") or []:
            ref_count += 1
            if not t.startswith("entity://") or t[9:] not in eids:
                broken[("工具引用", c["id"], t)] += 1
    for e in sk_e["entities"]:
        check(e.get("relations"), e["id"])

    # ---------- 质量统计 ----------
    no_ipo = [c["id"] for c in sk_c["concepts"] if not (c.get("ipo") or c.get("decomposition"))]
    no_rel = [e["id"] for e in sk_e["entities"] if not e.get("relations")]
    weak = [c["id"] for c in sk_c["concepts"] if "证据不足" in (c.get("tags") or [])]
    shallow = [c["id"] for c in sk_c["concepts"]
               if c.get("ipo") and len(((c["ipo"].get("process") or {}).get("steps") or [])) < 3]
    steps_hist = Counter()
    for c in sk_c["concepts"]:
        ipo = c.get("ipo") or {}
        steps_hist[len((ipo.get("process") or {}).get("steps") or [])] += 1

    # ---------- 写回 ----------
    def dump(path, doc, key, header):
        L = list(header)
        for e in doc[key]:
            L.append(f"  - id: {e['id']}")
            L.append("    sources:")
            for s in e.get("sources") or []:
                L.append(f"      - {s}")
            L.append(f"    define: {e.get('define','')}")
            if key == "concepts":
                L.append(f"    type: {e['type']}")
            else:
                L.append(f"    category: {e['category']}")
                L.append(f"    type: {e['type']}")
            if key == "concepts":
                L.extend(block(e.get("ipo"), "    ipo:"))
                L.extend(block(e.get("decomposition"), "    decomposition:"))
            L.extend(block(e.get("relations"), "    relations:"))
            if key == "entities":
                L.extend(block(e.get("children"), "    children:"))
            L.append("    tags: [" + "、".join(e.get("tags") or []) + "]" if False
                     else "    tags: [" + ", ".join(f'"{t}"' if any(ch in t for ch in ":#-") else t
                                                    for t in (e.get("tags") or [])) + "]")
            L.append("")
        with io.open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(L) + "\n")

    def block(v, head):
        """用 yaml.dump 生成缩进正确的块；空则不输出"""
        if v in (None, {}, []):
            return []
        s = yaml.dump(v, allow_unicode=True, default_flow_style=False, sort_keys=False)
        lines = s.rstrip("\n").split("\n")
        # head 在 4 空格（条目字段层级），子元素必须在 6 空格，否则会被解析成平级键
        return [head] + ["      " + l for l in lines]

    dump(os.path.join(MODEL, "concepts.yaml"), sk_c, "concepts", [
        "# ============================================================",
        "# concepts.yaml — 概念清单（唯一概念文件）",
        "# 第一轮：骨架（id/sources/define/type）",
        "# 第二轮：填充 ipo / decomposition / relations / tags",
        f"# 生成：_round2_merge.py 合并 _round2_part1..8.yaml（{TODAY}）",
        "# ============================================================",
        "",
        'version: "2.0"',
        f'updated_at: "{TODAY}"',
        "",
        "concepts:",
        "",
    ])
    dump(os.path.join(MODEL, "entities.yaml"), sk_e, "entities", [
        "# ============================================================",
        "# entities.yaml — 实体清单（唯一实体文件）",
        "# 第一轮：骨架（id/sources/category/type/define）",
        "# 第二轮：填充 relations / children / tags",
        f"# 生成：_round2_merge.py 合并 _round2_part1..8.yaml（{TODAY}）",
        "# ============================================================",
        "",
        'version: "2.0"',
        f'updated_at: "{TODAY}"',
        "",
        "entities:",
        "",
    ])

    print("\n========== 第二轮填充报告 ==========")
    print(f"概念：{len(sk_c['concepts'])} 条，已填充 {n_c} 条（{100*n_c//len(sk_c['concepts'])}%）")
    print(f"实体：{len(sk_e['entities'])} 条，已填充 {n_e} 条（{100*n_e//len(sk_e['entities'])}%）")
    print(f"\n引用总数 {ref_count}，失效引用 {sum(broken.values())} 处")
    for k, v in list(broken.items())[:20]:
        print(f"  ✗ {k[0]} | 来源 {k[1]} → {k[2]}")
    print(f"\nIPO 步骤数分布：{dict(sorted(steps_hist.items()))}")
    print(f"无 ipo/decomposition 的概念（{len(no_ipo)}）：{no_ipo[:15]}{' …' if len(no_ipo)>15 else ''}")
    print(f"无 relations 的实体（{len(no_rel)}）：{no_rel[:10]}")
    print(f"证据不足标记（{len(weak)}）：{weak}")
    print(f"IPO 步骤少于 3 步（{len(shallow)}）：{shallow[:15]}{' …' if len(shallow)>15 else ''}")


if __name__ == "__main__":
    main()
