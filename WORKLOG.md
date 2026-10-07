# WORKLOG

## 当前目标与状态

**用户已确认**：开始 v1.4 开发并纳入第一批功能。以程序目前的一跳为主流程理解，在 GUI 预览后续多跳思路及路径。

**Verified**：Studio v1.4.0 已实现一跳入口、统一字段证据、全局视图、GUI trace 与简单评价。31 项 Python 测试及 17 项前端 DOM/API 检查通过；模型与来源 55 个文件字节保持一致。具体命令、指标、打包结果和边界见 [验证报告](runs/build/studio-v1.4/verification.md)。

**Pending verification**：Windows 启动与真实浏览器视觉布局；段落支持是否充分和最终 Agent 答案质量。当前环境无可用浏览器内核，下载未得到有效压缩包，未将 DOM 检查写成视觉验证。种子题仍需人审；原文与模型导航来源命中率保持相同，不能宣称回答效果提升。

## 本轮执行动作

- 增加“一跳检索”主入口，解释候选场景、直接阶段引用、上下文知识预算、来源段落和待澄清状态。
- 在 GUI 预览后续明确关系路径；不增加一跳上下文，主动提交多跳才另建 trace。现有 BFS 评分与算法未重构。
- 抽取共享段落身份和字段人审逻辑，GUI、问题 CLI、Raw 与多跳终点统一读取；去重，保留旧确认并标记补充复核。
- 增加全部节点关系图、直接引用矩阵、证据覆盖、节点查询使用计数和历史运行叠加。
- GUI 与 CLI 共用 trace 保存、参数/快照/版本/耗时、冲突拒绝与旧记录回放；不自动记录外部 Agent 最终回答。
- GUI 评价复用反馈文件与待审队列；补齐版本冲突、幂等同步、审查状态保留、部分失败与重试。
- 更新 README、操作手册、Agent 提示与 ADR 005。保留已有数据的升级脚本及原有编辑、图谱、历史回滚能力。

## 验证结果

见 [verification.md](runs/build/studio-v1.4/verification.md)。查询预览隔离、字段/来源复核、GUI/CLI 共享状态、历史快照、失败后重试和正常路径分别检查；源知识未修改，测试人审仅发生在临时目录。

## 修改区域

gui/、scripts/kb_lib.py、kb_context.py、kb_multihop.py、kb_evidence.py、kb_trace.py、record_feedback.py、sync_feedback_queue.py、package_project.py、tests/、VERSION、README/CHANGELOG、工作台与项目治理文档、application/assistant_prompt.md、runs/build/studio-v1.4/。正式 model/、raw/accepted/、source_manifest 和原人工证据登记未改写。

## 下一项直接行动

在 Windows 本机将新包解压到项目外部，执行 apply_update.py --target 实际项目路径，重启 start-studio.bat。提交复杂问题示例，确认一个定义字段，再重查、查看全局矩阵和运行评价，核实页面布局及业务依据。出现具体问题后再进入下一轮，不预先实施第二批语义多跳改造。
