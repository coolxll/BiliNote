param(
    [string]$SshHost = "rn-direct",
    [int]$LocalPort = 11308,
    [int]$RemotePort = 11308
)

$ErrorActionPreference = "Continue"

while ($true) {
    & ssh.exe `
        -N `
        -L "127.0.0.1:${LocalPort}:127.0.0.1:${RemotePort}" `
        -o "ExitOnForwardFailure=yes" `
        -o "ConnectTimeout=10" `
        -o "ServerAliveInterval=15" `
        -o "ServerAliveCountMax=3" `
        -o "TCPKeepAlive=yes" `
        $SshHost

    Start-Sleep -Seconds 3
}
