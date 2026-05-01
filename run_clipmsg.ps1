param(
  [int]$Port = 8765,
  [switch]$NoOpen,
  [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

function Find-Python {
  $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
  if ($pyLauncher) {
    return @($pyLauncher.Source, "-3")
  }

  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) {
    return @($python.Source)
  }

  throw "Python 3 was not found. Install Python 3.11+ first."
}

function Invoke-Python {
  param(
    [string[]]$PythonCommand,
    [string[]]$Arguments
  )

  if ($PythonCommand.Length -gt 1) {
    & $PythonCommand[0] @($PythonCommand[1..($PythonCommand.Length - 1)]) @Arguments
  }
  else {
    & $PythonCommand[0] @Arguments
  }
}

function Get-MissingModules {
  param(
    [string[]]$PythonCommand,
    [string[]]$Modules
  )

  $quoted = $Modules | ForEach-Object { "'$_'" }
  $moduleList = $quoted -join ", "
  $code = "import importlib.util; modules = [$moduleList]; missing = [name for name in modules if importlib.util.find_spec(name) is None]; print('|'.join(missing))"
  $result = Invoke-Python -PythonCommand $PythonCommand -Arguments @("-c", $code) 2>$null
  if ($LASTEXITCODE -ne 0) {
    return $Modules
  }

  if ([string]::IsNullOrWhiteSpace($result)) {
    return @()
  }

  return $result.Trim().Split("|")
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$pythonCommand = Find-Python
Write-Host ""
Write-Host "ClipMsg launcher"
Write-Host "Project : $Root"
Write-Host "Python  : $($pythonCommand -join ' ')"
Write-Host "Port    : $Port (auto-falls forward if busy)"
Write-Host ""

$missing = @(Get-MissingModules -PythonCommand $pythonCommand -Modules @("fastapi", "uvicorn", "qrcode"))
if ($missing.Count -gt 0) {
  Write-Host "Installing missing packages: $($missing -join ', ')"
  Invoke-Python -PythonCommand $pythonCommand -Arguments @("-m", "pip", "install", "-r", "$Root\requirements.txt")
  if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Package installation failed."
    Pause
    exit 1
  }
  Write-Host ""
}

if ($CheckOnly) {
  Write-Host "Environment check passed."
  exit 0
}

$serverArgs = @("$Root\server.py", "--port", "$Port")
if ($NoOpen) {
  $serverArgs += "--no-open"
}

Write-Host "Starting ClipMsg..."
Write-Host "Close this window to stop the local server."
Write-Host ""

Invoke-Python -PythonCommand $pythonCommand -Arguments $serverArgs
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
  Write-Host ""
  Write-Host "ClipMsg exited with code $exitCode."
  Pause
}

exit $exitCode
