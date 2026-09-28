# -*- coding: utf-8 -*-
"""生成第二轮场景填充任务：按 sources 数量均衡分 3 组。"""
import io
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "model")

GROUPS = {
    1: ["如何构建个人思维框架与认知体系", "如何构建个人知识体系",
        "如何高效学习一个全新领域", "如何通过复盘实现能力进化闭环",
        "如何突破认知障碍实现认知升级"],
    2: ["如何分析和解决复杂问题", "如何培养架构思维与大架构观",
        "如何平衡知识广度与深度构建核心竞争力", "如何透过现象看事物本质".replace("看事物", "看透事物"),
        "如何制作一份完整的解决方案", "如何用模式匹配解决未知问题"],
    3: ["如何培养系统思维能力", "如何将隐性经验显性化并结构化输出",
        "如何从系统思维进阶到第一性原理", "如何定义融入个人经验的AI提示语与技能",
        "如何实现思维逻辑自洽", "如何进行结构化决策"],
}


def main():
    sc = yaml.safe_load(io.open(os.path.join(MODEL, "scenarios.yaml"), encoding="utf-8"))["scenarios"]
    con = yaml.safe_load(io.open(os.path.join(MODEL, "concepts.yaml"), encoding="utf-8"))["concepts"]
    ent = yaml.safe_load(io.open(os.path.join(MODEL, "entities.yaml"), encoding="utf-8"))["entities"]
    by_id = {s["id"]: s for s in sc}
    cid = "、".join(c["id"] for c in con)
    eid = "、".join(e["id"] for e in ent)

    for g, ids in GROUPS.items():
        L = [f"# 第二轮场景填充 · 第 {g} 组", "",
             "## 你要填的场景（含原文依据）", ""]
        for i in ids:
            s = by_id[i]
            L.append(f"### {s['id']}")
            L.append("sources:")
            for x in s["sources"]:
                L.append(f"- {x}")
            L.append(f"现有define: {s['define']}")
            L.append("")
        L += ["## 可引用的全量概念 id（composition 的 concept:// 只能取这里的）", "", cid, "",
              "## 可引用的全量实体 id（entity:// 只能取这里的）", "", eid, ""]
        io.open(os.path.join(MODEL, f"_round2_scen_task{g}.md"), "w",
                encoding="utf-8").write("\n".join(L))
        print(f"  _round2_scen_task{g}.md: {len(ids)} 个场景")


if __name__ == "__main__":
    main()
