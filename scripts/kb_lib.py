#!/usr/bin/env python3
"""Shared deterministic retrieval functions for the local knowledge project."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import yaml

from kb_evidence import source_index, read_bindings, resolve_bindings


STOP_TOKENS = {
    "如何",
    "怎样",
    "什么",
    "一个",
    "这个",
    "应该",
    "可以",
    "进行",
    "需要",
    "时候",
    "用户",
    "能够",
    "以及",
    "通过",
}
READY_THRESHOLD = 0.16
AMBIGUITY_GAP = 0.025


def load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def normalize(text: str) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", (text or "").lower())


def tokens(text: str) -> set[str]:
    """Return dependency-free Chinese character n-grams and ASCII words."""
    raw = (text or "").lower()
    result = set(re.findall(r"[a-z0-9][a-z0-9_\-]{1,}", raw))
    for sequence in re.findall(r"[\u4e00-\u9fff]+", raw):
        for size in (2, 3):
            result.update(sequence[i : i + size] for i in range(len(sequence) - size + 1))
    return {item for item in result if item not in STOP_TOKENS}


def weighted_overlap(query_tokens: set[str], document_tokens: set[str], idf: dict[str, float] | None = None) -> float:
    if not query_tokens:
        return 0.0
    weights = idf or {}
    denominator = sum(weights.get(token, 1.0) for token in query_tokens)
    if not denominator:
        return 0.0
    numerator = sum(weights.get(token, 1.0) for token in query_tokens & document_tokens)
    return numerator / denominator


def build_idf(documents: Iterable[set[str]]) -> dict[str, float]:
    documents = list(documents)
    count = len(documents)
    frequency: Counter[str] = Counter()
    for document in documents:
        frequency.update(document)
    return {
        token: math.log((count + 1) / (document_frequency + 1)) + 1
        for token, document_frequency in frequency.items()
    }


def flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(flatten_text(item) for item in value)
    return str(value)


def load_models(project: Path) -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    scenarios = load_yaml(project / "model/scenarios.yaml").get("scenarios") or []
    concepts = load_yaml(project / "model/concepts.yaml").get("concepts") or []
    entities = load_yaml(project / "model/entities.yaml").get("entities") or []
    return (
        scenarios,
        {item["id"]: item for item in concepts},
        {item["id"]: item for item in entities},
    )


def item_for_ref(reference: str, concepts: dict[str, dict], entities: dict[str, dict]) -> dict | None:
    if reference.startswith("concept://"):
        return concepts.get(reference.removeprefix("concept://"))
    if reference.startswith("entity://"):
        return entities.get(reference.removeprefix("entity://"))
    return None


def scenario_uses(scenario: dict) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for phase in scenario.get("composition") or []:
        for reference in phase.get("uses") or []:
            if reference not in seen:
                result.append(reference)
                seen.add(reference)
    return result


def scenario_search_text(scenario: dict, concepts: dict[str, dict], entities: dict[str, dict]) -> str:
    direct = " ".join(
        flatten_text(scenario.get(key))
        for key in ("id", "define", "trigger", "goal", "tags", "composition")
    )
    knowledge = []
    for reference in scenario_uses(scenario):
        item = item_for_ref(reference, concepts, entities)
        if item:
            knowledge.append(" ".join([item.get("id", ""), item.get("define", ""), flatten_text(item.get("tags"))]))
    return direct + " " + " ".join(knowledge)


def rank_scenarios(
    question: str,
    scenarios: list[dict],
    concepts: dict[str, dict],
    entities: dict[str, dict],
) -> list[dict]:
    question_tokens = tokens(question)
    scenario_documents = [tokens(scenario_search_text(item, concepts, entities)) for item in scenarios]
    idf = build_idf(scenario_documents)
    ranked = []
    for scenario, document_tokens in zip(scenarios, scenario_documents):
        direct_tokens = tokens(
            " ".join(
                flatten_text(scenario.get(key))
                for key in ("id", "define", "trigger", "goal", "tags", "composition")
            )
        )
        direct_score = weighted_overlap(question_tokens, direct_tokens, idf)
        knowledge_scores = []
        for reference in scenario_uses(scenario):
            item = item_for_ref(reference, concepts, entities)
            if item:
                knowledge_scores.append(weighted_overlap(question_tokens, tokens(flatten_text(item)), idf))
        knowledge_score = max(knowledge_scores, default=0.0)
        score = 0.78 * direct_score + 0.22 * knowledge_score
        question_norm = normalize(question)
        scenario_norm = normalize(scenario.get("id", "")).removeprefix("如何")
        if scenario_norm and scenario_norm in question_norm:
            score += 0.35
        ranked.append(
            {
                "id": scenario["id"],
                "score": round(min(score, 1.0), 4),
                "define": scenario.get("define", ""),
            }
        )
    return sorted(ranked, key=lambda item: (-item["score"], item["id"]))


def iter_paragraphs(project: Path, relative_paths: Iterable[str] | None = None):
    manifest = load_yaml(project / "registry/source_manifest.yaml")
    accepted = {item["path"] for item in manifest.get("sources", []) if item.get("status") == "accepted"}
    paths = accepted if relative_paths is None else set(relative_paths) & accepted
    for source in sorted(paths):
        try:
            yield from source_index(project, source)["paragraphs"]
        except (ValueError, OSError):
            continue


def rank_evidence(
    project: Path,
    question: str,
    relative_paths: Iterable[str] | None,
    expansion: str = "",
    limit: int = 8,
    nodes: dict[str, dict] | None = None,
) -> list[dict]:
    question_tokens, expansion_tokens = tokens(question), tokens(expansion)
    paragraphs = list(iter_paragraphs(project, relative_paths))
    by_id = {p["evidence_id"]: p for p in paragraphs}
    bindings, _ = read_bindings(project)
    if nodes is None:
        scenarios, concepts, entities = load_models(project)
        nodes = {**{"scenario://" + n["id"]: n for n in scenarios},
                 **{"concept://" + key: n for key, n in concepts.items()},
                 **{"entity://" + key: n for key, n in entities.items()}}
    confirmed = {}
    for ref, node in nodes.items():
        for item in resolve_bindings(ref, node, by_id, bindings):
            if item["status"] == "confirmed":
                confirmed.setdefault(item["evidence_id"], []).append({
                    "ref": ref, "support_field": item["support_field"],
                    "review_note": item.get("review_note", ""), "confirmed_at": item["confirmed_at"]})
    ranked = []
    for paragraph in paragraphs:
        paragraph_tokens = tokens(paragraph["text"])
        question_score = weighted_overlap(question_tokens, paragraph_tokens)
        expansion_score = weighted_overlap(expansion_tokens, paragraph_tokens) if expansion_tokens else 0.0
        title_score = weighted_overlap(question_tokens, tokens(Path(paragraph["source"]).stem))
        score = 0.68 * question_score + 0.22 * expansion_score + 0.10 * title_score
        reviews = confirmed.get(paragraph["evidence_id"], [])
        # Review is a bounded preference, never permission to ignore question relevance.
        bonus = 0.05 if reviews and question_score > 0 else 0.0
        if score <= 0 or (len(paragraph["text"].strip()) < 24 and not reviews):
            continue
        ranked.append({**paragraph, "score": round(min(1.0, score + bonus), 4),
                       "retrieval_score": round(score, 4), "confirmation_bonus": bonus,
                       "status": "confirmed" if reviews else "candidate_unconfirmed",
                       "confirmed_for": reviews})
    ranked.sort(key=lambda item: (-item["score"], item["source"], item["line_start"]))
    return ranked[:limit]


def compact_scenario(scenario: dict, score: float) -> dict:
    phases = []
    for phase in scenario.get("composition") or []:
        phases.append(
            {
                "phase": phase.get("phase"),
                "rule": phase.get("rule"),
                "uses": phase.get("uses") or [],
            }
        )
    return {
        "id": scenario["id"],
        "score": score,
        "define": scenario.get("define"),
        "goal": scenario.get("goal"),
        "phases": phases,
        "sources": scenario.get("sources") or [],
    }


def compact_knowledge(reference: str, item: dict, score: float) -> dict:
    return {
        "ref": reference,
        "id": item.get("id"),
        "score": round(score, 4),
        "define": item.get("define"),
        "sources": item.get("sources") or [],
    }


def build_context_text(context: dict) -> str:
    lines = [f"问题：{context['question']}", f"状态：{context['status']}"]
    if context.get("selected_scenario"):
        scenario = context["selected_scenario"]
        lines.append(f"选定场景：{scenario['id']}（score={scenario['score']}）")
        lines.append(f"场景目标：{scenario.get('goal') or scenario.get('define') or ''}")
    if context.get("knowledge_items"):
        lines.append("相关知识：" + "、".join(item["id"] for item in context["knowledge_items"]))
    lines.append("原文依据（人工确认仅针对登记的支持字段）：")
    for item in context.get("evidence") or []:
        reviews = item.get("confirmed_for") or []
        label = "；".join(review["ref"] + " / " + review["support_field"] for review in reviews)
        status = "已确认支持范围：" + label if reviews else "检索候选 · 未确认"
        lines.append(
            f"- {item['source']}:{item['line_start']}-{item['line_end']} | {status} | {item['text']}"
        )
    return "\n".join(lines)


def needs_clarification(question: str, ranked: list[dict]) -> bool:
    if not ranked:
        return False
    question_norm = normalize(question)
    top = ranked[0]
    second_score = ranked[1]["score"] if len(ranked) > 1 else 0.0
    gap = top["score"] - second_score
    exact_topic = normalize(top["id"]).removeprefix("如何") in question_norm
    short_generic = len(question_norm) <= 12 and top["score"] < 0.45 and not exact_topic
    multi_intent = any(marker in question for marker in ("还是", "不知道该先", "哪个更", "先做什么"))
    close_candidates = gap < AMBIGUITY_GAP and top["score"] < 0.42
    return short_generic or multi_intent or close_candidates


def retrieve_context(
    project: Path,
    question: str,
    mode: str = "model-guided",
    scenario_id: str | None = None,
    top_k: int = 3,
    evidence_k: int = 8,
) -> dict:
    project = project.resolve()
    if not question.strip():
        raise ValueError("question must not be empty")
    if mode not in {"model-guided", "raw"}:
        raise ValueError("mode must be model-guided or raw")

    scenarios, concepts, entities = load_models(project)
    base = {
        "question": question,
        "mode": mode,
        "query_kind": "raw" if mode == "raw" else "one_hop",
        "status": "no_evidence",
        "candidate_scenarios": [],
        "selected_scenario": None,
        "knowledge_items": [],
        "source_files": [],
        "evidence": [],
    }

    if mode == "raw":
        evidence = rank_evidence(project, question, None, limit=evidence_k)
        base["evidence"] = evidence
        base["source_files"] = list(dict.fromkeys(item["source"] for item in evidence))
        base["status"] = "context_ready" if evidence and evidence[0]["score"] >= 0.06 else "no_evidence"
        base["context_text"] = build_context_text(base)
        return base

    ranked = rank_scenarios(question, scenarios, concepts, entities)
    base["candidate_scenarios"] = ranked[:top_k]
    scenario_by_id = {item["id"]: item for item in scenarios}
    if scenario_id:
        if scenario_id not in scenario_by_id:
            raise ValueError(f"unknown scenario: {scenario_id}")
        selected_id = scenario_id
        selected_score = next((item["score"] for item in ranked if item["id"] == scenario_id), 1.0)
        status = "context_ready"
    elif not ranked or ranked[0]["score"] < READY_THRESHOLD:
        selected_id = None
        selected_score = ranked[0]["score"] if ranked else 0.0
        status = "no_evidence"
    else:
        selected_id = ranked[0]["id"]
        selected_score = ranked[0]["score"]
        status = "needs_clarification" if needs_clarification(question, ranked) else "context_ready"

    if not selected_id:
        base["context_text"] = build_context_text(base)
        return base

    scenario = scenario_by_id[selected_id]
    base["status"] = status
    base["selected_scenario"] = compact_scenario(scenario, selected_score)
    question_tokens = tokens(question)
    knowledge = []
    for reference in scenario_uses(scenario):
        item = item_for_ref(reference, concepts, entities)
        if not item:
            continue
        score = weighted_overlap(question_tokens, tokens(flatten_text(item)))
        knowledge.append(compact_knowledge(reference, item, score))
    knowledge.sort(key=lambda item: (-item["score"], item["ref"]))
    base["knowledge_items"] = knowledge[:12]

    sources = list(scenario.get("sources") or [])
    for item in base["knowledge_items"]:
        sources.extend(item.get("sources") or [])
    sources = list(dict.fromkeys(sources))
    expansion = " ".join(
        [scenario["id"], scenario.get("define", "")]
        + [item["id"] + " " + (item.get("define") or "") for item in base["knowledge_items"]]
    )
    scope = {"scenario://" + scenario["id"]: scenario}
    scope.update({item["ref"]: item_for_ref(item["ref"], concepts, entities) for item in base["knowledge_items"]})
    evidence = rank_evidence(project, question, sources, expansion=expansion, limit=evidence_k, nodes=scope)
    base["evidence"] = evidence
    base["source_files"] = list(dict.fromkeys(item["source"] for item in evidence))
    if not evidence:
        base["status"] = "no_evidence"
    base["context_text"] = build_context_text(base)
    return base
