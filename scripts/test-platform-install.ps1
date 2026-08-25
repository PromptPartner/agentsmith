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
function Get-HookCommandCount ([string]$settingsPath, [string]$event, [string]$command) {
  $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json -AsHashtable
  $count = 0
  if ((-not $settings.ContainsKey('hooks')) -or
      ($settings['hooks'] -isnot [Collections.IDictionary]) -or
      (-not $settings['hooks'].ContainsKey($event))) { return 0 }
  foreach ($group in @($settings['hooks'][$event])) {
    if (($group -isnot [Collections.IDictionary]) -or (-not $group.ContainsKey('hooks'))) { continue }
    foreach ($handler in @($group['hooks'])) {
      if (($handler -is [Collections.IDictionary]) -and
          $handler.ContainsKey('command') -and
          $handler['command'] -eq $command) { $count++ }
    }
  }
  return $count
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

  # RTK is default-on for code profiles and uses the selected account-specific CODEX_HOME.
  $fakeBin = Join-Path $sandbox 'fake bin'
  New-Item -ItemType Directory -Force -Path $fakeBin | Out-Null
  $fakeRtk = Join-Path $fakeBin 'rtk.ps1'
  [IO.File]::WriteAllText($fakeRtk, @'
if ($args[0] -eq '--version') { Write-Output 'rtk fake'; exit 0 }
Add-Content -LiteralPath $env:AGENTSMITH_RTK_CALL_LOG -Value ("{0}|{1}" -f $env:CODEX_HOME, ($args -join ' '))
exit 0
'@, [Text.UTF8Encoding]::new($false))
  $oldPath = $env:PATH
  $rtkLog = Join-Path $sandbox 'rtk calls.log'
  $env:PATH = "$fakeBin$([IO.Path]::PathSeparator)$oldPath"
  $env:AGENTSMITH_RTK_CALL_LOG = $rtkLog
  $rtkProject = Join-Path $sandbox 'rtk codex project'
  New-Item -ItemType Directory -Force -Path $rtkProject | Out-Null
  $rtkOutput = Run-Setup @('--platform','codex','--profile','software-dev','--target',$rtkProject)
  Assert-True ((Get-Content $rtkLog -Raw).Contains("$codex|init -g --codex")) 'Codex code profile did not initialize RTK with CODEX_HOME'
  Assert-True (-not $rtkOutput.Contains('Claude-specific wiring')) 'Codex RTK still emitted the obsolete Claude-only warning'
  Remove-Item $rtkLog -Force
  Run-Setup @('--platform','codex','--profile','software-dev','--target',$rtkProject,'--no-rtk') | Out-Null
  Assert-True (-not (Test-Path $rtkLog)) '--no-rtk did not suppress the code-profile default'

  $rtkRules = Join-Path $codex 'AGENTS.md'
  Set-Content $rtkRules '@RTK.md' -Encoding utf8
  $rtkDoctorMissing = Run-Setup @('--platform','codex','--doctor')
  Assert-True ($rtkDoctorMissing.Contains("Codex RTK import is dangling: $(Join-Path $codex 'RTK.md')")) 'doctor did not report a dangling Codex RTK import'
  Set-Content (Join-Path $codex 'RTK.md') '# generated RTK instructions' -Encoding utf8
  $rtkDoctorHealthy = Run-Setup @('--platform','codex','--doctor')
  Assert-True ($rtkDoctorHealthy.Contains('Codex RTK instructions wired')) 'doctor did not recognize healthy Codex RTK wiring'
  Remove-Item $rtkRules,(Join-Path $codex 'RTK.md') -Force
  $env:PATH = $oldPath
  Remove-Item Env:AGENTSMITH_RTK_CALL_LOG -ErrorAction SilentlyContinue

  # Seed foreign configuration and an existing skill; Agentsmith must preserve both.
  Set-Content (Join-Path $codex 'config.toml') "# keep user comment`nmodel = `"gpt-test`"`n`n[features]`nkeep_me = true`n" -Encoding utf8
  Set-Content (Join-Path $codex 'hooks.json') '{"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"foreign-user-hook"}]}],"Stop":[{"hooks":[{"type":"command","command":"foreign-stop-hook"}]}]}}' -Encoding utf8
  New-Item -ItemType Directory -Force -Path (Join-Path $project '.codex'),(Join-Path $project '.agents/skills/existing') | Out-Null
  Set-Content (Join-Path $project '.codex/config.toml') "# manual project server`n[mcp_servers.context7]`ncommand = `"manual-context7`"`n" -Encoding utf8
  Set-Content (Join-Path $project '.agents/skills/existing/SKILL.md') '# keep me' -Encoding utf8

  $first = Run-Setup @('--platform','codex','--profile','general-admin','--target',$project,'--safety','cautious','--with-skills','--with-mcp','playwright,context7','--with-handoff-hooks','--with-ui-design-hook')
  Assert-True (Test-Path (Join-Path $project 'AGENTS.md')) 'Codex project rules were not installed'
  Assert-True (-not (Test-Path (Join-Path $project 'CLAUDE.md'))) 'Codex-only run wrote CLAUDE.md'
  Assert-True (-not (Test-Path (Join-Path $project '.claude'))) 'Codex-only run created .claude'
  Assert-True (-not (Test-Path (Join-Path $fixtureHome '.claude'))) 'Codex-only run touched the Claude user home'
  Assert-True (Test-Path (Join-Path $project '.agents/skills/existing/SKILL.md')) 'existing Codex skill was removed'
  Assert-True (-not (Test-Path (Join-Path $project 'scripts/autonomous-run.py'))) 'non-code profile installed autonomous controller'
  Assert-True (-not (Test-Path (Join-Path $project '.harness/templates/autonomous-run.json'))) 'non-code profile installed autonomous manifest template'
  Assert-Contains (Join-Path $codex 'config.toml') '# keep user comment'
  Assert-Contains (Join-Path $codex 'config.toml') 'approval_policy = "on-request"'
  Assert-Contains (Join-Path $codex 'config.toml') 'sandbox_mode = "workspace-write"'
  Assert-Contains (Join-Path $project '.codex/config.toml') '[mcp_servers.playwright]'
  Assert-Contains (Join-Path $project '.codex/config.toml') 'command = "manual-context7"'
  Assert-True (([regex]::Matches((Get-Content (Join-Path $project '.codex/config.toml') -Raw), '\[mcp_servers\.context7\]')).Count -eq 1) 'manual MCP conflict was duplicated'
  Assert-True ($first.Contains('defined outside the Agentsmith block')) 'manual MCP conflict did not emit an actionable warning'
  Assert-True ((Get-HookCommandCount (Join-Path $codex 'hooks.json') 'UserPromptSubmit' 'foreign-user-hook') -eq 1) 'foreign Codex UserPromptSubmit hook was lost'
  Assert-True ((Get-HookCommandCount (Join-Path $codex 'hooks.json') 'Stop' 'foreign-stop-hook') -eq 1) 'foreign Codex Stop hook was lost'
  Assert-Toml (Join-Path $codex 'config.toml')
  Assert-Toml (Join-Path $project '.codex/config.toml')

  $softwareProject = Join-Path $fixtureHome 'autonomous-software'
  New-Item -ItemType Directory -Force -Path $softwareProject | Out-Null
  Run-Setup @('--platform','codex','--profile','software-dev','--no-rtk','--target',$softwareProject) | Out-Null
  Assert-True (Test-Path (Join-Path $softwareProject 'scripts/autonomous-run.py')) 'software-dev missing autonomous controller'
  Assert-True (Test-Path (Join-Path $softwareProject '.harness/templates/autonomous-run.json')) 'software-dev missing autonomous manifest template'

  # Re-run: update safety, union MCP selections, keep hook entries duplicate-free, and create backups.
  Set-Content (Join-Path $codex 'hooks/handoff-on-keyword.sh') '# stale Codex handoff hook' -Encoding utf8
  $codexHooksPath = Join-Path $codex 'hooks.json'
  $codexBefore = Get-Content $codexHooksPath -Raw | ConvertFrom-Json -AsHashtable
  $managedCodexCommand = @(
    foreach ($group in @($codexBefore['hooks']['UserPromptSubmit'])) {
      foreach ($handler in @($group['hooks'])) {
        if (($handler -is [Collections.IDictionary]) -and $handler['command'].Contains('handoff-on-keyword.sh')) { $handler['command'] }
      }
    }
  )[0]
  $codexBefore['hooks']['UserPromptSubmit'] = @($codexBefore['hooks']['UserPromptSubmit']) + @(@{ hooks = @(@{ type = 'command'; command = $managedCodexCommand }) })
  $codexBefore | ConvertTo-Json -Depth 100 | Set-Content $codexHooksPath -Encoding utf8
  Run-Setup @('--platform','codex','--profile','general-admin','--target',$project,'--safety','trusted','--with-skills','--with-mcp','excalidraw','--with-handoff-hooks','--with-ui-design-hook') | Out-Null
  Assert-Contains (Join-Path $codex 'config.toml') 'approval_policy = "never"'
  Assert-Contains (Join-Path $codex 'config.toml') 'sandbox_mode = "danger-full-access"'
  Assert-Contains (Join-Path $project '.codex/config.toml') '[mcp_servers.playwright]'
  Assert-Contains (Join-Path $project '.codex/config.toml') '[mcp_servers.excalidraw]'
  $hooks = Get-Content (Join-Path $codex 'hooks.json') -Raw | ConvertFrom-Json -AsHashtable
  $managedCodexHandoffCount = @(
    foreach ($group in @($hooks['hooks']['UserPromptSubmit'])) {
      foreach ($handler in @($group['hooks'])) {
        if (($handler -is [Collections.IDictionary]) -and
            $handler.ContainsKey('command') -and
            $handler['command'].Contains('handoff-on-keyword.sh')) { $handler }
      }
    }
  ).Count
  Assert-True ($managedCodexHandoffCount -eq 1) 'handoff hook duplicated on re-run'
  Assert-True ((Get-FileHash (Join-Path $codex 'hooks/handoff-on-keyword.sh')).Hash -eq (Get-FileHash (Join-Path $repo 'hooks/handoff-on-keyword.sh')).Hash) 'stale Codex handoff script was not refreshed'
  Assert-True (@($hooks['hooks']['PreToolUse']).Count -eq 1) 'UI hook duplicated on re-run'
  Assert-True ($hooks['hooks']['PreToolUse'][0]['matcher'] -eq '^apply_patch$') 'Codex UI matcher is wrong'
  Assert-True (-not (Test-Path (Join-Path $codex 'hooks/context-budget-nudge.sh'))) 'Codex received Claude context nudge'
  Assert-True (@(Get-ChildItem $codex -Filter 'config.toml.bak.*').Count -ge 1) 'Codex config was not backed up'
  Assert-Toml (Join-Path $codex 'config.toml')
  Assert-Toml (Join-Path $project '.codex/config.toml')

  # Fresh Claude handoff install owns its bundled statusline and wires each hook once.
  $freshClaudeHome = Join-Path $sandbox 'fresh Claude home'
  $freshClaudeProject = Join-Path $sandbox 'fresh Claude project'
  New-Item -ItemType Directory -Force -Path $freshClaudeHome,$freshClaudeProject | Out-Null
  $env:HOME = $freshClaudeHome; $env:USERPROFILE = $freshClaudeHome
  Run-Setup @('--platform','claude','--profile','general-admin','--target',$freshClaudeProject,'--with-handoff-hooks','--no-rtk') | Out-Null
  $freshClaudeDir = Join-Path $freshClaudeHome '.claude'
  Assert-True ((Get-FileHash (Join-Path $freshClaudeDir 'statusline-command.sh')).Hash -eq (Get-FileHash (Join-Path $repo 'config/statusline-command.sh')).Hash) 'fresh Claude handoff install did not supply the managed statusline'
  $freshSettings = Join-Path $freshClaudeDir 'settings.json'
  Assert-True ((Get-HookCommandCount $freshSettings 'UserPromptSubmit' 'bash ~/.claude/hooks/handoff-on-keyword.sh') -eq 1) 'fresh Claude keyword hook was not wired exactly once'
  Assert-True ((Get-HookCommandCount $freshSettings 'Stop' 'bash ~/.claude/hooks/context-budget-nudge.sh') -eq 1) 'fresh Claude context hook was not wired exactly once'
  $freshDoctor = Run-Setup @('--platform','claude','--doctor')
  Assert-True ($freshDoctor.Contains('Claude keyword handoff script healthy')) 'doctor did not recognize the fresh Claude keyword script'
  Assert-True ($freshDoctor.Contains('contains the per-session context-signal writer')) 'doctor did not recognize the managed statusline signal writer'

  # Existing AgentSmith hooks are refreshed, while foreign hooks and a custom statusline survive.
  $existingClaudeHome = Join-Path $sandbox 'existing Claude home'
  $existingClaudeProject = Join-Path $sandbox 'existing Claude project'
  $existingClaudeDir = Join-Path $existingClaudeHome '.claude'
  $existingHooksDir = Join-Path $existingClaudeDir 'hooks'
  New-Item -ItemType Directory -Force -Path $existingHooksDir,$existingClaudeProject | Out-Null
  $customStatusline = Join-Path $existingClaudeDir 'statusline-command.sh'
  [IO.File]::WriteAllText($customStatusline, "#!/usr/bin/env bash`nprintf 'custom statusline\n'`n", [Text.UTF8Encoding]::new($false))
  $customStatuslineHash = (Get-FileHash $customStatusline).Hash
  Set-Content (Join-Path $existingHooksDir 'handoff-on-keyword.sh') '# stale keyword hook' -Encoding utf8
  Set-Content (Join-Path $existingHooksDir 'context-budget-nudge.sh') '# stale context hook' -Encoding utf8
  $existingSettings = Join-Path $existingClaudeDir 'settings.json'
  [IO.File]::WriteAllText($existingSettings, '{"statusLine":{"type":"command","command":"bash ~/.claude/statusline-command.sh"},"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"foreign-user-hook"}]},{"hooks":[{"type":"command","command":"bash ~/.claude/hooks/handoff-on-keyword.sh"}]},{"hooks":[{"type":"command","command":"bash ~/.claude/hooks/handoff-on-keyword.sh"}]}],"Stop":[{"hooks":[{"type":"command","command":"foreign-stop-hook"}]},{"hooks":[{"type":"command","command":"bash ~/.claude/hooks/context-budget-nudge.sh"}]},{"hooks":[{"type":"command","command":"bash ~/.claude/hooks/context-budget-nudge.sh"}]}]}}', [Text.UTF8Encoding]::new($false))
  $env:HOME = $existingClaudeHome; $env:USERPROFILE = $existingClaudeHome
  $doctorBefore = Run-Setup @('--platform','claude','--doctor')
  Assert-True ($doctorBefore.Contains('Claude keyword handoff script stale or customized')) 'doctor did not report the stale Claude keyword script'
  Run-Setup @('--platform','claude','--profile','general-admin','--target',$existingClaudeProject,'--with-handoff-hooks','--no-rtk') | Out-Null
  Assert-True ((Get-FileHash (Join-Path $existingHooksDir 'handoff-on-keyword.sh')).Hash -eq (Get-FileHash (Join-Path $repo 'hooks/handoff-on-keyword.sh')).Hash) 'stale Claude keyword hook was not refreshed'
  Assert-True ((Get-FileHash (Join-Path $existingHooksDir 'context-budget-nudge.sh')).Hash -eq (Get-FileHash (Join-Path $repo 'hooks/context-budget-nudge.sh')).Hash) 'stale Claude context hook was not refreshed'
  Assert-True ((Get-FileHash $customStatusline).Hash -eq $customStatuslineHash) 'custom Claude statusline was overwritten'
  Assert-True ((Get-HookCommandCount $existingSettings 'UserPromptSubmit' 'foreign-user-hook') -eq 1) 'foreign Claude UserPromptSubmit hook was lost'
  Assert-True ((Get-HookCommandCount $existingSettings 'Stop' 'foreign-stop-hook') -eq 1) 'foreign Claude Stop hook was lost'
  Assert-True ((Get-HookCommandCount $existingSettings 'UserPromptSubmit' 'bash ~/.claude/hooks/handoff-on-keyword.sh') -eq 1) 'pre-existing duplicate Claude keyword hooks were not collapsed'
  Assert-True ((Get-HookCommandCount $existingSettings 'Stop' 'bash ~/.claude/hooks/context-budget-nudge.sh') -eq 1) 'pre-existing duplicate Claude context hooks were not collapsed'
  Run-Setup @('--platform','claude','--profile','general-admin','--target',$existingClaudeProject,'--with-handoff-hooks','--no-rtk') | Out-Null
  Assert-True ((Get-HookCommandCount $existingSettings 'UserPromptSubmit' 'bash ~/.claude/hooks/handoff-on-keyword.sh') -eq 1) 'Claude keyword hook duplicated on re-run'
  Assert-True ((Get-HookCommandCount $existingSettings 'Stop' 'bash ~/.claude/hooks/context-budget-nudge.sh') -eq 1) 'Claude context hook duplicated on re-run'
  Assert-True ((Get-FileHash $customStatusline).Hash -eq $customStatuslineHash) 'custom Claude statusline changed on re-run'
  $doctorAfter = Run-Setup @('--platform','claude','--doctor')
  Assert-True ($doctorAfter.Contains('Claude keyword handoff script healthy')) 'doctor did not recognize the refreshed Claude keyword script'
  Assert-True ($doctorAfter.Contains('no per-session context-signal writer was detected')) 'doctor did not report the non-emitting custom statusline'

  # Restore the original fixture account for the remaining Codex assertions.
  $env:HOME = $fixtureHome; $env:USERPROFILE = $fixtureHome; $env:CODEX_HOME = $codex

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
