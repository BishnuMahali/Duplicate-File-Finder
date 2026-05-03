# MIT License
# Copyright (c) 2026 Bishnu Mahali
# See LICENSE file in the repository root for full license text.

#Requires -Version 5.1

param(
    [string]$Path = (Get-Location).Path,
    [switch]$Recurse,
    [string]$Mode = "prompt",
    [string]$FileTypes = "videos",
    [string]$DeleteMode = "recycle",
    [string]$HardwareAccel = "prompt",
    [int]$Threshold = 70,
    [switch]$SkipDurationFilter,
    [switch]$SkipQuickSignatures,
    [switch]$ExtractMoreFrames
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

        $ModeChoice = Read-Host "Select Mode (1 = Similar Videos [Finds re-encodes], 2 = Identical Files [Fast, Exact Size]) [1]"
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

    if ($Mode -eq "video") {
        $DurChoice = Read-Host "`nGroup by Duration? (Fast, but misses edited lengths) (Y/N) [Y]"
        if ($DurChoice -eq "N" -or $DurChoice -eq "n") { $SkipDurationFilter = $true }

        $SigChoice = Read-Host "`nUse Quick Visual Signatures? (Fast, instantly matches identical keyframes) (Y/N) [Y]"
        if ($SigChoice -eq "N" -or $SigChoice -eq "n") { $SkipQuickSignatures = $true }

        $FrameChoice = Read-Host "`nExtract More Frames? (Slower, higher accuracy for re-encodes) (Y/N) [N]"
        if ($FrameChoice -eq "Y" -or $FrameChoice -eq "y") { $ExtractMoreFrames = $true }

        $ThreshChoice = Read-Host "`nEnter Match Threshold percentage [70]"
        if (-not [string]::IsNullOrWhiteSpace($ThreshChoice)) {
            $Threshold = [int]$ThreshChoice
        }
    }

    if ($Mode -eq "video" -and $HardwareAccel -eq "prompt") {
        Write-Host "`nSelect hardware acceleration mode:"
        Write-Host "1. Auto (Detect automatically, fallback to CPU)"
        Write-Host "2. NVIDIA (CUDA)"
        Write-Host "3. Intel (QSV)"
        Write-Host "4. AMD/Windows (D3D11VA)"
        Write-Host "5. CPU Only (None)"
        $AccelChoice = Read-Host "[1]"

        switch ($AccelChoice) {
            "2" { $HardwareAccel = "cuda" }
            "3" { $HardwareAccel = "qsv" }
            "4" { $HardwareAccel = "d3d11va" }
            "5" { $HardwareAccel = "cpu" }
            default { $HardwareAccel = "auto" }
        }
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

$hwArgs = @()
if ($HardwareAccel -ne "cpu" -and $HardwareAccel -ne "prompt") {
    if ($HardwareAccel -eq "auto") {
        if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
            Write-Host "⚡ GPU detected → CUDA" -ForegroundColor Cyan
            $hwArgs = @("-hwaccel", "cuda")
        }
    } else {
        $hwArgs = @("-hwaccel", $HardwareAccel)
    }
}

[System.IO.Directory]::CreateDirectory($temp) | Out-Null

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

if ($SkipDurationFilter) {
    Write-Host "`n⏭ Skipping duration filtering (Checking all videos against each other)..." -ForegroundColor Yellow
} else {
    Write-Host "`nGrouping by duration..." -ForegroundColor Cyan
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
}

if ($videos.Count -eq 0) {
    Write-Host "❌ No possible video duplicates to process." -ForegroundColor Green
    exit
}

# ─────────────────────────────────────────────
# FINGERPRINT FUNCTION
# ─────────────────────────────────────────────
function Get-Fingerprint($file) {

    $fps = if ($ExtractMoreFrames) { "1/5" } else { "1/10" }

    try {
        $outFile = Join-Path $temp ([System.IO.Path]::GetRandomFileName() + ".raw")

        if ($hwArgs.Count -gt 0) {
            & $ffmpeg $hwArgs[0] $hwArgs[1] -i "$file" -vf "fps=$fps,scale=8:8,format=gray" -f rawvideo $outFile -hide_banner -loglevel error
        } else {
            & $ffmpeg -i "$file" -vf "fps=$fps,scale=8:8,format=gray" -f rawvideo $outFile -hide_banner -loglevel error
        }

        if ($LASTEXITCODE -ne 0) {
            if ($hwArgs.Count -gt 0) {
                Write-Host "⚠ GPU acceleration failed for $(Split-Path $file -Leaf), falling back to CPU..." -ForegroundColor Yellow
                if (Test-Path -LiteralPath $outFile) { Remove-Item -LiteralPath $outFile -Force }

                & $ffmpeg -i "$file" -vf "fps=$fps,scale=8:8,format=gray" -f rawvideo $outFile -hide_banner -loglevel error
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "❌ Failed to extract frames from $(Split-Path $file -Leaf)" -ForegroundColor Red
                    return @()
                }
            } else {
                Write-Host "❌ Failed to extract frames from $(Split-Path $file -Leaf)" -ForegroundColor Red
                return @()
            }
        }

        $hashes = @()

        if (Test-Path -LiteralPath $outFile) {
            $bytes = [System.IO.File]::ReadAllBytes($outFile)
            for ($i = 0; $i -lt $bytes.Length; $i += 64) {
                if ($i + 64 -le $bytes.Length) {
                    $sum = 0
                    for ($j = 0; $j -lt 64; $j++) {
                        $sum += $bytes[$i + $j]
                    }
                    $mean = $sum / 64

                    $bits = ""
                    for ($j = 0; $j -lt 64; $j++) {
                        if ($bytes[$i + $j] -ge $mean) {
                            $bits += "1"
                        } else {
                            $bits += "0"
                        }
                    }
                    $hashes += [Convert]::ToUInt64($bits, 2)
                }
            }
        }

        return $hashes
    }
    finally {
        if (Test-Path -LiteralPath $outFile) {
            Remove-Item -LiteralPath $outFile -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-VisualQuickSignature($hashes) {
    if (-not $hashes -or $hashes.Count -eq 0) { return $null }
    if ($hashes.Count -lt 3) { return ($hashes -join ",") }
    $mid = [Math]::Floor($hashes.Count / 2)
    return "$($hashes[0]),$($hashes[$mid]),$($hashes[-1])"
}

function Get-HammingDistance([uint64]$h1, [uint64]$h2) {
    [uint64]$x = $h1 -bxor $h2
    $count = 0
    while ($x -gt 0) {
        $count += ($x -band 1)
        $x = $x -shr 1
    }
    return $count
}

# ─────────────────────────────────────────────
# BUILD / UPDATE CACHE
# ─────────────────────────────────────────────
$fingerprints = @{}

try {
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
            if ($hashes.Count -gt 0) {
                $fingerprints[$path] = $hashes

                $cache[$path] = @{
                    Path = $path
                    LastWriteTime = $lastWrite
                    Hashes = $hashes
                }

                # Save Cache immediately
                $cache.Values | ConvertTo-Json -Depth 5 | Set-Content $cacheFile
            }
        }
    }
} catch {
    Write-Host "`n⚠ Error occurred, saving cache..." -ForegroundColor Yellow
    $cache.Values | ConvertTo-Json -Depth 5 | Set-Content $cacheFile
    throw
}

# ─────────────────────────────────────────────
# SAVE CACHE (Final safety net)
# ─────────────────────────────────────────────
$cache.Values | ConvertTo-Json -Depth 5 | Set-Content $cacheFile

Write-Host "Cache saved → $cacheFile" -ForegroundColor Cyan

# ─────────────────────────────────────────────
# COMPARE
# ─────────────────────────────────────────────
$paths = @($fingerprints.Keys)

# Pre-compute Visual Quick Signatures
$quickSigs = @{}
foreach ($p in $paths) {
    $quickSigs[$p] = Get-VisualQuickSignature $fingerprints[$p]
}

$edges = @()

for ($i=0; $i -lt $paths.Count; $i++) {
    for ($j=$i+1; $j -lt $paths.Count; $j++) {

        $a = $paths[$i]
        $b = $paths[$j]
        $matched = $false

        # 1. Visual Quick Filter
        if (-not $SkipQuickSignatures) {
            $qa = $quickSigs[$a]
            $qb = $quickSigs[$b]
            if ($null -ne $qa -and $null -ne $qb -and $qa -eq $qb) {
                $matched = $true
            }
        }

        # 2. Full Perceptual Comparison
        if (-not $matched) {
            $listA = $fingerprints[$a]
            $listB = $fingerprints[$b]

            if ($listA -and $listB) {
                $smaller = [Math]::Min($listA.Count, $listB.Count)
                if ($smaller -gt 0) {
                    $matches = 0
                    foreach ($ha in $listA) {
                        foreach ($hb in $listB) {
                            if ((Get-HammingDistance $ha $hb) -le 10) {
                                $matches++
                                break
                            }
                        }
                    }

                    $percent = ($matches / $smaller) * 100
                    if ($percent -ge $Threshold) {
                        $matched = $true
                    }
                }
            }
        }

        if ($matched) {
            $edges += @{ A = $a; B = $b }
        }
    }
}

# Build Connected Components
$adj = @{}
foreach ($edge in $edges) {
    if (-not $adj.ContainsKey($edge.A)) { $adj[$edge.A] = @() }
    if (-not $adj.ContainsKey($edge.B)) { $adj[$edge.B] = @() }
    $adj[$edge.A] += $edge.B
    $adj[$edge.B] += $edge.A
}

$visited = @{}
$matchGroups = @()

foreach ($node in $adj.Keys) {
    if (-not $visited.ContainsKey($node)) {
        $group = @()
        $stack = @($node)
        $visited[$node] = $true

        while ($stack.Count -gt 0) {
            $curr = $stack[$stack.Count - 1]
            if ($stack.Count -eq 1) {
                $stack = @()
            } else {
                $stack = $stack[0..($stack.Count - 2)]
            }

            $group += $curr
            foreach ($neighbor in $adj[$curr]) {
                if (-not $visited.ContainsKey($neighbor)) {
                    $visited[$neighbor] = $true
                    $stack += $neighbor
                }
            }
        }
        if ($group.Count -gt 1) {
            $matchGroups += ,$group
        }
    }
}

Write-Host "✅ Done — $($matchGroups.Count) connected match group(s) found" -ForegroundColor Green

for ($i=0; $i -lt $matchGroups.Count; $i++) {
    Write-Host "`n================================================" -ForegroundColor Yellow
    Write-Host "🔥 MATCH GROUP $($i + 1)" -ForegroundColor Yellow

    $group = $matchGroups[$i]
    for ($k=0; $k -lt $group.Count; $k++) {
        Write-Host "$($k + 1): $($group[$k])"
    }

    $choice = Read-Host "`nEnter the numbers of the files to DELETE (comma-separated, e.g. 1,3) or enter to skip"

    if (-not [string]::IsNullOrWhiteSpace($choice)) {
        $delIndexes = $choice -split "," | ForEach-Object { $_.Trim() }

        foreach ($idx in $delIndexes) {
            $intIdx = [int]$idx - 1
            if ($intIdx -ge 0 -and $intIdx -lt $group.Count) {
                $delPath = $group[$intIdx]
                try {
                    if ($DeleteMode -eq "recycle") {
                        Add-Type -AssemblyName Microsoft.VisualBasic
                        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($delPath, 'OnlyErrorDialogs', 'SendToRecycleBin')
                    } else {
                        Remove-Item -LiteralPath $delPath -Force
                    }
                    Write-Host "Deleted: $delPath" -ForegroundColor Red
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