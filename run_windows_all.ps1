$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$rootVenvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$backendVenvPython = Join-Path $backendDir ".venv\Scripts\python.exe"

$lanIp = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.IPAddress -notlike '127.*' -and
        $_.IPAddress -notlike '169.254.*' -and
        $_.InterfaceAlias -eq 'WiFi'
    } |
    Select-Object -ExpandProperty IPAddress -First 1

if (-not $lanIp) {
    $lanIp = Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object {
            $_.IPAddress -notlike '127.*' -and
            $_.IPAddress -notlike '169.254.*'
        } |
        Select-Object -ExpandProperty IPAddress -First 1
}

if (Test-Path $rootVenvPython) {
    $pythonCommand = "& '$rootVenvPython'"
} elseif (Test-Path $backendVenvPython) {
    $pythonCommand = "& '$backendVenvPython'"
} else {
    $pythonCommand = "python"
}

$backendPythonExe = if (Test-Path $rootVenvPython) { $rootVenvPython } elseif (Test-Path $backendVenvPython) { $backendVenvPython } else { "python" }
$pollerPythonExe = $backendPythonExe
$frontendCommand = "Set-Location '$frontendDir'; npm.cmd run dev"

Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match 'uvicorn main:app' } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

for ($i = 0; $i -lt 40; $i++) {
    if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
        break
    }
    Start-Sleep -Milliseconds 250
}

Start-Process -FilePath $backendPythonExe -WorkingDirectory $backendDir -ArgumentList @(
    '-m', 'uvicorn', 'main:app', '--reload', '--host', '0.0.0.0', '--port', '8000'
)

$backendReady = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/' -UseBasicParsing -TimeoutSec 1
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
            $backendReady = $true
            break
        }
    } catch {
        Start-Sleep -Milliseconds 500
    }
}

if (-not $backendReady) {
    Write-Host "Backend did not become ready on http://127.0.0.1:8000/; frontend and poller will not be started."
    exit 1
}

Start-Process -FilePath $pollerPythonExe -WorkingDirectory $backendDir -ArgumentList @('poller.py')

Start-Process powershell.exe -WorkingDirectory $frontendDir -ArgumentList @(
    '-NoExit',
    '-ExecutionPolicy', 'Bypass',
    '-Command', $frontendCommand
)

Write-Host "Started backend, poller, and frontend in separate PowerShell windows."
if ($lanIp) {
    Write-Host "Frontend URL: http://$lanIp`:5173"
    Write-Host "Backend URL:  http://$lanIp`:8000"
} else {
    Write-Host "Could not detect a LAN IP automatically. Run Get-NetIPAddress -AddressFamily IPv4 and use your Wi-Fi IPv4 address."
}