# WORKLOG

## 当前目标与状态

**用户已确认**：合并开发并直接交付 Studio v1.3，更新已有本地 LLM-knowledgeBase，保留知识工程模型与后续多跳探索方向。

**Verified**：v1.3.0 程序已实现并完成模型、自动测试、真实 HTTP、前端 DOM/API 交互检查。正式模型仍为 17 场景、234 概念、163 实体，50 个来源；与原始三份 YAML 字节一致。具体结果与限制只记录在 [验证报告](runs/build/studio-v1.3/verification.md)。

**Pending verification**：Windows 启动脚本、真实浏览器视觉布局、知识内容的人工段落支持确认、最终答案质量。模型导航与 Raw 的种子题来源命中率仍相同，不能宣称回答效果已改善。

## 本轮执行动作

- 找回 v1.0.0 合并包，与原始包核对模型一致；替换原 GUI 的全文包含图谱与关键词多跳原型。
- 合入段落证据、人工登记/撤销/失效检测、局部图、明确引用多跳解释和 CLI。
- 补齐差异预览、引用影响、文件版本冲突、原子保存、备份和保护回滚。
- 统一为标准库本机 HTTP 同源入口，增加 Windows/Mac/Linux 启动入口及数据保留更新脚本。
- 修正模型/应用文档中的旧 GUI 限制，记录 ADR 004；MCP/向量数据库/Onto-Model 扩展未进入本轮。
- 清理合并时产生的 57 个字节一致的 `#Uxxxx` 文件名转义副本；未修改原始来源内容。修复 ZIP 重复 manifest 和缓存混入。

## 验证结果

见 [verification.md](runs/build/studio-v1.3/verification.md)，包含执行命令、结果、证据文件和未验证边界。执行代码修改与验证结果分别记录，不以语法检查代替启动与交互测试。

## 修改区域

`gui/`、`start-studio.*`、`apply_update.py`、`scripts/kb_multihop.py`、`scripts/verify_frontend.py`、`scripts/package_project.py`、`tests/`、`registry/gui_evidence.yaml`、版本与治理文档、`application/assistant_prompt.md`、`runs/build/studio-v1.3/`。正式 `model/`、`raw/accepted/` 内容和旧检索算法未改写。

## 下一项直接行动

在 Windows 本机应用更新后双击 `start-studio.bat`，访问 `http://127.0.0.1:8787`，选择 `concept://MECE` 检查证据弹窗和一跳/二跳图的视觉布局。仅在本机验证出现具体问题时开启下一轮修复。
