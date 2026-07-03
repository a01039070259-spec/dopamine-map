$ErrorActionPreference = "Stop"
$base = "https://dopamine-map.onrender.com"

$venues = Invoke-RestMethod "$base/api/venues" -TimeoutSec 120
$real = @($venues | Where-Object { -not $_.virtual })
$virtual = @($venues | Where-Object { $_.virtual })

Write-Output "GET /api/venues total: $($venues.Count)"
Write-Output "  real venues: $($real.Count)"
Write-Output "  virtual venues: $($virtual.Count)"
Write-Output ""
Write-Output "Real venue spotCount breakdown:"
$real | Sort-Object spotCount, name | ForEach-Object {
    Write-Output ("  id={0} spotCount={1} name={2}" -f $_.id, $_.spotCount, $_.name)
}
Write-Output ""
Write-Output "Virtual spotCount=1 count: $(@($virtual | Where-Object { $_.spotCount -eq 1 }).Count)"
Write-Output "Expected: total=120 real=7 virtual=113"
