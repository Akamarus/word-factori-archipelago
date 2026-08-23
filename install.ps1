[CmdletBinding()]
param([switch]$Force, [switch]$Uninstall)

$ErrorActionPreference = "Stop"
$distributionRoot = $PSScriptRoot
$worldSource = Join-Path $distributionRoot "word_factori.apworld"
$modSource = Join-Path $distributionRoot "game_mod\word factori archipelago"
$worldTargetDirectory = Join-Path $env:ProgramData "Archipelago\custom_worlds"
$worldTarget = Join-Path $worldTargetDirectory "word_factori.apworld"
$modTargetDirectory = Join-Path $env:LOCALAPPDATA "factori\mods"
$modTarget = Join-Path $modTargetDirectory "word factori archipelago"

function Assert-DirectChild([string]$Candidate, [string]$Parent) {
    $candidateFull = [IO.Path]::GetFullPath($Candidate)
    $parentFull = [IO.Path]::GetFullPath($Parent).TrimEnd('\', '/')
    $candidateParent = [IO.Path]::GetDirectoryName($candidateFull).TrimEnd('\', '/')
    if (-not $candidateParent.Equals($parentFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing unsafe staging path outside $parentFull"
    }
}

Assert-DirectChild $worldTarget $worldTargetDirectory
Assert-DirectChild $modTarget $modTargetDirectory
if ($Uninstall) {
    if (Test-Path -LiteralPath $worldTarget) {
        Remove-Item -LiteralPath $worldTarget -Force
    }
    if (Test-Path -LiteralPath $modTarget) {
        Remove-Item -LiteralPath $modTarget -Recurse -Force
    }
    Write-Host "Removed only the Word Factori Archipelago integration."
    exit 0
}

if (-not (Test-Path -LiteralPath $worldSource -PathType Leaf)) {
    throw "Missing package file: $worldSource"
}
if (-not (Test-Path -LiteralPath $modSource -PathType Container)) {
    throw "Missing game mod directory: $modSource"
}
if (-not $Force -and ((Test-Path -LiteralPath $worldTarget) -or (Test-Path -LiteralPath $modTarget))) {
    throw "Word Factori Archipelago is already installed. Rerun with -Force to update it."
}

New-Item -ItemType Directory -Force -Path $worldTargetDirectory | Out-Null
New-Item -ItemType Directory -Force -Path $modTargetDirectory | Out-Null

$transaction = [guid]::NewGuid().ToString('N')
$worldStage = Join-Path $worldTargetDirectory ".word_factori.$transaction.tmp"
$worldBackup = Join-Path $worldTargetDirectory ".word_factori.$transaction.backup"
$modStage = Join-Path $modTargetDirectory ".word-factori-archipelago.$transaction.stage"
$modBackup = Join-Path $modTargetDirectory ".word-factori-archipelago.$transaction.backup"
foreach ($pathPair in @(
    @($worldStage, $worldTargetDirectory), @($worldBackup, $worldTargetDirectory),
    @($modStage, $modTargetDirectory), @($modBackup, $modTargetDirectory)
)) {
    Assert-DirectChild $pathPair[0] $pathPair[1]
}

$worldWasPresent = Test-Path -LiteralPath $worldTarget
$modWasPresent = Test-Path -LiteralPath $modTarget
$worldCommitted = $false
$modCommitted = $false
try {
    Copy-Item -LiteralPath $worldSource -Destination $worldStage
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $worldZip = [IO.Compression.ZipFile]::OpenRead($worldStage)
    $worldZip.Dispose()

    New-Item -ItemType Directory -Path $modStage | Out-Null
    Copy-Item -Path (Join-Path $modSource '*') -Destination $modStage -Recurse -Force
    foreach ($required in @('levels.json', 'recipes.json', 'tips.json', 'credits.json', 'archipelago_campaign.json')) {
        $requiredPath = Join-Path $modStage $required
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Staged mod is missing $required"
        }
        Get-Content -LiteralPath $requiredPath -Raw | ConvertFrom-Json | Out-Null
    }
    $identityPath = Join-Path $modStage 'archipelago_campaign.json'
    $identity = Get-Content -LiteralPath $identityPath -Raw | ConvertFrom-Json
    if ($identity.campaign_id -ne 'word-factori-hybrid' -or
        $identity.manifest_version -ne '1.2.0' -or
        $identity.level_count -ne 40 -or
        $identity.manifest_digest -notmatch '^[0-9a-f]{64}$') {
        throw "Staged mod has an invalid Word Factori hybrid campaign identity"
    }

    if ($worldWasPresent) { Move-Item -LiteralPath $worldTarget -Destination $worldBackup }
    if ($modWasPresent) { Move-Item -LiteralPath $modTarget -Destination $modBackup }
    Move-Item -LiteralPath $worldStage -Destination $worldTarget
    $worldCommitted = $true
    Move-Item -LiteralPath $modStage -Destination $modTarget
    $modCommitted = $true
}
catch {
    if ($worldCommitted -and (Test-Path -LiteralPath $worldTarget)) {
        Remove-Item -LiteralPath $worldTarget -Force
    }
    if ($modCommitted -and (Test-Path -LiteralPath $modTarget)) {
        Remove-Item -LiteralPath $modTarget -Recurse -Force
    }
    if (Test-Path -LiteralPath $worldBackup) { Move-Item -LiteralPath $worldBackup -Destination $worldTarget }
    if (Test-Path -LiteralPath $modBackup) { Move-Item -LiteralPath $modBackup -Destination $modTarget }
    throw
}
finally {
    foreach ($temporary in @($worldStage, $worldBackup, $modStage, $modBackup)) {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Recurse -Force
        }
    }
}

Write-Host "Installed the Archipelago world to $worldTarget"
Write-Host "Installed the Word Factori mod to $modTarget"
Write-Host "Restart Archipelago and Word Factori before playing."
