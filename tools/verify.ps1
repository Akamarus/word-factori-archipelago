[CmdletBinding()]
param([string]$PythonExecutable = "")

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot

if ($PythonExecutable) {
    $python = @($PythonExecutable)
}
elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
    $python = @((Get-Command py.exe).Source, "-3")
}
elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
    $python = @((Get-Command python.exe).Source)
}
else {
    throw "Python 3.12 or newer is required."
}

function Invoke-Python([string[]]$Arguments) {
    $prefixArguments = if ($python.Count -gt 1) { $python[1..($python.Count - 1)] } else { @() }
    $executable = $python[0]
    $allArguments = @($prefixArguments) + @($Arguments)
    & $executable @allArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code ${LASTEXITCODE}: $($Arguments -join ' ')"
    }
}

Push-Location $repositoryRoot
try {
    Invoke-Python @("tools\build_release.py")
    Invoke-Python @("-m", "unittest", "discover", "-s", "tests", "-v")
    Invoke-Python @("tools\verify_release.py")
}
finally {
    Pop-Location
}

Write-Host "Word Factori Archipelago verification passed."
