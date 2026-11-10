# Rebuild every output from the PDFs in data/raw (named insurer_PERIOD.pdf, e.g. malath_2025Q2.pdf, walaa_2025FY.pdf).
# Run from the project root with the virtual environment active:   .\run_all.ps1
# Scanned statement pages are read by OCR the first time (about a minute per page); results are cached in data/interim/ocr.
$ErrorActionPreference = "Stop"
$py = "python"; $u = "-X", "utf8"

function Step($label, [scriptblock]$cmd) {
    Write-Host "==> $label" -ForegroundColor Cyan
    & $cmd
    if ($LASTEXITCODE -ne 0) { throw "step failed: $label" }
}

$filings = Get-ChildItem data\raw -Filter "*.pdf" | Where-Object { $_.Name -match '_20\d\d(Q\d|FY)\.pdf$' } |
           Sort-Object Name | ForEach-Object { $_.FullName }
if ($filings.Count -eq 0) { throw "no filings named insurer_PERIOD.pdf found in data\raw" }
Write-Host "$($filings.Count) filings" -ForegroundColor Cyan

Step "consolidated income statements"   { & $py @u -m src.income_statement @filings --out data/clean/statements_long.csv }
Step "Milliman exhibit tables"          { & $py @u -m src.milliman data/raw/6_4_26_KSA-Industry-update-2025.pdf --out data/clean/milliman_long.csv }
Step "whole-company panel"              { & $py @u -m src.clean }
Step "segment notes (medical / total)"  { & $py @u -m src.segments }
Step "segment panel + derived Q4"       { & $py @u -m src.panel }
Step "Milliman cross-check"             { & $py @u -m src.crosscheck }
Step "DuckDB database and SQL views"    { & $py @u -m src.build_db }
Step "analysis tables"                  { & $py @u -m src.analysis }
Step "figures"                          { & $py @u -m src.figures }
Step "Power BI export"                  { & $py @u -m src.export_powerbi }
Step "ratio definitions"                { & $py @u -m src.definitions }
Step "10% audit sample"                 { & $py @u -m src.audit }
Step "tests"                            { & $py @u -m pytest -q tests }
Write-Host "done" -ForegroundColor Green
