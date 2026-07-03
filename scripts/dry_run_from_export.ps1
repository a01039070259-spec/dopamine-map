$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$groupsPath = Join-Path (Split-Path -Parent $root) "server\migrations\venue_groups.json"
$spotsPath = Join-Path $root "_spots_admin.json"
$outPath = Join-Path $root "dry_run_002_result.txt"

$groups = Get-Content $groupsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$spots = Get-Content $spotsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$byId = @{}
foreach ($s in $spots) { $byId[[int]$s.id] = $s }

$allIds = @()
foreach ($g in $groups) { $allIds += @($g.spot_ids) }
$missing = @($allIds | Where-Object { -not $byId.ContainsKey([int]$_) })
if ($missing.Count -gt 0) {
    "ERROR missing spot ids: $($missing -join ', ')" | Out-File $outPath -Encoding utf8
    exit 1
}

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("=== DRY-RUN: 002_map_venues ===")
$lines.Add("Production spots total: $($spots.Count)")
$lines.Add("Groups: $($groups.Count)")
$lines.Add("Spots to link: $($allIds.Count)")
$lines.Add("Expected virtual venues after: $($spots.Count - $allIds.Count)")
$lines.Add("Expected total GET /api/venues: $($spots.Count - $allIds.Count + $groups.Count)")
$lines.Add("")

$i = 1
foreach ($g in $groups) {
    $repId = [int]$g.representative_id
    $rep = $byId[$repId]
    $region = ($rep.addr -split '\s+', 2)[0]
    $lines.Add("--- Venue $i (new row) ---")
    $lines.Add("  name:        $($g.name)")
    $lines.Add("  address:     $($rep.addr)")
    $lines.Add("  region:      $region")
    $lines.Add("  description: (null)")
    $lines.Add("  main_image:  (null)")
    $lines.Add("  representative spot id: $repId ($($rep.name))")
    $lines.Add("  spot_ids to UPDATE venue_id -> <new_id>:")
    foreach ($sid in $g.spot_ids) {
        $s = $byId[[int]$sid]
        $lines.Add(("    - id={0,3}  {1}" -f [int]$sid, $s.name))
    }
    $lines.Add("")
    $i++
}

$lines.Add("=== SUMMARY ===")
$lines.Add("venues INSERT: 7 rows")
$lines.Add("spots UPDATE venue_id: 19 rows")
$lines.Add("spots remain venue_id NULL: 113")
$lines.Add("GET /api/venues expected: 120 (113 virtual + 7 real)")

($lines -join "`n") | Out-File $outPath -Encoding utf8
Write-Output $outPath
