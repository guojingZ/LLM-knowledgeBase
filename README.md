# LLM KnowledgeBase Studio v1.5

本地知识建设与应用工作台。新增 Raw 按“准入 → 忠实提取 → 比较已有知识 → 人工审查 → 增量发布”进入模型；一跳检索、原文证据、全局视角和运行评价继续使用。人定义框架，桌面 Agent 负责语义提取、比较及最终回答，Python 负责校验和落盘。

## 本轮交付

| 入口 | 功能 |
|---|---|
| 资料与知识建设 | .md/.txt 导入、准入、全文、引用影响、重复内容和资料状态 |
| 两轮任务 | 原文与模型基线快照；忠实提取、增量比较；任务包导出和 JSON 结果导入 |
| 候选审查与发布 | 新增、补充字段/证据、合并名称、冲突、不纳入；逐条决定、差异预览、部分发布、无新增完成 |
| 资料更新 | 来源变化/缺失提示、旧任务阻止覆盖、新建任务复核、保留原文版本 |
| Agent 操作 | 根目录 AGENTS.md 路由、可发现 JSON 操作契约、CLI 与本机 HTTP 共用内核 |
| 历史能力 | 一跳与 Raw 对照、多跳预览/主动探索、字段证据、414 节点全局视角、trace 评价、编辑与保护回滚 |

没有内置 LLM 自动调用；两轮结果由桌面 Agent 生成。完整知识字段参与问答留到下期。当前没有安装个人 Skill 或 MCP。

## 更新已有项目

把新包解压到已有项目外部，从新包 LLM-knowledgeBase/ 根目录运行：

```powershell
python apply_update.py --target "C:/Tool/Code/Project/LLM-knowledgeBase"
```

路径改为实际位置。保留已有 model/、raw/、registry/、runs/、eval/ 和 Git，更新代码与文档；无须删除本地目录。关闭旧服务后更新，再重新启动并刷新浏览器。新项目可直接使用解压目录。

交付知识快照仍为 17 场景、234 概念、163 实体、50 来源，没有植入临时业务候选或确认。新建设登记在首次操作时创建。

## 启动与试用

Windows 双击 start-studio.bat。Python 3.10+；首次需联网安装 PyYAML，依赖齐全后可离线运行。

```bash
python -m pip install -r requirements.txt
python gui/backend/app.py --open
```

访问 http://127.0.0.1:8787。Mac/Linux 可运行 sh start-studio.sh，不需要 Flask/npm。

1. 进入“资料与知识建设”，导入一篇资料、阅读并准入。
2. 勾选资料创建任务，导出第一轮包让 Agent 提取，导入结果。
3. 导出第二轮包让 Agent 比较完整已有节点，导入增量建议。
4. 检查原文与支持字段，逐条审查，预览差异后发布。
5. 在知识浏览查看新增来源和字段支持，再从一跳检索、全局与运行记录检查调用。

Agent 直接读 AGENTS.md，并运行：

```bash
python scripts/kb_manage.py tools
python scripts/kb_manage.py sources.list
python scripts/kb_manage.py jobs.packet --input request.json
python scripts/kb_context.py --question "面对复杂业务故障时，如何定位根因？" --json
```

## 文档入口

- [项目目的、状态与模块位置](PROJECT.md)
- [资料、候选、发布与更新手册](docs/knowledge-construction.md)
- [Agent 路由](AGENTS.md) 与 [JSON 操作指南](application/agent-operations.md)
- [一跳、证据、全局、编辑与 API](docs/studio-guide.md)
- [知识应用提示](application/assistant_prompt.md)
- [当前交付记录](WORKLOG.md) 与 [v1.5 验证报告](runs/build/studio-v1.5/verification.md)

## 检查

```bash
python scripts/validate_model.py .
python -m unittest discover -s tests -p "test*.py" -v
python scripts/evaluate_retrieval.py . --no-save
python scripts/verify_frontend.py
```

最后一项是可选 Node DOM/API 检查，不是浏览器视觉测试。工程通过不等同于提炼语义正确或最终回答质量提升；种子题和实际业务候选仍需人审。
