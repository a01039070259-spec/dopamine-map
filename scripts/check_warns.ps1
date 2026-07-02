$path = Join-Path $PSScriptRoot "_img_result_85.json"
$j = [System.IO.File]::ReadAllText($path, [Text.Encoding]::UTF8) | ConvertFrom-Json
Write-Output ("name=" + $j.name)
Write-Output ("warnsCount=" + $j.warns.Count)
$j.warns | ForEach-Object { Write-Output ($_.i + " " + $_.tx) }
