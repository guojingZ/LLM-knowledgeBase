# 桌面 Agent 知识应用规则

当用户要求使用本项目知识库回答问题时：

1. 保留用户原始问题，不先替用户补充目标。
2. 从项目根目录运行：

   ```bash
   python scripts/kb_context.py --question "用户原始问题" --mode model-guided --json
   ```

3. 检查 `status`：
   - `context_ready`：继续；
   - `needs_clarification`：向用户说明最接近的候选场景及差异；
   - `no_evidence`：说明知识库没有足够依据，不用通用常识冒充库内答案。
4. 将 `candidate_scenarios` 视为召回候选，不盲信首选项。结合用户问题比较前三项：
   - 首选语义正确：继续；
   - 另一候选更准确：用 `--scenario "候选场景ID"` 重新运行，再使用新 context；
   - 仍无法判断：先向用户澄清，不自行猜测。
5. 阅读返回的 evidence 和必要的 source 文件。知识模型是导航，不是最终证据。
6. 按 `application/response_contract.yaml` 输出结论、步骤、依据与来源、不确定性和 `trace_id`。
7. 不把 context 中未出现、raw 中未确认的观点写成项目知识。
8. 用户纠正答案时，引导开发者运行 `record_feedback.py`；不要直接修改 model。

调试或对照时，可将 `--mode model-guided` 改为 `--mode raw`，比较两条路径返回的来源与证据。

当前种子题验证显示，确定性检索更适合作为“前三候选召回器”，不应被当作自动意图分类器。Agent 的语义判断和必要的二次指定场景，是 pre-MCP 阶段的正式使用方式。

## v1.3 明确引用的多跳探索

用户询问知识关联或希望展示路径时，可以从根目录执行：

```bash
python scripts/kb_multihop.py --question "用户原始问题"
```

已知起点终点时传入 `--start-ref`、`--target-ref`，避免仅靠文本召回。检查 `status`、`truncated`，逐步展示 `steps[].field` 和 `traversal`；反向浏览必须注明。路径是模型记录的关联，不等同于因果或已经证明的推理。终点证据 `candidate_unconfirmed` 必须回读原文判断，不能冒充人工确认。原有回答合同和反馈审查继续适用，脚本不会自动修改模型。


## v1.4 人工证据与运行记录

主上下文检索仍为场景阶段直接知识，不递归展开其他节点。GUI 后续路径是预览，不得当作本次已经取得的证据。

evidence 中的 confirmed_for 列出人工登记的节点及 support_field；确认只针对该范围，不表示本次答案所有主张被确认。候选、旧确认、失效确认不得提升为人审事实。确认状态属于 trace 保存时快照，当前状态需重新查询。

两种查询 CLI 默认保存 trace；--no-save 不保存。最终回答应输出 trace_id，供 GUI 查看检索依据和提交评价。本地程序不自动记录你的最终回答，也不会凭检索日志宣称答案质量改善。


## v1.5 任务路由与实际返回

用户要求接入资料、提取、比较或发布知识时，转到根目录 AGENTS.md 与 application/agent-operations.md，调用 kb_manage.py；不要将建设请求当作问答检索。框架仍由人定义，两轮候选经人审再发布。

知识问答仍使用本文件的一跳流程。kb_context.py JSON 包含 selected_scenario 的 define/goal/phases/sources、knowledge_items 的紧凑字段与 evidence；context_text 是更短的文本摘要，不能称为完整模型。完整 IPO、decomposition 和关系字段尚未加入主问答上下文。如需针对某节点核对完整字段，可通过 kb_manage.py catalog/ref 读取，但不能把额外读取冒称为本次 trace 原始结果。
