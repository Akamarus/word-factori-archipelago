[CmdletBinding()]
param(
    [string]$GameData,
    [string]$ModFolder = (Join-Path $env:LOCALAPPDATA 'factori\mods\word factori archipelago'),
    [string]$PatchFile,
    [switch]$Restore,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
if (-not $PatchFile) { $PatchFile = Join-Path $PSScriptRoot 'enhanced.patch.gz' }
$originalHash = 'd40ce3c6a37281c0bce46d8a631cd7dd7749334c7892f45669791d64e4e86978'
$legacyPatchedHash = '5a964d5155f8f7acc63fd90bc81882a0559c4586f5de4fd9a0657badd8594194'
$patchedHash = '33aeea0ae1429e35a8c8b5a98407d88c07b53eac33b40f1df8d47bb566eb7161'
function Hash-Bytes([byte[]]$Bytes) {
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hasher.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $hasher.Dispose() }
}
function Write-Atomic([string]$Path, [byte[]]$Bytes) {
    $stage = Join-Path ([IO.Path]::GetDirectoryName($Path)) ('.wf-ap-' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [IO.File]::WriteAllBytes($stage, $Bytes)
        if ([IO.File]::Exists($Path)) { [IO.File]::Replace($stage, $Path, [System.Management.Automation.Language.NullString]::Value) }
        else { [IO.File]::Move($stage, $Path) }
    }
    finally { if ([IO.File]::Exists($stage)) { [IO.File]::Delete($stage) } }
}
if (Get-Process -Name 'word factori' -ErrorAction SilentlyContinue) {
    throw 'Close Word Factori before installing or restoring the enhanced patch.'
}
if (-not $GameData) {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object Windows.Forms.OpenFileDialog
    $dialog.Title = 'Select data.win inside your Word Factori game folder'
    $dialog.Filter = 'Word Factori game data (data.win)|data.win'
    if ($dialog.ShowDialog() -ne 'OK') { throw 'Cancelled; no game files changed.' }
    $GameData = $dialog.FileName
}
$GameData = [IO.Path]::GetFullPath($GameData)
$ModFolder = [IO.Path]::GetFullPath($ModFolder)
if ([IO.Path]::GetFileName($GameData) -ne 'data.win') { throw 'Select the data.win file, not a folder.' }
$receiptPath = Join-Path $ModFolder 'archipelago_enhanced_install.json'
if ([IO.File]::Exists($receiptPath)) {
    $existingReceipt = [IO.File]::ReadAllText($receiptPath) | ConvertFrom-Json
    if ($existingReceipt.game_data -ne $GameData) { throw 'This mod is already paired with a different game copy.' }
}
$original = [IO.File]::ReadAllBytes($GameData)
$currentHash = Hash-Bytes $original
if ($null -ne $existingReceipt) {
    $legacyReceipt = $existingReceipt.protocol -eq 'enhanced_v1' -and $existingReceipt.patched_sha256 -eq $legacyPatchedHash
    $currentReceipt = $existingReceipt.protocol -eq 'enhanced_v2' -and $existingReceipt.patched_sha256 -eq $patchedHash -and $existingReceipt.capability -eq 'free_word_machine_enforcement_v1'
    if ((-not $legacyReceipt -and -not $currentReceipt) -or $existingReceipt.original_sha256 -ne $originalHash -or ($currentHash -ne $originalHash -and $existingReceipt.patched_sha256 -ne $currentHash)) {
        throw 'Receipt hashes, protocol or enforcement capability are invalid; nothing changed.'
    }
}
$backup = Join-Path ([IO.Path]::GetDirectoryName($GameData)) 'data.wf-ap-original.win'
if ([IO.Directory]::Exists($backup)) { throw 'The original backup path is a directory; nothing changed.' }
if ($Restore) {
    $saved = $null
    if ($currentHash -ne $originalHash) {
        if ($currentHash -ne $patchedHash -and $currentHash -ne $legacyPatchedHash) { throw 'Game changed since patching. Refusing to overwrite an unknown build.' }
        $saved = [IO.File]::ReadAllBytes($backup)
        if ((Hash-Bytes $saved) -ne $originalHash) { throw 'Backup does not match the verified original; nothing changed.' }
    }
    if (Get-Process -Name 'word factori' -ErrorAction SilentlyContinue) { throw 'Close Word Factori before restoring.' }
    if ((Hash-Bytes ([IO.File]::ReadAllBytes($GameData))) -ne $currentHash) { throw 'Game changed during preparation; retry with the game closed.' }
    if ($CheckOnly) { return $GameData }
    $gameRestored = $false
    try {
        if ($null -ne $saved) { Write-Atomic $GameData $saved; $gameRestored = $true }
        if ([IO.File]::Exists($receiptPath)) { [IO.File]::Delete($receiptPath) }
    }
    catch {
        if ($gameRestored -and (Hash-Bytes ([IO.File]::ReadAllBytes($GameData))) -eq $originalHash) { Write-Atomic $GameData $original }
        throw
    }
    Write-Host 'Original game restored. Your saves and the original backup were kept.'
    return
}
if ($currentHash -ne $originalHash -and $currentHash -ne $patchedHash -and $currentHash -ne $legacyPatchedHash) {
    throw 'Unsupported or already modified Word Factori build. No files changed.'
}
$sourceOriginal = $original
if ([IO.File]::Exists($backup)) {
    $sourceOriginal = [IO.File]::ReadAllBytes($backup)
    if ((Hash-Bytes $sourceOriginal) -ne $originalHash) { throw 'An unknown backup already exists; nothing changed.' }
}
elseif ($currentHash -ne $originalHash) {
    throw 'The verified original backup is missing. Restore the game through Steam before installing again.'
}
# Validate the complete delta on every install, including already patched games.
function Get-PatchedBytes {
    $stream = [IO.File]::OpenRead($PatchFile)
    $gzip = New-Object IO.Compression.GZipStream($stream, [IO.Compression.CompressionMode]::Decompress)
    $decoded = New-Object IO.MemoryStream
    try {
        $buffer = New-Object byte[] 65536
        while (($read = $gzip.Read($buffer, 0, $buffer.Length)) -gt 0) {
            if ($decoded.Length + $read -gt 134217728) { throw 'Patch payload is too large.' }
            $decoded.Write($buffer, 0, $read)
        }
        $patch = [Text.Encoding]::UTF8.GetString($decoded.ToArray()) | ConvertFrom-Json
    }
    finally { $decoded.Dispose(); $gzip.Dispose(); $stream.Dispose() }
    if ($patch.format -ne 1 -or $patch.protocol -ne 'enhanced_v2' -or $patch.capability -ne 'free_word_machine_enforcement_v1' -or $patch.original_sha256 -ne $originalHash -or $patch.patched_sha256 -ne $patchedHash -or $patch.size -lt 1 -or $patch.size -gt 134217728) {
        throw 'Patch does not match this integration version.'
    }
    $output = New-Object IO.MemoryStream
    try {
        foreach ($operation in $patch.operations) {
            if ($operation[0] -eq 'copy' -and $operation.Count -eq 3) {
                $offset = [long]$operation[1]; $length = [long]$operation[2]
                if ($offset -lt 0 -or $length -lt 0 -or $offset + $length -gt $sourceOriginal.Length -or $output.Length + $length -gt $patch.size) { throw 'Invalid patch copy range.' }
                $output.Write($sourceOriginal, [int]$offset, [int]$length)
            }
            elseif ($operation[0] -eq 'data' -and $operation.Count -eq 2) {
                $literal = [Convert]::FromBase64String($operation[1])
                if ($output.Length + $literal.Length -gt $patch.size) { throw 'Patch exceeds its expected size.' }
                $output.Write($literal, 0, $literal.Length)
            }
            else { throw 'Invalid patch operation.' }
        }
        $replacement = $output.ToArray()
    }
    finally { $output.Dispose() }
    if ($replacement.Length -ne $patch.size -or (Hash-Bytes $replacement) -ne $patchedHash) { throw 'Patched output failed verification; nothing changed.' }
    return ,$replacement
}
$replacement = Get-PatchedBytes
if (Get-Process -Name 'word factori' -ErrorAction SilentlyContinue) { throw 'Word Factori started during preparation. Close it and retry.' }
if ((Hash-Bytes ([IO.File]::ReadAllBytes($GameData))) -ne $currentHash) { throw 'Game changed during preparation; retry with the game closed.' }
if ($CheckOnly) { return $GameData }
if (-not [IO.Directory]::Exists($ModFolder)) { throw 'The Word Factori Archipelago mod folder is missing.' }
if (-not [IO.File]::Exists($backup)) {
    # Exclusive creation preserves any concurrently created backup.
    $backupStream = [IO.File]::Open($backup, 'CreateNew', 'Write', 'None')
    try { $backupStream.Write($sourceOriginal, 0, $sourceOriginal.Length); $backupStream.Flush($true) }
    finally { $backupStream.Dispose() }
}
$receipt = @{ protocol='enhanced_v2'; capability='free_word_machine_enforcement_v1'; original_sha256=$originalHash; patched_sha256=$patchedHash; game_data=$GameData }
$gamePatched = $false
try {
    if ($currentHash -ne $patchedHash) {
        if (Get-Process -Name 'word factori' -ErrorAction SilentlyContinue) { throw 'Word Factori started during preparation. Close it and retry.' }
        if ((Hash-Bytes ([IO.File]::ReadAllBytes($GameData))) -ne $currentHash) { throw 'Game changed during preparation; retry with the game closed.' }
        Write-Atomic $GameData $replacement
        $gamePatched = $true
    }
    Write-Atomic $receiptPath ([Text.Encoding]::UTF8.GetBytes(($receipt | ConvertTo-Json)))
}
catch {
    if ($gamePatched -and (Hash-Bytes ([IO.File]::ReadAllBytes($GameData))) -eq $patchedHash) { Write-Atomic $GameData $original }
    throw
}
Write-Host 'Required native integration installed. Start a fresh Archipelago room and an empty mod save.'
Write-Host 'New items apply when you return to Levels and enter a factory. Existing saves were not changed.'
