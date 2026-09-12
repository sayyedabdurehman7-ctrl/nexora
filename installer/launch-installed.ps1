$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:NEXORA_APP_DIR = $PSScriptRoot
$backend = Join-Path $PSScriptRoot 'backend\NexoraBackend.exe'
$ui = Join-Path $PSScriptRoot 'NEXORA.exe'
$owned = $null

function Test-Health {
    try { return (Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 2).status -eq 'ok' }
    catch { return $false }
}

try {
    if (!(Test-Path $backend) -or !(Test-Path $ui)) { throw 'NEXORA files are incomplete. Reinstall the application.' }
    if (!(Test-Health)) {
        $owned = Start-Process -FilePath $backend -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
        for ($i = 0; $i -lt 30 -and !(Test-Health); $i++) {
            if ($owned.HasExited) { throw 'NEXORA backend stopped unexpectedly.' }
            Start-Sleep -Milliseconds 500
        }
        if (!(Test-Health)) { throw 'NEXORA backend did not become ready.' }
    }
    & $ui
    if ($LASTEXITCODE -ne 0) { throw 'NEXORA could not open.' }
} catch {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($_.Exception.Message, 'NEXORA', 'OK', 'Error') | Out-Null
    exit 1
} finally {
    if ($null -ne $owned -and !$owned.HasExited) { Stop-Process $owned.Id -ErrorAction SilentlyContinue }
}
