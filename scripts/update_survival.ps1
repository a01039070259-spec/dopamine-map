$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$inputPath = Join-Path $root "survival_atv_horse.json"
$constPath = Join-Path $root "constants.json"
$pass = "0259"
$base = "https://dopamine-map.onrender.com"
$logPath = Join-Path $root "survival_update_log.txt"

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
  return $out
}

$const = Read-Utf8Json $constPath
$items = Read-Utf8Json $inputPath
$log = @()
$ok = 0; $fail = 0

foreach ($item in $items) {
  $id = [int]$item.id
  $name = [string]$item.name
  try {
    $getPath = Join-Path $root ("_surv_get_" + $id + ".json")
    $spotText = Invoke-CurlJson -Method "GET" -Url ($base + "/api/spots/" + $id) -OutPath $getPath
    if ($spotText -notmatch '"id"') { throw "get failed" }
    $spot = $spotText | ConvertFrom-Json
    $spot.br = [string]$item.br
    $spot.warns = Convert-WarnLines -Lines @($item.warns) -Const $const
    $payloadPath = Join-Path $root ("_surv_payload_" + $id + ".json")
    Write-Utf8Text $payloadPath ($spot | ConvertTo-Json -Depth 12 -Compress)
    $resultPath = Join-Path $root ("_surv_result_" + $id + ".json")
    $resultText = Invoke-CurlJson -Method "PUT" -Url ($base + "/api/spots/" + $id) -BodyPath $payloadPath -OutPath $resultPath
    if ($resultText -notmatch '"id"') { throw "put failed" }
    $res = $resultText | ConvertFrom-Json
    $ok++
    $log += ("OK id=" + $id + " name=" + $name + " warns=" + $res.warns.Count + " br=" + $res.br.Substring(0, [Math]::Min(28, $res.br.Length)))
  } catch {
    $fail++
    $log += ("FAIL id=" + $id + " name=" + $name + " :: " + $_.Exception.Message)
  }
  Start-Sleep -Milliseconds 350
}

$summary = "DONE ok=$ok fail=$fail total=$($items.Count)"
$log += $summary
Write-Utf8Text $logPath ($log -join "`n")
$log | ForEach-Object { Write-Output $_ }
