# Umi-OCR Team Inno Setup Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the current Umi-OCR team workspace as a repeatable per-user Windows installer with Inno Setup 7.0.2.

**Architecture:** A single Inno Setup script packages `Umi-OCR.exe` and `UmiOCR-data` directly. A PowerShell contract test validates installer behavior, while the compiler log and PE metadata validate the artifact without installing it.

**Tech Stack:** Inno Setup 7.0.2, PowerShell 5.1, Git

## Global Constraints

- Compile with `C:\Program Files\Inno Setup 7\ISCC.exe`.
- Use version `2.1.5` and `PrivilegesRequired=lowest`.
- Install to `{localappdata}\Programs\Umi-OCR-Team`.
- Preserve `UmiOCR-data\.settings` during upgrades.
- Create desktop and Start-menu shortcuts.
- Do not launch the application after installation.
- Output `dist/Umi-OCR-Team-Setup_2.1.5.exe`.
- Do not create a Git commit unless explicitly requested.

## File Structure

- Create `installer/team-installer.iss`: installer definition.
- Create `tests/test_team_installer.ps1`: contract checks.
- Generate `logs/inno-team-installer-build.log`: compiler evidence.
- Generate `dist/Umi-OCR-Team-Setup_2.1.5.exe`: final artifact.

---

### Task 1: Add Installer Contract Test

**Files:**
- Create/Test: `tests/test_team_installer.ps1`

**Interfaces:**
- Consumes: repository root resolved from the test location.
- Produces: exit code `0` when the `.iss` satisfies the approved contract; otherwise throws.

- [ ] **Step 1: Write the failing contract test**

```powershell
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$installerScript = Join-Path $repoRoot "installer\team-installer.iss"
if (-not (Test-Path -LiteralPath $installerScript)) {
    throw "Installer script is missing: $installerScript"
}
$content = Get-Content -LiteralPath $installerScript -Raw
$requiredPatterns = @(
    'AppId=\{\{BD035C23-75A7-4062-9C82-E176CEBE847F\}',
    'AppVersion=2.1.5',
    'DefaultDirName=\{localappdata\}\\Programs\\Umi-OCR-Team',
    'PrivilegesRequired=lowest',
    'OutputDir=\.\.\\dist',
    'OutputBaseFilename=Umi-OCR-Team-Setup_2.1.5',
    'Source: "\.\.\\Umi-OCR\.exe"; DestDir: "\{app\}"',
    'Source: "\.\.\\UmiOCR-data\\\*"; DestDir: "\{app\}\\UmiOCR-data"',
    'Excludes: "\.settings"',
    'onlyifdoesntexist',
    'Name: "\{autodesktop\}\\Umi-OCR Team"',
    'Name: "\{group\}\\Umi-OCR Team"'
)
foreach ($pattern in $requiredPatterns) {
    if ($content -notmatch $pattern) { throw "Missing installer requirement: $pattern" }
}
if ($content -match '(?m)^\[Run\]\s*$') {
    throw "Installer must not define a [Run] section."
}
Write-Output "Installer contract passed."
```

- [ ] **Step 2: Run the test and verify failure**

Run: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tests\test_team_installer.ps1`

Expected: non-zero exit with `Installer script is missing`.

---

### Task 2: Implement Inno Setup Script

**Files:**
- Create: `installer/team-installer.iss`
- Test: `tests/test_team_installer.ps1`

**Interfaces:**
- Consumes: `Umi-OCR.exe`, `UmiOCR-data`, and the application icon.
- Produces: the `Umi-OCR-Team-Setup_2.1.5` build definition.

- [ ] **Step 1: Create the installer definition**

```iss
#define MyAppName "Umi-OCR Team"
#define MyAppVersion "2.1.5"
#define MyAppExeName "Umi-OCR.exe"

[Setup]
AppId={{BD035C23-75A7-4062-9C82-E176CEBE847F}
AppName={#MyAppName}
AppVersion=2.1.5
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Umi-OCR Team
DefaultDirName={localappdata}\Programs\Umi-OCR-Team
DefaultGroupName=Umi-OCR Team
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir=..\dist
OutputBaseFilename=Umi-OCR-Team-Setup_2.1.5
SetupIconFile=..\UmiOCR-data\qt_res\images\icons\umiocr.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=2.1.5.0
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Files]
Source: "..\Umi-OCR.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\UmiOCR-data\*"; DestDir: "{app}\UmiOCR-data"; Excludes: ".settings"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\UmiOCR-data\.settings"; DestDir: "{app}\UmiOCR-data"; Flags: ignoreversion onlyifdoesntexist skipifsourcedoesntexist

[Icons]
Name: "{group}\Umi-OCR Team"; Filename: "{app}\Umi-OCR.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Umi-OCR Team"; Filename: "{app}\Umi-OCR.exe"; WorkingDir: "{app}"
```

- [ ] **Step 2: Run the contract test**

Run: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tests\test_team_installer.ps1`

Expected: exit code `0` and `Installer contract passed.`

- [ ] **Step 3: Compile the script**

Run: `& 'C:\Program Files\Inno Setup 7\ISCC.exe' '.\installer\team-installer.iss'`

Expected: exit code `0` and a new `dist\Umi-OCR-Team-Setup_2.1.5.exe`.

---

### Task 3: Verify Final Installer Artifact

**Files:**
- Generate: `logs/inno-team-installer-build.log`
- Generate: `dist/Umi-OCR-Team-Setup_2.1.5.exe`
- Test: `tests/test_team_installer.ps1`

**Interfaces:**
- Consumes: the `.iss` and Inno Setup compiler output.
- Produces: verified metadata, SHA-256 hash, and packaged-entry evidence.

- [ ] **Step 1: Rebuild with a captured compiler log**

```powershell
$output = '.\dist\Umi-OCR-Team-Setup_2.1.5.exe'
if (Test-Path -LiteralPath $output) {
    Remove-Item -LiteralPath $output -Force
}
& 'C:\Program Files\Inno Setup 7\ISCC.exe' '.\installer\team-installer.iss' 2>&1 |
    Tee-Object -FilePath '.\logs\inno-team-installer-build.log'
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed with exit code $LASTEXITCODE."
}
```

Expected: exit code `0`; the artifact is recreated during this command.

- [ ] **Step 2: Verify required entries in the compiler log**

```powershell
$log = Get-Content -LiteralPath '.\logs\inno-team-installer-build.log' -Raw
foreach ($entry in @('Umi-OCR.exe', 'UmiOCR-data\main.py')) {
    if ($log -notmatch [regex]::Escape($entry)) {
        throw "Compiler log does not include $entry"
    }
}
```

Expected: exit code `0` with no exception.

- [ ] **Step 3: Verify file metadata and hash**

```powershell
$artifact = Get-Item -LiteralPath '.\dist\Umi-OCR-Team-Setup_2.1.5.exe'
if ($artifact.Length -le 0) { throw "Installer artifact is empty." }
if ($artifact.VersionInfo.ProductVersion -ne '2.1.5') {
    throw "Unexpected product version: $($artifact.VersionInfo.ProductVersion)"
}
Get-FileHash -LiteralPath $artifact.FullName -Algorithm SHA256
```

Expected: a non-empty installer, product version `2.1.5`, and a SHA-256 hash.

- [ ] **Step 4: Run the final contract test**

Run: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tests\test_team_installer.ps1`

Expected: exit code `0` and `Installer contract passed.`

## 2026-08-28 Security Amendment

This amendment supersedes every direct `ISCC.exe` command and every reference to packaging `UmiOCR-data/.settings` in the earlier tasks.

- Generate `installer/generated/team.settings` with `installer/prepare-team-settings.ps1`.
- Retain only API address and model-name keys.
- Exclude `.pre_settings`, `logs`, and `temp_doc` from recursive installer inputs.
- Build only with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\installer\build-team-installer.ps1`.
- Require `tests/test_team_settings_sanitizer.ps1` and `tests/test_team_installer.ps1` to pass before distribution.
