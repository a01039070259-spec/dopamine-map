$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$auditPath = Join-Path $root "warns_audit.json"
$bulkPath = Join-Path $root "bulk_spots_all.json"
$survPath = Join-Path $root "survival_atv_horse.json"
$constPath = Join-Path $root "constants.json"
$typeTplPath = Join-Path $root "survival_type_templates.json"
$pass = "0259"
$base = "https://dopamine-map.onrender.com"
$logPath = Join-Path $root "fill_survival_log.txt"

function Read-Utf8Json($Path) {
  $raw = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
  return ($raw | ConvertFrom-Json)
}

function Write-Utf8Text($Path, $Text) {
  [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

function Invoke-CurlJson {
  param([string]$Method, [string]$Url, [string]$BodyPath = $null, [string]$OutPath = $null)
  $args = @("-s", "-S", "-X", $Method, $Url, "-H", ("X-Admin-Password: " + $pass), "-H", "Content-Type: application/json; charset=utf-8")
  if ($BodyPath) { $args += @("--data-binary", ("@" + $BodyPath)) }
  if ($OutPath) { $args += @("-o", $OutPath) }
  & curl.exe @args
  if ($LASTEXITCODE -ne 0) { throw ("curl failed: " + $Method + " " + $Url) }
  if ($OutPath -and (Test-Path $OutPath)) {
    return [System.IO.File]::ReadAllText($OutPath, [System.Text.Encoding]::UTF8)
  }
  return ""
}

function Convert-WarnLines {
  param([array]$Lines, $Const)
  $warnTypes = @{}
  foreach ($p in $Const.warnTypes.PSObject.Properties) { $warnTypes[$p.Name] = [string]$p.Value }
  $out = @()
  foreach ($line in $Lines) {
    $text = [string]$line
    if ($text -match '^(\S+)\s+(.*)$') {
      $icon = $matches[1]
      $tx = $matches[2]
      $t = [string]$Const.defaultWarnType
      if ($warnTypes.ContainsKey($icon)) { $t = $warnTypes[$icon] }
      $out += @{ t = $t; i = $icon; tx = $tx }
    }
  }
  if ($out.Count -eq 0) {
    $out += @{ t = "y"; i = [string]$Const.defaultWarnIcon; tx = [string]$Const.fallbackWarn }
  }
  return $out
}

$const = Read-Utf8Json $constPath
$audit = Read-Utf8Json $auditPath
$byName = @{}

foreach ($item in (Read-Utf8Json $bulkPath)) {
  $byName[[string]$item.name] = $item
}
foreach ($item in (Read-Utf8Json $survPath)) {
  $byName[[string]$item.name] = $item
}

$typeTpl = @{}
if (Test-Path $typeTplPath) {
  $tplRaw = Read-Utf8Json $typeTplPath
  foreach ($p in $tplRaw.PSObject.Properties) {
    $typeTpl[$p.Name] = $p.Value
  }
}

$log = @()
$ok = 0; $skip = 0; $fail = 0

foreach ($row in $audit) {
  if ([int]$row.warnsCount -gt 0) {
    $skip++
    continue
  }
  $id = [int]$row.id
  $name = [string]$row.name
  $type = [string]$row.type
  try {
    $src = $null
    if ($byName.ContainsKey($name)) { $src = $byName[$name] }
    elseif ($typeTpl.ContainsKey($type)) { $src = $typeTpl[$type] }

    if (-not $src) { throw ("no source for type=" + $type) }

    $getPath = Join-Path $root ("_fill_get_" + $id + ".json")
    $spotText = Invoke-CurlJson -Method "GET" -Url ($base + "/api/spots/" + $id) -OutPath $getPath
    if ($spotText -notmatch '"id"') { throw "get failed" }
    $spot = $spotText | ConvertFrom-Json

    $warnLines = @($src.warns | ForEach-Object { $_ })
    $spot.warns = Convert-WarnLines -Lines $warnLines -Const $const
    if ($src.br -and ([string]$src.br).Trim().Length -gt 0) {
      $spot.br = [string]$src.br
    }

    $payloadPath = Join-Path $root ("_fill_payload_" + $id + ".json")
    Write-Utf8Text $payloadPath ($spot | ConvertTo-Json -Depth 12 -Compress)
    $resultPath = Join-Path $root ("_fill_result_" + $id + ".json")
    $resultText = Invoke-CurlJson -Method "PUT" -Url ($base + "/api/spots/" + $id) -BodyPath $payloadPath -OutPath $resultPath
    if ($resultText -notmatch '"id"') { throw "put failed" }
    $res = $resultText | ConvertFrom-Json
    $ok++
    $log += ("OK id=" + $id + " warns=" + $res.warns.Count + " " + $name)
  } catch {
    $fail++
    $log += ("FAIL id=" + $id + " " + $name + " :: " + $_.Exception.Message)
  }
  Start-Sleep -Milliseconds 250
}

$summary = "DONE ok=$ok skip=$skip fail=$fail"
$log += $summary
Write-Utf8Text $logPath ($log -join "`n")
$log | ForEach-Object { Write-Output $_ }
