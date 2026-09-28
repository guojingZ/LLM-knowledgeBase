from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from kb_lib import retrieve_context  # noqa: E402


class KnowledgeApplicationTests(unittest.TestCase):
    def test_model_guided_retrieval_finds_complex_problem_scenario(self):
        context = retrieve_context(PROJECT, "面对复杂业务故障时，如何定位根因？")
        self.assertEqual(context["status"], "context_ready")
        self.assertEqual(
            context["selected_scenario"]["id"], "如何分析和解决复杂问题"
        )
        self.assertTrue(context["evidence"])

    def test_model_guided_retrieval_finds_knowledge_system_scenario(self):
        context = retrieve_context(
            PROJECT, "如何把零散文章和经验组织成个人知识体系？"
        )
        self.assertEqual(context["status"], "context_ready")
        self.assertEqual(context["selected_scenario"]["id"], "如何构建个人知识体系")

    def test_out_of_scope_question_abstains_without_evidence(self):
        context = retrieve_context(PROJECT, "明天上海会不会下雨？")
        self.assertEqual(context["status"], "no_evidence")
        self.assertIsNone(context["selected_scenario"])
        self.assertEqual(context["evidence"], [])

    def test_generic_multi_intent_question_requires_clarification(self):
        context = retrieve_context(PROJECT, "我该先学习还是先整理知识？")
        self.assertEqual(context["status"], "needs_clarification")
        self.assertGreaterEqual(len(context["candidate_scenarios"]), 2)

    def test_raw_mode_returns_traceable_source_lines(self):
        context = retrieve_context(PROJECT, "结构化思维", mode="raw")
        self.assertEqual(context["status"], "context_ready")
        evidence = context["evidence"][0]
        self.assertTrue(evidence["source"].startswith("raw/accepted/"))
        self.assertGreaterEqual(evidence["line_start"], 1)

    def test_cli_valid_business_outcomes_exit_successfully(self):
        process = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "kb_context.py"),
                "--project",
                str(PROJECT),
                "--question",
                "明天上海会不会下雨？",
                "--no-save",
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "no_evidence")


if __name__ == "__main__":
    unittest.main()
