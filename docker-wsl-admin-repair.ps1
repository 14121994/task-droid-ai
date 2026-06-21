$ErrorActionPreference = 'Continue'

$log = Join-Path $PSScriptRoot 'docker-wsl-admin-repair.log'
Start-Transcript -Path $log -Force | Out-Null

Write-Host "== Docker/WSL admin repair started: $(Get-Date -Format o) =="

Write-Host "`n== Enabling Windows optional features =="
$features = @(
  'Microsoft-Windows-Subsystem-Linux',
  'VirtualMachinePlatform',
  'HypervisorPlatform'
)

foreach ($feature in $features) {
  Write-Host "`n-- $feature --"
  Enable-WindowsOptionalFeature -Online -FeatureName $feature -All -NoRestart
}

Write-Host "`n== Setting hypervisor launch type =="
bcdedit /set hypervisorlaunchtype auto

Write-Host "`n== Service status before start =="
Get-Service vmcompute, hns, WSLService -ErrorAction SilentlyContinue |
  Select-Object Name, DisplayName, Status, StartType |
  Format-Table -AutoSize

Write-Host "`n== Starting services =="
Start-Service vmcompute -ErrorAction Continue
Start-Service hns -ErrorAction Continue
Start-Service WSLService -ErrorAction Continue

Write-Host "`n== Service status after start =="
Get-Service vmcompute, hns, WSLService -ErrorAction SilentlyContinue |
  Select-Object Name, DisplayName, Status, StartType |
  Format-Table -AutoSize

Write-Host "`n== WSL status =="
wsl --status
wsl --list --all --verbose

Write-Host "`n== Complete =="
Write-Host "If any feature changed state, reboot Windows before retrying Docker Desktop."

Stop-Transcript | Out-Null
