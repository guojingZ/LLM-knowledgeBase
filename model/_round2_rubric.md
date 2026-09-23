# 第二轮填充规范（内容填充阶段）

> 依据：`知识萃取规范指南.md` 第五章 5.3 + 第六章「建模规范」
> 输入：`model/concepts.yaml`、`model/entities.yaml`（第一轮骨架，含 id + sources + define + type）
> 原则：**原文忠实**——每条内容必须能在 sources 指向的文章里找到依据，禁止凭空编造。

## 1. 你要填什么

对每个概念：

| 字段 | 要求 |
|---|---|
| `define` | ≤50 字，只说"是什么"，不评价重要性。骨架里已有则保留或精简优化 |
| `ipo` **或** `decomposition` | **至少有一个**，两者可共存 |
| `relations` | 2-6 条，优先精确关系 |
| `tags` | 3-5 个关键词 |

对每个实体：

| 字段 | 要求 |
|---|---|
| `define` | ≤50 字 |
| `relations` | 1-6 条，至少 1 条 |
| `children` | 仅当原文明确提到子级实体时才填，最多 3 层 |
| `tags` | 2-4 个 |

## 2. IPO 建模方式怎么选

```
这个概念本身就能说清"输入→加工→输出"？
  ├─ 是 → 用 ipo（原子性概念）
  └─ 否，它是多个已有概念的组装 → 用 decomposition
两者都有 → 混合：ipo 写整体加工逻辑，decomposition 写关键步骤引用了哪些子概念
```

**`ipo` 合格标准**（规范 6.1 规范 2）：
- `input` 是具体的加工原料，不是"信息""数据"这种模糊词
- `process.steps` 是**有序的操作序列**（3-6 步），不是并列关键词罗列
- `output` 与 `input` 对应，是加工后的产物

差例子（禁止）：`input: [需求]` / `steps: [分析, 分解, 执行]` / `output: [解决方案]`

**`decomposition` 合格标准**：
- 2-6 个 step，每个 step 对应一个清晰动作
- `uses` 必须是 concepts.yaml 里**真实存在的 id**
- 写 `why`：为何在此步骤用这个子概念

## 3. 从原文抓 IPO 的信号词

| 原文表述 | 对应字段 |
|---|---|
| "首先…然后…最后…"、"第一步…第二步…" | `process.steps` |
| "以…为前提"、"基于…"、"需要…作为输入" | `input` |
| "得到…"、"产出…"、"形成…"、"最终输出" | `output` |
| "借助…工具"、"使用…"、"通过…软件" | `process.tools`（指向实体） |
| "XX 是一种 YY" | `relations.is_a` |
| "必须依赖 YY" | `relations.depends_on` |
| "XX 包含 YY" | `relations.contains` |
| "XX 产生/输出 YY" | `relations.produces` |
| "参考/借鉴了 YY" | `relations.references` |

## 4. 关系填写规则

优先级：`is_a` > `depends_on` > `contains` > `uses` > `produces` > `references` > `related_to`

- **引用必须可解析**：`concept://<id>` 的 id 必须在 concepts.yaml 全量 id 列表里；`entity://<id>` 同理
- 每个条目 relations 控制在 **2-6 条**（规范 5.4：不过度引用）
- 概念可以 `uses` 实体；实体可以 `references` 概念；**概念不能引用场景**
- 拿不准就用 `related_to` 兜底

## 5. 宁缺毋滥

找不到明确 IPO 的概念（规范 5.4）：
- 只填能找到的部分，其余留空 `{}`
- 在 `tags` 里加一个标记 `证据不足`
- **不要为了凑结构而编造步骤**

## 6. 输出格式

写入指定的 part 文件，**只写分配给你的条目**，不要新增/删除条目，不要改 `id` 和 `sources`。

```yaml
concepts:
  - id: 某概念
    define: 一句话定义
    ipo:
      input:
        - 输入A
      process:
        steps:
          - 步骤一
          - 步骤二
        tools:
          - entity://某工具
      output:
        - 输出A
    decomposition:
      - step: 阶段名
        uses: concept://子概念
        why: 为何用
    relations:
      is_a:
        - concept://父概念
      uses:
        - entity://某框架
      related_to:
        - concept://相关概念
    tags: [标签1, 标签2]

entities:
  - id: 某实体
    define: 一句话定义
    relations:
      is_a:
        - entity://父实体
      related_to:
        - concept://相关概念
    tags: [标签1]
```

注意：
- `type` / `category` / `sources` **不要重复输出**（脚本会从骨架合并）
- 中文值不加引号；含 `:` `#` `-` `{` `[` 等半角符号时加双引号
- `—`、`→`、`×`、`·` 等全角符号安全，可直接使用
