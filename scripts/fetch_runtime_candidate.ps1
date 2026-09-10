[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RuntimeDirectory)
$ErrorActionPreference = 'Stop'
# Community candidate used by DLSS5oneclick, not a verified Blender runtime.
$Url = 'https://github.com/RankFTW/rhi-repo/releases/download/dlssnr-310.8.SF-v2/nvngx_dlssnr_310.8.SF-v2.zip'
$Expected = '1da35941894994eb087e017577829e492454e9bae3a6a9397027069ceb74955c'
New-Item -ItemType Directory $RuntimeDirectory -Force | Out-Null
$Destination = Join-Path $RuntimeDirectory 'nvngx_dlssnr.dll'
if (Test-Path $Destination) { throw 'Runtime already exists; use a new directory.' }
$Work = Join-Path ([System.IO.Path]::GetTempPath()) ('dlss5-candidate-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $Work | Out-Null
$Archive = Join-Path $Work 'runtime.zip'
Invoke-WebRequest -Uri $Url -OutFile $Archive
if ((Get-FileHash $Archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Expected) {
  throw "Archive SHA256 mismatch. Download retained at $Archive; nothing installed."
}
# Read exactly one expected member without extracting arbitrary archive paths.
Add-Type -AssemblyName System.IO.Compression.FileSystem
$Zip = [System.IO.Compression.ZipFile]::OpenRead($Archive)
try {
  $Entries = @($Zip.Entries | Where-Object { $_.Name -ieq 'nvngx_dlssnr.dll' })
  if ($Entries.Count -ne 1) { throw 'Expected exactly one nvngx_dlssnr.dll in the archive.' }
  [System.IO.Compression.ZipFileExtensions]::ExtractToFile($Entries[0], $Destination, $false)
}
finally { $Zip.Dispose() }
$Receipt = [ordered]@{
  source = $Url
  archive_sha256 = $Expected
  dll_sha256 = (Get-FileHash $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
  compatibility_verified = $false
  note = 'Download integrity only. Run Test Runtime on the target GPU before enabling DLSS.'
}
$Receipt | ConvertTo-Json | Set-Content (Join-Path $RuntimeDirectory 'download-source.json') -Encoding UTF8
Write-Host "Runtime candidate downloaded: $Destination"
Write-Host 'No DLL executed. RTX 4070 / Blender compatibility remains unverified.'

