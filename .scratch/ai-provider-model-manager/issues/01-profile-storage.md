# 配置存储与任务快照

Status: ready-for-human

实现版本化配置、旧键迁移、页面覆盖及队列提交时快照；保留旧字段兼容，防止任务和页面之间串用配置。

## Comments

- 实现位于 `profile_store.py`、AIOCR Api 和 MissionOCR；验证记录见规格及自动化测试。
- 2026-10-27：已验证迁移幂等、同服务商多配置、QSettings 重载、页面隔离、队列及整份文档快照；保存等待活动和暂停的 OCR / 文档任务清空后重载引擎。
