[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$OptixRoot,
  [ValidateRange(1,64)][int]$Jobs = 4
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $Root 'blender-src'
$Build = Join-Path $Root 'build\blender-windows'
$Native = Join-Path $Root 'build\native-windows'
$ExpectedCommit = '9e2066aef7ef7e20c142ad7bd3303138a4304c93'

function Invoke-Checked {
  param([string]$Program, [string[]]$Arguments)
  & $Program @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}

if ($env:OS -ne 'Windows_NT') { throw 'Windows x64 is required.' }
foreach ($Tool in @('git', 'cmake', 'python')) {
  if (!(Get-Command $Tool -ErrorAction SilentlyContinue)) { throw "Install $Tool first." }
}
if (!(Test-Path (Join-Path $OptixRoot 'include\optix.h'))) {
  throw 'OptixRoot must point to an installed NVIDIA OptiX SDK.'
}
$OptixRoot = (Resolve-Path $OptixRoot).Path
if (!(Test-Path (Join-Path $Source '.git'))) {
  throw 'Run scripts\fetch_blender_5_2.ps1 first.'
}
$Commit = & git -C $Source rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $Commit.Trim() -ne $ExpectedCommit) {
  throw "Blender source must be pinned to $ExpectedCommit."
}
# Fetch libraries at the submodule commit recorded by Blender, never update HEAD.
Invoke-Checked git @('lfs', 'version')
# The source checkout skips smudging during clone. Its own startup blend and
# other LFS assets must be restored too, independently of the library submodule.
# GitHub is a code mirror; the large binary assets live on Blender's server.
Invoke-Checked git @('-C', $Source, '-c',
  'lfs.url=https://projects.blender.org/blender/blender.git/info/lfs', 'lfs', 'pull')
Invoke-Checked git @('-C', $Source, 'submodule', 'update', '--init', '--checkout', 'lib/windows_x64')
Invoke-Checked git @('-C', (Join-Path $Source 'lib\windows_x64'), 'lfs', 'pull')
# Run in a child shell: the existing patch helper uses exit for an applied patch.
Invoke-Checked powershell @('-NoProfile', '-File', (Join-Path $PSScriptRoot 'apply_blender_patch.ps1'))

$Portable = Join-Path $Root ('dist\blender-dlss5nr-' + [guid]::NewGuid().ToString('N'))
Invoke-Checked cmake @('-S', (Join-Path $Root 'native'), '-B', $Native,
  '-G', 'Visual Studio 17 2022', '-A', 'x64')
Invoke-Checked cmake @('--build', $Native, '--config', 'Release', '--parallel', "$Jobs")
Invoke-Checked python @((Join-Path $PSScriptRoot 'check_bridge_exports.py'), (Join-Path $Native 'Release'))
Invoke-Checked cmake @('-S', $Source, '-B', $Build,
  '-G', 'Visual Studio 17 2022', '-A', 'x64',
  '-DWITH_CYCLES=ON', '-DWITH_CYCLES_DLSS5_NR=ON',
  '-DWITH_CYCLES_DEVICE_CUDA=ON', '-DWITH_CYCLES_CUDA_BINARIES=ON',
  '-DCYCLES_CUDA_BINARIES_ARCH=sm_120', '-DWITH_CYCLES_CUDA_BUILD_SERIAL=ON',
  '-DWITH_CYCLES_DEVICE_OPTIX=ON', "-DOPTIX_ROOT_DIR=$OptixRoot",
  "-DCMAKE_INSTALL_PREFIX=$Portable")
# Compile our integration first. MSBuild otherwise continues unrelated Blender
# targets for hours after an early Cycles compile failure.
Invoke-Checked cmake @('--build', $Build, '--config', 'Release', '--target', 'cycles_integrator', '--parallel', "$Jobs")
Invoke-Checked cmake @('--build', $Build, '--config', 'Release', '--target', 'INSTALL', '--parallel', "$Jobs")
$Blender = Join-Path $Portable 'blender.exe'
if (!(Test-Path $Blender)) { throw "Installed blender.exe missing at $Blender" }
# No NVIDIA runtime is loaded by this smoke check.
Invoke-Checked $Blender @('--background', '--factory-startup', '--python-exit-code', '1',
  '--python-expr', 'import _cycles; assert _cycles.with_dlss5nr, "DLSS backend missing"')
Copy-Item (Join-Path $Native 'Release\dlss5nr_bridge.dll') $Portable
New-Item -ItemType Directory (Join-Path $Portable 'runtime\caller') -Force | Out-Null
Copy-Item (Join-Path $Native 'Release\nvngx.dll_blender.dll') (Join-Path $Portable 'runtime\caller')
# Local preferences keep the installed official Blender profile untouched.
New-Item -ItemType Directory (Join-Path $Portable '5.2\config') -Force | Out-Null
Invoke-Checked python @((Join-Path $PSScriptRoot 'package_addon.py'))
Copy-Item (Join-Path $Root 'dist\cycles_dlss5-experimental.zip') $Portable
Copy-Item (Join-Path $Root 'docs\WINDOWS_BUILD.md') $Portable
Copy-Item (Join-Path $Root 'THIRD_PARTY_NOTICES.md') $Portable
New-Item -ItemType Directory (Join-Path $Portable 'dlss5-addon\cycles_dlss5') -Force | Out-Null
Copy-Item (Join-Path $Root 'addon\cycles_dlss5\*.py') (Join-Path $Portable 'dlss5-addon\cycles_dlss5')
foreach ($File in @('start_portable.py', 'Start-DLSS-Blender.cmd', 'smoke_portable.py')) {
  Copy-Item (Join-Path $PSScriptRoot $File) $Portable
}
Copy-Item (Join-Path $Root 'LICENSE') (Join-Path $Portable 'DLSS5-LICENSE.txt')
Invoke-Checked $Blender @('--background', '--factory-startup', '--python-exit-code', '1',
  '--python', (Join-Path $Portable 'smoke_portable.py'))
Write-Host "Build and backend-import check complete: $Portable"
Write-Host 'Start with Start-DLSS-Blender.cmd; the panel is already enabled.'
Write-Host 'Neural rendering NOT tested. NVIDIA runtime intentionally not bundled.'

