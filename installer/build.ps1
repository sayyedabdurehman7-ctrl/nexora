param(
    [ValidateSet('developer', 'tester', 'production')]
    [string]$Profile = 'tester',
    [switch]$PortableOnly
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
$flet = Join-Path $root '.venv\Scripts\flet.exe'
$out = Join-Path $PSScriptRoot 'output'
$dist = Join-Path $out 'NEXORA'

if (!(Test-Path $python) -or !(Test-Path $flet)) {
    throw 'The project virtual environment is missing. Run docs\SETUP.md first.'
}
& $python -m pip install pyinstaller --quiet
if (Test-Path $out) { Remove-Item -LiteralPath $out -Recurse -Force }
New-Item -ItemType Directory -Path $dist -Force | Out-Null

Write-Host 'Packaging the NEXORA desktop interface...'
& $flet pack src\nexora\ui\app.py --name NEXORA --product-name NEXORA --product-version 0.3.1 `
    --onedir --distpath (Join-Path $out 'ui') --yes
if ($LASTEXITCODE -ne 0) { throw 'Flet packaging failed.' }

Write-Host 'Packaging the local NEXORA backend...'
& $python -m PyInstaller --clean --noconfirm --onedir --name NexoraBackend `
    --distpath (Join-Path $out 'backend') --paths src `
    --hidden-import nexora.api.conversation_routes --hidden-import nexora.speech_worker --hidden-import win32cred `
    --hidden-import google.genai --collect-submodules faster_whisper --collect-submodules pyttsx3 `
    --collect-data certifi --exclude-module nexora.ui --exclude-module flet `
    --exclude-module flet_desktop src\nexora\api\app.py
if ($LASTEXITCODE -ne 0) { throw 'Backend packaging failed.' }

Copy-Item -Path (Join-Path $out 'ui\NEXORA\*') -Destination $dist -Recurse -Force
$backendDist = Join-Path $dist 'backend'
New-Item -ItemType Directory -Path $backendDist -Force | Out-Null
Copy-Item -Path (Join-Path $out 'backend\NexoraBackend\*') -Destination $backendDist -Recurse -Force
Copy-Item -LiteralPath '.env.example' -Destination (Join-Path $dist '.env.example') -Force
Copy-Item -LiteralPath 'README.md' -Destination (Join-Path $dist 'README.md') -Force
Copy-Item -LiteralPath 'assets' -Destination (Join-Path $dist 'assets') -Recurse -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'launch-installed.ps1') -Destination (Join-Path $dist 'launch-installed.ps1') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'TESTER_INSTRUCTIONS.txt') -Destination $dist -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'CHANGELOG-v0.3.1.txt') -Destination $dist -Force
Set-Content -LiteralPath (Join-Path $dist 'build-profile.txt') -Value $Profile -Encoding ASCII

if (!$PortableOnly) {
    $iscc = Get-Command iscc -ErrorAction SilentlyContinue
    if ($null -eq $iscc) {
        $localIscc = Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'
        if (Test-Path -LiteralPath $localIscc) { $iscc = Get-Item -LiteralPath $localIscc }
    }
    if ($null -eq $iscc) {
        Write-Warning 'Inno Setup compiler (iscc.exe) was not found. Portable files were created; install Inno Setup and rerun with -PortableOnly:$false.'
    } else {
        $isccPath = if ($iscc.Source) { $iscc.Source } else { $iscc.FullName }
        & $isccPath (Join-Path $PSScriptRoot 'NEXORA.iss')
        if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed.' }
    }
}

Write-Host "Portable package: $dist"
