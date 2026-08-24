#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$setup = Join-Path $repo 'setup.ps1'
$pwsh = (Get-Command pwsh -ErrorAction Stop).Source
$sandbox = Join-Path ([IO.Path]::GetTempPath()) ("agentsmith-ps-platform-" + [guid]::NewGuid().ToString('N'))
$script:passed = 0

function Assert-True ([bool]$condition, [string]$message) {
  if (-not $condition) { throw "FAIL: $message" }
  $script:passed++
}
function Assert-Contains ([string]$path, [string]$needle) {
  Assert-True (Test-Path $path) "missing file: $path"
  Assert-True ((Get-Content $path -Raw).Contains($needle)) "$path does not contain: $needle"
}
function Run-Setup ([string[]]$arguments) {
  $output = & $pwsh -NoLogo -NoProfile -File $setup @arguments 2>&1
  if ($LASTEXITCODE -ne 0) { throw "setup.ps1 failed ($LASTEXITCODE):`n$($output -join "`n")" }
  return ($output -join "`n")
}
function Run-SetupExpectFailure ([string[]]$arguments) {
  $output = & $pwsh -NoLogo -NoProfile -File $setup @arguments 2>&1
  Assert-True ($LASTEXITCODE -ne 0) "setup.ps1 unexpectedly succeeded: $($arguments -join ' ')"
  return ($output -join "`n")
}
function Assert-Toml ([string]$path) {
  $python = $null
  foreach ($name in @('python3','python')) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if (-not $cmd) { continue }
    & $cmd.Source -c 'import tomllib' 2>$null
    if ($LASTEXITCODE -eq 0) { $python = $cmd.Source; break }
  }
  if (-not $python) { throw 'Python 3.11+ is required for the TOML assertions.' }
  & $python -c 'import sys,tomllib; tomllib.load(open(sys.argv[1], "rb"))' $path
  Assert-True ($LASTEXITCODE -eq 0) "invalid TOML: $path"
}

New-Item -ItemType Directory -Force -Path $sandbox | Out-Null
$oldHome = $env:HOME
$oldUserProfile = $env:USERPROFILE
$oldCodexHome = $env:CODEX_HOME
try {
  $fixtureHome = Join-Path $sandbox 'home'
  $codex = Join-Path $sandbox 'Orca Accounts/account one/codex home'
  $project = Join-Path $sandbox 'codex project'
  New-Item -ItemType Directory -Force -Path $fixtureHome,$codex,$project | Out-Null
  $env:HOME = $fixtureHome
  $env:USERPROFILE = $fixtureHome
  $env:CODEX_HOME = $codex

  $help = Run-Setup @('--help')
  Assert-True ($help.Contains('--platform claude|codex|both')) 'PowerShell help omits platform choices'
  $orgFailure = Run-SetupExpectFailure @('--platform','codex','--org-policy')
  Assert-True ($orgFailure.Contains('organization-policy installation is not supported')) 'Codex org-policy rejection is unclear'

  # Seed foreign configuration and an existing skill; Agentsmith must preserve both.
  Set-Content (Join-Path $codex 'config.toml') "# keep user comment`nmodel = `"gpt-test`"`n`n[features]`nkeep_me = true`n" -Encoding utf8
  New-Item -ItemType Directory -Force -Path (Join-Path $project '.codex'),(Join-Path $project '.agents/skills/existing') | Out-Null
  Set-Content (Join-Path $project '.codex/config.toml') "# manual project server`n[mcp_servers.context7]`ncommand = `"manual-context7`"`n" -Encoding utf8
  Set-Content (Join-Path $project '.agents/skills/existing/SKILL.md') '# keep me' -Encoding utf8

  $first = Run-Setup @('--platform','codex','--profile','general-admin','--target',$project,'--safety','cautious','--with-skills','--with-mcp','playwright,context7','--with-handoff-hooks','--with-ui-design-hook')
  Assert-True (Test-Path (Join-Path $project 'AGENTS.md')) 'Codex project rules were not installed'
  Assert-True (-not (Test-Path (Join-Path $project 'CLAUDE.md'))) 'Codex-only run wrote CLAUDE.md'
  Assert-True (-not (Test-Path (Join-Path $project '.claude'))) 'Codex-only run created .claude'
  Assert-True (-not (Test-Path (Join-Path $fixtureHome '.claude'))) 'Codex-only run touched the Claude user home'
  Assert-True (Test-Path (Join-Path $project '.agents/skills/existing/SKILL.md')) 'existing Codex skill was removed'
  Assert-Contains (Join-Path $codex 'config.toml') '# keep user comment'
  Assert-Contains (Join-Path $codex 'config.toml') 'approval_policy = "on-request"'
  Assert-Contains (Join-Path $codex 'config.toml') 'sandbox_mode = "workspace-write"'
  Assert-Contains (Join-Path $project '.codex/config.toml') '[mcp_servers.playwright]'
  Assert-Contains (Join-Path $project '.codex/config.toml') 'command = "manual-context7"'
  Assert-True (([regex]::Matches((Get-Content (Join-Path $project '.codex/config.toml') -Raw), '\[mcp_servers\.context7\]')).Count -eq 1) 'manual MCP conflict was duplicated'
  Assert-True ($first.Contains('defined outside the Agentsmith block')) 'manual MCP conflict did not emit an actionable warning'
  Assert-Toml (Join-Path $codex 'config.toml')
  Assert-Toml (Join-Path $project '.codex/config.toml')

  # Re-run: update safety, union MCP selections, keep hook entries duplicate-free, and create backups.
  Run-Setup @('--platform','codex','--profile','general-admin','--target',$project,'--safety','trusted','--with-skills','--with-mcp','excalidraw','--with-handoff-hooks','--with-ui-design-hook') | Out-Null
  Assert-Contains (Join-Path $codex 'config.toml') 'approval_policy = "never"'
  Assert-Contains (Join-Path $codex 'config.toml') 'sandbox_mode = "danger-full-access"'
  Assert-Contains (Join-Path $project '.codex/config.toml') '[mcp_servers.playwright]'
  Assert-Contains (Join-Path $project '.codex/config.toml') '[mcp_servers.excalidraw]'
  $hooks = Get-Content (Join-Path $codex 'hooks.json') -Raw | ConvertFrom-Json -AsHashtable
  Assert-True (@($hooks['hooks']['UserPromptSubmit']).Count -eq 1) 'handoff hook duplicated on re-run'
  Assert-True (@($hooks['hooks']['PreToolUse']).Count -eq 1) 'UI hook duplicated on re-run'
  Assert-True ($hooks['hooks']['PreToolUse'][0]['matcher'] -eq '^apply_patch$') 'Codex UI matcher is wrong'
  Assert-True (-not (Test-Path (Join-Path $codex 'hooks/context-budget-nudge.sh'))) 'Codex received Claude context nudge'
  Assert-True (@(Get-ChildItem $codex -Filter 'config.toml.bak.*').Count -ge 1) 'Codex config was not backed up'
  Assert-Toml (Join-Path $codex 'config.toml')
  Assert-Toml (Join-Path $project '.codex/config.toml')

  # Both produces byte-equivalent native rule files; dry-run produces no writes.
  $bothProject = Join-Path $sandbox 'both project'
  New-Item -ItemType Directory -Force -Path $bothProject | Out-Null
  Run-Setup @('--platform','both','--profile','general-admin','--target',$bothProject,'--assemble-only') | Out-Null
  Assert-True ((Get-Content (Join-Path $bothProject 'CLAUDE.md') -Raw) -ceq (Get-Content (Join-Path $bothProject 'AGENTS.md') -Raw)) 'both-mode rules differ'
  $dryProject = Join-Path $sandbox 'dry project'
  New-Item -ItemType Directory -Force -Path $dryProject | Out-Null
  Run-Setup @('--platform','codex','--profile','general-admin','--target',$dryProject,'--dry-run','--with-mcp','playwright') | Out-Null
  Assert-True (@(Get-ChildItem $dryProject -Force).Count -eq 0) 'dry-run wrote project files'

  # Uninstall removes only managed rules/config and leaves foreign TOML intact.
  Run-Setup @('--platform','codex','--global','--assemble-only') | Out-Null
  Assert-True (Test-Path (Join-Path $codex 'AGENTS.md')) 'global Codex rules were not installed'
  Run-Setup @('--platform','codex','--uninstall','--target',$project) | Out-Null
  Assert-True (-not (Test-Path (Join-Path $project 'AGENTS.md'))) 'project Codex rules survived uninstall'
  Assert-Contains (Join-Path $project '.codex/config.toml') 'command = "manual-context7"'
  Assert-True (-not (Get-Content (Join-Path $project '.codex/config.toml') -Raw).Contains('BEGIN AGENTSMITH MANAGED')) 'project managed TOML survived uninstall'
  Run-Setup @('--platform','codex','--uninstall','--global') | Out-Null
  Assert-True (-not (Test-Path (Join-Path $codex 'AGENTS.md'))) 'global Codex rules survived uninstall'
  Assert-Contains (Join-Path $codex 'config.toml') '# keep user comment'
  Assert-Contains (Join-Path $codex 'config.toml') '[features]'
  Assert-True (-not (Get-Content (Join-Path $codex 'config.toml') -Raw).Contains('BEGIN AGENTSMITH MANAGED')) 'user managed TOML survived uninstall'
  Assert-Toml (Join-Path $codex 'config.toml')

  # Legacy flag remains instruction-only and defaults to Claude.
  $legacyHome = Join-Path $sandbox 'legacy home'
  $legacyProject = Join-Path $sandbox 'legacy project'
  New-Item -ItemType Directory -Force -Path $legacyHome,$legacyProject | Out-Null
  $env:HOME = $legacyHome; $env:USERPROFILE = $legacyHome; $env:CODEX_HOME = Join-Path $legacyHome '.codex'
  $legacy = Run-Setup @('--profile','general-admin','--target',$legacyProject,'--assemble-only','--also-agents-md')
  Assert-True (Test-Path (Join-Path $legacyProject 'CLAUDE.md')) 'legacy run lost default Claude rules'
  Assert-True (Test-Path (Join-Path $legacyProject 'AGENTS.md')) 'legacy instruction copy missing'
  Assert-True (-not (Test-Path $env:CODEX_HOME)) 'legacy flag installed native Codex state'
  Assert-True ($legacy.Contains('--also-agents-md is deprecated')) 'legacy flag did not warn'

  # Without CODEX_HOME, Codex falls back to HOME/.codex.
  $fallbackHome = Join-Path $sandbox 'fallback home'
  New-Item -ItemType Directory -Force -Path $fallbackHome | Out-Null
  $env:HOME = $fallbackHome; $env:USERPROFILE = $fallbackHome; $env:CODEX_HOME = $null
  Run-Setup @('--platform','codex','--global','--assemble-only') | Out-Null
  Assert-True (Test-Path (Join-Path $fallbackHome '.codex/AGENTS.md')) 'CODEX_HOME fallback did not use HOME/.codex'

  Write-Host "PASS: $script:passed PowerShell platform installer assertions"
}
finally {
  $env:HOME = $oldHome
  $env:USERPROFILE = $oldUserProfile
  $env:CODEX_HOME = $oldCodexHome
  $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
  $resolvedSandbox = [IO.Path]::GetFullPath($sandbox)
  if ($resolvedSandbox.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path $resolvedSandbox)) {
    Remove-Item -LiteralPath $resolvedSandbox -Recurse -Force
  }
}
