# LLM KnowledgeBase Studio v1.4

本地知识工作台，帮助你看清“问题 → 场景 → 直接知识 → 原文依据”的一跳流程，维护人工证据，并从全局和运行记录中检查知识怎样被使用。最终自然语言回答仍由桌面 Agent 基于原文组织。

## 本轮交付

| 入口 | v1.4 功能 |
|---|---|
| 一跳检索 | 展示场景候选、选定场景、直接知识、引用位置和原文；提供 Raw 对照 |
| 多跳预览 | 提前展示后续明确路径，点击仅填写探索表单；主动查询才执行多跳 |
| 人工证据 | 确认具体支持范围及理由；GUI / CLI / Raw / 多跳终点统一读取；候选去重与变化复核 |
| 全局视角 | 全部 414 节点关系图、17 场景—397 知识项矩阵、证据覆盖、查询使用统计 |
| 运行记录 | 每次明确问题或多跳提交保存 trace；回放、版本、参数、耗时、图中叠加和导出 |
| 人工评价 | 场景、证据、有用性和问题说明；进入待审队列，不自动改模型 |

知识编辑、差异预览、版本冲突保护、保存历史、回滚和局部关系图继续保留。

## 更新已有项目

新包解压到现有项目外部目录，从新包的 LLM-knowledgeBase/ 根目录运行：

    python apply_update.py --target "C:\Tool\Code\Project\LLM-knowledgeBase"

把路径改为你的本地位置。脚本保留已有 model/、raw/、registry/、runs/、eval/ 和 Git，更新程序与文档；无须删除本地目录。随后关闭旧服务并重新启动，浏览器刷新页面。

新项目可直接使用 ZIP 中的目录。交付知识快照为 17 场景、234 概念、163 实体、50 来源，不替换你本地已修改的知识。旧人工确认会保留并提示补充支持范围。

## 启动与试用

Windows 双击 start-studio.bat。首次需要 Python 3.10+ 和联网安装 PyYAML；依赖已安装后可离线运行。

    python -m pip install -r requirements.txt
    python gui/backend/app.py --open

浏览器访问 http://127.0.0.1:8787。不需 Flask、npm、模型账号。Mac/Linux 可运行 sh start-studio.sh。

建议按以下顺序试用：

1. “一跳检索”输入“面对复杂业务故障时，如何定位根因？”。
2. 查看选定场景、直接知识与原文，在知识浏览中确认具体支持字段。
3. 重新检索，核对有效人工确认状态；查看多跳预览，但不必执行。
4. “全局视角”切换关系图、矩阵和证据覆盖。
5. “运行记录”查看本次上下文快照，评价后检查待审状态。

## CLI 与检查

    python scripts/kb_context.py --question "面对复杂业务故障时，如何定位根因？" --json
    python scripts/kb_multihop.py --start-ref "scenario://如何分析和解决复杂问题" --target-ref "entity://金字塔原理" --direction outgoing --max-depth 2
    python scripts/validate_model.py .
    python -m unittest discover -s tests -p "test*.py" -v

两种查询 CLI 默认保存 trace，--no-save 只输出结果。原有反馈和队列脚本继续使用。Node 只用于可选开发检查 python scripts/verify_frontend.py，不属于工作台运行依赖。

## 阅读入口

- [工作台手册与 API](docs/studio-guide.md)
- [项目目的与状态](PROJECT.md)
- [当前交付与验证证据](WORKLOG.md)
- [v1.4 决策与能力边界](docs/adr/005-one-hop-first-observable-studio.md)
- [桌面 Agent 提示](application/assistant_prompt.md)

工程检查不等同于业务答案质量验证。种子评测仍需人工确认；多跳仍是明确引用路径探索，不证明因果或逐步推理。
