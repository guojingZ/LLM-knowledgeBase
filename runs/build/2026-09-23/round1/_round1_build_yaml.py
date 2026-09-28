# -*- coding: utf-8 -*-
"""第三步：按 _round1_dedup_map.md 的决策，从 _round1_candidates.json 生成三个骨架 YAML。

输出：
  model/scenarios.yaml  —— id + sources + define（其余 TODO）
  model/concepts.yaml   —— id + sources + define + type
  model/entities.yaml   —— id + sources + category + type + define
"""
import json
import os
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "model")
TODAY = "2026-09-23"

# 合并后新造的 id，candidates 里没有，需给定 define
NEW_DEFINES = {
    "归纳": "由多个具体事例提炼出共性规律的推理方法",
    "演绎": "由普遍规律的大前提推导特殊情境结论的推理方法",
    "SOA": "面向服务的架构思想，其分层与复用是架构核心思考模式",
    "认知水平差异": "高认知与低认知在感知、抽象、结构、时空等维度上的系统性差异",
}
# 由被删场景降级而来的新概念，需补 sources
NEW_SOURCES = {
    "认知水平差异": ["raw/信息爆炸时代认知高和认知低的六大核心差异体现.md"],
}
# 跨层 category/type 冲突裁决（见 dedup_map 第 3 节）
TYPE_OVERRIDE = {
    "CMMI": ("技术与标准", "标准"),
    "PMBOK": ("技术与标准", "标准"),
    "思维导图": ("框架与模型", "模型-框架"),
    "知识图谱": ("框架与模型", "模型-框架"),
}


def q(v):
    """YAML 标量：含特殊字符才加引号"""
    s = str(v)
    if any(c in s for c in ":#-{}[]|>&*!%@`\"'"):
        return '"%s"' % s.replace('"', '\\"')
    return s


def split_ids(cell):
    """拆分"并入的候选id"单元格，跳过括号说明"""
    cell = cell.replace("（单篇，无合并）", "").replace("（新增，吸收被删场景“如何辨别认知水平高低的差异”）", "")
    cell = cell.replace("（新增", "（")
    import re
    cell = re.sub(r"（[^）]*）", "", cell)
    return [x.strip() for x in cell.split("、") if x.strip()]


def parse_dedup(path):
    """返回 (merge_rules, drop_list)，merge_rules = {layer: [(target, members, type, category)]}"""
    merge = {"scenarios": [], "concepts": [], "entities": []}
    drop = {"scenarios": [], "concepts": [], "entities": []}
    mode = None
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    header_seen = False
    for line in lines:
        s = line.strip()
        if s.startswith("#"):
            title = s.lstrip("#").strip()
            header_seen = False
            if "场景去重规则" in title:
                mode = ("merge", "scenarios")
            elif "场景删除名单" in title:
                mode = ("drop", "scenarios")
            elif "概念去重规则" in title:
                mode = ("merge", "concepts")
            elif "单条并入" in title:
                mode = ("merge2", "concepts")
            elif "概念删除名单" in title:
                mode = ("drop", "concepts")
            elif "实体去重规则" in title:
                mode = ("merge", "entities")
            elif "实体删除名单" in title:
                mode = ("drop", "entities")
            elif "冲突裁决" in title or "预期规模" in title:
                mode = None
            continue
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        if set("".join(cells)) <= set("-: "):
            header_seen = True
            continue
        if not header_seen or cells[0] in ("id", "标准id"):
            continue
        if mode is None:
            continue
        kind, layer = mode
        if kind == "drop":
            drop[layer].append(cells[0])
        elif layer == "concepts" and len(cells) >= 4:
            merge[layer].append((cells[0], split_ids(cells[1]), cells[2], None))
        elif layer == "concepts":
            merge[layer].append((cells[0], split_ids(cells[1]), None, None))
        elif layer == "entities" and len(cells) >= 5:
            merge[layer].append((cells[0], split_ids(cells[1]), cells[3], cells[2]))
        else:
            merge[layer].append((cells[0], split_ids(cells[1]), None, None))
    return merge, drop


def apply_dedup(cands, merge_rules, drop_list, layer):
    out = OrderedDict()
    for cid, e in cands.items():
        out[cid] = dict(e)

    for target, members, typ, cat in merge_rules:
        keys = [target] + [m for m in members if m in out]
        if not keys:
            continue
        if target not in out:
            out[target] = {"id": target, "defines": [], "types": [], "categories": [],
                           "sources": [], "batches": []}
        e = out[target]
        for k in keys:
            if k == target:
                continue
            src = out.get(k)
            if not src:
                continue
            for d in src["defines"]:
                if d not in e["defines"]:
                    e["defines"].append(d)
            for t in src["types"]:
                if t not in e["types"]:
                    e["types"].append(t)
            for c in src["categories"]:
                if c not in e["categories"]:
                    e["categories"].append(c)
            for s_ in src["sources"]:
                if s_ not in e["sources"]:
                    e["sources"].append(s_)
            for b in src["batches"]:
                if b not in e["batches"]:
                    e["batches"].append(b)
            del out[k]
        if not e["defines"]:
            e["defines"].append(NEW_DEFINES.get(target, ""))
        for s_ in NEW_SOURCES.get(target, []):
            if s_ not in e["sources"]:
                e["sources"].append(s_)
        if typ:
            e["types"] = [typ] + [t for t in e["types"] if t != typ]
        if cat:
            e["categories"] = [cat] + [c for c in e["categories"] if c != cat]
        if target in TYPE_OVERRIDE:
            e["categories"] = [TYPE_OVERRIDE[target][0]]
            e["types"] = [TYPE_OVERRIDE[target][1]]

    for cid in drop_list:
        out.pop(cid, None)
    return out


def emit(path, header_lines, entries, fields_fn):
    L = list(header_lines)
    for e in sorted(entries.values(), key=lambda x: x["id"]):
        L.append("  - id: %s" % q(e["id"]))
        L.append("    sources:")
        if e["sources"]:
            for s_ in sorted(e["sources"]):
                L.append("      - %s" % q(s_))
        else:
            L.append("      []  # TODO: 待第二轮填充")
        L.extend(fields_fn(e))
        L.append("")
    L.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main():
    with open(os.path.join(MODEL, "_round1_candidates.json"), encoding="utf-8") as f:
        cands = json.load(f)
    merge, drop = parse_dedup(os.path.join(MODEL, "_round1_dedup_map.md"))

    before = {k: len(cands[k]) for k in ("scenarios", "concepts", "entities")}
    final = {}
    for layer in ("scenarios", "concepts", "entities"):
        final[layer] = apply_dedup(cands[layer], merge[layer], drop[layer], layer)

    # ---- scenarios.yaml ----
    def sc_fields(e):
        return [
            "    define: %s" % q(e["defines"][0] if e["defines"] else ""),
            '    trigger: ""  # TODO: 待第二轮填充',
            '    goal: ""  # TODO: 待第二轮填充',
            "    composition: []  # TODO: 待第二轮填充",
            "    tags: []  # TODO: 待第二轮填充",
        ]

    emit(os.path.join(MODEL, "scenarios.yaml"), [
        "# ============================================================",
        "# scenarios.yaml — 场景清单（第一轮骨架）",
        "# 生成：_round1_build_yaml.py 依据 _round1_dedup_map.md",
        "# 去重：%d → %d" % (before["scenarios"], len(final["scenarios"])),
        "# ============================================================",
        "",
        'version: "2.0"',
        'updated_at: "%s"' % TODAY,
        "",
        "scenarios:",
        "",
    ], final["scenarios"], sc_fields)

    # ---- concepts.yaml ----
    def cp_fields(e):
        return [
            "    define: %s" % q(e["defines"][0] if e["defines"] else ""),
            "    type: %s" % q(e["types"][0] if e["types"] else "通用框架"),
            "    ipo: {}  # TODO: 待第二轮填充",
            "    decomposition: []  # TODO: 待第二轮填充",
            "    relations: {}  # TODO: 待第二轮填充",
            "    tags: []  # TODO: 待第二轮填充",
        ]

    emit(os.path.join(MODEL, "concepts.yaml"), [
        "# ============================================================",
        "# concepts.yaml — 概念清单（唯一概念文件，第一轮骨架）",
        "# 生成：_round1_build_yaml.py 依据 _round1_dedup_map.md",
        "# 去重：%d → %d" % (before["concepts"], len(final["concepts"])),
        "# ============================================================",
        "",
        'version: "2.0"',
        'updated_at: "%s"' % TODAY,
        "",
        "concepts:",
        "",
    ], final["concepts"], cp_fields)

    # ---- entities.yaml ----
    def en_fields(e):
        return [
            "    category: %s" % q(e["categories"][0] if e["categories"] else "知识资产"),
            "    type: %s" % q(e["types"][0] if e["types"] else "概念实体"),
            "    define: %s" % q(e["defines"][0] if e["defines"] else ""),
            "    relations: {}  # TODO: 待第二轮填充",
            "    children: []  # TODO: 待第二轮填充",
            "    tags: []  # TODO: 待第二轮填充",
        ]

    emit(os.path.join(MODEL, "entities.yaml"), [
        "# ============================================================",
        "# entities.yaml — 实体清单（唯一实体文件，第一轮骨架）",
        "# 生成：_round1_build_yaml.py 依据 _round1_dedup_map.md",
        "# 去重：%d → %d" % (before["entities"], len(final["entities"])),
        "# ============================================================",
        "",
        'version: "2.0"',
        'updated_at: "%s"' % TODAY,
        "",
        "entities:",
        "",
    ], final["entities"], en_fields)

    print("骨架生成完成：")
    for layer, label in (("scenarios", "scenarios.yaml"), ("concepts", "concepts.yaml"), ("entities", "entities.yaml")):
        print(f"  {label}: {before[layer]} → {len(final[layer])}")

    # 引用完整性自检
    cids = set(final["concepts"].keys())
    eids = set(final["entities"].keys())
    print("\n自检：概念 %d 条 / 实体 %d 条 / 场景 %d 条" % (len(cids), len(eids), len(final["scenarios"])))
    print("  concept:// 与 entity:// 引用待第二轮填充后校验")


if __name__ == "__main__":
    main()
