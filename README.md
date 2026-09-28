# LLM KnowledgeBase 3.0 pre-MCP

这是一个可离线维护、可审查、可回放的领域知识库项目。它已经完成知识模型构建，并提供了 MCP 之前的最小知识应用闭环：

```text
问题 → 场景候选 → 知识项 → raw 原文证据 → 桌面 Agent 回答 → 人工反馈 → 审查队列
```

项目不包含 MCP、GUI、远程模型 API 或可安装知识库 Skill。当前目标是先验证“模型导航 + 原文证据”是否真的改善业务回答。

## 5 分钟开始

要求 Python 3.10+。

```bash
python -m pip install -r requirements.txt
python scripts/project_status.py .
python scripts/validate_model.py .
python scripts/kb_context.py --question "面对复杂业务故障时，如何定位根因？" --json
```

在 WorkBuddy 或其他可访问本地目录的桌面 Agent 中输入：

```text
请读取 application/assistant_prompt.md，严格按其中规则使用这个项目回答：
面对复杂业务故障时，如何定位根因？
```

详细操作、评测与反馈方式见 `docs/local-operations.md` 和 `topics/knowledge-application.md`。

## 主要入口

| 角色 | 从这里开始 | 主要动作 |
|---|---|---|
| 业务员 | `application/assistant_prompt.md` | 提问、核对答案、提供反馈 |
| 开发者 | `docs/local-operations.md` | 本地检索、测试、批量评测 |
| 知识维护者 | `PROJECT.md`、`MEMORY.md` | 审查队列、更新模型、记录决策 |
| 审计/复盘 | `runs/`、`WORKLOG.md` | 回放构建、检索与验证记录 |

## 修改知识的安全路径

应用中的体会不会自动覆盖正式模型。先记录反馈并同步到队列：

```bash
python scripts/record_feedback.py . --trace-id TRACE_ID \
  --rating partial --issue incomplete_answer --notes "缺少假设验证步骤"
python scripts/sync_feedback_queue.py .
```

人工审查 `registry/application_feedback_queue.yaml` 后，再决定修改 `model/`、来源关系、别名或回答规则。修改后必须重新运行模型校验、自动测试和检索评测。

## 项目边界

- `raw/accepted/`：已准入的原始证据；`raw/inbox/`：待处理材料。
- `model/`：正式场景、概念、实体模型。
- `registry/`：来源、裁决和待审队列。
- `application/`：桌面 Agent 输入输出规则。
- `eval/`：待人工确认的种子题与评分表。
- `runs/`：可复现的构建、评测和反馈记录。
- `scripts/`、`tests/`：确定性本地工具和自动测试。
