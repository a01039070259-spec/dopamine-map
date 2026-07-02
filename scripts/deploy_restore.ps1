$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Output "=== 1/2 Bulk import spots to production ==="
& (Join-Path $root "bulk_import.ps1") -InputFile "bulk_spots_master_ready.json"

Write-Output "=== 2/2 Apply category images ==="
& (Join-Path $root "apply_spot_images.ps1") -OnlyEmpty

Write-Output "=== DEPLOY RESTORE DONE ==="
