# 知识模型

## 已确认

- 当前模型采用 Scenario–Concept–Entity 三层。
- 场景回答用户何时解决什么问题；概念承载可复用的 IPO 或分解；实体表示具名人物、工具、书籍、技术和框架。
- 正式规模和质量统计以 `runs/build/2026-09-23/validation.json` 为准。
- 正式节点 sources 保留文件级来源；逐字段段落支持另外登记于 registry/gui_evidence.yaml，GUI 与 CLI 共用。v1.5 通过已审候选发布支持记录，并保留原文快照与两轮建设历史。

## 待验证

- 17 个场景是否覆盖真实业务员提问方式。
- 234 个概念是否存在过细、过宽或从不被调用的节点。
- 大量 `related_to` 是否会干扰应用层知识选择。

## 更新入口

应用反馈先进入 `registry/application_feedback_queue.yaml`。通过审查后，按影响范围更新别名、场景、概念、实体或来源，再运行全量引用校验和固定评测。

## 建设流程

新增 Raw 的准入、两轮任务、候选审查、发布及来源更新复核见 [建设手册](../docs/knowledge-construction.md)。Agent 定向操作从 [AGENTS.md](../AGENTS.md) 开始，使用 [操作指南](../application/agent-operations.md)。完整字段参与问答留到下期。
