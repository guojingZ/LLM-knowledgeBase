# -*- coding: utf-8 -*-
"""第一步：把 progress + batch2..8 的候选汇总到临时文件。

产出两个文件：
  model/_round1_candidates.json   —— 机器可读全量候选（含全部 sources / define 变体）
  model/_round1_all_candidates.md —— 人读的紧凑清单（按语义词簇分组，便于聚类去重）
只做「id 完全相同」的机械合并，语义去重交给 _round1_dedup_map.md。
"""
import json
import os
import re
from collections import defaultdict, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "model")

FILES = [os.path.join(MODEL, "_round1_progress.md")]
for i in range(2, 9):
    FILES.append(os.path.join(MODEL, f"_round1_batch{i}.md"))

SECTIONS = {
    "候选场景": "scenarios",
    "候选概念": "concepts",
    "候选实体": "entities",
}

# 用于把近义候选排到一起，方便人工聚类
KEYWORDS = [
    "思维", "认知", "知识", "结构化", "系统", "问题", "学习", "抽象",
    "归纳", "演绎", "复盘", "闭环", "模式", "逻辑", "本质", "实践",
    "决策", "分析", "分解", "集成", "架构", "模型", "经验", "方法",
]


def cluster_of(cid):
    for kw in KEYWORDS:
        if kw in cid:
            return kw
    return "其他"


def parse_file(path):
    """返回 {layer: [row]}，row 为 dict"""
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    out = defaultdict(list)
    cur, header_seen = None, False
    for line in lines:
        s = line.strip()
        m = re.match(r"^#{2,3}\s*(.+)", s)
        if m:
            title = m.group(1)
            cur = None
            header_seen = False
            for cn, en in SECTIONS.items():
                if title.startswith(cn):
                    cur = en
                    break
            continue
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        if set("".join(cells)) <= set("-: "):
            header_seen = True
            continue
        if not header_seen or cells[0] in ("id", "候选名"):
            continue
        if cur is None:
            continue

        src_raw = cells[-1]
        sources = [x.strip() for x in src_raw.split(" / ") if x.strip().startswith("raw/")]

        if cur == "scenarios":
            out[cur].append({"id": cells[0], "define": cells[1], "sources": sources})
        elif cur == "concepts":
            out[cur].append({"id": cells[0], "type": cells[1], "define": cells[2], "sources": sources})
        else:
            out[cur].append({"id": cells[0], "category": cells[1], "type": cells[2],
                             "define": cells[3], "sources": sources})
    return out


def main():
    merged = {k: OrderedDict() for k in ("scenarios", "concepts", "entities")}
    for path in FILES:
        if not os.path.exists(path):
            continue
        fname = os.path.basename(path).replace("_round1_", "").replace(".md", "")
        for layer, rows in parse_file(path).items():
            for r in rows:
                cid = r["id"]
                if cid not in merged[layer]:
                    merged[layer][cid] = {
                        "id": cid,
                        "defines": [],
                        "types": [],
                        "categories": [],
                        "sources": [],
                        "batches": [],
                    }
                e = merged[layer][cid]
                if r["define"] not in e["defines"]:
                    e["defines"].append(r["define"])
                if layer in ("concepts", "entities") and r["type"] not in e["types"]:
                    e["types"].append(r["type"])
                if layer == "entities" and r["category"] not in e["categories"]:
                    e["categories"].append(r["category"])
                for s in r["sources"]:
                    if s not in e["sources"]:
                        e["sources"].append(s)
                if fname not in e["batches"]:
                    e["batches"].append(fname)

    with open(os.path.join(MODEL, "_round1_candidates.json"), "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=1)

    # ---- 人读清单 ----
    L = []
    L.append("# 第一轮候选 · 全量汇总（临时文件）\n")
    L.append("> 由 `_round1_merge.py` 从 8 个批次机械合并生成（id 完全相同者已合并）。")
    L.append("> ★ = 被 3 个以上批次独立提出；⚠ = 同一 id 在不同批次有不同 define（措辞漂移，需统一）。")
    L.append("> 语义去重见 `_round1_dedup_map.md`。\n")

    for layer, label in (("scenarios", "场景"), ("concepts", "概念"), ("entities", "实体")):
        items = list(merged[layer].values())
        L.append(f"\n## {label}汇总：{len(items)} 条\n")
        if layer == "concepts":
            buckets = defaultdict(list)
            for e in items:
                buckets[cluster_of(e["id"])].append(e)
            ordered = []
            for kw in KEYWORDS + ["其他"]:
                ordered.extend(sorted(buckets.get(kw, []), key=lambda x: (-len(x["batches"]), x["id"])))
        elif layer == "entities":
            ordered = sorted(items, key=lambda x: (x["categories"][0] if x["categories"] else "", -len(x["batches"]), x["id"]))
        else:
            ordered = sorted(items, key=lambda x: (-len(x["batches"]), x["id"]))

        for e in ordered:
            star = "★" if len(e["batches"]) >= 3 else " "
            warn = " ⚠" if len(e["defines"]) > 1 else ""
            b = ",".join(x.replace("progress", "b1").replace("batch", "b") for x in e["batches"])
            if layer == "concepts":
                L.append(f"| {star} `{e['id']}` | {'/'.join(e['types'])} | {e['defines'][0]} | {b} | {len(e['sources'])} |{warn}")
            elif layer == "entities":
                L.append(f"| {star} `{e['id']}` | {'/'.join(e['categories'])} | {'/'.join(e['types'])} | {e['defines'][0]} | {b} | {len(e['sources'])} |{warn}")
            else:
                L.append(f"| {star} `{e['id']}` | {e['defines'][0]} | {b} | {len(e['sources'])} |{warn}")

    with open(os.path.join(MODEL, "_round1_all_candidates.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    print("汇总完成：")
    for layer, label in (("scenarios", "场景"), ("concepts", "概念"), ("entities", "实体")):
        n = len(merged[layer])
        hot = sum(1 for e in merged[layer].values() if len(e["batches"]) >= 3)
        print(f"  {label}: {n} 条（其中 ★ 高频 {hot} 条）")
    print("  → model/_round1_candidates.json")
    print("  → model/_round1_all_candidates.md")


if __name__ == "__main__":
    main()
