# Team installer secret safety

Status: ready-for-human

## Problem

The 2.1.5 team installer directly packaged the local `UmiOCR-data/.settings` file. That file can contain API credentials, so distributing the installer could disclose a live key.

## Requirements

- Never use the live `UmiOCR-data/.settings` file as an Inno Setup source.
- Exclude `UmiOCR-data/.pre_settings`, `UmiOCR-data/logs`, and `UmiOCR-data/temp_doc` from installer inputs.
- Generate a dedicated installer settings file at build time.
- Retain only API address and model-name keys.
- Exclude API keys, tokens, secrets, passwords, credentials, authorization values, and unrelated user preferences.
- Preserve an existing installed `.settings` file during upgrades.
- Build through `installer/build-team-installer.ps1`.
- Remove obsolete distribution artifacts that may contain the previous settings payload.

## Verification

- A fixture test proves the sanitizer retains address/model keys and rejects secret and unrelated keys.
- The installer contract test rejects references to the live settings file.
- The generated settings file is compared in memory against every non-empty local secret value.
- The installer binary is scanned for the UTF-8 and UTF-16LE forms of every non-empty local secret value.
- The Inno compiler log must show `installer/generated/team.settings` and must not show live settings, pre-settings, logs, or temporary documents.
