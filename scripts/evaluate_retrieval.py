#!/usr/bin/env python3
"""Compare model-guided retrieval with direct raw paragraph search."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from kb_lib import retrieve_context


def ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def source_hit(context: dict, expected: list[str]) -> bool:
    if not expected:
        return False
    observed = set(context.get("source_files") or [])
    return bool(observed & set(expected))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", default=".")
    parser.add_argument("--questions", default="eval/questions.yaml")
    parser.add_argument("--run-id")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    question_doc = yaml.safe_load((project / args.questions).read_text(encoding="utf-8"))
    questions = question_doc.get("questions") or []
    rows = []
    answer_count = top1 = top3 = model_source = raw_source = 0
    boundary_count = boundary_correct = 0

    for item in questions:
        question = item["question"]
        expected_behavior = item.get("expected_behavior", "answer")
        expected_scenario = item.get("expected_scenario")
        expected_sources = item.get("expected_sources") or []
        model = retrieve_context(project, question, mode="model-guided")
        raw = retrieve_context(project, question, mode="raw")
        candidates = [candidate["id"] for candidate in model.get("candidate_scenarios") or []]
        selected = (model.get("selected_scenario") or {}).get("id")

        row = {
            "id": item["id"],
            "question": question,
            "expected_behavior": expected_behavior,
            "expected_scenario": expected_scenario,
            "model_status": model["status"],
            "model_selected": selected,
            "model_top_score": (model.get("candidate_scenarios") or [{}])[0].get("score", 0),
            "scenario_top1": bool(expected_scenario and selected == expected_scenario),
            "scenario_top3": bool(expected_scenario and expected_scenario in candidates[:3]),
            "model_source_hit": source_hit(model, expected_sources),
            "raw_source_hit": source_hit(raw, expected_sources),
            "model_sources": model.get("source_files") or [],
            "raw_sources": raw.get("source_files") or [],
        }

        if expected_behavior == "answer":
            answer_count += 1
            top1 += row["scenario_top1"]
            top3 += row["scenario_top3"]
            model_source += row["model_source_hit"]
            raw_source += row["raw_source_hit"]
        else:
            boundary_count += 1
            if expected_behavior == "clarify":
                row["boundary_correct"] = model["status"] in {"needs_clarification", "no_evidence"}
            else:
                row["boundary_correct"] = model["status"] == "no_evidence"
            boundary_correct += row["boundary_correct"]
        rows.append(row)

    metrics = {
        "question_count": len(questions),
        "answer_question_count": answer_count,
        "boundary_question_count": boundary_count,
        "scenario_top1_accuracy": ratio(top1, answer_count),
        "scenario_top3_recall": ratio(top3, answer_count),
        "expected_source_hit_rate_model": ratio(model_source, answer_count),
        "expected_source_hit_rate_raw": ratio(raw_source, answer_count),
        "boundary_behavior_accuracy": ratio(boundary_correct, boundary_count),
        "question_set_status": question_doc.get("status"),
    }
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "metrics": metrics,
        "results": rows,
    }
    print(json.dumps(metrics, ensure_ascii=False, indent=2))

    if not args.no_save:
        run_id = args.run_id or datetime.now(timezone.utc).strftime("retrieval-%Y%m%dT%H%M%SZ")
        output = project / "runs/evaluation" / run_id
        output.mkdir(parents=True, exist_ok=True)
        (output / "retrieval-results.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        lines = ["# 检索对照评测", "", "该结果使用待人工确认的种子问题集，不代表最终业务效果。", "", "## 指标", ""]
        for key, value in metrics.items():
            lines.append(f"- `{key}`: {value}")
        lines.extend(["", "## 逐题结果", "", "| ID | 预期 | 模型首选 | Top1 | Top3 | 模型来源 | Raw来源 | 状态 |", "|---|---|---|---:|---:|---:|---:|---|"])
        for row in rows:
            lines.append(
                "| {id} | {expected} | {selected} | {top1} | {top3} | {m_source} | {r_source} | {status} |".format(
                    id=row["id"],
                    expected=row.get("expected_scenario") or row["expected_behavior"],
                    selected=row.get("model_selected") or "—",
                    top1="✓" if row.get("scenario_top1") else "",
                    top3="✓" if row.get("scenario_top3") else "",
                    m_source="✓" if row.get("model_source_hit") else "",
                    r_source="✓" if row.get("raw_source_hit") else "",
                    status=row["model_status"],
                )
            )
        (output / "retrieval-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"saved: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
