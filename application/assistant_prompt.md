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
