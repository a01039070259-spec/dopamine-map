$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$groupsPath = Join-Path (Split-Path -Parent $root) "server\migrations\venue_groups.json"
$groups = Get-Content $groupsPath -Raw -Encoding UTF8 | ConvertFrom-Json

$spots = Invoke-RestMethod "https://dopamine-map.onrender.com/api/spots" -TimeoutSec 120
$byId = @{}
foreach ($s in $spots) { $byId[[int]$s.id] = $s }

$allIds = @()
foreach ($g in $groups) { $allIds += @($g.spot_ids) }
$missing = @($allIds | Where-Object { -not $byId.ContainsKey([int]$_) })
if ($missing.Count -gt 0) {
    Write-Output "ERROR missing spot ids: $($missing -join ', ')"
    exit 1
}

Write-Output "=== DRY-RUN: 002_map_venues ==="
Write-Output "Production spots total: $($spots.Count)"
Write-Output "Groups: $($groups.Count)"
Write-Output "Spots to link: $($allIds.Count)"
Write-Output "Expected virtual venues after: $($spots.Count - $allIds.Count)"
Write-Output "Expected total GET /api/venues: $($spots.Count - $allIds.Count + $groups.Count)"
Write-Output ""

$i = 1
foreach ($g in $groups) {
    $repId = [int]$g.representative_id
    $rep = $byId[$repId]
    $region = ($rep.addr -split '\s+', 2)[0]
    Write-Output "--- Venue $i (new row) ---"
    Write-Output "  name:        $($g.name)"
    Write-Output "  address:     $($rep.addr)"
    Write-Output "  region:      $region"
    Write-Output "  description: (null)"
    Write-Output "  main_image:  (null)"
    Write-Output "  representative spot id: $repId ($($rep.name))"
    Write-Output "  spot_ids to UPDATE venue_id -> <new_id>:"
    foreach ($sid in $g.spot_ids) {
        $s = $byId[[int]$sid]
        Write-Output ("    - id={0,3}  {1}" -f [int]$sid, $s.name)
    }
    Write-Output ""
    $i++
}

Write-Output "=== SUMMARY ==="
Write-Output "venues INSERT: 7 rows"
Write-Output "spots UPDATE venue_id: 19 rows"
Write-Output "spots remain venue_id NULL: 113"
Write-Output "GET /api/venues expected: 120 (113 virtual + 7 real)"
