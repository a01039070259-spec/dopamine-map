$s = [System.IO.File]::ReadAllText("$PSScriptRoot\_spots_check.json", [Text.Encoding]::UTF8) | ConvertFrom-Json
$atv = @($s | Where-Object { $_.type -eq "atv" })
$horse = @($s | Where-Object { $_.type -eq "horse" })
Write-Output ("total=$($s.Count) atv=$($atv.Count) horse=$($horse.Count)")
foreach ($x in ($atv + $horse)) {
  $len = if ($x.img) { $x.img.Length } else { 0 }
  Write-Output ("id=$($x.id) type=$($x.type) name=$($x.name) imgLen=$len")
}
