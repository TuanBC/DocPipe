# Start the full local stack (no containers): embedding shim, LiteLLM gateway, OpenViking, docpipe web UI.
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File scripts/start_services.ps1  [-NoWeb]
# Logs: data/logs/*.log. Stop everything: scripts/start_services.ps1 -Stop
param([switch]$NoWeb, [switch]$Stop)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force data/logs | Out-Null
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
if (-not $env:LITELLM_MASTER_KEY) { $env:LITELLM_MASTER_KEY = "sk-local-dev" }

$ports = [ordered]@{ embed = 8081; litellm = 4010; openviking = 1933; web = 8800 }

function Test-Port($p) { [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) }

if ($Stop) {
    foreach ($p in $ports.Values) {
        Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue |
            ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue; "stopped :$p" }
    }
    return
}

function Start-Svc($name, $port, $exe, $argList) {
    if (Test-Port $port) { "$name already listening on :$port"; return }
    Start-Process -FilePath $exe -ArgumentList $argList -WindowStyle Hidden `
        -RedirectStandardOutput "data/logs/$name.log" -RedirectStandardError "data/logs/$name.err.log" | Out-Null
    "$name starting on :$port (log data/logs/$name.log)"
}

# 1. Embeddings for OpenViking (GitHub Copilot text-embedding-3-small via the LiteLLM SDK sign-in)
Start-Svc "embed" $ports.embed "uv" @("run", "--group", "gateway", "uvicorn", "services.sdk_embed_server:app", "--host", "127.0.0.1", "--port", "$($ports.embed)")
# 2. LiteLLM gateway (alias 'luna' for OpenViking summaries, 'embed' for embeddings)
Start-Svc "litellm" $ports.litellm "uv" @("run", "--group", "gateway", "litellm", "--config", "deploy/litellm_config.yaml", "--port", "$($ports.litellm)")
# 3. OpenViking server (installed with: uv tool install --python 3.13 openviking)
Start-Svc "openviking" $ports.openviking "openviking-server" @("--config", "deploy/openviking/ov.native.conf")
# 4. docpipe web UI
if (-not $NoWeb) {
    Start-Svc "web" $ports.web "uv" @("run", "--group", "gateway", "python", "-m", "docpipe", "serve", "--port", "$($ports.web)")
}

"waiting for services (OpenViking takes ~60 s to import on this machine)..."
$deadline = (Get-Date).AddMinutes(4)
while ((Get-Date) -lt $deadline) {
    $want = $ports.GetEnumerator() | Where-Object { -not ($NoWeb -and $_.Key -eq "web") }
    if (-not ($want | Where-Object { -not (Test-Port $_.Value) })) { break }
    Start-Sleep -Seconds 3
}
$ports.GetEnumerator() | ForEach-Object { "{0,-11} :{1}  {2}" -f $_.Key, $_.Value, $(if (Test-Port $_.Value) { "up" } else { "DOWN (see data/logs)" }) }
if (-not $NoWeb) { "UI: http://127.0.0.1:$($ports.web)" }
