# MIT License
# Copyright (c) 2026 Bishnu Mahali
# See LICENSE file in the repository root for full license text.

#Requires -Version 5.1

param(
    [string]$Path = (Get-Location).Path,
    [switch]$Recurse
)

Set-StrictMode -Version 2
$ErrorActionPreference = "Continue"

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
$cacheFile = Join-Path $Path "video_fingerprints.json"
$temp = Join-Path $env:TEMP ([System.IO.Path]::GetRandomFileName())

$ffmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
if (-not $ffmpeg) {
    Write-Host "❌ ffmpeg not found!" -ForegroundColor Red
    exit
}

New-Item -ItemType Directory -Force -LiteralPath $temp | Out-Null

try {
# ─────────────────────────────────────────────
# LOAD CACHE
# ─────────────────────────────────────────────
$cache = @{}

if (Test-Path $cacheFile) {
    Write-Host "Loading cache..." -ForegroundColor Cyan
    $json = Get-Content $cacheFile -Raw | ConvertFrom-Json
    foreach ($entry in $json) {
        $cache[$entry.Path] = $entry
    }
}

# ─────────────────────────────────────────────
# GET FILES
# ─────────────────────────────────────────────
$videos = Get-ChildItem -LiteralPath $Path -File -Recurse:$Recurse |
Where-Object { $_.Extension -in ".mp4",".mkv",".avi",".mov",".wmv" }

Write-Host "Found $($videos.Count) videos"

# ─────────────────────────────────────────────
# FINGERPRINT FUNCTION
# ─────────────────────────────────────────────
function Get-Fingerprint($file) {

    $folder = Join-Path $temp ([IO.Path]::GetRandomFileName())
    New-Item -ItemType Directory -Force -LiteralPath $folder | Out-Null

    try {
        & $ffmpeg -i "$file" -vf "fps=1/10" "$folder\frame_%04d.jpg" -hide_banner -loglevel error

        $hashes = @()

        Get-ChildItem -LiteralPath $folder -Filter *.jpg | ForEach-Object {
            $hashes += (Get-FileHash -LiteralPath $_.FullName -Algorithm MD5).Hash
        }

        return $hashes
    }
    finally {
        if (Test-Path -LiteralPath $folder) {
            Remove-Item -LiteralPath $folder -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# ─────────────────────────────────────────────
# BUILD / UPDATE CACHE
# ─────────────────────────────────────────────
$fingerprints = @{}

foreach ($v in $videos) {

    $path = $v.FullName
    $lastWrite = $v.LastWriteTimeUtc

    if ($cache.ContainsKey($path) -and $cache[$path].LastWriteTime -eq $lastWrite) {
        Write-Host "✔ Cached: $($v.Name)" -ForegroundColor Green
        $fingerprints[$path] = $cache[$path].Hashes
    }
    else {
        Write-Host "Processing: $($v.Name)" -ForegroundColor Yellow

        $hashes = Get-Fingerprint $path

        $fingerprints[$path] = $hashes

        $cache[$path] = @{
            Path = $path
            LastWriteTime = $lastWrite
            Hashes = $hashes
        }
    }
}

# ─────────────────────────────────────────────
# SAVE CACHE
# ─────────────────────────────────────────────
$cache.Values | ConvertTo-Json -Depth 5 | Set-Content $cacheFile

Write-Host "Cache saved → $cacheFile" -ForegroundColor Cyan

# ─────────────────────────────────────────────
# COMPARE
# ─────────────────────────────────────────────
$paths = $fingerprints.Keys

for ($i=0; $i -lt $paths.Count; $i++) {
    for ($j=$i+1; $j -lt $paths.Count; $j++) {

        $a = $paths[$i]
        $b = $paths[$j]

        $hashA = $fingerprints[$a]
        $hashB = $fingerprints[$b]

        if (-not $hashA -or -not $hashB) { continue }

        $matches = ($hashA | Where-Object { $hashB -contains $_ }).Count

        $percent = ($matches / [Math]::Min($hashA.Count, $hashB.Count)) * 100

        if ($percent -ge 70) {

            Write-Host "`n============================" -ForegroundColor Yellow
            Write-Host "MATCH ($([int]$percent)% similar)" -ForegroundColor Yellow

            Write-Host "`n1: $a"
            Write-Host "2: $b"

            $choice = Read-Host "Delete one? (1/2/skip)"

            if ($choice -eq "1") {
                Remove-Item -LiteralPath $a -Force
                Write-Host "Deleted 1" -ForegroundColor Red
            }
            elseif ($choice -eq "2") {
                Remove-Item -LiteralPath $b -Force
                Write-Host "Deleted 2" -ForegroundColor Red
            }
        }
    }
}

Write-Host "`nDone." -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $temp) {
        Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Read-Host "Press Enter to exit"