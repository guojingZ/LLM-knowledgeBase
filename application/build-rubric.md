# 增量知识提炼判据

沿用项目人定义的场景—概念—实体框架。第一轮忠实提取原文，第二轮比较现有模型。

| 类型 | 判据 | 正式字段 |
|---|---|---|
| scenario | 有明确触发和目标的“如何…”任务；一篇可以没有场景 | id、define、sources、trigger、goal、composition、inputs、outputs、tags |
| concept | 可复用知识或操作；当前正式校验要求 ipo 或 decomposition | id、define、sources、type、ipo/decomposition、relations、tags |
| entity | 原文明确涉及的具名标准、工具、框架、人物、书籍或知识资产 | id、define、sources、category、type、relations、tags |

不凭空补定义、步骤或关系，不为凑数量制造节点。框架无法忠实表达的内容写入 question 或 conflict，不改框架、不编造 IPO。

第一轮 observations 每项登记 kind、id、define、evidence，可写 question。证据 excerpt 必须与 source_documents 对应 line_start 到 line_end 的完整原文逐字相等。保留多行时使用实际换行。

第二轮 actions：new 新增；update 补充具体字段；evidence 只补来源和支持关系；merge 复用已有节点并登记 aliases；conflict 保留冲突；ignore 无需纳入。每条建议关联 observation_ids，说明 reason。已有节点保持 id。同一目标的修改合并为一条建议。

new/update 提供完整 node；evidence/merge 由程序保留现有节点并增加本任务来源。支持字段例如 define、ipo.process.steps[0]、composition[0].rule、relations.references[0]。同一原文支持多个字段时分别写 supports；跨段落证据分别登记。

relations 仅使用 is_a、depends_on、contains、uses、produces、references、related_to，目标是正式或同批候选中的 concept://ID、entity://ID。文字提及不自动成为关系。场景通过 composition 的 phase、uses、rule 引用知识。

示例：新文档再次说明“分解”，已有定义和步骤一致时使用 evidence；确实新增条件或步骤时用 update；观点不一致时用 conflict。名称不同但语义一致时用 merge，不能只凭同名合并。

候选提交不等于发布。审查关键语义后，先预览再发布；确认表示原文支持登记字段，不表示所有内容或回答已经正确。

历史详细判据和样例位于 runs/build/2026-09-23/round1/_round1_rubric.md、runs/build/2026-09-23/round1/_round1_progress.md、runs/build/2026-09-23/round2/_round2_rubric.md。它们是历史领域案例；不得把思维类分类机械套用到新领域。
