param(
  [string]$InputFile = "bulk_spots_all.json",
  [string]$OutputFile = "bulk_spots_ready.json"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$inputPath = Join-Path $root $InputFile
$outPath = Join-Path $root $OutputFile
$constPath = Join-Path $root "constants.json"

function Read-Utf8Json($Path) {
  $raw = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
  return ($raw | ConvertFrom-Json)
}

function Write-Utf8Text($Path, $Text) {
  [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

$const = Read-Utf8Json $constPath
$fire = [string]$const.fire
$warnTypes = @{}
foreach ($p in $const.warnTypes.PSObject.Properties) { $warnTypes[$p.Name] = [string]$p.Value }

$items = Read-Utf8Json $inputPath
$out = @()

foreach ($item in $items) {
  $th = [Math]::Max(1, [Math]::Min(5, [int]$item.th))
  $warnOut = @()
  foreach ($w in ($item.warns | ForEach-Object { $_ })) {
    if ($w -match '^(\S+)\s+(.*)$') {
      $icon = $matches[1]
      $tx = $matches[2]
      $t = $const.defaultWarnType
      if ($warnTypes.ContainsKey($icon)) { $t = $warnTypes[$icon] }
      $warnOut += @{ t = $t; i = $icon; tx = $tx }
    }
  }
  if ($warnOut.Count -eq 0) {
    $warnOut += @{ t = "y"; i = [string]$const.defaultWarnIcon; tx = [string]$const.fallbackWarn }
  }
  $obj = @{
    name = [string]$item.name
    addr = [string]$item.addr
    type = [string]$item.type
    tl = [string]$item.tl
    em = [string]$item.em
    th = $th
    fp = [int]$item.fp
    sp2 = [int]$item.sp2
    ap = [int]$item.ap
    sp = if ($item.sp) { [int]$item.sp } else { 0 }
    rank = [string]$item.rank
    br = [string]$item.br
    tags = @($item.tags | ForEach-Object { [string]$_ })
    ts = ($fire * $th)
    warns = $warnOut
    img = ""
    reviews = @()
    custom = $true
    approved = $true
  }
  if ($item.bg) { $obj.bg = [string]$item.bg }
  if ($item.lat) { $obj.lat = [double]$item.lat }
  if ($item.lng) { $obj.lng = [double]$item.lng }
  $out += $obj
}

Write-Utf8Text $outPath ($out | ConvertTo-Json -Depth 10 -Compress)
Write-Output ("READY=" + $out.Count)
