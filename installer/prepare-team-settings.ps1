[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourcePath,

    [Parameter(Mandatory = $true)]
    [string]$DestinationPath
)

$ErrorActionPreference = "Stop"

$sourceFullPath = [IO.Path]::GetFullPath($SourcePath)
$destinationFullPath = [IO.Path]::GetFullPath($DestinationPath)
if (-not (Test-Path -LiteralPath $sourceFullPath)) {
    throw "Source settings file is missing: $sourceFullPath"
}

$allowedKeyPattern = '(?i)(api_base|base_url|endpoint|address|model|url)$'
$sensitiveKeyPattern = '(?i)(api.?key|token|secret|password|credential|authorization)'
$outputLines = New-Object 'System.Collections.Generic.List[string]'
$currentSection = ""
$sectionWritten = $false
$retainedCount = 0

foreach ($line in Get-Content -LiteralPath $sourceFullPath) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith(';') -or $trimmed.StartsWith('#')) {
        continue
    }

    if ($trimmed -match '^\[(.+)\]$') {
        $currentSection = $matches[1]
        $sectionWritten = $false
        continue
    }

    $separatorIndex = $line.IndexOf('=')
    if ($separatorIndex -lt 0) {
        continue
    }

    $key = $line.Substring(0, $separatorIndex).Trim()
    if ($key -match $sensitiveKeyPattern -or $key -notmatch $allowedKeyPattern) {
        continue
    }

    if ($currentSection -and -not $sectionWritten) {
        if ($outputLines.Count -gt 0) {
            $outputLines.Add("")
        }
        $outputLines.Add("[$currentSection]")
        $sectionWritten = $true
    }

    $outputLines.Add($line)
    $retainedCount++
}

$destinationDirectory = Split-Path -Parent $destinationFullPath
New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
$utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllLines($destinationFullPath, $outputLines, $utf8WithoutBom)

foreach ($line in Get-Content -LiteralPath $destinationFullPath) {
    $separatorIndex = $line.IndexOf('=')
    if ($separatorIndex -lt 0) {
        continue
    }
    $key = $line.Substring(0, $separatorIndex).Trim()
    if ($key -match $sensitiveKeyPattern -or $key -notmatch $allowedKeyPattern) {
        throw "Generated settings contain a forbidden key: $key"
    }
}

Write-Output "RetainedSettings=$retainedCount"
