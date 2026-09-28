# 检索对照评测

该结果使用待人工确认的种子问题集，不代表最终业务效果。

## 指标

- `question_count`: 24
- `answer_question_count`: 18
- `boundary_question_count`: 6
- `scenario_top1_accuracy`: 0.6111
- `scenario_top3_recall`: 0.9444
- `expected_source_hit_rate_model`: 0.8333
- `expected_source_hit_rate_raw`: 0.8333
- `boundary_behavior_accuracy`: 1.0
- `question_set_status`: needs_human_review

## 逐题结果

| ID | 预期 | 模型首选 | Top1 | Top3 | 模型来源 | Raw来源 | 状态 |
|---|---|---|---:|---:|---:|---:|---|
| Q001 | 如何分析和解决复杂问题 | 如何培养架构思维与大架构观 |  |  |  |  | needs_clarification |
| Q002 | 如何分析和解决复杂问题 | 如何分析和解决复杂问题 | ✓ | ✓ |  |  | needs_clarification |
| Q003 | 如何制作一份完整的解决方案 | 如何定义融入个人经验的AI提示语与技能 |  | ✓ | ✓ | ✓ | context_ready |
| Q004 | 如何培养架构思维与大架构观 | 如何培养架构思维与大架构观 | ✓ | ✓ | ✓ | ✓ | context_ready |
| Q005 | 如何培养系统思维能力 | 如何构建个人思维框架与认知体系 |  | ✓ | ✓ | ✓ | context_ready |
| Q006 | 如何定义融入个人经验的AI提示语与技能 | 如何将隐性经验显性化并结构化输出 |  | ✓ | ✓ | ✓ | context_ready |
| Q007 | 如何实现思维逻辑自洽 | 如何实现思维逻辑自洽 | ✓ | ✓ | ✓ | ✓ | context_ready |
| Q008 | 如何将隐性经验显性化并结构化输出 | 如何将隐性经验显性化并结构化输出 | ✓ | ✓ | ✓ | ✓ | context_ready |
| Q009 | 如何平衡知识广度与深度构建核心竞争力 | 如何平衡知识广度与深度构建核心竞争力 | ✓ | ✓ | ✓ | ✓ | context_ready |
| Q010 | 如何构建个人思维框架与认知体系 | 如何构建个人思维框架与认知体系 | ✓ | ✓ | ✓ | ✓ | context_ready |
| Q011 | 如何构建个人知识体系 | 如何将隐性经验显性化并结构化输出 |  | ✓ | ✓ | ✓ | context_ready |
| Q012 | 如何用模式匹配解决未知问题 | 如何构建个人思维框架与认知体系 |  | ✓ |  | ✓ | needs_clarification |
| Q013 | 如何突破认知障碍实现认知升级 | 如何突破认知障碍实现认知升级 | ✓ | ✓ | ✓ | ✓ | context_ready |
| Q014 | 如何进行结构化决策 | 如何进行结构化决策 | ✓ | ✓ | ✓ | ✓ | context_ready |
| Q015 | 如何透过现象看透事物本质 | 如何通过复盘实现能力进化闭环 |  | ✓ | ✓ |  | context_ready |
| Q016 | 如何通过复盘实现能力进化闭环 | 如何通过复盘实现能力进化闭环 | ✓ | ✓ | ✓ | ✓ | context_ready |
| Q017 | 如何高效学习一个全新领域 | 如何高效学习一个全新领域 | ✓ | ✓ | ✓ | ✓ | context_ready |
| Q018 | 如何从系统思维进阶到第一性原理 | 如何从系统思维进阶到第一性原理 | ✓ | ✓ | ✓ | ✓ | context_ready |
| Q019 | clarify | 如何平衡知识广度与深度构建核心竞争力 |  |  |  |  | needs_clarification |
| Q020 | clarify | 如何将隐性经验显性化并结构化输出 |  |  |  |  | needs_clarification |
| Q021 | abstain | — |  |  |  |  | no_evidence |
| Q022 | abstain | — |  |  |  |  | no_evidence |
| Q023 | abstain | — |  |  |  |  | no_evidence |
| Q024 | clarify | 如何用模式匹配解决未知问题 |  |  |  |  | needs_clarification |
