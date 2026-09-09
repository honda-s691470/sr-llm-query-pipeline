param(
    [string]$CodexCommand = "codex",
    [string]$CodexModel = "gpt-5.3-codex",
    [string]$PythonCommand = "python",
    [switch]$AutoRewriteSection00,
    [switch]$NoCodexApiFallback
)

$ErrorActionPreference = "Stop"

function Get-LatestQueryLaws {
    param([string]$DirPath)
    $files = Get-ChildItem -LiteralPath $DirPath -Filter "query_laws_ver*.txt" -File |
        Sort-Object {
            if ($_.BaseName -match 'query_laws_ver(\d+)$') { [int]$Matches[1] } else { 0 }
        } -Descending
    return $files | Select-Object -First 1
}

function Get-QueryVersion {
    param([string]$FileName)
    if ($FileName -match 'query_laws_ver(\d+)\.txt$') {
        return [int]$Matches[1]
    }
    throw "Could not parse query_laws version from: $FileName"
}

function Get-DotEnvValue {
    param([string]$Path, [string]$Name)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
        $parts = $trimmed.Split("=", 2)
        if ($parts[0].Trim() -eq $Name) {
            return $parts[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

function Get-OpenAIApiKey {
    if ($env:OPENAI_API_KEY) { return $env:OPENAI_API_KEY }
    $candidate = Get-DotEnvValue -Path (Join-Path $bundleRoot ".env") -Name "OPENAI_API_KEY"
    if ($candidate) { return $candidate }
    $candidate = Get-DotEnvValue -Path (Join-Path (Split-Path -Parent $bundleRoot) ".env") -Name "OPENAI_API_KEY"
    if ($candidate) { return $candidate }
    return $null
}

function Invoke-OpenAIResponsesFallback {
    param([string]$Prompt, [string]$Model, [string]$LogPath)
    $apiKey = Get-OpenAIApiKey
    if (-not $apiKey) { throw "OPENAI_API_KEY was not found for Codex API fallback." }
    $body = @{
        model = $Model
        input = $Prompt
        max_output_tokens = 8096
    } | ConvertTo-Json -Depth 8
    try {
        $resp = Invoke-RestMethod -Uri "https://api.openai.com/v1/responses" -Method Post -Headers @{
            Authorization = "Bearer $apiKey"
            "Content-Type" = "application/json"
        } -Body $body -TimeoutSec 300
        $texts = @()
        foreach ($item in $resp.output) {
            foreach ($content in $item.content) {
                if ($content.type -eq "output_text" -or $content.type -eq "text") { $texts += $content.text }
            }
        }
        "api_status=200`nmodel=$($resp.model)" | Set-Content -Encoding UTF8 $LogPath
        return ($texts -join "`n")
    } catch {
        "api_error=$($_.Exception.Message)" | Set-Content -Encoding UTF8 $LogPath
        throw
    }
}

$bundleRoot = (Get-Location).Path
$workflowDir = Join-Path $bundleRoot "02_query_laws_refinement"
$dataRoot = Join-Path $bundleRoot "04_data"
$runLogDir = Join-Path $workflowDir "run_logs"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryPath = Join-Path $runLogDir ("workflow_summary_" + $timestamp + ".json")

New-Item -ItemType Directory -Force -Path $runLogDir | Out-Null

& $PythonCommand (Join-Path $workflowDir "analyze_logs_ver2.py")

$latestQueryLaws = Get-LatestQueryLaws -DirPath $workflowDir
if (-not $latestQueryLaws) {
    throw "No query_laws_ver*.txt files found after running analyze_logs_ver2.py"
}

$version = Get-QueryVersion -FileName $latestQueryLaws.Name
$promptTemplate = Get-Content -Raw (Join-Path $workflowDir "test_prompt_with.md")
$queryLawsText = Get-Content -Raw $latestQueryLaws.FullName

$targetDirs = Get-ChildItem -LiteralPath $dataRoot -Directory -Recurse | Where-Object {
    Test-Path (Join-Path $_.FullName "input_config.json")
} | Sort-Object FullName

$results = @()

foreach ($target in $targetDirs) {
    $targetDir = $target.FullName
    $outDir = Join-Path $targetDir ("model_outputs\codex\with_laws_v{0}_training_eval" -f $version)
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null

    $rawOutputPath = Join-Path $outDir "raw_codex_output.txt"
    $normalizedQueryPath = Join-Path $outDir "normalized_query.txt"
    $metricsPath = Join-Path $outDir "last_metrics.json"
    $queryLawsCopyPath = Join-Path $outDir ("query_laws_v{0}.txt" -f $version)
    Copy-Item -LiteralPath $latestQueryLaws.FullName -Destination $queryLawsCopyPath -Force

    $inputConfigText = Get-Content -Raw (Join-Path $targetDir "input_config.json")
    $combinedPrompt = @"
$promptTemplate

----------------------------------------
INPUT CONFIG CONTENT
----------------------------------------
$inputConfigText

----------------------------------------
QUERY LAWS CONTENT
----------------------------------------
$queryLawsText
"@

    $rawOutput = $combinedPrompt | & $CodexCommand exec --skip-git-repo-check -s danger-full-access -C $targetDir -m $CodexModel - 2>&1
    $codexExitCode = $LASTEXITCODE
    if ($codexExitCode -ne 0) {
        if ($NoCodexApiFallback) {
            $rawOutput | Set-Content -Encoding UTF8 $rawOutputPath
            throw "Codex CLI failed for $targetDir (exit $codexExitCode)."
        }
        $fallbackLogPath = Join-Path $outDir "openai_api_fallback.log"
        $rawOutput = Invoke-OpenAIResponsesFallback -Prompt $combinedPrompt -Model $CodexModel -LogPath $fallbackLogPath
    }
    $rawOutput | Set-Content -Encoding UTF8 $rawOutputPath

    $fullQueryLine = ($rawOutput -split "`r?`n" | Where-Object { $_ -match '^FULL_QUERY:\s*' } | Select-Object -Last 1)
    if (-not $fullQueryLine) {
        throw "No FULL_QUERY line found in Codex output for $targetDir"
    }

    $normalizedQuery = ($fullQueryLine -replace '^FULL_QUERY:\s*', '').Trim()
    if (-not $normalizedQuery) {
        throw "Extracted query was empty for $targetDir"
    }

    Set-Content -Encoding UTF8 $normalizedQueryPath $normalizedQuery

    & $PythonCommand (Join-Path $workflowDir "tool_evaluator.py") `
        --input-config (Join-Path $targetDir "input_config.json") `
        --query-path $normalizedQueryPath `
        --metrics-path $metricsPath

    $metricsJson = & $PythonCommand -c "import json, pathlib, sys; p = pathlib.Path(sys.argv[1]); d = json.loads(p.read_text(encoding='utf-8-sig')); print(json.dumps({'recall': d['recall'], 'total_hits': d['total_hits'], 'found_count': d['found_count'], 'total_gold': d['total_gold']}))" $metricsPath
    $metrics = $metricsJson | ConvertFrom-Json
    $result = [ordered]@{
        path = $targetDir.Substring($bundleRoot.Length + 1).Replace('\','/')
        query_laws = $latestQueryLaws.Name
        recall = $metrics.recall
        total_hits = $metrics.total_hits
        found_count = $metrics.found_count
        total_gold = $metrics.total_gold
        outputs_written = (
            (Test-Path $queryLawsCopyPath) -and
            (Test-Path $rawOutputPath) -and
            (Test-Path $normalizedQueryPath) -and
            (Test-Path $metricsPath)
        )
    }
    $results += [pscustomobject]$result
}

$results | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $summaryPath
$results | Format-Table -AutoSize
Write-Host "SUMMARY_PATH=$summaryPath"

$diagnosticsOutput = & $PythonCommand (Join-Path $workflowDir "generate_step3_diagnostics.py") `
    --bundle-root $bundleRoot `
    --summary-path $summaryPath `
    --query-laws-file $latestQueryLaws.FullName

$diagnosticsOutput | ForEach-Object { Write-Host $_ }

if ($AutoRewriteSection00) {
    $summaryStem = [System.IO.Path]::GetFileNameWithoutExtension($summaryPath)
    $summaryStem = $summaryStem -replace '^workflow_summary_', ''
    $diagnosticsPath = Join-Path $runLogDir ("step3_diagnostics_" + $summaryStem + ".json")
    if (-not (Test-Path $diagnosticsPath)) {
        throw "AutoRewriteSection00 was requested but diagnostics file was not found at: $diagnosticsPath"
    }
    $rewriteOutput = & $PythonCommand (Join-Path $workflowDir "auto_rewrite_section00.py") `
        --bundle-root $bundleRoot `
        --workflow-prompt (Join-Path $workflowDir "RUN_WORKFLOW_PROMPT.md") `
        --diagnostics-path $diagnosticsPath `
        --codex-command $CodexCommand `
        --codex-model $CodexModel `
        --python-command $PythonCommand
    $rewriteOutput | ForEach-Object { Write-Host $_ }
}
