# Start the Automated Analyst on this machine - the one command a person needs.
#
#   Double-click start.cmd in the project folder, or run:  powershell -File tools\start.ps1
#
# Everything a first start needs, in order, and nothing it does not:
#   1. finds uv (installed, or as `python -m uv`) - it never downloads anything
#   2. installs the project's packages if they are missing or out of date
#   3. creates .env from .env.example if there is none, generates the mask vault key if it is
#      blank, and asks once for the Anthropic API key - typed into this window, stored only in
#      .env on this machine, never shown
#   4. makes the inbox and outbox folders
#   5. checks what is wired, starts the server, and opens the dashboard in the browser
#
# It changes nothing that is already set. Run it again any time; a second run just starts.

param(
    [int]$Port = 8000,
    [switch]$NoBrowser,
    [switch]$SetupOnly,   # prepare everything, start nothing
    [switch]$NoPrompt     # never ask for the API key (for scripted use)
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Say($text) { Write-Host "  $text" }
function Stop-With($text) {
    Write-Host ""
    Write-Host "  $text" -ForegroundColor Yellow
    Write-Host ""
    if (-not $NoPrompt) { Read-Host "  Press Enter to close" | Out-Null }
    exit 1
}

Write-Host ""
Write-Host "  Automated Analyst" -ForegroundColor Cyan
Write-Host ""

# 1. uv --------------------------------------------------------------------------------
$uv = $null
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uv = @('uv')
} else {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) {
        & python -m uv --version *> $null
        if ($LASTEXITCODE -eq 0) { $uv = @('python', '-m', 'uv') }
    }
}
if (-not $uv) {
    Stop-With "uv is not installed. Install it once (https://docs.astral.sh/uv/), or ask IT for it, then run this again."
}
function Invoke-Uv { param([Parameter(ValueFromRemainingArguments = $true)]$rest)
    if ($uv.Count -eq 1) { & $uv[0] @rest } else { & $uv[0] $uv[1] $uv[2] @rest }
}

# 2. packages --------------------------------------------------------------------------
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
$lock = Join-Path $root 'uv.lock'
$stale = (-not (Test-Path $venvPython)) -or ((Get-Item $lock).LastWriteTime -gt (Get-Item $venvPython).LastWriteTime)
if ($stale) {
    Say "Installing the project's packages (first start, or they changed)..."
    Invoke-Uv sync
    if ($LASTEXITCODE -ne 0) { Stop-With "Installing the packages failed - the lines above say why." }
}

# 3. .env ------------------------------------------------------------------------------
$envFile = Join-Path $root '.env'
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $root '.env.example') $envFile
    Say "Created .env from .env.example."
}
$lines = [System.Collections.Generic.List[string]](Get-Content $envFile -Encoding UTF8)

function Get-Setting($name) {
    foreach ($line in $lines) {
        if ($line -match "^\s*$name\s*=(.*)$") { return $Matches[1].Trim().Trim('"').Trim("'") }
    }
    return $null
}
function Set-Setting($name, $value) {
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*#?\s*$name\s*=") { $lines[$i] = "$name=$value"; return }
    }
    $lines.Add("$name=$value")
}

$changed = $false
if (-not (Get-Setting 'AA_VAULT_KEY')) {
    $key = & $venvPython -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    Set-Setting 'AA_VAULT_KEY' $key.Trim()
    $changed = $true
    Say "Generated the mask vault key. It lives only in .env - back .env up; losing the key loses the vault."
}

$apiKey = Get-Setting 'ANTHROPIC_API_KEY'
$hasKey = [bool]$apiKey -and $apiKey -ne 'sk-ant-...'
if (-not $hasKey -and $NoPrompt) {
    Say "No Anthropic API key in .env yet - runs will stop at the model step until one is added."
} elseif (-not $hasKey) {
    Write-Host ""
    Say "Paste your Anthropic API key (it is not shown), or press Enter to start without one."
    Say "Without a key, runs stop at the model step - setup, files and the dashboards all still work."
    $secure = Read-Host "  API key" -AsSecureString
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    if ($plain) {
        Set-Setting 'ANTHROPIC_API_KEY' $plain.Trim()
        Set-Setting 'AA_LLM_ADAPTER' 'anthropic_messages'
        $changed = $true
        Say "Key saved to .env, and the model adapter set to the Anthropic API."
    }
    $plain = $null
} elseif ((Get-Setting 'AA_LLM_ADAPTER') -eq 'fake') {
    Say "Note: .env has an API key but AA_LLM_ADAPTER=fake - runs will not reach the model. Set it to anthropic_messages to use the key."
}
if ($changed) { [IO.File]::WriteAllLines($envFile, $lines, (New-Object System.Text.UTF8Encoding $false)) }

# 4. folders ---------------------------------------------------------------------------
foreach ($name in @('AA_INBOX_ROOT', 'AA_OUTBOX_ROOT')) {
    $dir = Get-Setting $name
    if ($dir) {
        $full = [IO.Path]::GetFullPath($(if ([IO.Path]::IsPathRooted($dir)) { $dir } else { Join-Path $root $dir }))
        if (-not (Test-Path $full)) { New-Item -ItemType Directory -Path $full | Out-Null; Say "Made $full" }
    }
}

# The template workbooks are generated, and templates/*.xlsx is gitignored - so a clone
# has the schemas and none of the files. Without them every engagement resolves to an
# unregistered template, preflight refuses to activate anything, and the message tells a
# non-developer to "bind a fallthrough at a higher layer". Build what is missing.
$anyTemplate = Join-Path $root 'templates\Chartwell_Input_Help_v1.xlsx'
if (-not (Test-Path $anyTemplate)) {
    Say "Building the template workbooks (they are generated, not committed)."
    & $venvPython (Join-Path $root 'tools\synthesize_templates.py')
    if ($LASTEXITCODE -ne 0) { Say "Could not build the templates - see the error above." }
}

if ($SetupOnly) {
    Write-Host ""
    Say "Ready. Start it with start.cmd."
    & $venvPython (Join-Path $root 'tools\serve.py') --check
    exit $LASTEXITCODE
}

# 5. start -----------------------------------------------------------------------------
Write-Host ""
Say "Starting on http://127.0.0.1:$Port/  (close this window, or press Ctrl+C, to stop it)"
Write-Host ""
if (-not $NoBrowser) {
    $url = "http://127.0.0.1:$Port/"
    Start-Job -ArgumentList $url -ScriptBlock {
        param($url)
        for ($i = 0; $i -lt 60; $i++) {
            try { Invoke-WebRequest -UseBasicParsing -Uri ($url + 'api/runs') -TimeoutSec 2 | Out-Null; Start-Process $url; return }
            catch { Start-Sleep -Seconds 1 }
        }
    } | Out-Null
}
& $venvPython (Join-Path $root 'tools\serve.py') --port $Port
