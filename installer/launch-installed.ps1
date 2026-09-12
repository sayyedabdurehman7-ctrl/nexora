param([switch]$RecoveryTest)

$ErrorActionPreference = 'Stop'
$appVersion = '0.2.0'
$appDir = $PSScriptRoot
$dataRoot = Join-Path $env:LOCALAPPDATA 'NEXORA'
$logFolder = Join-Path $dataRoot 'logs'
$logFile = Join-Path $logFolder 'nexora.log'
$tempStdout = Join-Path $logFolder 'backend-output.tmp'
$tempStderr = Join-Path $logFolder 'backend-error.tmp'
$backend = Join-Path $appDir 'backend\NexoraBackend.exe'
$ui = Join-Path $appDir 'NEXORA.exe'
$script:startupStage = 'launcher initialization'
$script:ownedBackend = $null
$script:instanceMutex = $null

New-Item -ItemType Directory -Force -Path $logFolder, (Join-Path $dataRoot 'data'), `
    (Join-Path $dataRoot 'data\user_files'), (Join-Path $dataRoot 'feedback') | Out-Null

function Protect-DiagnosticText([string]$Text) {
    if (!$Text) { return '' }
    $safe = $Text -replace '(?i)(GEMINI_API_KEY|api[_ -]?key|authorization|token|password)\s*[:=]\s*\S+', '$1=[redacted]'
    return $safe -replace '\b(?:sk|AIza)[A-Za-z0-9_-]{12,}\b', '[redacted]'
}

function Write-NexoraLog([string]$Stage, [string]$Message, [string]$Details = '') {
    $timestamp = [DateTime]::UtcNow.ToString('o')
    $windows = [Environment]::OSVersion.VersionString
    $safeMessage = Protect-DiagnosticText $Message
    $safeDetails = Protect-DiagnosticText $Details
    $entry = "[$timestamp] version=$appVersion windows=`"$windows`" stage=`"$Stage`" message=`"$safeMessage`""
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
        return $health.status -eq 'ok' -and $health.version -eq $appVersion -and $health.safe_mode
    } catch { return $false }
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
    $databasePath = (Join-Path $dataRoot 'data\nexora.db').Replace('\', '/')
    $env:DATABASE_URL = "sqlite:///$databasePath"
    $env:NEXORA_WORKSPACE_DIR = Join-Path $dataRoot 'data\user_files'
    $port = Get-FreeLoopbackPort
    $env:PORT = [string]$port
    $env:NEXORA_API_URL = "http://127.0.0.1:$port"
    Remove-Item -LiteralPath $tempStdout, $tempStderr -Force -ErrorAction SilentlyContinue

    try {
        $script:startupStage = 'starting local service'
        Write-NexoraLog $script:startupStage "Starting on loopback port $port."
        $script:ownedBackend = Start-Process -FilePath $backend -WorkingDirectory $appDir -WindowStyle Hidden `
            -RedirectStandardOutput $tempStdout -RedirectStandardError $tempStderr -PassThru
        $ready = $false
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            if ($script:ownedBackend.HasExited) {
                throw "The local service stopped during startup.`r`n$(Get-BackendError)"
            }
            if (Test-NexoraHealth $port) { $ready = $true; break }
            Start-Sleep -Milliseconds 250
        }
        if (!$ready) { throw "The local service did not become ready in time.`r`n$(Get-BackendError)" }

        $script:startupStage = 'opening desktop interface'
        Write-NexoraLog $script:startupStage 'Local service health check passed.'
        & $ui
        if ($LASTEXITCODE -is [int] -and $LASTEXITCODE -ne 0) {
            throw 'The desktop interface closed with an error.'
        }
        Write-NexoraLog 'shutdown' 'NEXORA closed normally.'
    } finally {
        if ($null -ne $script:ownedBackend -and !$script:ownedBackend.HasExited) {
            Stop-Process -Id $script:ownedBackend.Id -ErrorAction SilentlyContinue
            $script:ownedBackend.WaitForExit(3000) | Out-Null
        }
        $script:ownedBackend = $null
        Remove-Item -LiteralPath $tempStdout, $tempStderr -Force -ErrorAction SilentlyContinue
    }
}

try {
    $script:instanceMutex = New-Object Threading.Mutex($false, 'Local\NEXORA-Desktop-v020')
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
