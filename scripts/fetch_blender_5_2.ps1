$ErrorActionPreference = 'Stop'
$ExpectedCommit = '9e2066aef7ef7e20c142ad7bd3303138a4304c93'
$Root = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $Root 'blender-src'

if (Test-Path (Join-Path $Source '.git')) {
  $Commit = (git -C $Source rev-parse HEAD).Trim()
  if ($Commit -ne $ExpectedCommit) {
    throw "Expected Blender 5.2.1 commit $ExpectedCommit, got $Commit."
  }
  Write-Host 'Pinned Blender checkout already exists.'
  exit 0
}

$PreviousSmudge = $env:GIT_LFS_SKIP_SMUDGE
try {
  $env:GIT_LFS_SKIP_SMUDGE = '1'
  git clone --depth 1 --branch v5.2.1 https://github.com/blender/blender.git $Source
  if ($LASTEXITCODE -ne 0) { throw 'Blender clone failed.' }
}
finally {
  $env:GIT_LFS_SKIP_SMUDGE = $PreviousSmudge
}

$Commit = (git -C $Source rev-parse HEAD).Trim()
if ($Commit -ne $ExpectedCommit) { throw "Unexpected Blender commit $Commit." }
Write-Host "Blender 5.2.1 fetched at $ExpectedCommit."

