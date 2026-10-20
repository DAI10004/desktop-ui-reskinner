#requires -Version 5.1
# WPF code-only 靶场构建脚本（幂等，可重复运行）
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$csc = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { throw "csc.exe not found: $csc" }

# 在 GAC 中定位 WPF 程序集引用
function Find-GacDll([string]$name) {
    $roots = @(
        'C:\Windows\Microsoft.NET\assembly\GAC_MSIL',
        'C:\Windows\Microsoft.NET\assembly\GAC_64',
        'C:\Windows\Microsoft.NET\assembly\GAC_32'
    )
    foreach ($r in $roots) {
        $hit = Get-ChildItem -Path $r -Recurse -Filter "$name.dll" -ErrorAction SilentlyContinue |
               Where-Object { $_.FullName -match '__' } | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    throw "GAC dll not found: $name.dll"
}

$refs = @(
    (Find-GacDll 'PresentationFramework'),
    (Find-GacDll 'PresentationCore'),
    (Find-GacDll 'WindowsBase'),
    (Find-GacDll 'System.Xaml')
)
Write-Host "refs:"; $refs | ForEach-Object { Write-Host "  $_" }

# 把浅色样例落地为运行时加载的 theme.xaml（幂等）
Copy-Item -Path (Join-Path $here 'theme.light.xaml') -Destination (Join-Path $here 'theme.xaml') -Force

$out = Join-Path $here 'WpfDemo.exe'
$src = Join-Path $here 'Program.cs'
$rsp = Join-Path $here 'build.rsp'

# 用响应文件传参，规避 PowerShell 原生命令参数拼接问题
$rspLines = @(
    '/nologo',
    '/target:winexe',
    '/platform:x64',
    "/out:`"$out`""
) + ($refs | ForEach-Object { "/reference:`"$_`"" }) + @("`"$src`"")
Set-Content -Path $rsp -Value $rspLines -Encoding utf8

Write-Host "Compiling $src -> $out"
& $csc "@$rsp"
if ($LASTEXITCODE -ne 0) { throw "csc exited with $LASTEXITCODE" }
Write-Host "BUILD OK: $out"
