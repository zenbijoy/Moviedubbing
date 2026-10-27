# Setup RVC v2 Voice Cloning Models
# Usage: .\tools\setup_rvc.ps1

$ErrorActionPreference = 'Stop'

Write-Host "=== RVC v2 Model Setup ==="

Write-Host "RVC v2 requires:"
Write-Host "  1. A .pth model file (trained voice model)"
Write-Host "  2. An .index file (FAISS index for retrieval)"
Write-Host ""
Write-Host "Download sources:"
Write-Host "  - HuggingFace: https://huggingface.co/models?search=rvc"
Write-Host "  - RVC community models: https://voice-models.com/"
Write-Host "  - Train your own: https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI"
Write-Host ""
Write-Host "After downloading, set in .env:"
Write-Host "  AIDUB_RVC_MODEL_PATH=C:\\path\\to\\model.pth"
Write-Host "  AIDUB_RVC_INDEX_PATH=C:\\path\\to\\index.index"
Write-Host "  AIDUB_ENABLE_RVC=1"
Write-Host ""

$modelsDir = Join-Path $PSScriptRoot '..\tools\rvc\files'
if (-not (Test-Path $modelsDir)) {
    New-Item -ItemType Directory -Path $modelsDir -Force | Out-Null
    Write-Host "Created models directory: $modelsDir"
}
Write-Host "Place your .pth and .index files in: $modelsDir"
