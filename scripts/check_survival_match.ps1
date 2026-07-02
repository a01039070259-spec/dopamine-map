$audit = [System.IO.File]::ReadAllText("$PSScriptRoot\warns_audit.json", [Text.Encoding]::UTF8) | ConvertFrom-Json
$bulk = [System.IO.File]::ReadAllText("$PSScriptRoot\bulk_spots_all.json", [Text.Encoding]::UTF8) | ConvertFrom-Json
$byName = @{}
foreach ($x in $bulk) { $byName[[string]$x.name] = $true }
$miss = @($audit | Where-Object { $_.warnsCount -eq 0 -and -not $byName.ContainsKey([string]$_.name) })
Write-Output ("empty=" + @($audit | Where-Object { $_.warnsCount -eq 0 }).Count)
Write-Output ("bulk=" + $bulk.Count)
Write-Output ("noMatch=" + $miss.Count)
$miss | ForEach-Object { Write-Output ("MISS id=$($_.id) type=$($_.type) name=$($_.name)") }
