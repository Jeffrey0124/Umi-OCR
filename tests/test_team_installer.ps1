$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$installerScript = Join-Path $repoRoot "installer\team-installer.iss"

if (-not (Test-Path -LiteralPath $installerScript)) {
    throw "Installer script is missing: $installerScript"
}

$content = Get-Content -LiteralPath $installerScript -Raw
$about = Get-Content -LiteralPath (Join-Path $repoRoot "UmiOCR-data\about.json") -Raw | ConvertFrom-Json
$appVersion = "$($about.version.major).$($about.version.minor).$($about.version.patch)"
$builder = Get-Content -LiteralPath (Join-Path $repoRoot "installer\build-team-installer.ps1") -Raw
if (-not $content.Contains("AppVersion=$appVersion") -or
    -not $content.Contains("VersionInfoVersion=$appVersion.0") -or
    -not $content.Contains("OutputBaseFilename=Umi-OCR-Team-Setup_$appVersion") -or
    -not $builder.Contains("Umi-OCR-Team-Setup_$appVersion.exe")) {
    throw "Application, installer and build output versions must match: $appVersion"
}
$requiredPatterns = @(
    'AppId=\{\{BD035C23-75A7-4062-9C82-E176CEBE847F\}',
    'AppVersion=2.1.8',
    'DefaultDirName=\{localappdata\}\\Programs\\Umi-OCR-Team',
    'PrivilegesRequired=lowest',
    'OutputDir=\.\.\\dist',
    'OutputBaseFilename=Umi-OCR-Team-Setup_2.1.8',
    'Source: "\.\.\\Umi-OCR\.exe"; DestDir: "\{app\}"',
    'Source: "\.\.\\UmiOCR-data\\\*"; DestDir: "\{app\}\\UmiOCR-data"',
    'Excludes: "\.settings,\.pre_settings,logs\\\*,temp_doc\\\*"',
    'Source: "generated\\team\.settings"; DestDir: "\{app\}\\UmiOCR-data"; DestName: "\.settings"',
    'onlyifdoesntexist',
    'Name: "\{autodesktop\}\\Umi-OCR Team"',
    'Name: "\{group\}\\Umi-OCR Team"'
)

foreach ($pattern in $requiredPatterns) {
    if ($content -notmatch $pattern) {
        throw "Missing installer requirement: $pattern"
    }
}

if ($content -match 'Source:\s*"\.\.\\UmiOCR-data\\\.settings"') {
    throw "Installer must not package the live UmiOCR-data\.settings file."
}

if ($content -match 'Source:\s*"\.\.\\UmiOCR-data\\\.pre_settings"') {
    throw "Installer must not package the live UmiOCR-data\.pre_settings file."
}

if ($content -match '(?m)^\[Run\]\s*$') {
    throw "Installer must not define a [Run] section."
}

Write-Output "Installer contract passed."
