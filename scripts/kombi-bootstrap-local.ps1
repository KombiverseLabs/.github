[CmdletBinding()]
param(
    [string]$WorkspaceRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$Manifest = (Join-Path (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path "local-dev\kombify-gates.json"),
    [string[]]$Repo = @(),
    [switch]$DryRun,
    [switch]$SkipDoctor,
    [switch]$SkipAudit,
    [switch]$SkipInstall,
    [switch]$SkipSetup,
    [string]$ReportPath = (Join-Path (Join-Path (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path "local-dev\reports") ("bootstrap-local-{0}.json" -f (Get-Date -Format "yyyyMMdd-HHmmss")))
)

$ErrorActionPreference = "Stop"
$SharedRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Cli = Join-Path $SharedRoot "scripts\kombi-local-gate.mjs"
$Steps = New-Object System.Collections.Generic.List[object]
$GitHubToken = $env:GITHUB_TOKEN

function Get-GitHubToken {
    if ($script:GitHubToken) {
        return $script:GitHubToken
    }

    $doppler = Get-Command doppler -ErrorAction SilentlyContinue
    if (-not $doppler) {
        return $null
    }

    $token = & doppler secrets get GITHUB_PAT --plain --project kombination --config prd --no-read-env 2>$null
    if ($LASTEXITCODE -eq 0 -and $token) {
        $script:GitHubToken = $token.Trim()
    }

    return $script:GitHubToken
}

function ConvertTo-CommandLine {
    param([string[]]$Command)
    return ($Command | ForEach-Object {
        if ($_ -match "\s") {
            '"' + ($_ -replace '"', '\"') + '"'
        } else {
            $_
        }
    }) -join " "
}

function Normalize-RepoId {
    param([string]$Value)
    return ($Value.ToLowerInvariant() -replace "[^a-z0-9]+", "-").Trim("-")
}

function Add-BlockedStep {
    param(
        [string]$Name,
        [string]$Reason
    )

    $Steps.Add([ordered]@{
        name = $Name
        status = "blocked"
        reason = $Reason
        startedAt = (Get-Date).ToUniversalTime().ToString("o")
        finishedAt = (Get-Date).ToUniversalTime().ToString("o")
    })
    Write-Host "BLOCKED $Name - $Reason"
}

function Invoke-Step {
    param(
        [string]$Name,
        [string[]]$Command,
        [string]$Cwd = $SharedRoot
    )

    $startedAt = (Get-Date).ToUniversalTime().ToString("o")
    if ($DryRun) {
        $step = [ordered]@{
            name = $Name
            status = "dry-run"
            command = $Command
            cwd = $Cwd
            exitCode = 0
            stdout = ""
            stderr = ""
            startedAt = $startedAt
            finishedAt = (Get-Date).ToUniversalTime().ToString("o")
        }
        $Steps.Add($step)
        Write-Host ("DRY {0} (cwd={1})" -f (ConvertTo-CommandLine $Command), $Cwd)
        return $step
    }

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $Command[0]
    for ($index = 1; $index -lt $Command.Count; $index++) {
        [void]$psi.ArgumentList.Add($Command[$index])
    }
    $psi.WorkingDirectory = $Cwd
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.Environment["CI"] = "true"
    $psi.Environment["MISE_YES"] = "1"
    $githubToken = Get-GitHubToken
    if ($githubToken) {
        $psi.Environment["GITHUB_TOKEN"] = $githubToken
    }

    $process = [System.Diagnostics.Process]::Start($psi)
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    $step = [ordered]@{
        name = $Name
        status = if ($process.ExitCode -eq 0) { "ok" } else { "failed" }
        command = $Command
        cwd = $Cwd
        exitCode = $process.ExitCode
        stdout = $stdout
        stderr = $stderr
        startedAt = $startedAt
        finishedAt = (Get-Date).ToUniversalTime().ToString("o")
    }
    $Steps.Add($step)
    Write-Host ("{0} {1}" -f $step.status.ToUpperInvariant(), $Name)
    return $step
}

function Write-Report {
    $resolvedReport = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ReportPath)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $resolvedReport) | Out-Null
    $report = [ordered]@{
        schema = "kombify-local-bootstrap-report"
        generatedAt = (Get-Date).ToUniversalTime().ToString("o")
        workspaceRoot = $WorkspaceRoot
        manifest = $Manifest
        dryRun = [bool]$DryRun
        repoFilter = @($Repo)
        steps = @($Steps.ToArray())
    }
    $report | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $resolvedReport -Encoding UTF8
    Write-Host "Report: $resolvedReport"
}

$manifestPayload = Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
$repoFilter = @($Repo | ForEach-Object { $_ -split "," } | Where-Object { $_ } | ForEach-Object { Normalize-RepoId $_ })
$repos = @($manifestPayload.repos)
if ($repoFilter.Count -gt 0) {
    $repos = @($repos | Where-Object {
        $candidateIds = @($_.id, $_.name, $_.path) | ForEach-Object { Normalize-RepoId $_ }
        Compare-Object -ReferenceObject $repoFilter -DifferenceObject $candidateIds -IncludeEqual -ExcludeDifferent | Select-Object -First 1
    })
}

$miseFound = $true
if (-not $SkipDoctor) {
    $doctor = Invoke-Step -Name "doctor" -Command @("node", $Cli, "doctor", "--json") -Cwd $SharedRoot
    if (-not $DryRun -and $doctor.stdout) {
        try {
            $doctorPayload = $doctor.stdout | ConvertFrom-Json
            $miseTool = @($doctorPayload.tools | Where-Object { $_.name -eq "mise" }) | Select-Object -First 1
            $miseFound = [bool]$miseTool.found
        } catch {
            $miseFound = $false
        }
    }
}

if (-not $SkipAudit) {
    Invoke-Step -Name "audit" -Command @("node", $Cli, "audit", "--workspace-root", $WorkspaceRoot, "--manifest", $Manifest, "--json") -Cwd $SharedRoot | Out-Null
}

if (-not $DryRun -and -not $miseFound) {
    Add-BlockedStep -Name "mise repo preparation" -Reason "mise is not available on PATH. Install mise, restart the shell, then rerun this bootstrap."
    Write-Report
    exit 1
}

foreach ($repoEntry in $repos) {
    $repoPath = Join-Path $WorkspaceRoot $repoEntry.path
    if (-not (Test-Path -LiteralPath $repoPath)) {
        Add-BlockedStep -Name ("prepare {0}" -f $repoEntry.id) -Reason "Repository path does not exist: $repoPath"
        continue
    }

    Invoke-Step -Name ("trust {0}" -f $repoEntry.id) -Command @("mise", "trust") -Cwd $repoPath | Out-Null
    if (-not $SkipInstall) {
        Invoke-Step -Name ("install tools {0}" -f $repoEntry.id) -Command @("mise", "install") -Cwd $repoPath | Out-Null
    }
    if (-not $SkipSetup) {
        Invoke-Step -Name ("setup {0}" -f $repoEntry.id) -Command @("mise", "run", "setup") -Cwd $repoPath | Out-Null
    }
}

Write-Report

$failed = @($Steps | Where-Object { $_.status -in @("failed", "blocked") })
if ($failed.Count -gt 0) {
    exit 1
}
