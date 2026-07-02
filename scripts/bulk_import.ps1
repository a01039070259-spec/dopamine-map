param(
  [string]$InputFile = "bulk_spots_ready.json"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$inputPath = Join-Path $root $InputFile
$typeMetaPath = Join-Path $root "type_meta.json"
$pass = "0259"
$base = "https://dopamine-map.onrender.com"
$logPath = Join-Path $root "bulk_import_log.txt"

function Read-Utf8Json($Path) {
  $raw = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
  return ($raw | ConvertFrom-Json)
}

function Write-Utf8Text($Path, $Text) {
  [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

function Invoke-CurlJson {
  param([string]$Method, [string]$Url, [string]$BodyPath = $null, [string]$OutPath = $null)
  $args = @("-s", "-X", $Method, $Url, "-H", ("X-Admin-Password: " + $pass), "-H", "Content-Type: application/json; charset=utf-8")
  if ($BodyPath) { $args += @("--data-binary", ("@" + $BodyPath)) }
  if ($OutPath) { $args += @("-o", $OutPath) }
  & curl.exe @args | Out-Null
  if ($OutPath -and (Test-Path $OutPath)) {
    return [System.IO.File]::ReadAllText($OutPath, [System.Text.Encoding]::UTF8)
  }
  return ""
}

function Geocode-Address {
  param([string]$Addr, [string]$Name)
  $bodyPath = Join-Path $root "_geo_body.json"
  Write-Utf8Text $bodyPath ((@{ queries = @($Addr); keywords = @($Name) } | ConvertTo-Json -Compress))
  $outPath = Join-Path $root "_geo_out.json"
  $text = Invoke-CurlJson -Method "POST" -Url ($base + "/api/admin/geocode") -BodyPath $bodyPath -OutPath $outPath
  if ($text -notmatch '"lat"') { throw "geocode failed" }
  $obj = $text | ConvertFrom-Json
  return @{ lat = [double]$obj.lat; lng = [double]$obj.lng }
}

$typeMetaRaw = Read-Utf8Json $typeMetaPath
$typeMeta = @{}
foreach ($k in $typeMetaRaw.PSObject.Properties.Name) {
  $typeMeta[$k] = @{ tl = [string]$typeMetaRaw.$k.tl; bg = [string]$typeMetaRaw.$k.bg }
}

$existing = @{}
$existingText = Invoke-CurlJson -Method "GET" -Url ($base + "/api/spots")
if ($existingText) {
  foreach ($s in ($existingText | ConvertFrom-Json)) { $existing[[string]$s.name] = $true }
}

$items = Read-Utf8Json $inputPath
$ok = 0; $skip = 0; $fail = 0
$log = @()
$idx = 0

foreach ($item in $items) {
  $name = [string]$item.name
  if ($existing.ContainsKey($name)) {
    $skip++
    $log += ("SKIP " + $name)
    continue
  }
  try {
    $type = [string]$item.type
    if (-not $typeMeta.ContainsKey($type)) { $type = "zipline" }
    $meta = $typeMeta[$type]
    $th = [int]$item.th
    $fp = [int]$item.fp
    $lat = $item.lat; $lng = $item.lng
    if (-not $lat -or -not $lng) {
      Start-Sleep -Milliseconds 350
      $geo = Geocode-Address -Addr $item.addr -Name $name
      $lat = $geo.lat; $lng = $geo.lng
    }
    $payload = @{
      name = $name
      addr = [string]$item.addr
      type = $type
      tl = if ($item.tl) { [string]$item.tl } else { $meta.tl }
      em = [string]$item.em
      bg = if ($item.bg) { [string]$item.bg } else { $meta.bg }
      img = ""
      lat = [double]$lat
      lng = [double]$lng
      th = $th
      fe = [Math]::Max(1, [Math]::Min(5, [int][Math]::Round($th * ($fp / 100.0))))
      sp = if ($item.sp) { [int]$item.sp } else { 0 }
      fp = $fp
      sp2 = [int]$item.sp2
      ap = [int]$item.ap
      rank = [string]$item.rank
      markerType = if ($th -ge 5) { "skull" } else { "fire" }
      tags = @($item.tags | ForEach-Object { [string]$_ })
      br = [string]$item.br
      ts = [string]$item.ts
      warns = @($item.warns | ForEach-Object { $_ })
      reviews = @()
      custom = $true
      approved = $true
    }
    $payloadPath = Join-Path $root ("_bulk_payload_" + $idx + ".json")
    Write-Utf8Text $payloadPath ($payload | ConvertTo-Json -Depth 10 -Compress)
    $resultPath = Join-Path $root ("_bulk_result_" + $idx + ".json")
    $resultText = Invoke-CurlJson -Method "POST" -Url ($base + "/api/spots") -BodyPath $payloadPath -OutPath $resultPath
    if ($resultText -match '"id"') {
      $ok++
      $existing[$name] = $true
      $log += ("OK   " + $name)
    } else {
      $fail++
      $short = if ($resultText.Length -gt 160) { $resultText.Substring(0, 160) } else { $resultText }
      $log += ("FAIL " + $name + " :: " + $short)
    }
  } catch {
    $fail++
    $log += ("FAIL " + $name + " :: " + $_.Exception.Message)
  }
  $idx++
  Start-Sleep -Milliseconds 200
}

$summary = "DONE ok=$ok skip=$skip fail=$fail total=$($items.Count)"
$log += $summary
Write-Utf8Text $logPath ($log -join "`n")
$log | ForEach-Object { Write-Output $_ }
