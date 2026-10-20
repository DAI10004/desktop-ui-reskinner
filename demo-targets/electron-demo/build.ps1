#requires -Version 5.1
# Electron 靶场构建脚本（幂等，可重复运行）
# 前置：.tools\electron-deps 下已 npm install electron @electron/asar
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projRoot = Split-Path -Parent (Split-Path -Parent $root)
$deps = Join-Path $projRoot '.tools\electron-deps'
$appSrc = Join-Path $root 'app-src'
$appDir = Join-Path $root 'App'
$electronDist = Join-Path $deps 'node_modules\electron\dist'
$asarBin = Join-Path $deps 'node_modules\@electron\asar\bin\asar.mjs'

if (-not (Test-Path (Join-Path $electronDist 'electron.exe'))) {
    throw "electron dist not found at $electronDist — run npm install electron first"
}
if (-not (Test-Path $asarBin)) {
    throw "@electron/asar not found at $asarBin"
}

# 1) 整体复制 electron dist -> App（幂等：先清后拷）
if (Test-Path $appDir) { Remove-Item -Recurse -Force $appDir }
Copy-Item -Recurse -Force $electronDist $appDir

# 2) 删除 default_app.asar，确保加载我们自己的 app.asar
$defaultAsar = Join-Path $appDir 'resources\default_app.asar'
if (Test-Path $defaultAsar) { Remove-Item -Force $defaultAsar }

# 3) 打包 app-src -> resources/app.asar
$outAsar = Join-Path $appDir 'resources\app.asar'
if (Test-Path $outAsar) { Remove-Item -Force $outAsar }
& node $asarBin pack $appSrc $outAsar
if ($LASTEXITCODE -ne 0) { throw "asar pack failed ($LASTEXITCODE)" }

Write-Host "BUILD OK: $appDir\electron.exe"
