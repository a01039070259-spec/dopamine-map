$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Output "=== 1/3 Remove duplicate spots ==="
& (Join-Path $root "dedupe_spots.ps1")

Write-Output "=== 2/3 Bulk import missing spots ==="
& (Join-Path $root "bulk_import.ps1") -InputFile "bulk_spots_master_ready.json"

Write-Output "=== 3/3 Apply category images ==="
& (Join-Path $root "apply_spot_images.ps1") -OnlyEmpty

Write-Output "=== DEPLOY RESTORE DONE ==="
