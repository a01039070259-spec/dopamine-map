$ErrorActionPreference = "Stop"
$base = "https://dopamine-map.onrender.com"

Write-Output "=== Render persistence check ==="
$h = Invoke-RestMethod -Uri ($base + "/api/health") -TimeoutSec 90
Write-Output ("ok=" + $h.ok)
Write-Output ("dataDir=" + $h.dataDir)
Write-Output ("dataDirWritable=" + $h.dataDirWritable)
Write-Output ("dbExists=" + $h.dbExists)
Write-Output ("spotCount=" + $h.spotCount)
Write-Output ("persistentDiskExpected=" + $h.persistentDiskExpected)

if ($h.dataDir -ne "/app/data") {
  Write-Output "WARN: DOPAMINE_DATA_DIR is not /app/data — disk mount may be wrong"
}
if (-not $h.dataDirWritable) {
  Write-Output "FAIL: data dir not writable — check Render disk attachment"
  exit 1
}
if ($h.spotCount -eq 0) {
  Write-Output "WARN: no spots — run scripts/deploy_restore.ps1"
}
Write-Output "=== OK ==="
