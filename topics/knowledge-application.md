# 本地知识应用与测试

## 业务员如何使用

在 WorkBuddy 或其他可访问本项目目录的桌面 Agent 中输入：

```text
请阅读 application/assistant_prompt.md，并使用本项目知识库回答：
面对一个复杂业务问题时，我应该如何定位根因？
```

Agent 应先运行模型导航，回查证据后再回答，并给出 `trace_id` 和来源。

## 开发者如何测试

在项目根目录安装依赖：

```bash
python -m pip install -r requirements.txt
```

Windows 如果没有 `python` 命令，可将以下命令中的 `python` 改成 `py`。

检查正式模型：

```bash
python scripts/validate_model.py .
```

使用模型导航检索：

```bash
python scripts/kb_context.py --question "面对复杂业务问题时，如何定位根因？" --mode model-guided
```

直接搜索 raw 作为基线：

```bash
python scripts/kb_context.py --question "面对复杂业务问题时，如何定位根因？" --mode raw
```

明确指定场景：

```bash
python scripts/kb_context.py --question "请给出具体步骤" --scenario "如何分析和解决复杂问题"
```

批量运行种子问题集：

```bash
python scripts/evaluate_retrieval.py .
```

记录某次问答反馈：

```bash
python scripts/record_feedback.py . \
  --trace-id TRACE_ID \
  --rating partial \
  --issue incomplete_answer \
  --notes "缺少假设验证步骤"
```

把反馈汇总到人工审查队列：

```bash
python scripts/sync_feedback_queue.py .
```

## 当前能力边界

脚本返回知识上下文和证据候选，不调用模型 API，也不直接生成最终自然语言答案。最终回答由桌面 Agent 完成。这使检索和回答可以分开验证，避免把问题混在一起。

## 每次更新后的回归检查

```bash
python scripts/validate_model.py .
python -m unittest discover -s tests -v
python scripts/evaluate_retrieval.py . --run-id YOUR_RUN_ID
```

先审查 `eval/questions.yaml` 的业务标签，再解释批量指标。当前脚本的前三候选召回优于首选分类，因此 Agent 应比较候选；首选语义不对时，用 `--scenario` 指定候选并重新取上下文。
