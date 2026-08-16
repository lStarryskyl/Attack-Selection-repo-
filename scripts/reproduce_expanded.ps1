param(
    [string]$Python = "python",
    [string]$OutputDir = "work/reproduced_expanded"
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:PYTHONPATH = Join-Path $RepositoryRoot "src"
$ResolvedOutputDir = if ([System.IO.Path]::IsPathRooted($OutputDir)) { $OutputDir } else { Join-Path $RepositoryRoot $OutputDir }

& $Python -m oracle_gap.cli validate `
    --input (Join-Path $RepositoryRoot "work/paper_full/records.jsonl") `
    --output (Join-Path $ResolvedOutputDir "data_quality.json")
if ($LASTEXITCODE -ne 0) { throw "Input validation failed." }

& $Python -m oracle_gap.cli reproduce-ranking `
    --records (Join-Path $RepositoryRoot "work/paper_full/records.jsonl") `
    --games (Join-Path $RepositoryRoot "work/paper_full/games.json") `
    --scores (Join-Path $RepositoryRoot "work/nvidia_replication/scores.jsonl") `
    --output-dir $ResolvedOutputDir `
    --expected-model "nvidia/nemotron-3-nano-30b-a3b" `
    --bootstraps 1000 `
    --seed 20260809
if ($LASTEXITCODE -ne 0) { throw "Ranking reproduction failed." }

& $Python -m unittest discover -s (Join-Path $RepositoryRoot "tests") -v
if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
