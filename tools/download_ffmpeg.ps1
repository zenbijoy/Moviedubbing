# Download and bundle FFmpeg 8.0+ static build for Windows
# Usage: .\tools\download_ffmpeg.ps1

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$binDir = Join-Path $projectRoot 'bin'
$ffmpegUrl = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'

Write-Host "Downloading FFmpeg..."
$tempZip = Join-Path $env:TEMP 'ffmpeg_download.zip'
Invoke-WebRequest -Uri $ffmpegUrl -OutFile $tempZip -UseBasicParsing

Write-Host "Extracting..."
$tempExtract = Join-Path $env:TEMP 'ffmpeg_extract'
if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
Expand-Archive -Path $tempZip -DestinationPath $tempExtract -Force

New-Item -ItemType Directory -Path $binDir -Force | Out-Null

$ffmpegExe = Get-ChildItem -Path $tempExtract -Recurse -Filter 'ffmpeg.exe' | Select-Object -First 1
$ffprobeExe = Get-ChildItem -Path $tempExtract -Recurse -Filter 'ffprobe.exe' | Select-Object -First 1

if ($ffmpegExe) {
    Copy-Item $ffmpegExe.FullName -Destination (Join-Path $binDir 'ffmpeg.exe') -Force
    Write-Host "Copied ffmpeg.exe to $binDir"
} else {
    Write-Error "ffmpeg.exe not found in archive"
}

if ($ffprobeExe) {
    Copy-Item $ffprobeExe.FullName -Destination (Join-Path $binDir 'ffprobe.exe') -Force
    Write-Host "Copied ffprobe.exe to $binDir"
} else {
    Write-Error "ffprobe.exe not found in archive"
}

Remove-Item $tempZip -Force -ErrorAction SilentlyContinue
Remove-Item $tempExtract -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "FFmpeg setup complete. Binaries in: $binDir"
