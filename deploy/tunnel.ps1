# tunnel.ps1 — SSH tunnel to the Aliyun ECS exposing the QQ-bot stack on localhost.
#
#   http://127.0.0.1:6185  AstrBot dashboard
#   http://127.0.0.1:5099  SnowLuma WebUI
#   http://127.0.0.1:6081  noVNC remote desktop (QQ QR login)
#
# Reconnects automatically. Press Ctrl+C to stop.

$ErrorActionPreference = 'Continue'
$key = Join-Path $PSScriptRoot '..\.ssh\your-key.pem'
$ssh = 'C:\WINDOWS\System32\OpenSSH\ssh.exe'
$ecs = 'root@203.0.113.10'

if (-not (Test-Path -LiteralPath $key)) {
    Write-Host "SSH key not found: $key" -ForegroundColor Red
    exit 1
}

while ($true) {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] connecting SSH tunnel to $ecs ..."
    & $ssh -N `
        -o ExitOnForwardFailure=yes `
        -o ServerAliveInterval=20 `
        -o ServerAliveCountMax=3 `
        -o TCPKeepAlive=yes `
        -o StrictHostKeyChecking=no `
        -o UserKnownHostsFile=NUL `
        -i $key `
        -L 127.0.0.1:6185:127.0.0.1:6185 `
        -L 127.0.0.1:5099:127.0.0.1:5099 `
        -L 127.0.0.1:6081:127.0.0.1:6081 `
        $ecs
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] tunnel closed (exit=$LASTEXITCODE); reconnecting in 5s ..."
    Start-Sleep -Seconds 5
}
