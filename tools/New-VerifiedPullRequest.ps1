[CmdletBinding()]
param(
    [switch]$Publish,
    [string]$PlanDigest = '',
    [string]$Confirmation = '',
    [string]$Title = 'Improve the factual space simulator'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ExpectedConfirmation = 'PUSH VERIFIED FACTUAL SPACE PR'
$Root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $Root

function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    $output = & $Command @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "$Command $($Arguments -join ' ') failed:`n$($output -join "`n")"
    }
    return ($output -join "`n").Trim()
}

function Get-RelativeChanges {
    $rows = @(& git status --porcelain=v1 --untracked-files=all)
    if ($LASTEXITCODE -ne 0) { throw 'Git status failed.' }
    $changes = @()
    foreach ($row in $rows) {
        if ([string]::IsNullOrWhiteSpace($row)) { continue }
        if ($row.Length -lt 4) { throw "Git returned an unreadable status row: $row" }
        $status = $row.Substring(0, 2)
        if ($status -match '[DRC]') {
            throw "Deletion, rename and copy status are review-only and refused by this publisher: $row"
        }
        $relative = $row.Substring(3).Trim('"').Replace('\', '/')
        $absolute = [System.IO.Path]::GetFullPath((Join-Path $Root $relative))
        if (-not $absolute.StartsWith($Root + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Changed path escapes the repository: $relative"
        }
        if (-not (Test-Path -LiteralPath $absolute -PathType Leaf)) {
            throw "Changed path is not a regular file: $relative"
        }
        $item = Get-Item -LiteralPath $absolute
        if ($item.Length -ge 100MB) {
            throw "Changed file reaches GitHub's 100 MB refusal boundary: $relative"
        }
        $changes += [ordered]@{
            status = $status
            path = $relative
            bytes = $item.Length
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $absolute).Hash.ToLowerInvariant()
        }
    }
    return @($changes | Sort-Object path)
}

function Find-PublicSafetyIssues {
    param([object[]]$Changes)
    $textExtensions = @('.bat', '.cmd', '.css', '.html', '.ini', '.js', '.json', '.md', '.mjs', '.ps1', '.py', '.sh', '.toml', '.txt', '.yaml', '.yml')
    $rules = @(
        [ordered]@{ id = 'private-key'; pattern = '-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----' },
        [ordered]@{ id = 'openai-key'; pattern = '\bsk-[A-Za-z0-9_-]{24,}\b' },
        [ordered]@{ id = 'anthropic-key'; pattern = '\bsk-ant-[A-Za-z0-9_-]{20,}\b' },
        [ordered]@{ id = 'github-token'; pattern = '\bgh[pousr]_[A-Za-z0-9]{20,}\b' }
    )
    $issues = @()
    foreach ($change in $Changes) {
        $absolute = Join-Path $Root $change.path
        $extension = [System.IO.Path]::GetExtension($absolute).ToLowerInvariant()
        if ($textExtensions -notcontains $extension -or $change.bytes -gt 2MB) { continue }
        $content = [System.IO.File]::ReadAllText($absolute, [System.Text.Encoding]::UTF8)
        foreach ($rule in $rules) {
            if ([System.Text.RegularExpressions.Regex]::IsMatch($content, $rule.pattern)) {
                $issues += [ordered]@{ path = $change.path; rule = $rule.id }
            }
        }
    }
    return $issues
}

function New-Plan {
    $top = [System.IO.Path]::GetFullPath((Invoke-Checked 'git' @('rev-parse', '--show-toplevel')))
    if (-not $top.Equals($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Publisher must run at the exact repository root: $Root"
    }
    $remote = Invoke-Checked 'git' @('remote', 'get-url', 'origin')
    if ($remote -match 'https?://[^/@]+:[^/@]+@') { throw 'Credential-bearing remote URLs are refused.' }
    if ($remote -notmatch '^(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?$') {
        throw 'Origin must be a credential-free github.com repository URL.'
    }

    Invoke-Checked 'python' @('tools/reseal_package.py', '--check') | Out-Null
    $head = Invoke-Checked 'git' @('rev-parse', 'HEAD')
    $branch = Invoke-Checked 'git' @('branch', '--show-current')
    $manifestSha = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $Root 'PACKAGE_MANIFEST.json')).Hash.ToLowerInvariant()
    $targetBranch = 'automation/package-' + $manifestSha.Substring(0, 12)
    if ($branch -ne 'main' -and $branch -ne $targetBranch) {
        throw "Run from main or the digest-derived branch $targetBranch; current branch is $branch"
    }

    $changes = @(Get-RelativeChanges)
    $issues = @(Find-PublicSafetyIssues -Changes $changes)
    $digestBody = [ordered]@{
        policy = 'verified-no-delete-draft-pr/v1'
        baseBranch = 'main'
        baseHead = $head
        targetBranch = $targetBranch
        remote = $remote
        manifestSha256 = $manifestSha
        changes = $changes
    }
    $digestJson = $digestBody | ConvertTo-Json -Depth 8 -Compress
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = ([System.BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($digestJson)))).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }

    return [ordered]@{
        schema = 'axm.factual-space-github-pr-plan/v1'
        generatedAt = [DateTimeOffset]::UtcNow.ToString('o')
        planDigest = $digest
        executable = ($changes.Count -gt 0 -and $issues.Count -eq 0)
        baseBranch = 'main'
        baseHead = $head
        currentBranch = $branch
        targetBranch = $targetBranch
        remote = $remote
        manifestSha256 = $manifestSha
        changedFiles = $changes.Count
        changes = $changes
        blockers = $issues
        confirmation = $ExpectedConfirmation
        publishCommand = "run_github_pr_publish.bat $digest"
        truth = [ordered]@{
            directMainPush = $false
            deletionWrites = $false
            pullRequestDraft = $true
            mergeAuthority = $false
            credentialsStoredByScript = $false
            fullAcceptanceRequired = $true
        }
    }
}

$plan = New-Plan
if (-not $Publish) {
    $plan | ConvertTo-Json -Depth 10
    exit 0
}

if ($Confirmation -ne $ExpectedConfirmation) { throw 'Exact publication confirmation is required.' }
if ($PlanDigest -notmatch '^[a-f0-9]{64}$' -or $PlanDigest -ne $plan.planDigest) {
    throw 'Reviewed plan digest is missing or stale. Build and review a new plan.'
}
if (-not $plan.executable) { throw 'Plan has no publishable changes or has public-safety blockers.' }

if ($env:OS -eq 'Windows_NT') {
    Invoke-Checked 'cmd.exe' @('/d', '/c', 'run_local_acceptance.bat') | Out-Null
} else {
    Invoke-Checked 'sh' @('./run_local_acceptance.sh') | Out-Null
}
$verifiedPlan = New-Plan
if ($verifiedPlan.planDigest -ne $PlanDigest) { throw 'Plan changed during verification; publication refused.' }

if ($plan.currentBranch -eq 'main') {
    Invoke-Checked 'git' @('switch', '-c', $plan.targetBranch) | Out-Null
}
Invoke-Checked 'git' @('add', '--all') | Out-Null
Invoke-Checked 'git' @('commit', '-m', "chore: verified simulator update $($PlanDigest.Substring(0, 12))") | Out-Null
$commit = Invoke-Checked 'git' @('rev-parse', 'HEAD')
Invoke-Checked 'git' @('push', '-u', 'origin', "HEAD:refs/heads/$($plan.targetBranch)") | Out-Null

$existingUrl = & gh pr list --head $plan.targetBranch --state open --json url --jq '.[0].url' 2>$null
if ($LASTEXITCODE -ne 0) { throw 'GitHub CLI could not inspect existing pull requests.' }
$prUrl = ($existingUrl -join "`n").Trim()
if (-not $prUrl) {
    $bodyPath = [System.IO.Path]::GetTempFileName()
    try {
        $body = @"
Deterministic, locally verified simulator update.

- Plan digest: ``$PlanDigest``
- Manifest SHA-256: ``$($plan.manifestSha256)``
- Changed files: $($plan.changedFiles)
- Full local acceptance: passed before commit

This publisher creates a draft PR only. It has no merge or CANON authority.
"@
        [System.IO.File]::WriteAllText($bodyPath, $body, [System.Text.Encoding]::UTF8)
        $prUrl = Invoke-Checked 'gh' @('pr', 'create', '--draft', '--base', 'main', '--head', $plan.targetBranch, '--title', $Title, '--body-file', $bodyPath)
    } finally {
        Remove-Item -LiteralPath $bodyPath -Force -ErrorAction SilentlyContinue
    }
}

[ordered]@{
    schema = 'axm.factual-space-github-pr-receipt/v1'
    state = 'DRAFT_PR_READY'
    planDigest = $PlanDigest
    branch = $plan.targetBranch
    commit = $commit
    pullRequest = $prUrl
    merged = $false
    canonAuthority = $false
} | ConvertTo-Json -Depth 6
