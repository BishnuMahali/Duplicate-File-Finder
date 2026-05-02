# MIT License
# Copyright (c) 2026 Bishnu Mahali
# See LICENSE file in the repository root for full license text.

#Requires -Version 5.1

param(
    [string]$Path = (Get-Location).Path,
    [switch]$Recurse,
    [string]$Mode = "prompt",
    [string]$FileTypes = "videos",
    [string]$DeleteMode = "recycle"
)

Set-StrictMode -Version 2
$ErrorActionPreference = "Continue"

# ─────────────────────────────────────────────
# UI PROMPT
# ─────────────────────────────────────────────
if ($Mode -eq "prompt") {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "        DUPLICATE FILE FINDER" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    $ModeChoice = Read-Host "Select Mode (1 = Video/Similar, 2 = Exact/All files) [1]"
    if ($ModeChoice -eq "2") {
        $Mode = "exact"

        Write-Host "`nSelect File Types for Exact Match:"
        Write-Host "1. All Files"
        Write-Host "2. Videos"
        Write-Host "3. Images"
        Write-Host "4. Documents"
        Write-Host "5. Audio"
        $TypeChoice = Read-Host "[1]"

        switch ($TypeChoice) {
            "2" { $FileTypes = "videos" }
            "3" { $FileTypes = "images" }
            "4" { $FileTypes = "documents" }
            "5" { $FileTypes = "audio" }
            default { $FileTypes = "all" }
        }
    } else {
        $Mode = "video"
    }

    $DelChoice = Read-Host "`nSelect Delete Mode (1 = Recycle Bin, 2 = Permanent) [1]"
    if ($DelChoice -eq "2") {
        $DeleteMode = "permanent"
    } else {
        $DeleteMode = "recycle"
    }
}

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

$ffprobe = (Get-Command ffprobe -ErrorAction SilentlyContinue).Source
if (-not $ffprobe) {
    Write-Host "❌ ffprobe not found! (Needed for duration grouping)" -ForegroundColor Red
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
# EXACT MATCH ENGINE
# ─────────────────────────────────────────────
function Find-ExactDuplicates {
    param (
        [string]$TargetFolder,
        [switch]$Recursive,
        [string]$FileTypes = "all"
    )

    $allFiles = Get-ChildItem -LiteralPath $TargetFolder -File -Recurse:$Recursive

    if ($FileTypes -eq "videos") {
        $allFiles = $allFiles | Where-Object { $_.Extension -in ".mp4",".mkv",".avi",".mov",".wmv",".flv",".webm",".mpeg",".mpg",".m4v",".3gp",".vob",".ts",".f4v" }
    } elseif ($FileTypes -eq "images") {
        $allFiles = $allFiles | Where-Object { $_.Extension -in ".jpg",".jpeg",".png",".gif",".bmp",".webp",".tiff" }
    } elseif ($FileTypes -eq "documents") {
        $allFiles = $allFiles | Where-Object { $_.Extension -in ".pdf",".doc",".docx",".txt",".rtf",".xls",".xlsx",".csv" }
    } elseif ($FileTypes -eq "audio") {
        $allFiles = $allFiles | Where-Object { $_.Extension -in ".mp3",".wav",".flac",".aac",".ogg",".m4a" }
    }

    Write-Host "Found $($allFiles.Count) files for exact matching." -ForegroundColor Cyan

    # 1. Group by Size
    Write-Host "Grouping by size..." -ForegroundColor Cyan
    $sizeGroups = $allFiles | Group-Object Length | Where-Object Count -gt 1

    if ($sizeGroups.Count -eq 0) {
        Write-Host "✅ No exact duplicates found." -ForegroundColor Green
        return @()
    }

    # 2. Quick Signature Filter (First/Last 1KB)
    Write-Host "Running quick signature filter..." -ForegroundColor Cyan
    $candidates = @()
    foreach ($group in $sizeGroups) {
        $candidates += $group.Group
    }

    Write-Host "Candidate files: $($candidates.Count)" -ForegroundColor Yellow

    $quickGroups = @{}
    foreach ($file in $candidates) {
        try {
            $stream = [System.IO.File]::OpenRead($file.FullName)
            $buffer = New-Object byte[] 1024
            $read1 = $stream.Read($buffer, 0, 1024)
            $startBytes = $buffer[0..($read1-1)]

            if ($stream.Length -gt 1024) {
                $stream.Seek(-1024, [System.IO.SeekOrigin]::End) | Out-Null
                $read2 = $stream.Read($buffer, 0, 1024)
                $endBytes = $buffer[0..($read2-1)]
            } else {
                $endBytes = $startBytes
            }
            $stream.Close()

            $combined = $startBytes + $endBytes
            $md5 = [System.Security.Cryptography.MD5]::Create()
            $hash = [BitConverter]::ToString($md5.ComputeHash($combined)) -replace "-"

            $key = "$($file.Length)_$hash"
            if (-not $quickGroups.ContainsKey($key)) {
                $quickGroups[$key] = @()
            }
            $quickGroups[$key] += $file.FullName
        } catch {}
    }

    $candidates = @()
    foreach ($g in $quickGroups.Values) {
        if ($g.Count -gt 1) {
            $candidates += $g
        }
    }

    if ($candidates.Count -eq 0) {
        Write-Host "✅ No exact duplicates found." -ForegroundColor Green
        return @()
    }

    # 3. Full Hash
    Write-Host "Computing full hashes..." -ForegroundColor Cyan
    $fullGroups = @{}
    foreach ($file in $candidates) {
        try {
            $hash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash
            if (-not $fullGroups.ContainsKey($hash)) {
                $fullGroups[$hash] = @()
            }
            $fullGroups[$hash] += $file
        } catch {}
    }

    $matches = @()
    foreach ($g in $fullGroups.Values) {
        if ($g.Count -gt 1) {
            $matches += ,$g
        }
    }

    return $matches
}

# ─────────────────────────────────────────────
# EXACT MATCH EXECUTION
# ─────────────────────────────────────────────
if ($Mode -eq "exact") {
    $matches = Find-ExactDuplicates -TargetFolder $Path -Recursive:$Recurse -FileTypes $FileTypes

    if ($matches.Count -gt 0) {
        Write-Host "`n✅ Done — $($matches.Count) match group(s) found" -ForegroundColor Green
        for ($i=0; $i -lt $matches.Count; $i++) {
            $group = $matches[$i]
            Write-Host "`n============================" -ForegroundColor Yellow
            Write-Host "EXACT MATCH GROUP $($i+1)" -ForegroundColor Yellow

            for ($j=0; $j -lt $group.Count; $j++) {
                Write-Host "$($j+1): $($group[$j])"
            }

            $choice = Read-Host "Delete a file? (Enter number, or skip)"

            if ($choice -match '^\d+$') {
                $idx = [int]$choice - 1
                if ($idx -ge 0 -and $idx -lt $group.Count) {
                    $delPath = $group[$idx]
                    try {
                        if ($DeleteMode -eq "recycle") {
                            Add-Type -AssemblyName Microsoft.VisualBasic
                            [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($delPath, 'OnlyErrorDialogs', 'SendToRecycleBin')
                        } else {
                            Remove-Item -LiteralPath $delPath -Force
                        }
                        Write-Host "Deleted $choice" -ForegroundColor Red
                    } catch {
                        Write-Host "❌ Failed to delete: $_" -ForegroundColor Red
                    }
                }
            }
        }
    }

    Write-Host "`nDone." -ForegroundColor Green
    Read-Host "Press Enter to exit"
    exit
}

# ─────────────────────────────────────────────
# GET FILES (VIDEO MODE)
# ─────────────────────────────────────────────
$videos = Get-ChildItem -LiteralPath $Path -File -Recurse:$Recurse |
Where-Object { $_.Extension -in ".mp4",".mkv",".avi",".mov",".wmv",".flv",".webm",".mpeg",".mpg",".m4v",".3gp",".vob",".ts",".f4v" }

Write-Host "Found $($videos.Count) videos"

# ─────────────────────────────────────────────
# DURATION GROUPING
# ─────────────────────────────────────────────
function Get-VideoDuration($file) {
    try {
        $output = & $ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$file"
        return [double]$output.Trim()
    } catch {
        return $null
    }
}

Write-Host "Grouping by duration..." -ForegroundColor Cyan
$groups = @()
foreach ($v in $videos) {
    $d = Get-VideoDuration $v.FullName
    if ($null -eq $d) { continue }

    $placed = $false
    foreach ($g in $groups) {
        if ([Math]::Abs($g.Duration - $d) -le 5) {
            $g.Files += $v
            $placed = $true
            break
        }
    }
    if (-not $placed) {
        $groups += @{
            Duration = $d
            Files = @($v)
        }
    }
}

$videos = @()
foreach ($g in $groups) {
    if ($g.Files.Count -gt 1) {
        $videos += $g.Files
    }
}

Write-Host "Candidate videos after duration filter: $($videos.Count)" -ForegroundColor Yellow

if ($videos.Count -eq 0) {
    Write-Host "❌ No possible video duplicates after duration filtering" -ForegroundColor Green
}

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

            $delPath = $null
            if ($choice -eq "1") { $delPath = $a }
            elseif ($choice -eq "2") { $delPath = $b }

            if ($null -ne $delPath) {
                try {
                    if ($DeleteMode -eq "recycle") {
                        Add-Type -AssemblyName Microsoft.VisualBasic
                        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($delPath, 'OnlyErrorDialogs', 'SendToRecycleBin')
                    } else {
                        Remove-Item -LiteralPath $delPath -Force
                    }
                    Write-Host "Deleted $choice" -ForegroundColor Red
                } catch {
                    Write-Host "❌ Failed to delete: $_" -ForegroundColor Red
                }
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