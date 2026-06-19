<#
.SYNOPSIS
  Orchestrate the Stage A' self-refinement loop.

.DESCRIPTION
  For each iteration:
    1. run_pipeline_prime_A_B_C.py --mode training  (writes logs + results CSV)
    2. analyze_aprime_logs.py                        (compute aprime_laws_verN.json)
    3. analyze_aprime_results.py                     (check convergence stop condition)
    4. auto_rewrite_aprime.py --skip-analyze         (LLM rewrite; laws already computed)
  Repeats until stop condition or MaxIterations reached.

  The loop always uses with_laws_test_eval as the query source.
  Phase 5 rewritten queries (with_laws_stageA_prime) are NOT used as loop input.
  Phase 5 papers are recorded in diagnostics for reference only.

.PARAMETER Model
  Rewrite model ID for the Codex step (default: gpt-5.3-codex)

.PARAMETER MaxIterations
  Maximum number of refinement iterations (default: 5)

.PARAMETER PipelineProvider
  Provider for run_pipeline_prime_A_B_C.py --provider (default: codex)

.PARAMETER DryRun
  Prepare prompts but do not call the LLM or modify files

.EXAMPLE
  .\run_exclusion_refinement.ps1
  .\run_exclusion_refinement.ps1 -Model gpt-5.3-codex
  .\run_exclusion_refinement.ps1 -DryRun -MaxIterations 1
#>
param(
    [string]$Model = "gpt-5.3-codex",
    [int]$MaxIterations = 5,
    [string]$PipelineProvider = "codex",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "python"

function Invoke-Step {
    param([string]$Label, [string[]]$Cmd)
    Write-Host "`n=== $Label ===" -ForegroundColor Cyan
    Write-Host "  $ $($Cmd -join ' ')"
    & $Cmd[0] $Cmd[1..($Cmd.Length-1)]
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: step '$Label' failed (exit $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

for ($iter = 1; $iter -le $MaxIterations; $iter++) {
    Write-Host "`n==============================" -ForegroundColor Yellow
    Write-Host " Iteration $iter / $MaxIterations" -ForegroundColor Yellow
    Write-Host "==============================" -ForegroundColor Yellow

    # Step 1: Run pipeline (always with_laws_test_eval — no --query-condition override)
    Invoke-Step "Pipeline (training)" @(
        $Python,
        "$ScriptDir\run_pipeline_prime_A_B_C.py",
        "--mode", "training",
        "--provider", $PipelineProvider
    )

    # Step 2: Compute laws file from this iteration's logs (non-fatal: writes empty file if no A' logs)
    Write-Host "`n=== analyze_aprime_logs (iteration $iter) ===" -ForegroundColor Cyan
    Write-Host "  $ $Python $ScriptDir\analyze_aprime_logs.py"
    & $Python "$ScriptDir\analyze_aprime_logs.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  WARNING: analyze_aprime_logs exited non-zero — continuing to stop check" -ForegroundColor Yellow
    }

    # Step 3: Check convergence stop condition
    Write-Host "`n=== analyze_aprime_results (iteration $iter) ===" -ForegroundColor Cyan
    $analyzeArgs = @(
        "$ScriptDir\analyze_aprime_results.py",
        "--iteration", "$iter",
        "--max-iterations", "$MaxIterations"
    )
    Write-Host "  $ $Python $($analyzeArgs -join ' ')"
    $analyzeOut = & $Python @analyzeArgs
    Write-Host $analyzeOut
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: analyze_aprime_results failed" -ForegroundColor Red
        exit $LASTEXITCODE
    }

    # Parse STOP flag from stdout
    $stopMatch = [regex]::Match($analyzeOut, "STOP=(true|false)")
    $shouldStop = $stopMatch.Success -and $stopMatch.Groups[1].Value -eq "true"

    if ($shouldStop) {
        Write-Host "`nStop condition reached after iteration $iter." -ForegroundColor Green
        break
    }

    if ($iter -eq $MaxIterations) {
        Write-Host "`nMax iterations ($MaxIterations) reached." -ForegroundColor Yellow
        break
    }

    # Step 4: Rewrite (laws already computed in Step 2 -- skip re-running analyze_aprime_logs)
    $rewriteArgs = @(
        "$ScriptDir\auto_rewrite_aprime.py",
        "--iteration", "$iter",
        "--model", $Model,
        "--skip-analyze"
    )
    if ($DryRun) { $rewriteArgs += "--dry-run" }
    Invoke-Step "auto_rewrite_aprime (iteration $iter)" (@($Python) + $rewriteArgs)

    if ($DryRun) {
        Write-Host "`nDRY RUN: stopping after first iteration." -ForegroundColor Yellow
        break
    }
}

Write-Host "`n[run_exclusion_refinement] Done." -ForegroundColor Green
