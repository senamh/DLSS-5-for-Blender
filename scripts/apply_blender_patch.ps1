$ErrorActionPreference = 'Stop'
$ExpectedCommit = '9e2066aef7ef7e20c142ad7bd3303138a4304c93'
$Root = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $Root 'blender-src'
$Patch = Join-Path $Root 'patches\blender-v5.2.1-dlss5nr.patch'

if (!(Test-Path (Join-Path $Source '.git'))) { throw 'Run scripts\fetch_blender_5_2.ps1 first.' }
$Commit = (git -C $Source rev-parse HEAD).Trim()
if ($Commit -ne $ExpectedCommit) { throw "Expected Blender 5.2.1 commit $ExpectedCommit, got $Commit." }

$Status = git -C $Source status --porcelain
if ($Status) {
  & git -C $Source apply --reverse --check $Patch *>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { Write-Host 'Patch is already applied.'; exit 0 }
  throw 'Blender checkout contains unrelated changes.'
}

git -C $Source apply --check $Patch
if ($LASTEXITCODE -ne 0) { throw 'Patch does not apply cleanly.' }
git -C $Source apply $Patch
if ($LASTEXITCODE -ne 0) { throw 'Patch application failed.' }
Write-Host 'Blender 5.2.1 DLSS 5 patch applied.'

