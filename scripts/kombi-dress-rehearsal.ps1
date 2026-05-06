[CmdletBinding()]
param(
    [string]$WorkspaceRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$Manifest = (Join-Path (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path "local-dev\kombify-gates.json"),
    [switch]$DryRun,
    [switch]$SkipDoctor,
    [switch]$SkipAudit,
    [switch]$SkipLive,
    [switch]$Keep,
    [switch]$StartAspire,
    [string[]]$LiveAspireModes = @("local"),
    [string]$ReportPath = (Join-Path (Join-Path (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path "local-dev\reports") ("dress-rehearsal-{0}.json" -f (Get-Date -Format "yyyyMMdd-HHmmss")))
)

$ErrorActionPreference = "Stop"
$SharedRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Cli = Join-Path $SharedRoot "scripts\kombi-local-gate.mjs"
$Steps = New-Object System.Collections.Generic.List[object]
$ToolStatus = @{
    docker = $false
    mise = $false
    dotnet = $false
    aspire = $false
}
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

function Normalize-List {
    param([string[]]$Values)

    return @($Values | ForEach-Object { $_ -split "," } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
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
        [string]$Cwd = $SharedRoot,
        [switch]$ForceDryRun
    )

    $startedAt = (Get-Date).ToUniversalTime().ToString("o")
    if ($DryRun -or $ForceDryRun) {
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

function Invoke-GateStep {
    param(
        [string]$Name,
        [string[]]$CliArgs,
        [switch]$ForceDryRun
    )

    $command = @("node", $Cli) + $CliArgs
    Invoke-Step -Name $Name -Command $command -Cwd $SharedRoot -ForceDryRun:$ForceDryRun | Out-Null
}

function Test-RepoKnown {
    param(
        [object]$ManifestPayload,
        [string]$RepoId
    )
    return [bool](@($ManifestPayload.repos | Where-Object { $_.id -eq $RepoId }) | Select-Object -First 1)
}

function Write-Report {
    $resolvedReport = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ReportPath)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $resolvedReport) | Out-Null
    $report = [ordered]@{
        schema = "kombify-local-dress-rehearsal-report"
        generatedAt = (Get-Date).ToUniversalTime().ToString("o")
        workspaceRoot = $WorkspaceRoot
        manifest = $Manifest
        dryRun = [bool]$DryRun
        skipLive = [bool]$SkipLive
        keep = [bool]$Keep
        startAspire = [bool]$StartAspire
        liveAspireModes = @($script:ResolvedLiveAspireModes)
        tools = $ToolStatus
        steps = @($Steps.ToArray())
    }
    $report | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $resolvedReport -Encoding UTF8
    Write-Host "Report: $resolvedReport"
}

$manifestPayload = Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
$baseCliArgs = @("--workspace-root", $WorkspaceRoot, "--manifest", $Manifest)
$ResolvedLiveAspireModes = Normalize-List $LiveAspireModes
if ($ResolvedLiveAspireModes.Count -eq 0) {
    $ResolvedLiveAspireModes = @("local")
}
if ($StartAspire -and -not ($ResolvedLiveAspireModes -contains "saas")) {
    $ResolvedLiveAspireModes += "saas"
}

if (-not $SkipDoctor) {
    $doctor = Invoke-Step -Name "doctor" -Command @("node", $Cli, "doctor", "--json") -Cwd $SharedRoot
    if (-not $DryRun -and $doctor.stdout) {
        try {
            $doctorPayload = $doctor.stdout | ConvertFrom-Json
            foreach ($tool in $doctorPayload.tools) {
                if ($tool.name -eq "Docker Desktop") {
                    $ToolStatus.docker = [bool]$tool.found
                }
                if ($tool.name -eq "mise") {
                    $ToolStatus.mise = [bool]$tool.found
                }
                if ($tool.name -eq ".NET SDK") {
                    $ToolStatus.dotnet = [bool]$tool.found
                }
                if ($tool.name -eq "aspire") {
                    $ToolStatus.aspire = [bool]$tool.found
                }
            }
        } catch {
            Add-BlockedStep -Name "tool status parse" -Reason "Could not parse doctor JSON output."
        }
    }
}

if ($DryRun -or $SkipDoctor) {
    $ToolStatus.docker = $true
    $ToolStatus.mise = $true
    $ToolStatus.dotnet = $true
    $ToolStatus.aspire = $true
}

if (-not $SkipAudit) {
    $auditCommand = @("node", $Cli, "audit", "--json") + $baseCliArgs
    Invoke-Step -Name "audit" -Command $auditCommand -Cwd $SharedRoot | Out-Null
}

if (Test-RepoKnown -ManifestPayload $manifestPayload -RepoId "kombify-blog") {
    Invoke-GateStep -Name "quick gate kombify-blog" -CliArgs @("run", "kombify-blog", "--gate", "quick", "--dry-run") + $baseCliArgs
    Invoke-GateStep -Name "local up kombify-blog" -CliArgs @("up", "kombify-blog", "--mode", "local", "--dry-run") + $baseCliArgs
    Invoke-GateStep -Name "local smoke kombify-blog" -CliArgs @("smoke", "kombify-blog", "--dry-run") + $baseCliArgs
    Invoke-GateStep -Name "local down kombify-blog" -CliArgs @("down", "kombify-blog", "--dry-run") + $baseCliArgs
}

if (Test-RepoKnown -ManifestPayload $manifestPayload -RepoId "kombify-techstack") {
    Invoke-GateStep -Name "standard gate kombify-techstack" -CliArgs @("run", "kombify-techstack", "--gate", "standard", "--dry-run") + $baseCliArgs
    Invoke-GateStep -Name "hybrid up kombify-techstack" -CliArgs @("up", "kombify-techstack", "--mode", "hybrid", "--dry-run") + $baseCliArgs
}

if (Test-RepoKnown -ManifestPayload $manifestPayload -RepoId "kombify-db") {
    Invoke-GateStep -Name "full gate kombify-db" -CliArgs @("run", "kombify-db", "--gate", "full", "--dry-run") + $baseCliArgs
}

if (Test-RepoKnown -ManifestPayload $manifestPayload -RepoId "kombify-cloud") {
    Invoke-GateStep -Name "saas up kombify-cloud" -CliArgs @("up", "kombify-cloud", "--mode", "saas", "--dry-run") + $baseCliArgs
}

if ($DryRun -or $SkipLive) {
    Write-Report
    exit 0
}

if (-not $ToolStatus.mise) {
    Add-BlockedStep -Name "live mise gates" -Reason "mise is not available on PATH."
} else {
    if (Test-RepoKnown -ManifestPayload $manifestPayload -RepoId "kombify-blog") {
        Invoke-GateStep -Name "live quick gate kombify-blog" -CliArgs @("run", "kombify-blog", "--gate", "quick") + $baseCliArgs
        Invoke-GateStep -Name "live standard gate kombify-blog" -CliArgs @("run", "kombify-blog", "--gate", "standard") + $baseCliArgs
    }
}

if (-not $ToolStatus.docker) {
    Add-BlockedStep -Name "live docker preview kombify-blog" -Reason "Docker Desktop is not available."
} elseif (Test-RepoKnown -ManifestPayload $manifestPayload -RepoId "kombify-blog") {
    Invoke-GateStep -Name "live local up kombify-blog" -CliArgs @("up", "kombify-blog", "--mode", "local") + $baseCliArgs
    Invoke-GateStep -Name "live local smoke kombify-blog" -CliArgs @("smoke", "kombify-blog", "--retries", "10", "--timeout-ms", "5000") + $baseCliArgs
    if (-not $Keep) {
        Invoke-GateStep -Name "live local down kombify-blog" -CliArgs @("down", "kombify-blog") + $baseCliArgs
    }
}

if (-not $ToolStatus.aspire) {
    Add-BlockedStep -Name "live Aspire topology" -Reason "Aspire CLI is not available on PATH."
} elseif (-not $ToolStatus.dotnet) {
    Add-BlockedStep -Name "live Aspire topology" -Reason ".NET SDK is not available on PATH."
} elseif (Test-RepoKnown -ManifestPayload $manifestPayload -RepoId "kombify-cloud") {
    foreach ($aspireMode in $ResolvedLiveAspireModes) {
        Invoke-GateStep -Name ("live Aspire {0} up kombify-cloud" -f $aspireMode) -CliArgs @("up", "kombify-cloud", "--mode", $aspireMode, "--start-timeout-ms", "300000") + $baseCliArgs
        Invoke-GateStep -Name ("live Aspire {0} smoke kombify-cloud" -f $aspireMode) -CliArgs @("smoke", "kombify-cloud", "--mode", $aspireMode, "--retries", "10", "--timeout-ms", "5000") + $baseCliArgs
        if (-not $Keep) {
            Invoke-GateStep -Name ("live Aspire {0} down kombify-cloud" -f $aspireMode) -CliArgs @("down", "kombify-cloud") + $baseCliArgs
        }
    }
}

Write-Report

$failed = @($Steps | Where-Object { $_.status -in @("failed", "blocked") })
if ($failed.Count -gt 0) {
    exit 1
}
