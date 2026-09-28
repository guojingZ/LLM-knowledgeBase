# WORKLOG

## 当前目标

验证现有知识模型是否比直接搜索 raw 更能帮助桌面 Agent 定位正确场景、知识项和原文证据，并建立人工反馈回流但不自动污染正式模型的闭环。

## 当前状态

- **Verified**：知识构建阶段已完成，正式模型为 17 个场景、234 个概念、163 个实体。
- **Verified**：本地上下文检索、Raw 基线、批量检索评测和反馈记录脚本已实现。
- **Pending verification**：`eval/questions.yaml` 为种子题集，场景标签和预期来源仍需用户逐题确认。
- **Pending verification**：最终答案的帮助程度、完整性和无依据陈述率需要在桌面 Agent 中人工评分。
- **Blocked by design**：在应用验证完成前不实现 MCP，不安装知识库 Skill。

## 本轮执行动作

- 按 Project 治理边界重建轻量项目目录。
- 将旧批次、WorkBuddy 记录和分析报告归入 `runs/build/2026-09-23/`。
- 增加项目内 Agent 使用规则、输入输出合同和本地运行脚本。
- 增加 Raw/模型导航对照评测和反馈转审查队列机制。

## 验证结果

最终结果见 `runs/build/2026-09-25-pre-mcp/verification.md`：来源清单无重复，模型 0 断链，7/7 自动测试通过，压缩包解压后的检索—反馈—审查队列集成链路通过。

24 道待审种子题的自动结果为 Top1 61.11%、Top3 94.44%、边界行为 100%。模型导航和 Raw 的预期来源命中率目前同为 83.33%，因此尚不能宣称模型导航优于 Raw，也不进入 MCP。

## 修改区域

`PROJECT.md`、`WORKLOG.md`、`MEMORY.md`、`application/`、`eval/`、`registry/`、`scripts/`、`tests/`、`topics/`、`docs/adr/`、`runs/`。

## 下一项直接行动

由用户审查 `eval/questions.yaml` 中的问题、预期场景和预期来源，然后在桌面 Agent 中完成首批人工答案评分；优先复核 Top1 与 Top3 不一致的题目。
