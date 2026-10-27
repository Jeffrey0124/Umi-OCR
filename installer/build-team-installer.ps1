[CmdletBinding()]
param(
    [string]$SourceSettings,
    [string]$CompilerPath = "C:\Program Files\Inno Setup 7\ISCC.exe"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $SourceSettings) {
    $SourceSettings = Join-Path $repoRoot "UmiOCR-data\.settings"
}

$sanitizer = Join-Path $PSScriptRoot "prepare-team-settings.ps1"
$generatedSettings = Join-Path $PSScriptRoot "generated\team.settings"
$installerScript = Join-Path $PSScriptRoot "team-installer.iss"
$artifact = Join-Path $repoRoot "dist\Umi-OCR-Team-Setup_2.1.8.exe"
$buildLog = Join-Path $repoRoot "logs\inno-team-installer-build.log"

if (-not (Test-Path -LiteralPath $CompilerPath)) {
    throw "Inno Setup compiler is missing: $CompilerPath"
}

$sanitizerOutput = & $sanitizer -SourcePath $SourceSettings -DestinationPath $generatedSettings
$beforeBuild = if (Test-Path -LiteralPath $artifact) {
    (Get-Item -LiteralPath $artifact).LastWriteTimeUtc
} else {
    [datetime]::MinValue
}

$buildOutput = & $CompilerPath $installerScript 2>&1
$compilerExitCode = $LASTEXITCODE
$utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllLines($buildLog, [string[]]$buildOutput, $utf8WithoutBom)

if ($compilerExitCode -ne 0) {
    $buildOutput | Select-Object -Last 40
    throw "Inno Setup compilation failed with exit code $compilerExitCode."
}

$artifactInfo = Get-Item -LiteralPath $artifact
if ($artifactInfo.LastWriteTimeUtc -le $beforeBuild) {
    throw "Installer artifact timestamp was not updated."
}

$sanitizerOutput
Write-Output "BuildArtifact=$($artifactInfo.FullName)"
Write-Output "ProductVersion=$($artifactInfo.VersionInfo.ProductVersion.Trim())"
