# Generate text output for portfolio screenshots and demo scripts.
# Run after bootstrap + createsuperuser + runserver (optional for API section).
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .\.venv\Scripts\Activate.ps1
}

$outDir = "docs\screenshots"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "Capturing CLI demo transcript..."
$cli = @(
    @("create", "demo_flag", "--env", "production", "--default", "false"),
    @("enable", "demo_flag", "--env", "production"),
    @("rollout", "demo_flag", "100", "--env", "production"),
    @("list", "--env", "production"),
    @("eval", "demo_flag", "--env", "production", "--user", "user_123"),
    @("env-list")
)

$transcript = @()
foreach ($args in $cli) {
    $buffer = New-Object System.IO.StringWriter
    python manage.py flagctl @args 2>&1 | ForEach-Object { $buffer.WriteLine($_) }
    $transcript += "`$ python manage.py flagctl $($args -join ' ')"
    $transcript += $buffer.ToString()
    $transcript += ""
}

$transcriptPath = Join-Path $outDir "cli-demo.txt"
$transcript -join "`n" | Set-Content -Encoding utf8 $transcriptPath
Write-Host "Wrote $transcriptPath"
Write-Host "Capture PNG screenshots from: Django admin, this CLI output, and snapshot JSON in the browser."
