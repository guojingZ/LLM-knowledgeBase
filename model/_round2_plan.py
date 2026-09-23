# -*- coding: utf-8 -*-
"""第二轮任务分派：按「主源文章所属批次」把待填条目分给 8 组。

产出 model/_round2_taskN.md（N=2..8），N=1 由主 agent 自己做示范。
"""
import io
import os
import re
from collections import defaultdict, Counter

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "model")


def load(path, key):
    with io.open(path, encoding="utf-8") as f:
        d = yaml.safe_load(f)
    return d[key]


def article_batches():
    """从 round1 批次文件还原 文章 -> 批次号"""
    m = {}
    m.update({p: 1 for p in parse_files(os.path.join(MODEL, "_round1_progress.md"))})
    for i in range(2, 9):
        m.update({p: i for p in parse_files(os.path.join(MODEL, f"_round1_batch{i}.md"))})
    return m


def parse_files(path):
    out = []
    if not os.path.exists(path):
        return out
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s.startswith("- raw/") or re.match(r"^raw/.*\.md$", s):
                out.append(s.lstrip("- ").strip())
    return out


def main():
    concepts = load(os.path.join(MODEL, "concepts.yaml"), "concepts")
    entities = load(os.path.join(MODEL, "entities.yaml"), "entities")
    ab = article_batches()

    con_ids = [c["id"] for c in concepts]
    ent_ids = [e["id"] for e in entities]

    def assign(sources):
        c = Counter(ab.get(s, 0) for s in sources if ab.get(s))
        if not c:
            return 0
        return max(c.items(), key=lambda kv: (kv[1], -kv[0]))[0]

    bins_c = defaultdict(list)
    bins_e = defaultdict(list)
    for c in concepts:
        bins_c[assign(c.get("sources") or [])].append(c)
    for e in entities:
        bins_e[assign(e.get("sources") or [])].append(e)

    print("分派结果：")
    for i in sorted(set(list(bins_c) + list(bins_e))):
        who = "主agent示范" if i == 1 else f"task{i}"
        print(f"  批次{i} ({who}): 概念 {len(bins_c.get(i,[]))} / 实体 {len(bins_e.get(i,[]))}")

    idblock_c = "、".join(con_ids)
    idblock_e = "、".join(ent_ids)

    for i in range(2, 9):
        arts = sorted([a for a, b in ab.items() if b == i])
        L = [f"# 第二轮任务 {i}", "",
             "## 本组负责的文章（必须逐篇读完，这是你的原文依据）", ""]
        L += [f"- {a}" for a in arts]
        L += ["", "## 待填概念", "",
              "| id | type | 现有define | sources |", "|---|---|---|---|"]
        for c in sorted(bins_c.get(i, []), key=lambda x: x["id"]):
            src = "；".join(c.get("sources") or [])
            L.append(f"| {c['id']} | {c.get('type','')} | {c.get('define','')} | {src} |")
        L += ["", "## 待填实体", "",
              "| id | category | type | 现有define | sources |", "|---|---|---|---|---|"]
        for e in sorted(bins_e.get(i, []), key=lambda x: x["id"]):
            src = "；".join(e.get("sources") or [])
            L.append(f"| {e['id']} | {e.get('category','')} | {e.get('type','')} | {e.get('define','')} | {src} |")
        L += ["", "## 可引用的全量概念 id（relations 中的 concept:// 只能取这里的）", "",
              idblock_c, "",
              "## 可引用的全量实体 id（relations 中的 entity:// 只能取这里的）", "",
              idblock_e, ""]
        with io.open(os.path.join(MODEL, f"_round2_task{i}.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(L))

    # 主 agent 示范批次
    arts = sorted([a for a, b in ab.items() if b == 1])
    L = ["# 第二轮任务 1（主 agent 示范）", "", "## 文章"] + [f"- {a}" for a in arts]
    L += ["", "## 待填概念", "", "| id | type | 现有define |", "|---|---|---|"]
    for c in sorted(bins_c.get(1, []), key=lambda x: x["id"]):
        L.append(f"| {c['id']} | {c.get('type','')} | {c.get('define','')} |")
    L += ["", "## 待填实体", "", "| id | category | type | 现有define |", "|---|---|---|---|"]
    for e in sorted(bins_e.get(1, []), key=lambda x: x["id"]):
        L.append(f"| {e['id']} | {e.get('category','')} | {e.get('type','')} | {e.get('define','')} |")
    with io.open(os.path.join(MODEL, "_round2_task1.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    print("\n已写出 model/_round2_task1.md ~ _round2_task8.md")


if __name__ == "__main__":
    main()
