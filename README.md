# LLM Knowledge Base

一个面向大语言模型（LLM）的知识库构建提示词与参考资料仓库。项目参考 Karpathy 的 LLM-Wiki 实践，将原始文章通过“场景 → 概念 → 实体”三层知识元模型组织起来，再使用严格的来源约束提示词进行知识萃取和知识问答。

本仓库不绑定特定模型、向量数据库或应用框架，适合作为个人知识库、团队知识工程和 LLM RAG/Agent 项目的方法论与提示词基础。

## 核心能力

- **三层知识元模型**：场景层描述要解决的问题，概念层描述可复用的思维加工单元，实体层描述具体的人、工具、框架或产品。
- **两轮知识萃取**：第一轮快速扫描并建立候选清单，第二轮补充定义、IPO、关系、来源和组合结构。
- **来源可追溯**：知识问答只能使用 `raw/` 中的原始文章，回答应标明对应来源，避免模型凭空补充外部知识。
- **结构化问答**：先理解元模型，再匹配场景和概念，定位原文，最后按原文风格组织答案。
- **可视化参考**：提供知识元模型、两轮萃取流程和三种概念建模方式的 HTML 架构图。

## 目录结构

```text
LLM-knowledgeBase/
├── raw/                                      # 原始文章库（知识问答的唯一内容来源）
│   ├── *.md
│   └── ...
├── 知识萃取规范指南.md                         # 建模规范、YAML Schema、去重规则、萃取提示词
├── 知识问答提示词.md                           # 基于元模型和原文的结构化问答提示词
├── 架构图1-知识元模型三层架构全景图.html         # 三层知识元模型可视化
├── 架构图2-两轮萃取流程图.html                   # 两轮知识萃取流程可视化
├── 架构图3-概念建模三种方式对比图.html           # IPO、分解、混合建模对比
├── 01-知识图谱参考.jpg                         # 知识图谱参考图
├── 02-知识问答参考.jpg                         # 知识问答参考图
├── LICENSE                                    # MIT License
└── README.md
```

当前仓库重点提供原始资料与提示词规范。指南中定义的 `scenarios.yaml`、`concepts.yaml`、`entities.yaml` 是后续知识建模的目标产物，可在独立的知识库工作目录中创建。

## 快速开始

### 1. 准备原始资料

将待处理的 Markdown、纯文本或其他可读资料放入 `raw/`。建议每篇文章使用一个文件，并保持稳定、可引用的文件名。`raw/` 是问答阶段的唯一事实来源。

### 2. 阅读建模规范

打开 [知识萃取规范指南](知识萃取规范指南.md)，重点阅读：

1. 三层知识元模型的边界和职责。
2. 场景、概念、实体的 YAML Schema。
3. 关系类型、去重和颗粒度控制规则。
4. 第一轮快速扫描和第二轮内容填充流程。
5. 最小质量检查清单。

建议在知识库目录中创建如下模型文件：

```text
model/
├── scenarios.yaml
├── concepts.yaml
└── entities.yaml
```

所有 `sources` 路径建议使用相对于知识库根目录的路径，例如 `raw/结构化思维.md`；跨层引用使用 `scenario://`、`concept://` 和 `entity://` 前缀。

### 3. 执行两轮萃取

第一轮用于快速扫描全部原文，输出候选场景、概念、实体及来源清单，并完成初步去重。第二轮按对象类型逐项填充：

- 概念：定义、IPO（输入/处理/输出）、子概念分解和关系。
- 实体：类别、定义、层级关系和与概念的关联。
- 场景：触发条件、目标、阶段以及阶段中调用的概念和实体。

每轮都应保留进度记录，并在写入模型文件后执行结构、引用、来源和重复项检查。

### 4. 使用知识问答提示词

打开 [知识问答提示词](知识问答提示词.md)，将它作为系统提示词或工作流提示词使用。每次回答遵循以下顺序：

```text
用户问题
  → 阅读场景/概念/实体模型
  → 匹配场景并构建回答纲要
  → 根据 sources 定位 raw 原文
  → 组织结构化答案并标注来源
```

问答提示词的关键约束是：不编造模型中不存在的概念，不引用 `raw/` 之外的知识，不以模型自身常识替代原文作者观点；当知识库没有覆盖问题时，应明确说明范围不足。

## 建模约定摘要

### 场景（Scenario）

场景回答“我要解决什么问题”，通常以“如何……”描述，包含触发条件、目标和按顺序组织的阶段。阶段通过 `uses` 调用概念或实体。

### 概念（Concept）

概念是可复用的思维加工单元，可以使用以下一种或多种方式建模：

- **IPO**：描述输入、处理步骤和输出。
- **Decomposition**：描述由哪些子概念组合完成。
- **Hybrid**：同时保留自身 IPO，并在关键步骤引用其他概念。

### 实体（Entity）

实体是可指认的具体对象，例如人物、软件、工具、书籍或具名框架。实体通常提供定义、分类和关系，不承担通用思维加工过程。

## 查看架构图

三张 HTML 图无需构建工具，直接用浏览器打开即可。它们是离线静态文件，不会请求外部服务：

- `架构图1-知识元模型三层架构全景图.html`
- `架构图2-两轮萃取流程图.html`
- `架构图3-概念建模三种方式对比图.html`

## 与 LLM 集成

本仓库只提供提示词、规范和资料，不包含 API 客户端或模型密钥。接入 OpenAI、兼容 OpenAI 协议的服务、本地模型或其他 LLM 平台时，请在调用方通过环境变量或密钥管理服务注入凭据，不要把密钥写入提示词、原始文章或 Git 历史。

推荐的调用拆分：

1. 使用萃取提示词生成或更新模型文件。
2. 使用程序或人工校验 YAML 结构、引用和来源路径。
3. 使用问答提示词读取模型和原文，生成带来源的回答。
4. 对回答执行来源覆盖率、事实一致性和格式检查。

## 内容边界与版权说明

`raw/` 中的文章可能包含原作者的观点、引用和第三方内容。使用者应自行确认这些材料的转载、再分发和商业使用权利。MIT 许可适用于本仓库作者拥有或有权许可的项目文件；第三方内容的权利不因本仓库采用 MIT License 而自动转移。

## License

本项目采用 [MIT License](LICENSE) 开源。您可以自由使用、复制、修改、合并、发布、分发和再许可本项目，但须保留版权声明和许可声明。

---

# English

## Overview

**LLM Knowledge Base** is a prompt and reference repository for building knowledge bases with large language models. Inspired by Karpathy's LLM-Wiki work, it organizes source articles with a three-layer knowledge meta-model: **scenarios → concepts → entities**, and applies source-constrained prompts for extraction and question answering.

The repository is model- and framework-agnostic. It does not require a specific LLM provider, vector database, RAG framework, or application runtime. It can be used as a methodology and prompt foundation for personal knowledge management, knowledge engineering, RAG, and agent projects.

## What Is Included

- **Three-layer meta-model**: scenarios define problems to solve, concepts represent reusable reasoning units, and entities represent concrete people, tools, frameworks, or products.
- **Two-pass extraction**: a fast inventory pass followed by a content-enrichment pass for definitions, IPO structures, relations, and sources.
- **Traceable answers**: answers must be grounded in the articles under `raw/` and should identify the supporting source files.
- **Structured Q&A**: understand the model first, match scenarios and concepts, locate source passages, and then compose the answer.
- **Offline diagrams**: HTML diagrams explain the model layers, extraction workflow, and concept modeling options.

## Repository Layout

```text
LLM-knowledgeBase/
├── raw/                                      # Source articles; the only Q&A content source
├── 知识萃取规范指南.md                         # Modeling rules, schema, deduplication, extraction prompts
├── 知识问答提示词.md                           # Source-constrained Q&A prompt
├── 架构图1-知识元模型三层架构全景图.html         # Three-layer model diagram
├── 架构图2-两轮萃取流程图.html                   # Two-pass extraction diagram
├── 架构图3-概念建模三种方式对比图.html           # IPO/decomposition comparison
├── 01-知识图谱参考.jpg                         # Knowledge graph reference image
├── 02-知识问答参考.jpg                         # Q&A reference image
├── LICENSE                                    # MIT License
└── README.md
```

The repository currently focuses on source material and prompt specifications. The guide defines `scenarios.yaml`, `concepts.yaml`, and `entities.yaml` as target model artifacts; create them in a separate knowledge-base workspace as needed.

## Quick Start

1. Put Markdown, text, or other readable source material in `raw/`. Keep one article per file and use stable filenames so sources remain traceable.
2. Read [知识萃取规范指南](知识萃取规范指南.md), especially the model boundaries, YAML schema, relation rules, deduplication rules, two-pass workflow, and quality checklist.
3. Create a model directory containing `scenarios.yaml`, `concepts.yaml`, and `entities.yaml`.
4. Run the extraction prompts with your preferred LLM, validate the generated YAML and source paths, and record progress between passes.
5. Use [知识问答提示词](知识问答提示词.md) as a system or workflow prompt for grounded Q&A.

The Q&A flow is:

```text
User question
  → Read scenario/concept/entity models
  → Match scenarios and build an answer outline
  → Locate passages through source fields
  → Compose a structured, source-traceable answer
```

The prompt explicitly forbids invented concepts, unsupported examples, and external knowledge that is not present in `raw/`. When the repository does not cover a question, the assistant should state that limitation instead of guessing.

## Integration and Security

This repository contains prompts, guidelines, diagrams, and source articles only. It does not contain an API client or an LLM credential. Inject provider credentials through environment variables or a secret manager at runtime; never place API keys in prompts, source files, commits, or issue posts.

## Content and Copyright

Articles under `raw/` may contain quotations, opinions, or third-party material. Users are responsible for verifying redistribution and commercial-use rights. The MIT License applies to files the repository author owns or is authorized to license; third-party rights are not transferred by this repository's MIT License.

## License

This project is released under the [MIT License](LICENSE). You may use, copy, modify, merge, publish, distribute, sublicense, and sell copies of the software, provided that the copyright and permission notices are retained.
