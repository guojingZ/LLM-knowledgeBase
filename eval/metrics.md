# 评测口径

## 自动检索指标

- `scenario_top1_accuracy`：第一候选场景与种子标签一致的比例。
- `scenario_top3_recall`：预期场景进入前三候选的比例。
- `expected_source_hit_rate_model`：模型导航证据中命中至少一个预期来源的比例。
- `expected_source_hit_rate_raw`：Raw 基线证据中命中至少一个预期来源的比例。
- `boundary_behavior_accuracy`：对 clarify/abstain 问题是否没有高置信路由到具体场景。

这些指标只验证路由和证据候选，不代表最终答案正确。

## 人工回答指标

- 场景是否符合用户真实意图；
- 来源是否支撑答案；
- 关键点是否完整；
- 是否出现无依据扩写；
- 是否正确表达不确定性；
- 对业务员是否有帮助。

`eval/questions.yaml` 在人工确认前不得称为金标准。
