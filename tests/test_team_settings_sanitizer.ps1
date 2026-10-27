$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$sanitizer = Join-Path $repoRoot "installer\prepare-team-settings.ps1"

if (-not (Test-Path -LiteralPath $sanitizer)) {
    throw "Settings sanitizer is missing: $sanitizer"
}

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("Umi-OCR-Team-Settings-Test-" + [guid]::NewGuid().ToString("N"))
$source = Join-Path $tempRoot "source.settings"
$destination = Join-Path $tempRoot "generated\team.settings"
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    @"
[Global]
ocr.AIOCR.custom_openai_api_base=https://example.invalid/v1
ocr.AIOCR.custom_openai_api_key=fake-secret-value
ocr.AIOCR.yaoji_api_key=fake-builtin-secret
ocr.AIOCR.custom_openai_model=vision-model
ocr.AIOCR.a_profiles={"version":1,"profiles":[{"api_key":"fake-profile-secret","api_base":"https://example.invalid/v1","model":"vision-model"}]}
ocr.AIOCR.z_proxy_url=http://proxy.invalid:8080
ui.theme=Moonlight

[Other]
service.endpoint=https://endpoint.invalid
service.password=fake-password
"@ | Set-Content -LiteralPath $source -Encoding UTF8

    & $sanitizer -SourcePath $source -DestinationPath $destination
    $content = Get-Content -LiteralPath $destination -Raw

    foreach ($required in @(
        "ocr.AIOCR.custom_openai_api_base=https://example.invalid/v1",
        "ocr.AIOCR.custom_openai_model=vision-model",
        "ocr.AIOCR.z_proxy_url=http://proxy.invalid:8080",
        "service.endpoint=https://endpoint.invalid"
    )) {
        if (-not $content.Contains($required)) { throw "Missing retained setting: $required" }
    }

    foreach ($forbidden in @("api_key", "fake-secret-value", "fake-builtin-secret", "password", "fake-password", "ui.theme", "a_profiles", "fake-profile-secret")) {
        if ($content -match [regex]::Escape($forbidden)) { throw "Sanitized settings contain forbidden content: $forbidden" }
    }

    Write-Output "Settings sanitizer contract passed."
}
finally {
    $resolvedTemp = [IO.Path]::GetFullPath($tempRoot)
    $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if ($resolvedTemp.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolvedTemp)) {
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force
    }
}
