# Download theme-world hero photos for bundled venues (Unsplash)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$imgDir = Join-Path $root "images\venues"
$mapPath = Join-Path $root "venue_image_sources.json"
if (-not (Test-Path $imgDir)) { New-Item -ItemType Directory -Path $imgDir -Force | Out-Null }

$map = Get-Content $mapPath -Raw -Encoding UTF8 | ConvertFrom-Json
$done = @{}

foreach ($prop in $map.PSObject.Properties) {
  $venueId = [string]$prop.Name
  $url = [string]$prop.Value.url
  $label = [string]$prop.Value.label
  $out = Join-Path $imgDir ("venue_" + $venueId + ".jpg")

  if ($done.ContainsKey($url)) {
    Copy-Item -Force $done[$url] $out
    Write-Output "COPY venue=$venueId"
    continue
  }

  Write-Output "GET venue=$venueId — $label"
  Start-Sleep -Milliseconds 600
  $tmp = Join-Path $env:TEMP ("venue_img_" + $venueId + ".jpg")
  & curl.exe -sS -L -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DopamineMapImageFetcher/1.0" -o $tmp $url
  if ($LASTEXITCODE -ne 0) { throw "curl failed venue=$venueId" }
  $size = (Get-Item $tmp).Length
  if ($size -lt 8000) {
    $preview = [System.IO.File]::ReadAllText($tmp)
    throw "Download too small venue=$venueId ($size bytes): $preview"
  }
  Move-Item -Force $tmp $out
  $done[$url] = $out
  Write-Output "OK venue=$venueId size=$size"
}

Write-Output "Done."
