# -*- coding: utf-8 -*-
"""第一轮候选清单统计：合并 progress + batch2..8，统计数量、跨批次重复、高频 id。
只读，不修改任何候选内容。"""
import re
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "model")

FILES = [os.path.join(MODEL, "_round1_progress.md")]
for i in range(2, 9):
    FILES.append(os.path.join(MODEL, f"_round1_batch{i}.md"))

SECTION_MAP = {
    "候选场景": "scenarios",
    "候选概念": "concepts",
    "候选实体": "entities",
    "存疑项": "doubt",
}


def parse(path):
    """返回 {layer: [(id, sources_tuple)]}"""
    if not os.path.exists(path):
        return {}, []
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    out = defaultdict(list)
    current = None
    header_seen = False
    for line in lines:
        s = line.strip()
        for cn, en in SECTION_MAP.items():
            if s.startswith("###") and cn in s:
                current = en
                header_seen = False
                break
            if s.startswith("##") and cn in s:
                current = en
                header_seen = False
                break
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        if set("".join(cells)) <= set("-: "):
            header_seen = True
            continue
        if not header_seen:
            continue
        if cells[0] in ("id", "候选名"):
            continue
        if current is None:
            continue
        cid = cells[0].strip("` ")
        sources = tuple(cells[-1].split("/")) if cells[-1] else ()
        out[current].append((cid, sources))
    return out, lines


def main():
    all_rows = defaultdict(list)          # layer -> [(id, src, file)]
    src_of = defaultdict(set)             # (layer, id) -> {sources}
    files_of = defaultdict(list)          # (layer, id) -> [file]
    defined = {}                          # (layer, id) -> define

    for path in FILES:
        rows, _ = parse(path)
        fname = os.path.basename(path)
        for layer, items in rows.items():
            for cid, src in items:
                all_rows[layer].append((cid, fname))
                key = (layer, cid)
                for s in src:
                    src_of[key].add(s)
                if fname not in files_of[key]:
                    files_of[key].append(fname)

    print("=" * 62)
    print("第一轮扫描 · 候选汇总")
    print("=" * 62)
    for layer, label in [("scenarios", "场景"), ("concepts", "概念"), ("entities", "实体"), ("doubt", "存疑项")]:
        items = all_rows[layer]
        ids = [i for i, _ in items]
        uniq = sorted(set(ids))
        print(f"{label:<5} 候选条目 {len(items):>4}  →  去重后 {len(uniq):>4}  （冗余率 {100*(1-len(uniq)/max(len(items),1)):.0f}%）")
    print("-" * 62)

    # 跨批次重复最多的 id
    for layer, label in [("concepts", "概念"), ("scenarios", "场景"), ("entities", "实体")]:
        dup = {k: v for k, v in files_of.items() if k[0] == layer and len(v) > 1}
        dup = sorted(dup.items(), key=lambda kv: -len(kv[1]))[:15]
        print(f"\n【{label}】被 2 个以上批次重复提出的 id（前 15）")
        if not dup:
            print("  （无）")
        for (_, cid), fs in dup:
            print(f"  {cid:<18} ×{len(fs)}  {' '.join(f.replace('_round1_','').replace('.md','') for f in fs)}")

    # 只被 1 篇 source 支撑的概念（后续去重重点）
    solo = [(k, v) for k, v in src_of.items() if k[0] == "concepts" and len(v) <= 1]
    print(f"\n概念中仅 1 个来源支撑的：{len(solo)} 个（占比 {100*len(solo)/max(1,len(set(i for i,_ in all_rows['concepts']))):.0f}%）→ 第二轮填充时证据最薄")

    # 疑似近义簇（按包含关系粗判）
    print("\n【粗判】可能近义的概念簇（共享 2 字以上核心词）")
    ids = sorted(set(i for i, _ in all_rows["concepts"]))
    clusters = defaultdict(list)
    for cid in ids:
        for kw in ["思维", "认知", "知识", "结构化", "系统", "问题", "学习", "抽象", "归纳", "演绎", "复盘", "闭环", "模式"]:
            if kw in cid:
                clusters[kw].append(cid)
                break
    for kw, members in clusters.items():
        if len(members) >= 5:
            print(f"  [{kw}] {len(members)} 个：{'、'.join(members[:14])}{' …' if len(members) > 14 else ''}")


if __name__ == "__main__":
    main()
