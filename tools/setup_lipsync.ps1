# Setup Lip-Sync Engines (MuseTalk / LatentSync)
# Usage: .\tools\setup_lipsync.ps1

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$toolsDir = Join-Path $projectRoot 'tools'

Write-Host "=== Lip-Sync Engine Setup ==="

# MuseTalk
$museTalkDir = Join-Path $toolsDir 'MuseTalk'
if (-not (Test-Path $museTalkDir)) {
    Write-Host "Cloning MuseTalk..."
    git clone https://github.com/TMElyralab/MuseTalk.git $museTalkDir
    Write-Host "MuseTalk cloned. Install dependencies: pip install -r $museTalkDir\requirements.txt"
} else {
    Write-Host "MuseTalk already exists at $museTalkDir"
}

# LatentSync
$latentSyncDir = Join-Path $toolsDir 'LatentSync'
if (-not (Test-Path $latentSyncDir)) {
    Write-Host "Cloning LatentSync..."
    git clone https://github.com/bytedance/LatentSync.git $latentSyncDir
    Write-Host "LatentSync cloned. Install dependencies: pip install -r $latentSyncDir\requirements.txt"
} else {
    Write-Host "LatentSync already exists at $latentSyncDir"
}

Write-Host ""
Write-Host "=== Setup Complete ==="
Write-Host "Set environment variables in .env:"
Write-Host "  AIDUB_MUSETALK_COMMAND=python -m musetalk.inference --video {video} --audio {audio} --output {output}"
Write-Host "  AIDUB_LATENTSYNC_COMMAND=python LatentSync/inference.py --video {video} --audio {audio} --output {output}"
Write-Host ""
Write-Host "MuseTalk repo: https://github.com/TMElyralab/MuseTalk"
Write-Host "LatentSync repo: https://github.com/bytedance/LatentSync"
