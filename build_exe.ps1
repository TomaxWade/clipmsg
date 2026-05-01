param(
  [switch]$Clean
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

function Get-MissingModules($PythonCommand, [string[]]$Modules) {
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
$RepoDist = Join-Path $Root "dist"
$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) "ClipMsgBuild"
$TempDist = Join-Path $TempRoot "dist"
$TempWork = Join-Path $TempRoot "build"
$StageDir = Join-Path $TempRoot "src"
$StageWeb = Join-Path $StageDir "web"
$StageVersion = Join-Path $StageDir "VERSION"

$pythonCommand = Find-Python
$missing = @(Get-MissingModules $pythonCommand @("PyInstaller", "fastapi", "uvicorn", "qrcode"))

if ($missing.Count -gt 0) {
  Write-Host "Installing build dependencies..."
  Invoke-Python -PythonCommand $pythonCommand -Arguments @("-m", "pip", "install", "-r", "$Root\requirements-build.txt")
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to install build dependencies."
  }
}

if ($Clean -and (Test-Path $TempRoot)) {
  Remove-Item -LiteralPath $TempRoot -Recurse -Force
}

if ($Clean -and (Test-Path $RepoDist)) {
  foreach ($tempFile in (Get-ChildItem -Path $RepoDist -Filter "RCX*.tmp" -ErrorAction SilentlyContinue)) {
    try {
      Remove-Item -LiteralPath $tempFile.FullName -Force -ErrorAction Stop
    }
    catch {
      Write-Warning "Could not remove leftover file: $($tempFile.FullName)"
    }
  }

  $repoExe = Join-Path $RepoDist "ClipMsg.exe"
  if (Test-Path $repoExe) {
    try {
      Remove-Item -LiteralPath $repoExe -Force -ErrorAction Stop
    }
    catch {
      Write-Warning "Could not remove existing EXE: $repoExe"
    }
  }
}

if (Test-Path $StageDir) {
  Remove-Item -LiteralPath $StageDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
Copy-Item -LiteralPath "$Root\server.py" -Destination "$StageDir\server.py" -Force
Copy-Item -LiteralPath "$Root\clipboard_win.py" -Destination "$StageDir\clipboard_win.py" -Force
Copy-Item -LiteralPath "$Root\runtime_support.py" -Destination "$StageDir\runtime_support.py" -Force
Copy-Item -LiteralPath "$Root\storage.py" -Destination "$StageDir\storage.py" -Force
Copy-Item -LiteralPath "$Root\VERSION" -Destination "$StageDir\VERSION" -Force
Copy-Item -LiteralPath "$Root\web" -Destination $StageWeb -Recurse -Force

$args = @(
  "-m",
  "PyInstaller",
  "--noconfirm",
  "--onefile",
  "--name",
  "ClipMsg",
  "--distpath",
  $TempDist,
  "--workpath",
  $TempWork,
  "--specpath",
  $TempRoot,
  "--runtime-tmpdir",
  ".clipmsg-runtime",
  "--add-data",
  "$StageVersion;.",
  "--add-data",
  "$StageWeb;web",
  "--hidden-import",
  "uvicorn.logging",
  "--hidden-import",
  "uvicorn.loops.auto",
  "--hidden-import",
  "uvicorn.protocols.http.auto",
  "--hidden-import",
  "uvicorn.protocols.websockets.auto",
  "--hidden-import",
  "uvicorn.lifespan.on",
  "server.py"
)

if ($Clean) {
  $args = @("-m", "PyInstaller", "--clean") + $args[2..($args.Length - 1)]
}

Write-Host "Building ClipMsg.exe ..."
Push-Location $StageDir
try {
  Invoke-Python -PythonCommand $pythonCommand -Arguments $args
}
finally {
  Pop-Location
}

if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller failed."
}

New-Item -ItemType Directory -Force -Path $RepoDist | Out-Null
Copy-Item -Path (Join-Path $TempDist "ClipMsg.exe") -Destination (Join-Path $RepoDist "ClipMsg.exe") -Force
Write-Host "Copied final EXE to $RepoDist\\ClipMsg.exe"
