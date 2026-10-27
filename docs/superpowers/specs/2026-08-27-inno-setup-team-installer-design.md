# Umi-OCR 团队版 Inno Setup 安装包设计

## 目标

使用本机 Inno Setup 7.0.2，将当前仓库中的最新 Umi-OCR 团队版本构建为可重复生成的 Windows 安装包。

## 安装行为

- 安装范围为当前 Windows 用户，不请求管理员权限。
- Inno Setup 使用 `PrivilegesRequired=lowest`。
- 默认安装目录为 `%LOCALAPPDATA%\Programs\Umi-OCR-Team`。
- 安装内容包括根目录的 `Umi-OCR.exe` 和完整的 `UmiOCR-data` 目录。
- 创建桌面快捷方式和开始菜单快捷方式。
- 安装完成后不自动启动 Umi-OCR。
- 使用 Inno Setup 标准卸载器注册到 Windows 应用列表。

## 升级行为

- 使用固定 `AppId` 识别已有团队版安装。
- 覆盖升级程序文件和资源文件。
- 升级时保留 `UmiOCR-data\.settings`。
- 全新安装时写入仓库提供的默认 `.settings`（如果该文件存在）。

## 构建输入与输出

- 应用版本：`2.1.5`。
- 构建输入：当前工作树中的 `Umi-OCR.exe` 与 `UmiOCR-data`。
- Inno Setup 脚本：`installer/team-installer.iss`。
- 编译器：`C:\Program Files\Inno Setup 7\ISCC.exe`。
- 输出文件：`dist/Umi-OCR-Team-Setup_2.1.5.exe`。

## 实现约束

- 不继续包装现有 IExpress/PowerShell 安装流程。
- 不把 `dist`、`.git`、测试文件或仓库文档放入安装包。
- 安装脚本应支持从仓库根目录稳定编译。
- 构建失败时不得把旧安装包误报为新产物。

## 验证

- `ISCC.exe` 编译退出码为 0。
- 输出文件的修改时间来自本次构建。
- 安装包版本信息为 `2.1.5`。
- 使用 Inno Setup 解包或静默安装到隔离目录，确认包含 `Umi-OCR.exe` 和 `UmiOCR-data/main.py`。
- 确认安装脚本未配置安装完成后自动启动程序。

## 2026-08-28 安全修订

- 禁止将本机 `UmiOCR-data/.settings` 直接作为安装包输入。
- 构建时通过 `installer/prepare-team-settings.ps1` 生成 `installer/generated/team.settings`。
- 生成配置仅保留 API 地址和模型名称字段，不保留密钥、令牌、密码、凭据或其他用户设置。
- 递归文件输入必须排除 `.pre_settings`、`logs` 和 `temp_doc` 等用户运行时数据。
- 必须通过 `installer/build-team-installer.ps1` 构建团队安装包。
- 升级已有安装时继续保留用户现有的 `.settings`。
