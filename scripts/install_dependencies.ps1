<#
.SYNOPSIS
    Installiere alle Laufzeitvoraussetzungen für MultiScreenKiosk auf Windows-Systemen.

.DESCRIPTION
    Dieses Skript richtet eine komplette Laufzeitumgebung ein, damit MultiScreenKiosk
    entweder als gepackte EXE oder aus dem Quellcode gestartet werden kann. Es führt die
    folgenden Schritte aus:
      1. Stellt sicher, dass das Skript mit administrativen Rechten ausgeführt wird.
      2. Installiert (oder aktualisiert) die Microsoft Visual C++ 2015-2022 Redistributable.
      3. Installiert optional eine aktuelle Python-Laufzeit (Standard 3.11.x), falls Python
         noch nicht vorhanden ist.
      4. Installiert alle Python-Abhängigkeiten aus requirements.txt innerhalb des Repositories.

    Hinweis: Für den produktiven Einsatz empfehlen wir, das Skript per Rechtsklick
    "Mit PowerShell ausführen" in einer erhöhten PowerShell-Konsole zu starten.
#>

[CmdletBinding()]
param(
    [switch]$SkipPython,
    [string]$PythonVersion = '3.11.8'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Administrator {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Dieses Skript muss mit administrativen Rechten ausgeführt werden.'
    }
}

function Invoke-DownloadFile {
    param(
        [Parameter(Mandatory)] [string]$Uri,
        [Parameter(Mandatory)] [string]$Destination
    )

    Write-Host "Lade $Uri herunter ..."
    Invoke-WebRequest -Uri $Uri -OutFile $Destination -UseBasicParsing
}

function Invoke-ExternalProcess {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$Description = $FilePath
    )

    Write-Host "Starte $Description ..."
    $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "$Description wurde mit Exit-Code $($process.ExitCode) beendet."
    }
}

function Test-VisualCppRuntimeInstalled {
    $vcKeyPaths = @(
        'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
        'HKLM:\SOFTWARE\Wow6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64'
    )

    foreach ($keyPath in $vcKeyPaths) {
        if (Test-Path $keyPath) {
            $props = Get-ItemProperty -Path $keyPath -ErrorAction SilentlyContinue
            if ($null -ne $props -and $props.Installed -eq 1) {
                return $true
            }
        }
    }

    return $false
}

function Install-VisualCppRuntime {
    if (Test-VisualCppRuntimeInstalled) {
        Write-Host 'Visual C++ 2015-2022 Redistributable ist bereits installiert.'
        return
    }

    $vcUrl = 'https://aka.ms/vs/17/release/vc_redist.x64.exe'
    $tempPath = Join-Path $env:TEMP 'vc_redist.x64.exe'

    Invoke-DownloadFile -Uri $vcUrl -Destination $tempPath
    try {
        Invoke-ExternalProcess -FilePath $tempPath -ArgumentList @('/quiet', '/norestart') -Description 'Visual C++ Redistributable'
    }
    finally {
        Remove-Item -Path $tempPath -ErrorAction SilentlyContinue
    }
}

function Get-PythonCommand {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        return $py.Source
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    return $null
}

function Install-Python {
    param(
        [Parameter(Mandatory)] [string]$Version
    )

    $installerName = "python-$Version-amd64.exe"
    $downloadUrl = "https://www.python.org/ftp/python/$Version/$installerName"
    $tempPath = Join-Path $env:TEMP $installerName

    Invoke-DownloadFile -Uri $downloadUrl -Destination $tempPath
    try {
        Invoke-ExternalProcess -FilePath $tempPath -ArgumentList @('/quiet', 'InstallAllUsers=1', 'PrependPath=1', 'Include_test=0') -Description "Python $Version Installer"
    }
    finally {
        Remove-Item -Path $tempPath -ErrorAction SilentlyContinue
    }

    $pythonCmd = Get-PythonCommand
    if (-not $pythonCmd) {
        throw 'Python-Installation fehlgeschlagen. Der Python-Launcher konnte nicht gefunden werden.'
    }

    return $pythonCmd
}

function Get-PythonVersion {
    param(
        [Parameter(Mandatory)] [string]$PythonCommand
    )

    $version = & $PythonCommand - <<<'PY'
import sys
print("{}.{}.{}".format(*sys.version_info[:3]))
PY

    if ($LASTEXITCODE -ne 0) {
        throw 'Python-Version konnte nicht ermittelt werden.'
    }

    return $version.Trim()
}

function Invoke-PythonCommand {
    param(
        [Parameter(Mandatory)] [string]$PythonCommand,
        [Parameter(Mandatory)] [string[]]$Arguments,
        [string]$Description = 'Python'
    )

    Write-Host "Ausführen: $Description"
    & $PythonCommand @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Description schlug fehl (Exit-Code $LASTEXITCODE)."
    }
}

function Install-PythonRequirements {
    param(
        [Parameter(Mandatory)] [string]$PythonCommand,
        [Parameter(Mandatory)] [string]$RequirementsFile
    )

    if (-not (Test-Path $RequirementsFile)) {
        throw "Requirements-Datei nicht gefunden: $RequirementsFile"
    }

    Invoke-PythonCommand -PythonCommand $PythonCommand -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip') -Description 'pip aktualisieren'
    Invoke-PythonCommand -PythonCommand $PythonCommand -Arguments @('-m', 'pip', 'install', '--upgrade', '-r', $RequirementsFile) -Description 'Python-Abhängigkeiten installieren'
}

try {
    Assert-Administrator

    Write-Host '### Installationsroutine MultiScreenKiosk ###'
    Install-VisualCppRuntime

    $pythonCommand = Get-PythonCommand
    $pythonFound = $null -ne $pythonCommand

    if (-not $pythonFound -and -not $SkipPython) {
        Write-Host 'Python wurde nicht gefunden. Installation wird gestartet ...'
        $pythonCommand = Install-Python -Version $PythonVersion
    }

    if (-not $pythonCommand) {
        Write-Warning 'Python wurde nicht gefunden oder bewusst ausgelassen. Überspringe Installation der Python-Abhängigkeiten.'
    }
    else {
        $detectedVersion = Get-PythonVersion -PythonCommand $pythonCommand
        Write-Host "Python-Version: $detectedVersion"

        $requirementsPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'kiosk_app\modules\requirements.txt'
        Install-PythonRequirements -PythonCommand $pythonCommand -RequirementsFile $requirementsPath
    }

    Write-Host 'Alle Schritte erfolgreich abgeschlossen.'
}
catch {
    Write-Error $_
    throw
}
