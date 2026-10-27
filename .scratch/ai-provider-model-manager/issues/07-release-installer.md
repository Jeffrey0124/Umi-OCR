# 构建 2.1.8 团队安装包

Status: ready-for-human

## 验收与构建

- 2026-10-27：用户确认 AI 配置功能已测试跑通，要求按既定流程生成安装包。
- 本轮仅构建已验收的 2.1.8，不改动产品代码或递增版本。
- 使用 `installer/build-team-installer.ps1` 生成专用默认配置后，调用本机 Inno Setup 7 编译；177.734 秒完成，退出码 0。
- 产物：`dist/Umi-OCR-Team-Setup_2.1.8.exe`，232,949,939 字节；产品版本 2.1.8，文件版本 2.1.8.0。
- SHA-256：`73431265187652b07e772116d86386231a6751b71c3d1c780a15c59de7c07f39`，同目录保存 `.exe.sha256`。
- 旧版 2.1.5 安装包移至 `.scratch/team-installer-secret-safety/retired-artifacts/`，避免与本次分发包混用，保留本地回溯能力。

## 验证

- `tests/test_team_settings_sanitizer.ps1`、`tests/test_team_installer.ps1` 通过。
- 专用配置仅含 44 个允许的地址、模型等字段；未包含本机密钥或 AI 配置集合。
- 按本地安全规格在内存读取现有配置中的密钥，检查生成配置及安装包原始字节的 UTF-8、UTF-16LE 表示，未发现命中；不输出或保存密钥值。
- 编译日志确认包含入口、新 AI 配置组件、按住查看密钥组件及 Python 连接器；未包含本机 `.settings`、`.pre_settings`、日志或临时文档目录。
- 未执行安装或解包；以上为构建产物、编译输入清单与原始字节校验。用户已有安装配置保持原样，安装脚本升级时保留原配置。
- 结构化记录：`../release-2.1.8.json`；编译日志：`logs/inno-team-installer-build.log`。

## Comments

- 2026-10-27：构建及产物检查完成，可交付安装包。
