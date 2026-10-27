# 问题跟踪：本地 Markdown

本仓库的问题和规格说明以 Markdown 文件形式存放在 `.scratch/` 目录中。

## 约定

- 每个功能使用一个目录：`.scratch/<feature-slug>/`
- 规格说明文件为：`.scratch/<feature-slug>/spec.md`
- 实现问题每个工单使用一个文件：`.scratch/<feature-slug>/issues/<NN>-<slug>.md`
- 工单编号从 `01` 开始，不使用合并后的单一工单文件
- Triage 状态记录在工单文件顶部附近的 `Status:` 行中
- 评论和对话历史追加到文件底部的 `## Comments` 标题下

## 当技能要求“发布到问题跟踪系统”时

在 `.scratch/<feature-slug>/` 下创建文件；如果目录不存在则先创建。

## 当技能要求“获取相关工单”时

读取指定路径下的文件。通常用户会直接提供文件路径或工单编号。

## Wayfinding 操作

`/wayfinder` 使用一个主图文件和多个子工单文件：

- **主图**：`.scratch/<effort>/map.md`
  - 保存 Notes、Decisions-so-far 和 Fog 内容
- **子工单**：`.scratch/<effort>/issues/NN-<slug>.md`
  - 编号从 `01` 开始
  - 正文包含待回答的问题
  - 使用 `Type:` 行记录工单类型：`research`、`prototype`、`grilling` 或 `task`
  - 使用 `Status:` 行记录状态：`claimed` 或 `resolved`
- **阻塞关系**：在文件顶部附近使用 `Blocked by: NN, NN`
- 当它列出的所有工单都处于 `resolved` 状态时，该工单解除阻塞
- **Frontier**：扫描 `.scratch/<effort>/issues/`，找到已开放、未阻塞且未认领的工单；优先处理编号最小的工单
- **Claim**：设置 `Status: claimed` 并保存
- **Resolve**：在 `## Answer` 标题下追加答案，设置 `Status: resolved`，然后将上下文指针追加到 `map.md` 的 Decisions-so-far 中
