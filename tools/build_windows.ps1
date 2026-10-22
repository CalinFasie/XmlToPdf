$ErrorActionPreference = "Stop"

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
$SpecFile = Join-Path $RepositoryRoot "XmlToPdf.spec"
$DistributionDirectory = Join-Path $RepositoryRoot "dist"
$BuildDirectory = Join-Path $RepositoryRoot "build"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Mediul virtual nu există. Creează .venv și instalează dependențele din .[dev]."
}

& $Python -m PyInstaller --clean --noconfirm `
    --distpath $DistributionDirectory `
    --workpath $BuildDirectory `
    $SpecFile

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$Executable = Join-Path $DistributionDirectory "XmlToPdf.exe"
if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
    throw "Build-ul s-a încheiat fără să producă dist\XmlToPdf.exe."
}

Write-Output "Build reușit: $Executable"
