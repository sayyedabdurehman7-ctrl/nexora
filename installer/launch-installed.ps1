param([switch]$RecoveryTest)

$ErrorActionPreference = 'Stop'
$appVersion = '0.3.0'
$appDir = $PSScriptRoot
$profileFile = Join-Path $appDir 'build-profile.txt'
$buildProfile = if (Test-Path -LiteralPath $profileFile) {
    (Get-Content -LiteralPath $profileFile -Raw).Trim().ToLowerInvariant()
} else { 'tester' }
if ($buildProfile -notin @('developer', 'tester', 'production')) { $buildProfile = 'tester' }
$dataRoot = Join-Path $env:LOCALAPPDATA 'NEXORA'
$logFolder = Join-Path $dataRoot 'logs'
$logFile = Join-Path $logFolder 'nexora.log'
$tempStdout = Join-Path $logFolder 'backend-output.tmp'
$tempStderr = Join-Path $logFolder 'backend-error.tmp'
$restartSignal = Join-Path $dataRoot 'restart-service.request'
$backend = Join-Path $appDir 'backend\NexoraBackend.exe'
$ui = Join-Path $appDir 'NEXORA.exe'
$script:startupStage = 'launcher initialization'
$script:ownedBackend = $null
$script:instanceMutex = $null

New-Item -ItemType Directory -Force -Path $logFolder, (Join-Path $dataRoot 'data'), `
    (Join-Path $dataRoot 'data\user_files'), (Join-Path $dataRoot 'feedback'), `
    (Join-Path $dataRoot 'exports') | Out-Null
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Text.UTF8Encoding]::new($false)

function Protect-DiagnosticText([string]$Text) {
    if (!$Text) { return '' }
    $safe = $Text -replace '(?i)(GEMINI_API_KEY|api[_ -]?key|authorization|token|password)\s*[:=]\s*\S+', '$1=[redacted]'
    $safe = $safe -replace '\b(?:sk|AIza)[A-Za-z0-9_-]{12,}\b', '[redacted]'
    $userProfile = [Environment]::GetFolderPath('UserProfile')
    if ($userProfile) { $safe = $safe.Replace($userProfile, '%USERPROFILE%') }
    if ($env:LOCALAPPDATA) { $safe = $safe.Replace($env:LOCALAPPDATA, '%LOCALAPPDATA%') }
    return $safe
}

function Write-NexoraLog([string]$Stage, [string]$Message, [string]$Details = '') {
    if ((Test-Path -LiteralPath $logFile) -and (Get-Item -LiteralPath $logFile).Length -gt 2097152) {
        $archive = Join-Path $logFolder 'nexora.previous.log'
        Move-Item -LiteralPath $logFile -Destination $archive -Force
    }
    $timestamp = [DateTime]::UtcNow.ToString('o')
    $windows = [Environment]::OSVersion.VersionString
    $safeMessage = Protect-DiagnosticText $Message
    $safeDetails = Protect-DiagnosticText $Details
    $entry = "[$timestamp] version=$appVersion profile=$buildProfile windows=`"$windows`" stage=`"$Stage`" message=`"$safeMessage`""
    if ($safeDetails) { $entry += "`r`n$safeDetails" }
    Add-Content -LiteralPath $logFile -Value $entry -Encoding UTF8
}

function Get-ErrorReport([string]$Failure) {
    $tail = if (Test-Path -LiteralPath $logFile) {
        (Get-Content -LiteralPath $logFile -Tail 80 -ErrorAction SilentlyContinue) -join "`r`n"
    } else { 'No diagnostic log is available.' }
    return Protect-DiagnosticText @"
NEXORA Error Report
Version: $appVersion
Build profile: $buildProfile
Windows: $([Environment]::OSVersion.VersionString)
Startup stage: $script:startupStage
Problem: $Failure

Recent diagnostic log:
$tail
"@
}

function Show-NexoraRecovery([string]$Failure) {
    Add-Type -AssemblyName PresentationFramework
    [xml]$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" Title="NEXORA needs attention"
 Height="285" Width="590" WindowStartupLocation="CenterScreen" ResizeMode="NoResize" Background="#0B0B0D">
  <Grid Margin="28">
    <Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="*"/><RowDefinition Height="Auto"/></Grid.RowDefinitions>
    <TextBlock Text="NEXORA needs attention" Foreground="#F4F4F5" FontSize="24" FontWeight="SemiBold"/>
    <TextBlock Grid.Row="1" Margin="0,22,0,18" TextWrapping="Wrap" FontSize="15" Foreground="#D4D4D8"
      Text="NEXORA could not start its local service. Your chats and saved data have not been removed."/>
    <StackPanel Grid.Row="2" Orientation="Horizontal" HorizontalAlignment="Right">
      <Button Name="OpenLogs" Content="Open Diagnostic Folder" Margin="0,0,8,0" Padding="12,7"/>
      <Button Name="CopyReport" Content="Copy Error Report" Margin="0,0,8,0" Padding="12,7"/>
      <Button Name="CloseButton" Content="Close" Margin="0,0,8,0" Padding="12,7"/>
      <Button Name="TryAgain" Content="Try Again" Padding="14,7" Background="#596FE8" Foreground="White"/>
    </StackPanel>
  </Grid>
</Window>
'@
    $reader = New-Object System.Xml.XmlNodeReader $xaml
    $window = [Windows.Markup.XamlReader]::Load($reader)
    $window.FindName('OpenLogs').Add_Click({ Start-Process -FilePath 'explorer.exe' -ArgumentList $logFolder })
    $window.FindName('CopyReport').Add_Click({ [Windows.Clipboard]::SetText((Get-ErrorReport $Failure)) })
    $window.FindName('TryAgain').Add_Click({ $window.Tag = 'TryAgain'; $window.Close() })
    $window.FindName('CloseButton').Add_Click({ $window.Tag = 'Close'; $window.Close() })
    if ($RecoveryTest) {
        $timer = New-Object Windows.Threading.DispatcherTimer
        $timer.Interval = [TimeSpan]::FromMilliseconds(750)
        $timer.Add_Tick({ $timer.Stop(); $window.Tag = 'Close'; $window.Close() })
        $timer.Start()
    }
    $null = $window.ShowDialog()
    return [string]$window.Tag
}

function Get-FreeLoopbackPort {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    try {
        $listener.Start()
        return ([Net.IPEndPoint]$listener.LocalEndpoint).Port
    } finally { $listener.Stop() }
}

function Get-BackendError {
    $details = @()
    if (Test-Path -LiteralPath $tempStdout) { $details += Get-Content -LiteralPath $tempStdout -ErrorAction SilentlyContinue }
    if (Test-Path -LiteralPath $tempStderr) { $details += Get-Content -LiteralPath $tempStderr -ErrorAction SilentlyContinue }
    return Protect-DiagnosticText ($details -join "`r`n")
}

function Test-NexoraHealth([int]$Port) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
        return $health.status -eq 'ok' -and $health.version -eq $appVersion -and `
            $health.build_profile -eq $buildProfile -and $health.safe_mode
    } catch { return $false }
}

function Stop-OwnedBackend {
    if ($null -ne $script:ownedBackend -and !$script:ownedBackend.HasExited) {
        Stop-Process -Id $script:ownedBackend.Id -ErrorAction SilentlyContinue
        $script:ownedBackend.WaitForExit(3000) | Out-Null
    }
    $script:ownedBackend = $null
}

function Start-ManagedBackend([int]$Port) {
    $env:PORT = [string]$Port
    $env:NEXORA_API_URL = "http://127.0.0.1:$Port"
    Remove-Item -LiteralPath $tempStdout, $tempStderr -Force -ErrorAction SilentlyContinue
    $script:ownedBackend = Start-Process -FilePath $backend -WorkingDirectory $appDir -WindowStyle Hidden `
        -RedirectStandardOutput $tempStdout -RedirectStandardError $tempStderr -PassThru
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($script:ownedBackend.HasExited) {
            $exitCode = $script:ownedBackend.ExitCode
            throw "The local service stopped during startup (exit code $exitCode).`r`n$(Get-BackendError)"
        }
        if (Test-NexoraHealth $Port) { return }
        Start-Sleep -Milliseconds 250
    }
    throw "The local service did not become ready in time.`r`n$(Get-BackendError)"
}

function Start-NexoraSession {
    if (!(Test-Path -LiteralPath $backend) -or !(Test-Path -LiteralPath $ui)) {
        throw 'Required application files are missing. Reinstall NEXORA.'
    }
    $script:startupStage = 'preparing user data'
    $userEnv = Join-Path $dataRoot '.env'
    if (!(Test-Path -LiteralPath $userEnv)) {
        Copy-Item -LiteralPath (Join-Path $appDir '.env.example') -Destination $userEnv
    }
    $env:NEXORA_APP_DIR = $appDir
    $env:NEXORA_DATA_DIR = $dataRoot
    $env:NEXORA_BUILD_PROFILE = $buildProfile
    if ($buildProfile -eq 'tester') {
        $env:LLM_PROVIDER = 'mock'
        $env:GEMINI_API_KEY = ''
        $env:GEMINI_MODEL = ''
    }
    $databasePath = (Join-Path $dataRoot 'data\nexora.db').Replace('\', '/')
    $env:DATABASE_URL = "sqlite:///$databasePath"
    $env:NEXORA_WORKSPACE_DIR = Join-Path $dataRoot 'data\user_files'
    try {
        $script:startupStage = 'starting local service'
        $ready = $false
        for ($startAttempt = 1; $startAttempt -le 3; $startAttempt++) {
            $port = Get-FreeLoopbackPort
            Write-NexoraLog $script:startupStage "Starting on loopback port $port (attempt $startAttempt of 3)."
            try {
                Start-ManagedBackend $port
                $ready = $true
                break
            } catch {
                Write-NexoraLog $script:startupStage 'Local service start attempt failed.' (Get-BackendError)
                Stop-OwnedBackend
            }
        }
        if (!$ready) { throw "The local service did not become ready after three attempts.`r`n$(Get-BackendError)" }

        $script:startupStage = 'opening desktop interface'
        Write-NexoraLog $script:startupStage 'Local service health check passed.'
        $uiProcess = Start-Process -FilePath $ui -WorkingDirectory $appDir -PassThru
        $healthFailures = 0
        $restartAttempts = 0
        $recoveryExhausted = $false
        while (!$uiProcess.HasExited) {
            Start-Sleep -Milliseconds 750
            $manualRestart = Test-Path -LiteralPath $restartSignal
            if ($manualRestart) {
                Remove-Item -LiteralPath $restartSignal -Force -ErrorAction SilentlyContinue
                $restartAttempts = 0
                $recoveryExhausted = $false
                $healthFailures = 3
                Write-NexoraLog 'runtime recovery' 'The user requested a local service restart.'
            } elseif (!$recoveryExhausted -and (
                $null -eq $script:ownedBackend -or $script:ownedBackend.HasExited -or !(Test-NexoraHealth $port)
            )) {
                $healthFailures++
            } else {
                if (!$recoveryExhausted -and $healthFailures -gt 0) {
                    Write-NexoraLog 'runtime health' 'Local service connection recovered.'
                }
                if (!$recoveryExhausted) { $healthFailures = 0 }
            }

            if ($healthFailures -ge 3 -and $restartAttempts -lt 3) {
                $restartAttempts++
                $exitDetails = Get-BackendError
                Write-NexoraLog 'runtime recovery' "Restarting local service (attempt $restartAttempts of 3)." $exitDetails
                Stop-OwnedBackend
                try {
                    Start-ManagedBackend $port
                    $healthFailures = 0
                    $recoveryExhausted = $false
                } catch {
                    Write-NexoraLog 'runtime recovery' 'Local service restart failed.' (Get-BackendError)
                    Stop-OwnedBackend
                }
            } elseif ($healthFailures -ge 3 -and $restartAttempts -ge 3) {
                Write-NexoraLog 'runtime recovery failed' 'Automatic recovery reached its retry limit.' (Get-BackendError)
                $healthFailures = 0
                $recoveryExhausted = $true
            }
        }
        if ($uiProcess.ExitCode -ne 0) {
            throw "The desktop interface closed with exit code $($uiProcess.ExitCode)."
        }
        Write-NexoraLog 'shutdown' 'NEXORA closed normally.'
    } finally {
        Stop-OwnedBackend
        Remove-Item -LiteralPath $tempStdout, $tempStderr -Force -ErrorAction SilentlyContinue
    }
}

try {
    $script:instanceMutex = New-Object Threading.Mutex($false, "Local\NEXORA-Desktop-v030-$buildProfile")
    if (!$script:instanceMutex.WaitOne(0)) {
        Add-Type -AssemblyName PresentationFramework
        [Windows.MessageBox]::Show('NEXORA is already open.', 'NEXORA', 'OK', 'Information') | Out-Null
        exit 0
    }
    if ($RecoveryTest) {
        $script:startupStage = 'recovery window test'
        Show-NexoraRecovery 'Recovery window test.' | Out-Null
        exit 0
    }
    while ($true) {
        try {
            Start-NexoraSession
            break
        } catch {
            $failure = Protect-DiagnosticText $_.Exception.Message
            Write-NexoraLog $script:startupStage 'Startup failed.' (Protect-DiagnosticText ($_ | Out-String))
            if ((Show-NexoraRecovery $failure) -ne 'TryAgain') { break }
        }
    }
} finally {
    if ($null -ne $script:instanceMutex) {
        try { $script:instanceMutex.ReleaseMutex() } catch {}
        $script:instanceMutex.Dispose()
    }
}
