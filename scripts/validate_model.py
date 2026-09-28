#!/usr/bin/env python3
"""Validate canonical YAML models, sources, and cross-references."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

import yaml


ALLOWED_RELATIONS = {
    "references",
    "related_to",
    "depends_on",
    "produces",
    "uses",
    "contains",
    "is_a",
}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.metrics: dict[str, Any] = {}

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def load_yaml(path: Path, report: Report) -> dict:
    if not path.exists():
        report.error(f"Missing file: {path}")
        return {}
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # PyYAML emits several parser exception types.
        report.error(f"Cannot parse {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        report.error(f"Top level must be a mapping: {path}")
        return {}
    return value


def unique_items(items: Any, key: str, label: str, report: Report) -> tuple[list[dict], set[str]]:
    if not isinstance(items, list):
        report.error(f"{label} must be a list")
        return [], set()
    clean: list[dict] = []
    ids: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            report.error(f"{label}[{index}] must be a mapping")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            report.error(f"{label}[{index}] has no non-empty id")
            continue
        clean.append(item)
        ids.append(item_id)
    duplicates = sorted(item for item, count in Counter(ids).items() if count > 1)
    if duplicates:
        report.error(f"Duplicate {label} ids: {duplicates}")
    return clean, set(ids)


def iter_relation_targets(item: dict, owner: str, report: Report):
    relations = item.get("relations") or {}
    if not isinstance(relations, dict):
        report.error(f"{owner}: relations must be a mapping")
        return
    for relation, targets in relations.items():
        if relation not in ALLOWED_RELATIONS:
            report.warn(f"{owner}: unknown relation type {relation}")
        if not isinstance(targets, list):
            report.error(f"{owner}: relation {relation} must be a list")
            continue
        for target in targets:
            if not isinstance(target, str):
                report.error(f"{owner}: non-string relation target {target!r}")
                continue
            yield relation, target


def resolve_reference(target: str, concept_ids: set[str], entity_ids: set[str]) -> bool:
    if target.startswith("concept://"):
        return target.removeprefix("concept://") in concept_ids
    if target.startswith("entity://"):
        return target.removeprefix("entity://") in entity_ids
    return False


def validate(project: Path) -> Report:
    report = Report()
    scenarios_doc = load_yaml(project / "model/scenarios.yaml", report)
    concepts_doc = load_yaml(project / "model/concepts.yaml", report)
    entities_doc = load_yaml(project / "model/entities.yaml", report)

    scenarios, scenario_ids = unique_items(scenarios_doc.get("scenarios"), "id", "scenarios", report)
    concepts, concept_ids = unique_items(concepts_doc.get("concepts"), "id", "concepts", report)
    entities, entity_ids = unique_items(entities_doc.get("entities"), "id", "entities", report)

    all_sources: set[str] = set()
    relation_counts: Counter[str] = Counter()
    relation_target_counts: list[int] = []
    broken: list[str] = []
    self_refs: list[str] = []
    weak_evidence: list[str] = []
    only_related_entities: list[str] = []
    ipo_steps = 0
    scenario_uses = 0

    def validate_sources(item: dict, label: str) -> None:
        sources = item.get("sources")
        if not isinstance(sources, list) or not sources:
            report.error(f"{label}: missing sources")
            return
        for source in sources:
            if not isinstance(source, str):
                report.error(f"{label}: source must be a string")
                continue
            all_sources.add(source)
            if not (project / source).is_file():
                report.error(f"{label}: source does not exist: {source}")

    for concept in concepts:
        owner = f"concept://{concept['id']}"
        validate_sources(concept, owner)
        ipo = concept.get("ipo") or {}
        decomposition = concept.get("decomposition") or []
        if not ipo and not decomposition:
            report.error(f"{owner}: requires ipo or decomposition")
        if ipo and not isinstance(ipo, dict):
            report.error(f"{owner}: ipo must be a mapping")
        else:
            steps = ((ipo.get("process") or {}).get("steps") or []) if ipo else []
            if steps and not isinstance(steps, list):
                report.error(f"{owner}: ipo.process.steps must be a list")
            ipo_steps += len(steps) if isinstance(steps, list) else 0
            for tool in ((ipo.get("process") or {}).get("tools") or []) if ipo else []:
                if not resolve_reference(tool, concept_ids, entity_ids):
                    broken.append(f"{owner} -> {tool}")
        if decomposition and not isinstance(decomposition, list):
            report.error(f"{owner}: decomposition must be a list")
        elif isinstance(decomposition, list):
            for part in decomposition:
                if isinstance(part, dict) and part.get("uses"):
                    target = part["uses"]
                    if not resolve_reference(target, concept_ids, entity_ids):
                        broken.append(f"{owner} -> {target}")
        if "证据不足" in (concept.get("tags") or []):
            weak_evidence.append(concept["id"])
        count = 0
        for relation, target in iter_relation_targets(concept, owner, report) or []:
            relation_counts[relation] += 1
            count += 1
            if not resolve_reference(target, concept_ids, entity_ids):
                broken.append(f"{owner} -> {target}")
            if target == owner:
                self_refs.append(owner)
        relation_target_counts.append(count)

    for entity in entities:
        owner = f"entity://{entity['id']}"
        validate_sources(entity, owner)
        rel_types: set[str] = set()
        count = 0
        for relation, target in iter_relation_targets(entity, owner, report) or []:
            rel_types.add(relation)
            relation_counts[relation] += 1
            count += 1
            if not resolve_reference(target, concept_ids, entity_ids):
                broken.append(f"{owner} -> {target}")
            if target == owner:
                self_refs.append(owner)
        if count == 0:
            report.error(f"{owner}: requires at least one relation")
        if rel_types == {"related_to"}:
            only_related_entities.append(entity["id"])
        relation_target_counts.append(count)

    for scenario in scenarios:
        owner = f"scenario://{scenario['id']}"
        validate_sources(scenario, owner)
        if not scenario["id"].startswith("如何"):
            report.warn(f"{owner}: id does not start with 如何")
        composition = scenario.get("composition")
        if not isinstance(composition, list) or not composition:
            report.error(f"{owner}: composition must be a non-empty list")
            continue
        for phase_index, phase in enumerate(composition):
            if not isinstance(phase, dict):
                report.error(f"{owner}: phase {phase_index} must be a mapping")
                continue
            uses = phase.get("uses") or []
            if not isinstance(uses, list):
                report.error(f"{owner}: phase {phase_index} uses must be a list")
                continue
            for target in uses:
                scenario_uses += 1
                if not resolve_reference(target, concept_ids, entity_ids):
                    broken.append(f"{owner} -> {target}")

    if broken:
        for item in broken:
            report.error(f"Broken reference: {item}")
    if self_refs:
        report.warn(f"Self references: {sorted(set(self_refs))}")

    accepted_files = {
        path.relative_to(project).as_posix()
        for path in (project / "raw/accepted").rglob("*")
        if path.is_file()
    }
    ignored_source_files = {"raw/accepted/PUT_RAW_FILES_HERE.md"}
    unreferenced = sorted((accepted_files - ignored_source_files) - all_sources)
    if unreferenced:
        report.warn(f"Accepted sources not referenced by model: {unreferenced}")

    over_six = sum(value > 6 for value in relation_target_counts)
    if over_six:
        report.warn(f"Items with more than 6 relation targets: {over_six}")
    if only_related_entities:
        report.warn(
            f"Entities using only related_to: {len(only_related_entities)}; inspect semantics"
        )

    report.metrics = {
        "counts": {
            "scenarios": len(scenarios),
            "concepts": len(concepts),
            "entities": len(entities),
            "accepted_sources": len(accepted_files),
            "referenced_sources": len(all_sources),
        },
        "scenario_uses": scenario_uses,
        "ipo_steps": ipo_steps,
        "relation_targets": sum(relation_counts.values()),
        "relation_types": dict(sorted(relation_counts.items())),
        "relation_targets_median": median(relation_target_counts) if relation_target_counts else 0,
        "weak_evidence_concepts": weak_evidence,
        "entities_only_related_to": len(only_related_entities),
        "broken_references": len(broken),
        "errors": len(report.errors),
        "warnings": len(report.warnings),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", default=".")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    parser.add_argument("--report", help="Write JSON report to this path")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    report = validate(project)
    result = {
        "project": str(project),
        "ok": not report.errors and not (args.strict and report.warnings),
        "metrics": report.metrics,
        "errors": report.errors,
        "warnings": report.warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.report:
        output = Path(args.report)
        if not output.is_absolute():
            output = project / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if report.errors or (args.strict and report.warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
