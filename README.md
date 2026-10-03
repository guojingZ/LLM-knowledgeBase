# LLM KnowledgeBase Studio v1.3

这是面向场景、概念、实体三层知识模型的本地维护与探索工作台。支持浏览、编辑回写 YAML、差异预览、保存历史、段落证据、局部关系图和明确引用的多跳路径解释。仍保留原有桌面 Agent 检索、评测与反馈流程。

## 开始使用

Windows 双击 `start-studio.bat`；首次安装需要 Python 3.10+ 和联网安装 PyYAML。已有依赖后运行不需要联网。也可手动执行：

```powershell
python -m pip install -r requirements.txt
python gui/backend/app.py --open
```

页面地址：`http://127.0.0.1:8787`。不需要 Flask、npm 或远程模型账户。

已有本地项目：把新包解压到项目外部目录，从新包根目录运行：

```powershell
python apply_update.py --target "C:\Tool\Code\Project\LLM-knowledgeBase"
```

把路径改为你的实际位置。更新脚本保留本地已有知识数据和 Git，不删除旧文件。详见 [覆盖与工作台手册](docs/studio-guide.md)。

## 本轮交付

| 阶段 | 合入 v1.3 的功能 |
|---|---|
| v1.1 Evidence Explorer | 来源清单、章节/段落/行号、稳定证据 ID、人工确认/撤销/失效检测 |
| v1.2 Knowledge Graph | 明确引用图、一跳/二跳、方向/类型/关系过滤、节点点击与字段明细 |
| v1.3 Multi-hop Explorer | 问题召回或指定起点终点、1–4 跳、逐步解释、反向标注、证据候选、JSON/CLI 输出 |
| 基础维护补齐 | 差异预览、引用影响、版本冲突检测、原子保存、唯一备份与保护回滚 |

多跳查询是确定性引用路径探索，不是自动生成因果推理或业务答案。人工确认的证据与检索候选有明确区别。模型知识和真实问题回答效果仍需要你审查；本轮工程验证不能证明回答质量提升。

原有 CLI 可继续使用：

```powershell
python scripts/validate_model.py .
python scripts/kb_context.py --question "面对复杂业务故障时，如何定位根因？" --json
python scripts/kb_multihop.py --question "面对复杂业务故障时，如何定位根因？"
python -m unittest discover -s tests -p "test*.py" -v
```

## 主要入口

| 角色 | 从这里开始 | 主要动作 |
|---|---|---|
| 业务员 | `application/assistant_prompt.md` | 提问、核对答案、提供反馈 |
| 开发者 | `docs/studio-guide.md`、`docs/local-operations.md` | 工作台、检索、测试、评测 |
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
