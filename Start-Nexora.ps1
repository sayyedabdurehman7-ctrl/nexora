$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:NEXORA_APP_DIR = $PSScriptRoot
$backendPath = Join-Path $PSScriptRoot '.venv\Scripts\nexora-api.exe'
$uiPath = Join-Path $PSScriptRoot '.venv\Scripts\nexora-ui.exe'
$ownedBackend = $null

function Test-NexoraHealth {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2
        return ($health.status -eq 'ok' -and $health.safe_mode)
    } catch {
        return $false
    }
}

try {
    if (!(Test-Path -LiteralPath $backendPath) -or !(Test-Path -LiteralPath $uiPath)) {
        throw 'NEXORA is not installed. Follow docs\SETUP.md first.'
    }
    Write-Host 'Opening NEXORA. Please keep this window open until you close the app.'
    if (!(Test-NexoraHealth)) {
        $ownedBackend = Start-Process -FilePath $backendPath -WorkingDirectory $PSScriptRoot `
            -WindowStyle Hidden -PassThru
        $ready = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            if ($ownedBackend.HasExited) { throw 'The backend could not start. Port 8000 may be busy.' }
            if (Test-NexoraHealth) { $ready = $true; break }
            Start-Sleep -Milliseconds 500
        }
        if (!$ready) { throw 'The backend did not become ready. Try again or check docs\SETUP.md.' }
    }
    Write-Host 'First launch may download the desktop runtime. This can take a few minutes.'
    try {
        $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/conversations' -TimeoutSec 5
    } catch {
        throw 'An older or unavailable NEXORA backend is using port 8000. Close older NEXORA launchers and restart. If needed, restart Windows.'
    }
    $env:PIP_NO_CACHE_DIR = '1'
    & $uiPath
    if ($LASTEXITCODE -ne 0) { throw 'The app could not open. See the error above.' }
} catch {
    Write-Host "Could not open NEXORA: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    if ($null -ne $ownedBackend -and !$ownedBackend.HasExited) {
        Stop-Process -Id $ownedBackend.Id -ErrorAction SilentlyContinue
    }
}
