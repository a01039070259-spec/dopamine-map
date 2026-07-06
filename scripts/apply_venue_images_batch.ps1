param(
  [switch]$DryRun,
  [int[]]$VenueIds = @()
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$imgDir = Join-Path $root "images\venues"
$mapPath = Join-Path $root "venue_image_sources.json"
$pass = "0259"
$base = "https://dopamine-map.onrender.com"
$logPath = Join-Path $root "apply_venue_images_batch_log.txt"

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
  $maxW = 900; $maxH = 600
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
  $ep.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality, 84L)
  $outBmp.Save($ms, $enc, $ep)
  $outBmp.Dispose()
  $bytes = $ms.ToArray(); $ms.Dispose()
  return "data:image/jpeg;base64," + [Convert]::ToBase64String($bytes)
}

$map = Get-Content $mapPath -Raw -Encoding UTF8 | ConvertFrom-Json
$targets = @()
foreach ($prop in $map.PSObject.Properties) {
  $id = [int]$prop.Name
  if ($VenueIds.Count -gt 0 -and ($VenueIds -notcontains $id)) { continue }
  $targets += $id
}

$dataUrls = @{}
foreach ($id in $targets) {
  $path = Join-Path $imgDir ("venue_" + $id + ".jpg")
  if (-not (Test-Path $path)) { throw "Missing image: $path — run fetch_venue_images_batch.ps1 first" }
  $dataUrls[$id] = Compress-ToDataUrl -InputPath $path
  Write-Output ("cached venue=" + $id + " len=" + $dataUrls[$id].Length)
}

$log = @()
$ok = 0; $fail = 0

foreach ($id in $targets) {
  if ($DryRun) {
    $ok++
    $log += ("DRY id=" + $id)
    continue
  }
  $payload = @{ mainImage = $dataUrls[$id] }
  $payloadPath = Join-Path $root ("_venue_payload_" + $id + ".json")
  Write-Utf8Text $payloadPath ($payload | ConvertTo-Json -Depth 6 -Compress)
  $resultPath = Join-Path $root ("_venue_result_" + $id + ".json")
  try {
    $resultText = Invoke-CurlJson -Method "PUT" -Url ($base + "/api/venues/" + $id) -BodyPath $payloadPath -OutPath $resultPath
    if ($resultText -match '"hasImage":true') {
      $ok++
      $res = $resultText | ConvertFrom-Json
      $log += ("OK id=" + $id + " name=" + $res.name + " hasImage=" + $res.hasImage)
    } else {
      $fail++
      $log += ("FAIL id=" + $id + " bad response: " + $resultText.Substring(0, [Math]::Min(120, $resultText.Length)))
    }
  } catch {
    $fail++
    $log += ("FAIL id=" + $id + " " + $_.Exception.Message)
  }
  Start-Sleep -Milliseconds 350
}

Write-Utf8Text $logPath (($log -join "`n") + "`nSUMMARY ok=$ok fail=$fail")
Write-Output ("SUMMARY ok=$ok fail=$fail")
Write-Output ("log=" + $logPath)
