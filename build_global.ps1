#!/usr/bin/env pwsh
<#+
.SYNOPSIS
Build the package and install it for the current user.
#>

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

function Get-PythonCommand {
    if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
    if (Get-Command py -ErrorAction SilentlyContinue) { return "py -3" }
    throw "Python interpreter not found. Install Python 3.9+ and add it to PATH."
}

$python = Get-PythonCommand
Write-Host "Using Python command: $python"
& $python -m pip install --upgrade pip setuptools wheel build
& $python -m build

$wheel = Get-ChildItem -Path "$scriptDir\dist\subnet-calculator-*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $wheel) {
    throw "Wheel file not found in dist/."
}

Write-Host "Installing wheel: $($wheel.Name)"
& $python -m pip install --user --force-reinstall $wheel.FullName

Write-Host "Done. The 'subnet-calc' command is now installed for the current user."
Write-Host "If it is not found in your terminal, add the Python user Scripts directory to PATH:"
Write-Host "  Windows: %APPDATA%\Python\PythonXX\Scripts"
Write-Host "  Linux/macOS: ~/.local/bin"
