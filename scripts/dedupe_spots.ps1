$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pass = "0259"
$base = "https://dopamine-map.onrender.com"
$logPath = Join-Path $root "dedupe_spots_log.txt"
$headers = @{ "X-Admin-Password" = $pass }

function Spot-Score($s) {
  $score = 0
  if ($s.img -and [string]$s.img.Length -gt 20) { $score += 100 }
  if ($s.lat -and $s.lng) { $score += 10 }
  return $score
}

function Get-AllSpots {
  for ($try = 1; $try -le 8; $try++) {
    try {
      $parsed = Invoke-RestMethod -Uri ($base + "/api/spots") -TimeoutSec 90
      return @($parsed)
    } catch {
      if ($try -ge 8) { throw }
      Start-Sleep -Seconds ([Math]::Min(6, $try * 2))
    }
  }
}

$spots = Get-AllSpots
$groups = $spots | Group-Object -Property name
$deleted = 0
$kept = 0
$log = @("=== dedupe " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " ===")
$log += ("before total=" + $spots.Count + " unique=" + $groups.Count)

foreach ($g in $groups) {
  if ($g.Count -eq 1) {
    $kept++
    continue
  }
  $best = $g.Group | Sort-Object @{ Expression = { Spot-Score $_ }; Descending = $true }, id | Select-Object -First 1
  foreach ($s in $g.Group) {
    if ($s.id -eq $best.id) {
      $kept++
      continue
    }
    Invoke-RestMethod -Uri ($base + "/api/spots/" + $s.id) -Method Delete -Headers $headers -TimeoutSec 30 | Out-Null
    $deleted++
    $log += ("DELETE id=" + $s.id + " name=" + $s.name)
    Start-Sleep -Milliseconds 80
  }
}

$after = @(Get-AllSpots).Count
$log += ("deleted=" + $deleted + " after=" + $after)
$log += "=== DONE ==="
[System.IO.File]::WriteAllLines($logPath, $log, (New-Object System.Text.UTF8Encoding($false)))
Write-Output ($log -join "`n")
