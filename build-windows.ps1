$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$buildId = Get-Date -Format "yyyyMMdd-HHmmss"
$workPath = Join-Path $root "build-release-$buildId"
$distPath = Join-Path $root "dist-release-$buildId"

# Each run uses timestamped output paths so we never overwrite an open or protected bundle.
# Remove the artifacts from the most recent prior run to keep disk usage bounded.
$previousIds = Get-ChildItem -LiteralPath $root -Directory |
    ForEach-Object {
        if ($_.Name -match '^(?:dist|build)-release-(\d{8}-\d{6})$') { $Matches[1] }
    } |
    Sort-Object -Descending -Unique
$previousId = $previousIds | Select-Object -First 1
if ($previousId) {
    $rootPrefix = [System.IO.Path]::GetFullPath($root).TrimEnd('\') + '\'
    foreach ($oldPath in @(
        (Join-Path $root "dist-release-$previousId"),
        (Join-Path $root "build-release-$previousId")
    )) {
        if (Test-Path -LiteralPath $oldPath -PathType Container) {
            $resolvedPath = [System.IO.Path]::GetFullPath($oldPath)
            if (-not $resolvedPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Refusing to clean a build directory outside the project root: $resolvedPath"
            }
            Write-Host "Removing previous build artifacts: $resolvedPath"
            try {
                Remove-Item -LiteralPath $resolvedPath -Recurse -Force
            }
            catch {
                throw "Could not remove '$resolvedPath'. Close Practicum if it is running, then retry. $($_.Exception.Message)"
            }
        }
    }
}

$venv = Join-Path $root ".venv-build"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
    $existingPython = Join-Path $root ".venv\Scripts\python.exe"
    if (Test-Path $existingPython) {
        $venv = Join-Path $root ".venv"
        $python = $existingPython
    }
    else {
        python -m venv $venv
    }
}

if (-not (Test-Path $python)) {
    throw "Could not create the build environment. Install Python 3.12 or newer."
}

& $python (Join-Path $root "tools\create_app_icon.py")
if ($LASTEXITCODE -ne 0) {
    throw "Could not generate the Practicum Windows icon."
}

& $python -c "import PyInstaller, PySide6, uvicorn, fastapi"
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install -e $root -e (Join-Path $root "desktop") "pyinstaller>=6.10,<7.0"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install the app and packaging dependencies."
    }
}

Push-Location $root
try {
    & $python -m PyInstaller --noconfirm --windowed `
        --name Practicum `
        --icon (Join-Path $root "assets\practicum.ico") `
        --add-data "$(Join-Path $root 'assets\practicum.ico');assets" `
        --workpath $workPath `
        --distpath $distPath `
        --paths (Join-Path $root "src") `
        --paths (Join-Path $root "desktop\src") `
        --hidden-import practicum.main `
        --hidden-import uvicorn.logging `
        --collect-all PySide6.QtWebEngineCore `
        --collect-all PySide6.QtWebEngineWidgets `
        (Join-Path $root "desktop\src\practicum_desktop\main.py")
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

$appDistPath = Join-Path $distPath "Practicum"
Write-Host "Built executable: $(Join-Path $appDistPath 'Practicum.exe')"

$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    $knownPaths = @(
        "${env:LOCALAPPDATA}\Programs\Inno Setup 7\ISCC.exe",
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 7\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
    )
    $compilerPath = $knownPaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
else {
    $compilerPath = $iscc.Source
}

if ($compilerPath) {
    $installerArgs = @(
        "/DRepoDir=$root",
        "/DDistDir=$appDistPath",
        "/DOutputDir=$distPath",
        (Join-Path $root "installer\practicum.iss")
    )
    & $compilerPath @installerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed with exit code $LASTEXITCODE."
    }
    Write-Host "Built installer: $(Join-Path $distPath 'Practicum-Setup-0.1.0.exe')"
}
else {
    Write-Warning "Inno Setup is not installed. The portable app is built; install Inno Setup 6, then run build-windows.ps1 again to create Practicum-Setup-0.1.0.exe."
}
