## Agent skills

### Issue tracker

问题和规格说明使用本地 Markdown，存放在 `.scratch/` 目录。详见 `docs/agents/issue-tracker.md`。

### Triage labels

使用默认的五个 Triage 标签：`needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix`。详见 `docs/agents/triage-labels.md`。

### Domain docs

这是一个 single-context 仓库，使用根目录下的 `CONTEXT.md` 和 `docs/adr/`。详见 `docs/agents/domain.md`。

### Versioning

每次完成一轮代码改动，版本号的 patch 加 1；同步 `UmiOCR-data/about.json`、安装脚本中的版本和产物名及对应版本检查。一次需求内的编辑和测试修复合并为一次递增。
