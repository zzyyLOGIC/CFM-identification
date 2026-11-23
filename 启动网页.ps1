param(
    [int]$Port = 8796,
    [string]$Python
)
$ErrorActionPreference = 'Stop'
if (-not $Python) {
    $localPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (Test-Path -LiteralPath $localPython -PathType Leaf) {
        $Python = $localPython
    } else {
        $Python = (Get-Command python -CommandType Application -ErrorAction Stop).Source
    }
}
& $Python -B -X utf8 (Join-Path $PSScriptRoot 'serve.py') --port $Port
exit $LASTEXITCODE
