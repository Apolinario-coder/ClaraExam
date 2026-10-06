param([switch]$OneFile)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (!(Test-Path '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar ambiente Python.' }
}
$env:VIRTUAL_ENV = "$PWD\.venv"
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"
if (Test-Path '.tools\rust\bin\cargo.exe') {
    $env:PATH = "$PWD\.tools\rust\bin;$env:PATH"
    $env:RUSTC = "$PWD\.tools\rust\bin\rustc.exe"
    $env:RUSTDOC = "$PWD\.tools\rust\bin\rustdoc.exe"
}
python -m pip install 'maturin>=1.9,<2' 'PySide6>=6.8,<7' 'pyinstaller>=6.16,<7' 'pytest>=8,<10'
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependências.' }
maturin develop --release --locked
if ($LASTEXITCODE -ne 0) { throw 'Falha ao compilar Rust.' }
cargo test --lib --locked
if ($LASTEXITCODE -ne 0) { throw 'Falha nos testes do núcleo Rust.' }
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Falha nos testes.' }
$mode = if ($OneFile) { '--onefile' } else { '--onedir' }
$previousBuildPath = $env:PATH
$pythonBase = python -c 'import sys; print(sys.base_prefix)'
try {
    # Foreign DLLs on PATH (e.g. another program's ICU) must not enter the bundle.
    $env:PATH = "$PWD\.venv\Scripts;$pythonBase;$env:SystemRoot\System32;$env:SystemRoot"
    python -m PyInstaller --noconfirm --clean --windowed $mode --name ClaraExam --paths src --hidden-import clara._core launch.py
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao empacotar o aplicativo.' }
} finally {
    $env:PATH = $previousBuildPath
}
Write-Host 'Build concluído. Consulte a pasta dist.'
