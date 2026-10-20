# run-tests.ps1 — desktop-ui-reskinner 自测一键脚本
# 用法: powershell -ExecutionPolicy Bypass -File run-tests.ps1
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
$py = Join-Path $root "scripts\reskin.py"
$asarJs = Join-Path $root "scripts\asar_pack.js"
$fx = Join-Path $here "fixtures"

$pass = 0; $fail = 0; $results = @()
function Check($name, $cond, $detail = "") {
  if ($cond) { $script:pass++; $script:results += "[PASS] $name" }
  else { $script:fail++; $script:results += "[FAIL] $name  $detail" }
}

Write-Host "== 0. 重建夹具 =="
python (Join-Path $here "build_fixtures.py") | Out-Null
Check "夹具重建" ($LASTEXITCODE -eq 0)

$qt = Join-Path $fx "fake-qt"
$el = Join-Path $fx "fake-electron"
$wpf = Join-Path $fx "fake-wpf"
$qtSkin = Join-Path $fx "skins\qt-dark"
$elSkin = Join-Path $fx "skins\electron-dark"

Write-Host "== 1. detect 三个夹具 =="
foreach ($case in @(
  @{path=$qt;   want="qt"},
  @{path=$el;   want="electron"},
  @{path=$wpf;  want="wpf"})) {
  $out = python $py --json detect --target $case.path 2>$null | ConvertFrom-Json
  Check ("detect " + (Split-Path $case.path -Leaf) + " => " + $case.want) ($out.framework -eq $case.want) ("实际=" + $out.framework)
  Check ("detect confidence 非空 " + (Split-Path $case.path -Leaf)) ($out.confidence -in @("high","medium","low"))
}

Write-Host "== 2. plan 无 --confirm 必须退出 2 且不写入 =="
$before = (Get-Content "$qt\config.ini" -Raw)
$out = python $py --json plan --target $qt --skin $qtSkin 2>$null | ConvertFrom-Json
Check "plan 退出码 2" ($LASTEXITCODE -eq 2) ("exit=" + $LASTEXITCODE)
Check "plan 标注 dry-run" ($out.mode -eq "dry-run")
Check "plan 未写入 config.ini" ((Get-Content "$qt\config.ini" -Raw) -eq $before)

Write-Host "== 3. apply --confirm (Qt) =="
$out = python $py --json apply --target $qt --skin $qtSkin --confirm 2>$null | ConvertFrom-Json
Check "apply 退出码 0" ($LASTEXITCODE -eq 0) ("exit=" + $LASTEXITCODE)
Check "apply mode=applied" ($out.mode -eq "applied")
Check "qss 已替换为深色" ((Get-Content "$qt\skins\style.qss" -Raw) -match "#1e1e1e")
Check "config.ini 已 patch 为 dark" ((Get-Content "$qt\config.ini" -Raw) -match "theme=dark")

Write-Host "== 4. verify =="
$out = python $py --json verify --target $qt 2>$null | ConvertFrom-Json
Check "verify 两个文件都 changed" (($out.checks | Where-Object {$_.status -eq "changed"}).Count -eq 2)
Check "verify-report.json 已生成" (Test-Path $out.report_path)

Write-Host "== 5. rollback =="
$out = python $py --json rollback --target $qt 2>$null | ConvertFrom-Json
Check "rollback 退出码 0" ($LASTEXITCODE -eq 0)
Check "rollback 无 mismatch" ($out.mismatches.Count -eq 0)
Check "qss 还原浅色" ((Get-Content "$qt\skins\style.qss" -Raw) -match "#ffffff")
Check "config.ini 还原 light" ((Get-Content "$qt\config.ini" -Raw) -match "theme=light")

Write-Host "== 6. Electron asar_replace 端到端 =="
$out = python $py --json apply --target $el --skin $elSkin --confirm 2>$null | ConvertFrom-Json
Check "asar apply 退出码 0" ($LASTEXITCODE -eq 0)
$css = node $asarJs extract-member "$el\resources\app.asar" "dist/styles/theme.css" 2>$null |
       Select-Object -Last 1 | ConvertFrom-Json | ForEach-Object { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_.data_b64)) }
Check "asar 内 theme.css 已替换为深色" ($css -match "#111111")
$pkg = node $asarJs extract-member "$el\resources\app.asar" "package.json" 2>$null |
       Select-Object -Last 1 | ConvertFrom-Json | ForEach-Object { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_.data_b64)) }
Check "asar 内 package.json 未变" ($pkg -match '"name": "fake-app"')

Write-Host "== 7. 安全用例：dst 越界 =="
$badSkin = Join-Path $fx "skins\bad-escape"
New-Item -ItemType Directory -Force "$badSkin\assets" | Out-Null
Copy-Item "$qtSkin\assets\style.qss" "$badSkin\assets\style.qss" -Force
'{"manifest_version":1,"name":"bad-escape","framework":"qt","version":"1.0.0","target_match":{"signals_all":["qt6core-dll"],"files_any":["FakeQtApp.exe"]},"ops":[{"op":"replace_file","src":"assets/style.qss","dst":"../evil.qss","backup":true}]}' |
  Out-File "$badSkin\skin.json" -Encoding utf8
$out = python $py --json apply --target $qt --skin $badSkin --confirm 2>$null | ConvertFrom-Json
Check "越界 apply 退出码 2" ($LASTEXITCODE -eq 2)
Check "越界文件未落到 fixtures 根" (-not (Test-Path (Join-Path $fx "evil.qss")))

Write-Host "== 8. 安全用例：must_match 不符自动回滚 =="
$bp = Join-Path $fx "skins\bad-patch"
New-Item -ItemType Directory -Force "$bp\assets" | Out-Null
Copy-Item "$qtSkin\assets\style.qss" "$bp\assets\style.qss" -Force
'{"manifest_version":1,"name":"bad-patch","framework":"qt","version":"1.0.0","target_match":{"signals_all":["qt6core-dll"],"files_any":["FakeQtApp.exe"]},"ops":[{"op":"replace_file","src":"assets/style.qss","dst":"skins/style.qss","backup":true},{"op":"patch_text","file":"config.ini","find":"theme=light","replace":"theme=dark","must_match":2,"encoding":"utf-8","backup":true}]}' |
  Out-File "$bp\skin.json" -Encoding utf8
$out = python $py --json apply --target $qt --skin $bp --confirm 2>$null | ConvertFrom-Json
Check "must_match 失败 mode=rolled-back" ($out.mode -eq "rolled-back")
Check "已做 op 回滚且无 mismatch" ($out.rollback_mismatches.Count -eq 0)
Check "qss 仍是浅色（回滚生效）" ((Get-Content "$qt\skins\style.qss" -Raw) -match "#ffffff")

Write-Host "== 9. pe_resource 缺工具返回 unsupported =="
$ws = Join-Path $fx "skins\win32-synth"
New-Item -ItemType Directory -Force "$ws\assets" | Out-Null
Copy-Item "$qtSkin\assets\style.qss" "$ws\assets\style.qss" -Force
'{"manifest_version":1,"name":"win32-synth","framework":"win32","version":"1.0.0","target_match":{"signals_all":[],"files_any":["FakeQtApp.exe"]},"ops":[{"op":"pe_resource","image":"FakeQtApp.exe","restype":"RCDATA","resname":"QSS","lang":0,"src":"assets/style.qss","backup":true}]}' |
  Out-File "$ws\skin.json" -Encoding utf8
$out = python $py --json apply --target $qt --skin $ws --confirm 2>$null | ConvertFrom-Json
Check "pe_resource 返回 unsupported" ($out.unsupported.code -eq "RESOURCE_HACKER_MISSING")

Write-Host "== 10. Bug1 回归: 从 tests 目录(CWD 非 target 根)执行 apply 必须成功 =="
Push-Location $here
$out = python $py --json apply --target $qt --skin $qtSkin --confirm 2>$null | ConvertFrom-Json
Check "非 target CWD 下 apply 成功" ($LASTEXITCODE -eq 0 -and $out.mode -eq "applied") ("exit=$LASTEXITCODE mode=$($out.mode)")
Check "非 target CWD 下 qss 落盘深色" ((Get-Content "$qt\skins\style.qss" -Raw) -match "#1e1e1e")
python $py --json rollback --target $qt 2>$null | Out-Null
Pop-Location

Write-Host ""
Write-Host "================ 结果 ================"
$results | ForEach-Object { Write-Host $_ }
Write-Host "PASS=$pass  FAIL=$fail"
if ($fail -gt 0) { exit 1 } else { exit 0 }
