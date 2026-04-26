#requires -Version 7
<#
.SYNOPSIS
    Launch Blender pre-wired for the NFC-bead live-MCP workflow.

.DESCRIPTION
    Idempotently installs / enables the BlenderMCP addon, starts its socket
    server, and (optionally) opens a specific .blend file.

.PARAMETER Bead
    Charm name under beads/<bead>/. Loads beads/<bead>/print/<bead>_charm.blend
    if it exists. Default: rezz.

.PARAMETER BlendFile
    Explicit .blend path. Overrides -Bead.

.PARAMETER Blender
    Path to blender.exe. Falls back to $env:NFC_BEAD_BLENDER, then
    D:\tools\blender\blender.exe.

.EXAMPLE
    .\tools\launch.ps1                          # rezz bead, default Blender
    .\tools\launch.ps1 -Bead wooli              # different bead
    .\tools\launch.ps1 -BlendFile foo.blend     # arbitrary file
    .\tools\launch.ps1 -Bead rezz -Blender 'C:\Program Files\Blender Foundation\Blender 4.4\blender.exe'
#>
param(
    [string]$Bead      = 'rezz',
    [string]$BlendFile = '',
    [string]$Blender   = ''
)

$ErrorActionPreference = 'Stop'

# Resolve Blender path
if (-not $Blender) {
    $Blender = $env:NFC_BEAD_BLENDER
    if (-not $Blender) { $Blender = 'D:\tools\blender\blender.exe' }
}
if (-not (Test-Path $Blender)) {
    throw "Blender not found at: $Blender. Pass -Blender <path> or set NFC_BEAD_BLENDER."
}

# Resolve repo + bootstrap script
$Repo      = (Get-Item $PSScriptRoot).Parent.FullName
$Bootstrap = Join-Path $Repo 'tools\blender_bootstrap.py'
if (-not (Test-Path $Bootstrap)) {
    throw "Bootstrap script missing: $Bootstrap"
}

# Resolve .blend to load (optional)
if (-not $BlendFile -and $Bead) {
    $candidate = Join-Path $Repo "beads\$Bead\print\${Bead}_charm.blend"
    if (Test-Path $candidate) { $BlendFile = $candidate }
}
# Final fallback: the canonical sample bead scene (rezz with architect rig + DBG overlays).
# Lives in this worktree at samples/rezz_sample.blend; useful when working on aesthetics
# without a per-charm beads/<name>/print/ tree present.
if (-not $BlendFile) {
    $sample = Join-Path $Repo 'samples\rezz_sample.blend'
    if (Test-Path $sample) { $BlendFile = $sample }
}

# Build argument list. Blender CLI: [blendfile] --python <script>
$blenderArgs = @()
if ($BlendFile) { $blenderArgs += $BlendFile }
$blenderArgs += @('--python', $Bootstrap)

Write-Host "[launch] Blender:   $Blender" -ForegroundColor Cyan
if ($BlendFile) { Write-Host "[launch] Loading:   $BlendFile" -ForegroundColor Cyan }
Write-Host "[launch] Bootstrap: $Bootstrap" -ForegroundColor Cyan

# Detach so Blender's stays open after this script returns
Start-Process -FilePath $Blender -ArgumentList $blenderArgs
Write-Host "[launch] Blender launched. After it opens, /mcp here to reconnect." -ForegroundColor Green
