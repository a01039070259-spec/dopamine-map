param(
  [switch]$DryRun,
  [switch]$SkipExisting,
  [switch]$OnlyEmpty,
  [string[]]$Types = @()
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$imgDir = Join-Path $root "images"
$pass = "0259"
$base = "https://dopamine-map.onrender.com"
$logPath = Join-Path $root "apply_images_log.txt"

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

function Compress-ToDataUrl {
  param([string]$InputPath)
  $src = [System.Drawing.Image]::FromFile($InputPath)
  $maxW = 800; $maxH = 600
  $ratio = [Math]::Min($maxW / $src.Width, [Math]::Min($maxH / $src.Height, 1.0))
  $w = [Math]::Max(1, [int]($src.Width * $ratio))
  $h = [Math]::Max(1, [int]($src.Height * $ratio))
  $outBmp = New-Object System.Drawing.Bitmap $w, $h
  $g = [System.Drawing.Graphics]::FromImage($outBmp)
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.DrawImage($src, 0, 0, $w, $h)
  $g.Dispose(); $src.Dispose()

  $ms = New-Object System.IO.MemoryStream
  $enc = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq "image/jpeg" }
  $ep = New-Object System.Drawing.Imaging.EncoderParameters 1
  $ep.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality, 82L)
  $outBmp.Save($ms, $enc, $ep)
  $outBmp.Dispose()
  $bytes = $ms.ToArray(); $ms.Dispose()
  return "data:image/jpeg;base64," + [Convert]::ToBase64String($bytes)
}

$typeToFile = @{
  zipline     = "cat_zipline.jpg"
  bungee      = "cat_bungee.jpg"
  paragliding = "cat_paragliding.jpg"
  balloon     = "cat_balloon.jpg"
  aircraft    = "cat_aircraft.jpg"
  seawalk     = "cat_seawalk.jpg"
  skybike     = "cat_skybike.jpg"
  coaster     = "cat_coaster.jpg"
  amphibious  = "cat_amphibious.jpg"
  monorail    = "cat_monorail.jpg"
  slide       = "cat_slide.jpg"
  skywalk     = "cat_skywalk.jpg"
  netadv      = "cat_netadv.jpg"
  jetboat     = "cat_jetboat.jpg"
  kart        = "cat_kart.jpg"
  atv         = "cat_atv.jpg"
  horse       = "cat_horse.jpg"
}

$dataUrlCache = @{}
foreach ($t in $typeToFile.Keys) {
  $path = Join-Path $imgDir $typeToFile[$t]
  if (-not (Test-Path $path)) { throw ("missing image: " + $path) }
  $dataUrlCache[$t] = Compress-ToDataUrl -InputPath $path
  Write-Output ("cached " + $t + " len=" + $dataUrlCache[$t].Length)
}

$spotsOut = Join-Path $root "_spots_get.json"
$spotsText = Invoke-CurlJson -Method "GET" -Url ($base + "/api/spots") -OutPath $spotsOut
$spots = $spotsText | ConvertFrom-Json
Write-Output ("spots=" + $spots.Count)

$log = @()
$ok = 0; $skip = 0; $fail = 0

foreach ($spot in $spots) {
  $id = [int]$spot.id
  $type = [string]$spot.type
  if ($Types.Count -gt 0 -and ($Types -notcontains $type)) {
    $skip++
    continue
  }
  if ($OnlyEmpty -and $spot.img -and ([string]$spot.img).Length -gt 100) {
    $skip++
    $log += ("SKIP id=" + $id + " has img")
    continue
  }
  if ($SkipExisting -and $spot.img -and ([string]$spot.img).Length -gt 100) {
    $skip++
    $log += ("SKIP id=" + $id + " has img")
    continue
  }
  if (-not $dataUrlCache.ContainsKey($type)) {
    $fail++
    $log += ("FAIL id=" + $id + " unknown type=" + $type)
    continue
  }
  if ($DryRun) {
    $ok++
    $log += ("DRY id=" + $id + " type=" + $type)
    continue
  }

  $getPath = Join-Path $root ("_img_get_" + $id + ".json")
  $fullText = Invoke-CurlJson -Method "GET" -Url ($base + "/api/spots/" + $id) -OutPath $getPath
  if ($fullText -notmatch '"id"') {
    $fail++
    $log += ("FAIL id=" + $id + " get failed")
    continue
  }
  $payload = $fullText | ConvertFrom-Json
  $payload.img = $dataUrlCache[$type]
  $payloadPath = Join-Path $root ("_img_payload_" + $id + ".json")
  Write-Utf8Text $payloadPath ($payload | ConvertTo-Json -Depth 12 -Compress)
  $resultPath = Join-Path $root ("_img_result_" + $id + ".json")
  try {
    $resultText = Invoke-CurlJson -Method "PUT" -Url ($base + "/api/spots/" + $id) -BodyPath $payloadPath -OutPath $resultPath
    if ($resultText -match '"id"') {
      $ok++
      $res = $resultText | ConvertFrom-Json
      $log += ("OK id=" + $id + " type=" + $type + " imgLen=" + $res.img.Length)
    } else {
      $fail++
      $log += ("FAIL id=" + $id + " bad response")
    }
  } catch {
    $fail++
    $log += ("FAIL id=" + $id + " " + $_.Exception.Message)
  }
  Start-Sleep -Milliseconds 300
}

Write-Utf8Text $logPath (($log -join "`n") + "`nSUMMARY ok=$ok skip=$skip fail=$fail")
Write-Output ("SUMMARY ok=$ok skip=$skip fail=$fail")
Write-Output ("log=" + $logPath)
