[CmdletBinding()]
param(
    [string]$SshHost = "rn-direct",
    [string]$RemoteDir = "/opt/app/bilinote",
    [string]$PublicUrl = "https://bilinote.229929605.xyz",
    [switch]$DryRun,
    [switch]$KeepRemoteStage,
    [switch]$SkipPublicAccessCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Assert-LastExitCode {
    param([string]$Operation)
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE"
    }
}

function Quote-BashArgument {
    param([string]$Value)
    $singleQuoteEscape = "'" + '"' + "'" + '"' + "'"
    return "'" + $Value.Replace("'", $singleQuoteEscape) + "'"
}

function Test-ManagedPath {
    param([string]$Path)

    $normalized = $Path.Replace("\", "/").TrimStart("./")
    return $normalized -eq "docker-compose.yml" -or
        $normalized.StartsWith("BillNote_frontend/", [System.StringComparison]::Ordinal) -or
        $normalized.StartsWith("backend/", [System.StringComparison]::Ordinal) -or
        $normalized.StartsWith("nginx/", [System.StringComparison]::Ordinal) -or
        $normalized.StartsWith("deploy/compose/", [System.StringComparison]::Ordinal)
}

function Get-GitLines {
    param(
        [string]$GitExe,
        [string[]]$Arguments
    )

    $effectiveArguments = @("-c", "core.safecrlf=false") + $Arguments
    $output = @(& $GitExe @effectiveArguments)
    Assert-LastExitCode "git $($Arguments -join ' ')"
    return @($output | Where-Object { $_ } | ForEach-Object { $_.Trim().Replace("\", "/") })
}

function Remove-LocalStage {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $leaf = Split-Path -Leaf $resolvedPath
    if (-not $resolvedPath.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not $leaf.StartsWith("bilinote-deploy-", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove unexpected temporary path: $resolvedPath"
    }

    Remove-Item -LiteralPath $resolvedPath -Recurse -Force
}

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$gitExe = (Get-Command git -ErrorAction Stop).Source
$sshExe = (Get-Command ssh -ErrorAction Stop).Source
$scpExe = (Get-Command scp -ErrorAction Stop).Source
$tarExe = Join-Path $env:SystemRoot "System32\tar.exe"
$remoteHelperSource = Join-Path $PSScriptRoot "deploy_rn_direct_remote.sh"

if (-not (Test-Path -LiteralPath $tarExe -PathType Leaf)) {
    throw "Windows tar.exe was not found at $tarExe"
}
if (-not (Test-Path -LiteralPath $remoteHelperSource -PathType Leaf)) {
    throw "Remote deployment helper was not found: $remoteHelperSource"
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot ".git") -PathType Container)) {
    throw "Repository root was not found: $repoRoot"
}

$managedSpecs = @(
    "BillNote_frontend",
    "backend",
    "nginx",
    "docker-compose.yml",
    "deploy/compose"
)

$deploymentId = (Get-Date -Format "yyyyMMdd-HHmmss") + "-" + ([Guid]::NewGuid().ToString("N").Substring(0, 8))
$localStage = Join-Path ([System.IO.Path]::GetTempPath()) "bilinote-deploy-$deploymentId"
$snapshotDir = Join-Path $localStage "source"
$baseArchive = Join-Path $localStage "base.tar"
$sourceArchive = Join-Path $localStage "source.tar"
$manifestPath = Join-Path $localStage "managed-files.txt"
$remoteHelperPath = Join-Path $localStage "deploy_remote.sh"
$remoteStage = "/tmp/bilinote-deploy-$deploymentId"
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

try {
    New-Item -ItemType Directory -Path $snapshotDir -Force | Out-Null
    Push-Location $repoRoot
    try {
        Write-Step "Creating normalized source snapshot"

        $archiveRoots = @()
        foreach ($spec in $managedSpecs) {
            & $gitExe cat-file -e "HEAD:$spec" 2>$null
            if ($LASTEXITCODE -eq 0) {
                $archiveRoots += $spec
            }
        }
        if ($archiveRoots.Count -eq 0) {
            throw "No managed paths exist in HEAD"
        }

        & $gitExe archive --format=tar "--output=$baseArchive" HEAD -- @archiveRoots
        Assert-LastExitCode "git archive"
        & $tarExe -xf $baseArchive -C $snapshotDir
        Assert-LastExitCode "extracting the Git snapshot"

        $changedArgs = @("diff", "--no-renames", "--name-only", "--diff-filter=ACMRTUXB", "HEAD", "--") + $managedSpecs
        $deletedArgs = @("diff", "--no-renames", "--name-only", "--diff-filter=D", "HEAD", "--") + $managedSpecs
        $untrackedArgs = @("ls-files", "--others", "--exclude-standard", "--") + $managedSpecs

        $changedPaths = Get-GitLines $gitExe $changedArgs
        $deletedPaths = Get-GitLines $gitExe $deletedArgs
        $untrackedPaths = Get-GitLines $gitExe $untrackedArgs
        $overlayPaths = @($changedPaths + $untrackedPaths | Sort-Object -Unique)

        foreach ($relativePath in $overlayPaths) {
            if (-not (Test-ManagedPath $relativePath)) {
                throw "Refusing to package unmanaged path: $relativePath"
            }

            $localPath = Join-Path $repoRoot ($relativePath.Replace("/", [System.IO.Path]::DirectorySeparatorChar))
            if (-not (Test-Path -LiteralPath $localPath -PathType Leaf)) {
                throw "Changed source file is missing: $relativePath"
            }

            $snapshotPath = Join-Path $snapshotDir ($relativePath.Replace("/", [System.IO.Path]::DirectorySeparatorChar))
            $snapshotParent = Split-Path -Parent $snapshotPath
            New-Item -ItemType Directory -Path $snapshotParent -Force | Out-Null
            Copy-Item -LiteralPath $localPath -Destination $snapshotPath -Force
        }

        foreach ($relativePath in $deletedPaths) {
            if (-not (Test-ManagedPath $relativePath)) {
                throw "Refusing to delete unmanaged path from snapshot: $relativePath"
            }

            $snapshotPath = Join-Path $snapshotDir ($relativePath.Replace("/", [System.IO.Path]::DirectorySeparatorChar))
            if (Test-Path -LiteralPath $snapshotPath -PathType Leaf) {
                Remove-Item -LiteralPath $snapshotPath -Force
            }
        }

        $manifest = @(
            Get-ChildItem -LiteralPath $snapshotDir -Recurse -Force -File |
                ForEach-Object {
                    if ($_.LinkType) {
                        throw "Symbolic links are not supported by this deployment script: $($_.FullName)"
                    }
                    [System.IO.Path]::GetRelativePath($snapshotDir, $_.FullName).Replace("\", "/")
                } |
                Sort-Object -Unique
        )

        if ($manifest.Count -eq 0) {
            throw "The deployment snapshot is empty"
        }
        foreach ($relativePath in $manifest) {
            if (-not (Test-ManagedPath $relativePath)) {
                throw "Snapshot contains unmanaged path: $relativePath"
            }
        }

        [System.IO.File]::WriteAllText($manifestPath, (($manifest -join "`n") + "`n"), $utf8NoBom)
        & $tarExe -cf $sourceArchive -C $snapshotDir -T $manifestPath
        Assert-LastExitCode "creating the deployment archive"

        $archiveHash = (Get-FileHash -LiteralPath $sourceArchive -Algorithm SHA256).Hash.ToLowerInvariant()
        $localHead = (& $gitExe rev-parse HEAD).Trim()
        Assert-LastExitCode "reading the local commit"
        $workingChanges = @(Get-GitLines $gitExe (@("status", "--porcelain", "--") + $managedSpecs))

        Write-Host "Snapshot files : $($manifest.Count)"
        Write-Host "Working changes: $($workingChanges.Count)"
        Write-Host "Archive size   : $([Math]::Round((Get-Item -LiteralPath $sourceArchive).Length / 1MB, 2)) MB"
        Write-Host "Local commit   : $localHead"
        Write-Host "Archive SHA256 : $archiveHash"
    }
    finally {
        Pop-Location
    }

    if ($DryRun) {
        Write-Host "`nDry run complete. No remote changes were made." -ForegroundColor Yellow
        return
    }

    $helperContent = [System.IO.File]::ReadAllText($remoteHelperSource).Replace("`r`n", "`n").Replace("`r", "`n")
    [System.IO.File]::WriteAllText($remoteHelperPath, $helperContent, $utf8NoBom)

    Write-Step "Creating remote staging directory"
    $quotedRemoteStage = Quote-BashArgument $remoteStage
    & $sshExe $SshHost "mkdir -p -- $quotedRemoteStage && chmod 700 -- $quotedRemoteStage"
    Assert-LastExitCode "creating the remote staging directory"

    Write-Step "Uploading source snapshot"
    & $scpExe $sourceArchive $manifestPath $remoteHelperPath "${SshHost}:$remoteStage/"
    Assert-LastExitCode "uploading the deployment snapshot"

    $remoteArguments = @(
        "bash",
        "$remoteStage/deploy_remote.sh",
        "--remote-dir", $RemoteDir,
        "--stage-dir", $remoteStage,
        "--public-url", $PublicUrl,
        "--archive-sha256", $archiveHash,
        "--local-head", $localHead
    )
    if ($KeepRemoteStage) {
        $remoteArguments += "--keep-stage"
    }
    if ($SkipPublicAccessCheck) {
        $remoteArguments += "--skip-public-access-check"
    }

    $remoteCommand = ($remoteArguments | ForEach-Object { Quote-BashArgument $_ }) -join " "
    Write-Step "Building and deploying on $SshHost"
    & $sshExe $SshHost $remoteCommand
    Assert-LastExitCode "remote deployment"

    Write-Host "`nDeployment completed: $PublicUrl" -ForegroundColor Green
}
finally {
    Remove-LocalStage $localStage
}
