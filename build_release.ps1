param(
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Version = (Get-Content (Join-Path $Root "VERSION") -Raw).Trim()
if (-not $Version) {
  throw "VERSION file is empty."
}

$ExePath = Join-Path $Root "dist\ClipMsg.exe"
$ReleaseRoot = Join-Path $Root "release"
$BundleName = "ClipMsg-v$Version-windows-x64"
$BundleDir = Join-Path $ReleaseRoot $BundleName
$ZipPath = Join-Path $ReleaseRoot "$BundleName.zip"
$ReadmePath = Join-Path $BundleDir "README.txt"
$LicensePath = Join-Path $Root "LICENSE"

if (-not $SkipBuild) {
  & (Join-Path $Root "build_exe.ps1")
  if ($LASTEXITCODE -ne 0) {
    throw "EXE build failed."
  }
}

if (-not (Test-Path $ExePath)) {
  throw "EXE not found at $ExePath"
}

if (Test-Path $BundleDir) {
  Remove-Item -LiteralPath $BundleDir -Recurse -Force
}

if (Test-Path $ZipPath) {
  Remove-Item -LiteralPath $ZipPath -Force
}

New-Item -ItemType Directory -Force -Path $BundleDir | Out-Null
Copy-Item -LiteralPath $ExePath -Destination (Join-Path $BundleDir "ClipMsg.exe") -Force
Copy-Item -LiteralPath $LicensePath -Destination (Join-Path $BundleDir "LICENSE.txt") -Force

$readme = @"
ClipMsg v$Version

What it does
- Lets you send text from your phone to your Windows desktop.
- Incoming phone messages are copied to the Windows clipboard automatically.
- That means you can press Ctrl+V in any app right away without manually copying from the desktop page.

How to use
1. Double-click ClipMsg.exe.
2. Wait for the desktop page to open in your browser.
3. Scan the QR code with your phone.
4. Send text from your phone.

Notes
- Windows only.
- No Python installation is required for this EXE release.
- Phone and desktop should be on a reachable trusted network, such as the same LAN or a private overlay like Tailscale.
"@

Set-Content -LiteralPath $ReadmePath -Value $readme -Encoding UTF8
Compress-Archive -Path (Join-Path $BundleDir "*") -DestinationPath $ZipPath -CompressionLevel Optimal

Write-Host ""
Write-Host "Release bundle ready:"
Write-Host $ZipPath
