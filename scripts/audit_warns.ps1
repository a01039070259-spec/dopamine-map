$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pass = "0259"
$base = "https://dopamine-map.onrender.com"
$outPath = Join-Path $root "warns_audit.json"

function Invoke-CurlJson {
  param([string]$Method, [string]$Url, [string]$OutPath = $null)
  $args = @("-s", "-S", "-X", $Method, $Url, "-H", ("X-Admin-Password: " + $pass))
  if ($OutPath) { $args += @("-o", $OutPath) }
  & curl.exe @args
  if ($LASTEXITCODE -ne 0) { throw ("curl failed: " + $Url) }
  if ($OutPath -and (Test-Path $OutPath)) {
    return [System.IO.File]::ReadAllText($OutPath, [System.Text.Encoding]::UTF8)
  }
  return ""
}

$listPath = Join-Path $root "_audit_list.json"
$listText = Invoke-CurlJson -Method "GET" -Url ($base + "/api/spots") -OutPath $listPath
$list = $listText | ConvertFrom-Json
$results = @()

foreach ($s in $list) {
  $id = [int]$s.id
  $getPath = Join-Path $root ("_audit_get_" + $id + ".json")
  Start-Sleep -Milliseconds 120
  $text = Invoke-CurlJson -Method "GET" -Url ($base + "/api/spots/" + $id) -OutPath $getPath
  if ($text -notmatch '"id"') {
    $results += @{ id = $id; name = $s.name; type = $s.type; warnsCount = -1; br = "" }
    continue
  }
  $spot = $text | ConvertFrom-Json
  $wc = if ($spot.warns) { @($spot.warns).Count } else { 0 }
  $results += @{
    id = $id
    name = [string]$spot.name
    type = [string]$spot.type
    warnsCount = $wc
    br = [string]$spot.br
    hasImg = ([string]$spot.img).Length -gt 100
  }
  Write-Output ("id=$id wc=$wc type=$($spot.type) name=$($spot.name)")
}

$empty = @($results | Where-Object { $_.warnsCount -eq 0 })
Write-Output ("TOTAL=$($results.Count) EMPTY=$($empty.Count)")
[System.IO.File]::WriteAllText($outPath, ($results | ConvertTo-Json -Depth 5 -Compress), (New-Object System.Text.UTF8Encoding($false)))
