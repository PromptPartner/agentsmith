#!/usr/bin/env pwsh
# ============================================================================
#  Agentsmith — the universal agent harness — setup (PowerShell port of setup.sh)
#  Same flags, same behaviour, for native Windows without Git Bash. Also runs on
#  PowerShell 7+ anywhere (Linux/macOS). Assembles a lean CLAUDE.md from core/ +
#  chosen profiles, and (optionally) installs global config, plugins, and skills.
#
#  DEFAULT — just run it. With no options, the interactive wizard walks you through
#  everything (and prints the exact command it runs, so you learn the flags):
#    ./setup.ps1                        # ← the wizard (same as --wizard)
#
#  Everything below is the non-interactive path — pass options to skip the wizard.
#
#  Per-project (self-contained CLAUDE.md = core + profile):
#    ./setup.ps1 --profile software-dev --target C:\path\to\project
#    ./setup.ps1 --profile devops-setup,software-dev --operator-name "Your Name" `
#                --operator-role "sysadmin / GTM" --tracker linear --target .
#
#  Layered (recommended): install the core ONCE globally, thin profile per project:
#    ./setup.ps1 --global --operator-name "Your Name"     # core -> ~/.claude/CLAUDE.md + config
#    ./setup.ps1 --profile software-dev --profile-only --target C:\path\to\project
#
#  About --global: it writes ~/.claude/CLAUDE.md and nothing else can redirect it — --target is
#  refused, and --assemble-only only skips config/plugins, it does NOT make the run local. A
#  re-run keeps the operator name/role/tracker already in the file unless you pass new ones, so
#  `--global` on its own is safe to repeat. Use --dry-run to write nothing at all.
#
#  Other options:
#    ./setup.ps1 --tracker linear --tracker-writes ask|allowed
#                                       # --tracker says WHERE the team tracks work. It does NOT
#                                       #   grant write access — that's --tracker-writes:
#                                       #   ask (default) = the agent drafts the issue, you post it;
#                                       #   allowed = it may file/comment in the tracker itself.
#                                       #   Availability is not authorization (core/10, feedback 0002).
#    ./setup.ps1 --safety cautious|trusted  # cautious = auto-apply edits, ask before shell/network;
#                                       #   trusted = run almost everything without asking (flag-path
#                                       #   default; the wizard defaults to cautious)
#    ./setup.ps1 --assemble-only ...    # skip the config/plugins install; still writes CLAUDE.md
#                                       #   (under --global that IS ~/.claude/CLAUDE.md — see above)
#    ./setup.ps1 --with-plugins dev-workflow,stack-lsp ...   # opt-in plugin packs (latest)
#    ./setup.ps1 --with-mcp playwright,context7 ...   # add named MCP server(s) to project .mcp.json
#    ./setup.ps1 --with-skills ...      # install the bundled skill pack (handoff, verify, harness-doctor,
#                                       #   new-research, new-feedback, harness-help); project mode →
#                                       #   <project>/.claude/skills, --global → ~/.claude/skills
#    ./setup.ps1 --with-hooks ...       # install git guardrails (secret-scan+protect-main+conventional)
#    ./setup.ps1 --update-plugins       # update installed plugins to latest, then exit
#    ./setup.ps1 --doctor               # print install health, then exit
#    ./setup.ps1 --profile X --export-instructions > inst.md   # paste-ready blob for web/Cowork
#    sudo ./setup.ps1 --org-policy      # machine-wide managed CLAUDE.md + hardened (no-bypass) settings
#    ./setup.ps1 --with-handoff-hooks   # install reliable 'handoff' keyword hook (+ best-effort ctx-% nudge)
#    ./setup.ps1 --self-update          # pull the latest harness into this checkout + re-assemble managed CLAUDE.md
#                                       #   remote: --from <url> | $env:HARNESS_REMOTE | .harness/remote | the checkout's origin
#                                       #   auth:   git@/ssh:// -> SSH key; https:// -> $env:HARNESS_GH_TOKEN (never stored)
#                                       #   add --no-reassemble to fetch only; --dry-run to preview without pulling
#    ./setup.ps1 --profile auto --target .   # auto-detect the profile from the project's files
#    ./setup.ps1 --uninstall --target .  # remove the harness section (auto-backup first); --global for the core
#    ./setup.ps1 --help
#
#  Idempotent. Never clobbers your files without --force.
# ============================================================================
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$HarnessDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CcDir = Join-Path $HOME '.claude'
$SkillsDest = Join-Path $CcDir 'skills'   # global by default; project mode repoints to <project>/.claude/skills

$BeginMark = '<!-- BEGIN AGENTSMITH — universal agent harness (managed by setup.sh — edit core/profiles, not here) -->'
$EndMark   = '<!-- END AGENTSMITH -->'
# Legacy pre-rebrand ("Universal Claude Harness") markers: read-only aliases so installs made
# before the Agentsmith rename are still found by update/reassemble/uninstall. Never written.
$LegacyBeginMark = '<!-- BEGIN UNIVERSAL CLAUDE HARNESS (managed by setup.sh — edit core/profiles, not here) -->'
$LegacyEndMark   = '<!-- END UNIVERSAL CLAUDE HARNESS -->'
$AllMarkPairs = @(
  @{ Begin = $BeginMark;       End = $EndMark }        # written; tried first
  @{ Begin = $LegacyBeginMark; End = $LegacyEndMark }  # pre-rebrand; read-only
)
function Find-ManagedMarks ([string]$path) {  # -> @{Begin=..;End=..} of the marker pair present, or $null
  if (-not $path -or -not (Test-Path $path)) { return $null }
  foreach ($pair in $AllMarkPairs) {
    if (Select-String -Path $path -SimpleMatch $pair.Begin -Quiet) { return $pair }
  }
  return $null
}

# ---- options ---------------------------------------------------------------
$o = @{
  Profiles     = ''
  Target       = ''
  # Operator identity starts EMPTY on purpose — empty means "the flag was not passed", which is the
  # only thing that lets a re-run tell "leave this alone" apart from "set it to exactly this". The
  # real defaults are Default* below, applied LAST, after any recovery (feedback 0003).
  OperatorName = ''
  OperatorRole = ''
  OperatorBio  = ''
  Tracker      = ''
  TrackerWrites = ''
  DefaultOperatorName = 'the project lead'
  DefaultOperatorRole = 'owner / decision-maker'
  DefaultOperatorBio  = 'They decide direction and accept the risk; you are the technical co-pilot — proactive, evidence-driven, and honest about trade-offs.'
  DefaultTracker      = "your project's tracker (or a KNOWN-ISSUES.md at the repo root)"
  # Consent, not inference: naming a tracker says WHERE the team tracks work, never that the agent
  # may write there (feedback 0002). Default is ask; --tracker-writes allowed is a deliberate opt-in.
  # Keep these two sentences byte-identical to setup.sh's — they are the recovery anchors in
  # Recover-OperatorFields, and scripts/test-tracker-consent.sh asserts on the substrings
  # "writes are NOT authorized" / "writes are authorized".
  DefaultTrackerWrites = 'ask'
  TrackerPolicyAsk     = "**writes are NOT authorized** — draft the entry and surface it for the operator to post; never create or comment on items yourself. Offer once; if they say yes, that's durable for this session."
  TrackerPolicyAllowed = "**writes are authorized** (the operator opted in at setup) — file it directly, and make agent work visible there (a note when work starts and when it lands)."
  Global = $false; ProfileOnly = $false; AssembleOnly = $false; Force = $false; DryRun = $false
  AlsoAgents = $false; AlsoGemini = $false; WithSkills = $false; WithHooks = $false; WithHandoffHooks = $false
  WithPlugins = ''; WithMcp = ''
  UpdatePlugins = $false; Doctor = $false; Export = $false; OrgPolicy = $false; Wizard = $false
  SelfUpdate = $false; SelfUpdateRemote = ''; NoReassemble = $false; Uninstall = $false
  Safety = 'trusted'   # trusted = bypassPermissions (flag-path default); cautious = acceptEdits (wizard default)
}

# ---- pretty output (Write-Host => host stream, so `> file` captures only the blob) -
function Say  ($m) { Write-Host "» $m"   -ForegroundColor Cyan }
function Ok   ($m) { Write-Host "  ✓ $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "  ! $m" -ForegroundColor Yellow }
function Die  ($m) { Write-Host "✗ $m"   -ForegroundColor Red; exit 1 }
function Err  ($m) { [Console]::Error.WriteLine($m) }   # stderr, so `> file` captures only Write-Output
function Usage {
  # print the banner-delimited header block (opening '# ===' line through the closing one)
  $lines = Get-Content $PSCommandPath
  $marks = @(); for ($j = 0; $j -lt $lines.Count; $j++) { if ($lines[$j] -match '^# ={3,}') { $marks += $j } }
  $lines[$marks[0]..$marks[1]] | ForEach-Object { $_ -replace '^# ?','' }
  exit 0
}

function Have-Cmd ($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }

# ---- profile auto-detect + uninstall (used by --profile auto, the wizard, --uninstall) -----
function Test-Has ([string]$dir, [string[]]$globs) {  # $true if any glob matches an entry in $dir
  foreach ($g in $globs) {
    if (Get-ChildItem -Path $dir -Filter $g -Force -ErrorAction SilentlyContinue | Select-Object -First 1) { return $true }
  }
  return $false
}
function Detect-Profile ([string]$dir) {  # best-guess profile name from the files present (first strong signal wins)
  if (Test-Has $dir @('go.mod','package.json','tsconfig.json','Cargo.toml','pyproject.toml','requirements.txt','pom.xml','build.gradle*','*.csproj','Gemfile','composer.json')) { return 'software-dev' }
  if ((Test-Has $dir @('Dockerfile','docker-compose.y*ml','*.tf','ansible.cfg','Vagrantfile')) -or (Test-Path (Join-Path $dir 'ansible') -PathType Container) -or (Test-Path (Join-Path $dir 'terraform') -PathType Container) -or (Test-Path (Join-Path $dir 'k8s') -PathType Container)) { return 'devops-setup' }
  if ((Test-Has $dir @('*.ipynb','*.csv','*.parquet')) -or (Test-Path (Join-Path $dir 'notebooks') -PathType Container)) { return 'data-crunching' }
  if ((Test-Has $dir @('mkdocs.yml','docusaurus.config.*','_config.yml','*.tex')) -or ((Test-Path (Join-Path $dir 'docs') -PathType Container) -and (Test-Has (Join-Path $dir 'docs') @('*.md')))) { return 'document-creation' }
  return 'general-admin'
}
function Uninstall-From ([string]$path) {  # back up, strip the managed block; delete file if nothing else remains
  $marks = Find-ManagedMarks $path
  if (-not $marks) { return }
  $leaf = Split-Path $path -Leaf
  $bak = Backup-File $path
  $content = Get-Content $path -Raw
  $pat = [regex]::Escape($marks.Begin) + '[\s\S]*?' + [regex]::Escape($marks.End)
  $new = [regex]::Replace($content, $pat, '', 'Singleline')
  if ($new -match '\S') {
    Set-Content -Path $path -Value $new -Encoding utf8 -NoNewline
    Ok "removed the harness section from $leaf (backup: $(Split-Path $bak -Leaf))"
  } else {
    Remove-Item $path -Force
    Ok "removed $leaf — it only held the harness section (backup: $(Split-Path $bak -Leaf))"
  }
}

# ---- arg parse (mirrors setup.sh's --flag UX exactly) ----------------------
for ($i = 0; $i -lt $args.Count; $i++) {
  switch ($args[$i]) {
    '--profile'           { $o.Profiles = $args[++$i] }
    '--target'            { $o.Target = $args[++$i] }
    '--operator-name'     { $o.OperatorName = $args[++$i] }
    '--operator-role'     { $o.OperatorRole = $args[++$i] }
    '--operator-bio'      { $o.OperatorBio = $args[++$i] }
    '--tracker'           { $o.Tracker = $args[++$i] }
    '--tracker-writes'    { $o.TrackerWrites = $args[++$i]
                            if ($o.TrackerWrites -notin @('ask','allowed')) {
                              Die "--tracker-writes must be 'ask' (default: agent drafts, you post) or 'allowed' (agent may write to the tracker itself); got '$($o.TrackerWrites)'"
                            } }
    '--global'            { $o.Global = $true }
    '--profile-only'      { $o.ProfileOnly = $true }
    '--with-plugins'      { $o.WithPlugins = $args[++$i] }
    '--with-mcp'          { $o.WithMcp = $args[++$i] }
    '--with-skills'       { $o.WithSkills = $true }
    '--with-hooks'        { $o.WithHooks = $true }
    '--with-handoff-hooks'{ $o.WithHandoffHooks = $true }
    '--update-plugins'    { $o.UpdatePlugins = $true }
    '--doctor'            { $o.Doctor = $true }
    '--export-instructions'{ $o.Export = $true }
    '--org-policy'        { $o.OrgPolicy = $true }
    '--assemble-only'     { $o.AssembleOnly = $true }
    '--also-agents-md'    { $o.AlsoAgents = $true }
    '--also-gemini-md'    { $o.AlsoGemini = $true }
    '--force'             { $o.Force = $true }
    '--dry-run'           { $o.DryRun = $true }
    '--wizard'            { $o.Wizard = $true }
    '--self-update'       { $o.SelfUpdate = $true }
    '--from'              { $o.SelfUpdateRemote = $args[++$i] }
    '--no-reassemble'     { $o.NoReassemble = $true }
    '--uninstall'         { $o.Uninstall = $true }
    '--safety'            { $o.Safety = $args[++$i] }
    '--help'              { Usage }
    '-h'                  { Usage }
    default               { Die "Unknown option: $($args[$i]) (try --help)" }
  }
}

if ($o.Safety -notin @('cautious','trusted')) { Die "--safety must be 'cautious' or 'trusted' (got: '$($o.Safety)')" }

# Resolve --profile auto by inspecting the target project (before validation).
if ($o.Profiles -eq 'auto') {
  $autodir = if ($o.Target) { $o.Target } else { (Get-Location).Path }
  $o.Profiles = Detect-Profile $autodir
  Say "auto-detected profile: $($o.Profiles)  (from the files in $autodir)"
}

# profile list -> array, validate
$ProfileArr = @()
if ($o.Profiles) {
  $ProfileArr = @($o.Profiles.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
  foreach ($p in $ProfileArr) {
    if (-not (Test-Path (Join-Path $HarnessDir "profiles/$p.md"))) {
      $avail = (Get-ChildItem (Join-Path $HarnessDir 'profiles') -Filter *.md | ForEach-Object { $_.BaseName }) -join ' '
      Die "No such profile: '$p'. Available: $avail"
    }
  }
}

# ---- core assembly ---------------------------------------------------------
function Assemble-Block ([bool]$IncludeCore) {
  $parts = @()
  $parts += $BeginMark
  $pf = if ($o.Profiles) { $o.Profiles } else { 'none' }
  $coreStr = $IncludeCore.ToString().ToLower()
  $parts += "<!-- Generated. Profiles: $pf. core=$coreStr. Edit core/ or profiles/, then re-run setup. -->"
  $parts += ''
  if ($IncludeCore) {
    Get-ChildItem (Join-Path $HarnessDir 'core') -Filter *.md | Sort-Object Name | ForEach-Object {
      $parts += ((Get-Content $_.FullName -Raw).TrimEnd("`r","`n")); $parts += ''; $parts += ''
    }
  }
  if ($ProfileArr.Count -gt 0) {
    $parts += '---'; $parts += ''
    $parts += "# Work-Type Profile(s): $($o.Profiles)"; $parts += ''
    foreach ($p in $ProfileArr) {
      $parts += ((Get-Content (Join-Path $HarnessDir "profiles/$p.md") -Raw).TrimEnd("`r","`n")); $parts += ''; $parts += ''
    }
  }
  $parts += $EndMark
  return ($parts -join "`n")
}

function Fill-Placeholders ([string]$text) {
  $text = $text.Replace('{{OPERATOR_NAME}}', $o.OperatorName)
  $text = $text.Replace('{{OPERATOR_ROLE}}', $o.OperatorRole)
  $text = $text.Replace('{{OPERATOR_BIO}}',  $o.OperatorBio)
  $text = $text.Replace('{{TRACKER}}',       $o.Tracker)
  $policy = if ($o.TrackerWrites -eq 'allowed') { $o.TrackerPolicyAllowed } else { $o.TrackerPolicyAsk }
  $text = $text.Replace('{{TRACKER_POLICY}}', $policy)
  return [regex]::Replace($text, '\{\{([A-Z_]+)\}\}', { param($m) "[TODO: set $($m.Groups[1].Value)]" })
}

# Name the placeholders the human still has to fill, instead of hoping they skim for them.
# Deliberately generic (any {{TOKEN}} with no flag renders as "[TODO: set TOKEN]"). Mirrors
# setup.sh's report_todos.
function Report-Todos ([string]$file) {
  if (-not (Test-Path $file)) { return }
  $todos = @([regex]::Matches((Get-Content $file -Raw), '\[TODO: set ([A-Z_]+)\]') |
             ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
  if (-not $todos) { return }
  Write-Host ''
  Warn "$(Split-Path $file -Leaf) is missing $($todos.Count) value(s) only you can give: $($todos -join ' ')"
  Write-Host '      They render as [TODO: set ...] inside the rules, so the assistant will ask you for them'
  Write-Host "      (or guess). Fill them in: $file"
}

function Backup-File ([string]$path) {  # if it exists, save a timestamped copy beside it; return the backup path
  if (-not (Test-Path $path)) { return $null }
  $bak = "$path.bak.$(Get-Date -Format 'yyyyMMdd-HHmmss')"
  Copy-Item $path $bak -Force
  return $bak
}

function Write-Managed ([string]$dest, [string]$content) {
  $leaf = Split-Path $dest -Leaf
  $marks = Find-ManagedMarks $dest
  if ($marks) {
    # Existing harness install: replace ONLY our managed block (old or new markers) — your
    # other edits are left alone. The block, markers included, is swapped for the new one.
    $existing = Get-Content $dest -Raw
    $pat = [regex]::Escape($marks.Begin) + '[\s\S]*?' + [regex]::Escape($marks.End)
    $new = [regex]::Replace($existing, $pat, { param($m) $content }, 'Singleline')
    Set-Content -Path $dest -Value $new -Encoding utf8 -NoNewline
    Ok "updated the harness section in $leaf (your other content left untouched)"
    if ($marks.Begin -ne $BeginMark) { Ok 'migrated the section markers to the Agentsmith brand' }
  } elseif ((Test-Path $dest) -and (-not $o.Force)) {
    # You already have your own file with no harness section: back it up, then add ours at the end.
    $bak = Backup-File $dest
    Add-Content -Path $dest -Value ("`n" + $content) -Encoding utf8
    Ok "added the harness section to your existing $leaf"
    if ($bak) { Ok "backup of the original saved: $(Split-Path $bak -Leaf)" }
  } else {
    # New file, or --force replacing a file that has no harness section.
    if (Test-Path $dest) {
      $bak = Backup-File $dest
      Warn "--force replaced the ENTIRE $leaf — original backed up to $(Split-Path $bak -Leaf)"
    }
    Set-Content -Path $dest -Value $content -Encoding utf8
    Ok "wrote $leaf"
  }
}

function Assemble-To ([string]$dest, [bool]$IncludeCore) {
  $content = Fill-Placeholders (Assemble-Block $IncludeCore)
  if ($o.DryRun) {
    $n = ($content -split "`n").Count
    $pf = if ($o.Profiles) { $o.Profiles } else { 'none' }
    Say "DRY RUN — $(Split-Path $dest -Leaf) would be $n lines (core=$IncludeCore, profiles=$pf)"
    ($content -split "`n" | Select-Object -First 30) -join "`n" | Write-Output
    return
  }
  New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
  Write-Managed $dest $content
}

# ---- plugins ---------------------------------------------------------------
function Install-Marketplace ($m) {
  if (Have-Cmd claude) { try { claude plugin marketplace add $m *> $null; Ok "marketplace $m" } catch { Warn "add later: /plugin marketplace add $m" } }
  else { Warn "add later: /plugin marketplace add $m" }
}
function Install-Plugin ($spec) {
  if (Have-Cmd claude) { try { claude plugin install $spec *> $null; Ok "plugin $spec" } catch { Warn "install later: /plugin install $spec" } }
  else { Warn "install later: /plugin install $spec" }
}

# recursive object merge mirroring jq '.[0] * .[1]' (objects merge, scalars/arrays replace)
function Merge-Json ([hashtable]$base, [hashtable]$over) {
  foreach ($k in @($over.Keys)) {
    if ($base.ContainsKey($k) -and ($base[$k] -is [hashtable]) -and ($over[$k] -is [hashtable])) {
      Merge-Json $base[$k] $over[$k] | Out-Null
    } else { $base[$k] = $over[$k] }
  }
  return $base
}

function Install-Skills ([string]$Dest = $SkillsDest) {  # default global; project mode passes <project>/.claude/skills
  New-Item -ItemType Directory -Force -Path $Dest | Out-Null
  $n = 0
  foreach ($sk in (Get-ChildItem (Join-Path $HarnessDir 'skills') -Directory)) {
    if (-not (Test-Path (Join-Path $sk.FullName 'SKILL.md'))) { continue }
    $d = Join-Path $Dest $sk.Name
    if ((Test-Path $d) -and (-not $o.Force)) { Warn "skill '$($sk.Name)' exists — skipped (use --force)"; continue }
    Copy-Item $sk.FullName $d -Recurse -Force; Ok "skill $($sk.Name)"; $n++
  }
  Ok "skills installed: $n (into $Dest)"
}

# Get-Recommendation <profile> — parse the "<!-- MAP <profile> | packs: ... | skills: ... -->" line
# from skills/RECOMMENDED.md (single source of truth). Returns @{Packs=..; Skills=..}: '-' = none,
# '' = the profile isn't mapped (wizard falls back to generic prompts).
function Get-Recommendation ([string]$Profile) {
  $r = @{ Packs = ''; Skills = '' }
  $prof = ($Profile -split ',')[0]
  $f = Join-Path $HarnessDir 'skills/RECOMMENDED.md'
  if (-not $prof -or -not (Test-Path $f)) { return $r }
  $line = (Select-String -Path $f -Pattern "MAP\s+$([regex]::Escape($prof))\s*\|" | Select-Object -First 1)
  if (-not $line) { return $r }
  $t = $line.Line
  if ($t -match 'packs:\s*([^|]*)\|')  { $r.Packs  = $Matches[1].Trim() }
  if ($t -match 'skills:\s*(.*?)-->')  { $r.Skills = $Matches[1].Trim() }
  return $r
}

function Install-GlobalConfig {
  Say "Installing global config into $CcDir"
  New-Item -ItemType Directory -Force -Path $CcDir | Out-Null
  $statusDest = Join-Path $CcDir 'statusline-command.sh'
  if (-not (Test-Path $statusDest)) {
    Copy-Item (Join-Path $HarnessDir 'config/statusline-command.sh') $statusDest -Force; Ok "statusline installed"
    if ($IsWindows) { Warn "the statusline is a bash script — on native Windows it needs a POSIX shell (Git Bash/WSL) on PATH" }
  }
  $settingsDest = Join-Path $CcDir 'settings.json'
  $settingsSrc  = Join-Path $HarnessDir 'config/settings.json'
  if (Test-Path $settingsDest) {
    Copy-Item $settingsDest "$settingsDest.bak.$PID" -Force
    try {
      $base = Get-Content $settingsDest -Raw | ConvertFrom-Json -AsHashtable
      $over = Get-Content $settingsSrc  -Raw | ConvertFrom-Json -AsHashtable
      (Merge-Json $base $over) | ConvertTo-Json -Depth 100 | Set-Content $settingsDest -Encoding utf8
      Ok "merged settings.json (backup: settings.json.bak.$PID)"
    } catch { Warn "could not merge settings.json — left as-is; merge config/settings.json by hand (INSTALL.md)" }
  } else {
    Copy-Item $settingsSrc $settingsDest -Force; Ok "wrote settings.json"
  }
  # Cautious safety: don't leave the dangerous-mode confirmation silently disabled globally.
  # (config/settings.json ships skipDangerousModePermissionPrompt=true for the trusted box.)
  if (($o.Safety -eq 'cautious') -and (Test-Path $settingsDest)) {
    try {
      $s = Get-Content $settingsDest -Raw | ConvertFrom-Json -AsHashtable
      $s['skipDangerousModePermissionPrompt'] = $false
      $s | ConvertTo-Json -Depth 100 | Set-Content $settingsDest -Encoding utf8
      Ok "cautious: kept the dangerous-mode confirmation ON (skipDangerousModePermissionPrompt=false)"
    } catch { Warn "cautious: could not set skipDangerousModePermissionPrompt=false — do it by hand in ~/.claude/settings.json" }
  }
  Install-Marketplace 'thedotmack/claude-mem'
  Install-Marketplace 'openai/codex-plugin-cc'
  foreach ($spec in @('superpowers@claude-plugins-official','code-review@claude-plugins-official','claude-mem@thedotmack','codex@openai-codex')) { Install-Plugin $spec }
  if ((-not $o.WithPlugins) -and (-not [Console]::IsInputRedirected) -and ($env:WIZARD_RUN -ne '1')) {
    $o.WithPlugins = Read-Host '  Optional plugin packs? Enter any of: dev-workflow stack-lsp (space-separated, blank=none)'
  }
  if ($o.WithPlugins -match 'dev-workflow') {
    Say "Plugin pack: dev-workflow (latest from source)"
    Install-Marketplace 'shinpr/claude-code-workflows'
    foreach ($spec in @('dev-workflows@claude-code-workflows','dev-workflows-frontend@claude-code-workflows','feature-dev@claude-plugins-official','frontend-design@claude-plugins-official','qodo-skills@claude-plugins-official')) { Install-Plugin $spec }
  }
  if ($o.WithPlugins -match 'stack-lsp') {
    Say "Plugin pack: stack-lsp (example: Go + web — swap LSPs for your languages)"
    Install-Marketplace 'gopherguides/gopher-ai'
    Install-Marketplace 'Piebald-AI/claude-code-lsps'
    foreach ($spec in @('go-dev@gopher-ai','tailwind@gopher-ai','gopls@claude-code-lsps','typescript-lsp@claude-plugins-official','gopls-lsp@claude-plugins-official')) { Install-Plugin $spec }
  }
  if ($o.WithSkills) { Install-Skills $SkillsDest }
  if ($o.WithHandoffHooks) { Install-HandoffHooks }
}

function Build-VerifyConf ([string]$dest) {
  $lines = @()
  $lines += "# .harness/verify.conf — generated for profile(s): $($o.Profiles)"
  $lines += '# One phase per line:  Label :: shell command. Runs in order; first failure stops the run.'
  $lines += '# This is YOUR definition of "shippable". Uncomment + edit the phases that fit this project,'
  $lines += '# then DELETE the sanity line below once at least one real phase is active.'
  $lines += ''
  foreach ($p in $ProfileArr) {
    $preset = Join-Path $HarnessDir "config/verify-presets/$p.conf"
    if (Test-Path $preset) { $lines += (Get-Content $preset); $lines += '' }
  }
  $lines += '# Universal placeholder so verify.sh runs green until you wire real phases — REPLACE THIS:'
  $lines += "sanity :: echo `"verify.sh wired for: $($o.Profiles) — replace this phase with real checks`""
  Set-Content -Path $dest -Value ($lines -join "`n") -Encoding utf8
}

function Add-McpServers ([string]$names) {
  $src = Join-Path $HarnessDir 'config/mcp.example.json'
  $dest = Join-Path $o.Target '.mcp.json'
  if (-not (Test-Path $dest)) { '{ "mcpServers": {} }' | Set-Content $dest -Encoding utf8 }
  $srcObj  = Get-Content $src  -Raw | ConvertFrom-Json -AsHashtable
  $destObj = Get-Content $dest -Raw | ConvertFrom-Json -AsHashtable
  if (-not $destObj.ContainsKey('mcpServers')) { $destObj['mcpServers'] = @{} }
  $have = ($srcObj['mcpServers'].Keys) -join ', '
  $added = 0
  foreach ($n in ($names.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
    if (-not $srcObj['mcpServers'].ContainsKey($n)) { Warn "no MCP server '$n' in mcp.example.json (available: $have)"; continue }
    $block = $srcObj['mcpServers'][$n]
    if ($block -is [hashtable] -and $block.ContainsKey('_use')) { $block.Remove('_use') }
    $destObj['mcpServers'][$n] = $block; Ok "MCP server '$n' → .mcp.json"; $added++
  }
  if ($added -gt 0) {
    $destObj | ConvertTo-Json -Depth 100 | Set-Content $dest -Encoding utf8
    Ok ".mcp.json now serves: $((Get-Content $dest -Raw | ConvertFrom-Json -AsHashtable)['mcpServers'].Keys -join ', ')"
  }
}

function Export-Instructions {
  if (-not $o.Profiles) { Die "Pick a profile to export: --profile <name[,name]> --export-instructions" }
  $parts = @()
  $parts += '<!-- Agentsmith — universal agent harness — portable instructions (core + ' + $o.Profiles + '). -->'
  $parts += '<!-- Paste this WHOLE block into a surface that has no on-disk CLAUDE.md: a claude.ai -->'
  $parts += "<!-- Project's custom-instructions box, Claude Cowork, or any assistant's system-prompt -->"
  $parts += '<!-- field. On-disk Claude Code should run setup for a real CLAUDE.md instead. To -->'
  $parts += "<!-- change this, edit core/ or profiles/ and re-export — don't hand-edit the paste. -->"
  $parts += ''
  Get-ChildItem (Join-Path $HarnessDir 'core') -Filter *.md | Sort-Object Name | ForEach-Object {
    $parts += ((Get-Content $_.FullName -Raw).TrimEnd("`r","`n")); $parts += ''; $parts += ''
  }
  $parts += '---'; $parts += ''
  $parts += "# Work-Type Profile(s): $($o.Profiles)"; $parts += ''
  foreach ($p in $ProfileArr) { $parts += ((Get-Content (Join-Path $HarnessDir "profiles/$p.md") -Raw).TrimEnd("`r","`n")); $parts += ''; $parts += '' }
  $text = Fill-Placeholders ($parts -join "`n")
  $text | Write-Output
  $n = ($text -split "`n").Count
  Err "» Exported portable instructions ($n lines) to stdout."
  Err "  Save:   ./setup.ps1 --profile $($o.Profiles) --export-instructions > harness-instructions.md"
  Err "  Copy:   ./setup.ps1 --profile $($o.Profiles) --export-instructions | Set-Clipboard"
  Err "  Then paste into the project's custom-instructions / system-prompt box."
}

function OrgPolicy-Install {
  if ($IsWindows)        { $orgDir = 'C:\Program Files\ClaudeCode' }
  elseif ($IsMacOS)      { $orgDir = '/Library/Application Support/ClaudeCode' }
  else                   { $orgDir = '/etc/claude-code' }
  if ($env:HARNESS_ORG_DIR) { $orgDir = $env:HARNESS_ORG_DIR }
  $orgMd = Join-Path $orgDir 'CLAUDE.md'
  $orgSettings = Join-Path $orgDir 'managed-settings.json'
  $hardened = Join-Path $HarnessDir 'config/managed-settings.hardened.json'

  Say "Org-policy install — applies to EVERY user + project on this machine"
  Write-Host "  managed CLAUDE.md : $orgMd   (loads before user/project CLAUDE.md, cannot be excluded)"
  Write-Host "  managed settings  : $orgSettings   (highest precedence; CLI/user/project cannot override)"
  Write-Host "  hardening         : disableBypassPermissionsMode + disableAutoMode  (no dangerous/auto mode)"
  if ($o.Profiles) { Write-Host "  profile(s) baked in: $($o.Profiles)" } else { Write-Host "  content: universal core only (add --profile to bake one in)" }

  if ($o.DryRun) { Say "DRY RUN — nothing written."; return }

  try { New-Item -ItemType Directory -Force -Path $orgDir | Out-Null }
  catch { Die "cannot write $orgDir — managed config needs admin. Re-run elevated: setup.ps1 --org-policy$(if($o.Profiles){" --profile $($o.Profiles)"})" }

  Assemble-To $orgMd $true

  if (Test-Path $orgSettings) {
    Copy-Item $orgSettings "$orgSettings.bak.$PID" -Force
    try {
      $base = Get-Content $orgSettings -Raw | ConvertFrom-Json -AsHashtable
      $over = Get-Content $hardened    -Raw | ConvertFrom-Json -AsHashtable
      (Merge-Json $base $over) | ConvertTo-Json -Depth 100 | Set-Content $orgSettings -Encoding utf8
      Ok "merged hardening into existing managed-settings.json (backup: .bak.$PID)"
    } catch { Warn "could not merge — left existing managed-settings.json as-is; apply $hardened by hand" }
  } else {
    Copy-Item $hardened $orgSettings -Force; Ok "wrote hardened managed-settings.json"
  }
  Write-Host ''; Say "Org policy in force."
  Write-Host "  Verify on this box:  claude  (then /status — bypass/dangerous mode should be unavailable)"
  Write-Host "  Admins: extend $orgSettings with org allow/deny rules as needed."
}

function Install-HandoffHooks {
  $hooksDir = Join-Path $CcDir 'hooks'
  New-Item -ItemType Directory -Force -Path $hooksDir | Out-Null
  Copy-Item (Join-Path $HarnessDir 'hooks/handoff-on-keyword.sh')   (Join-Path $hooksDir 'handoff-on-keyword.sh')   -Force
  Copy-Item (Join-Path $HarnessDir 'hooks/context-budget-nudge.sh') (Join-Path $hooksDir 'context-budget-nudge.sh') -Force
  Ok "handoff hook scripts → $hooksDir"
  Copy-Item (Join-Path $HarnessDir 'config/statusline-command.sh') (Join-Path $CcDir 'statusline-command.sh') -Force
  $settings = Join-Path $CcDir 'settings.json'
  if (-not (Test-Path $settings)) { '{}' | Set-Content $settings -Encoding utf8 }
  $kw = 'bash ~/.claude/hooks/handoff-on-keyword.sh'
  $st = 'bash ~/.claude/hooks/context-budget-nudge.sh'
  if (Select-String -Path $settings -SimpleMatch $kw -Quiet) { Ok "handoff hooks already wired in settings.json" }
  else {
    Copy-Item $settings "$settings.bak.$PID" -Force
    try {
      $s = Get-Content $settings -Raw | ConvertFrom-Json -AsHashtable
      if (-not $s.ContainsKey('statusLine')) { $s['statusLine'] = @{ type = 'command'; command = 'bash ~/.claude/statusline-command.sh' } }
      if (-not $s.ContainsKey('hooks')) { $s['hooks'] = @{} }
      foreach ($evt in @('UserPromptSubmit','Stop')) { if (-not $s['hooks'].ContainsKey($evt)) { $s['hooks'][$evt] = @() } }
      $s['hooks']['UserPromptSubmit'] = @($s['hooks']['UserPromptSubmit']) + @(@{ hooks = @(@{ type = 'command'; command = $kw }) })
      $s['hooks']['Stop']             = @($s['hooks']['Stop'])             + @(@{ hooks = @(@{ type = 'command'; command = $st }) })
      $s | ConvertTo-Json -Depth 100 | Set-Content $settings -Encoding utf8
      Ok "wired handoff hooks into settings.json (backup .bak.$PID)"
    } catch { Warn "merge failed — add the snippet from hooks/README.md by hand" }
  }
  Write-Host ''; Say "Handoff hooks installed."
  Write-Host "  • 'handoff' / 'wrap up' in a prompt → injects the safe-state + recall-prompt protocol (reliable)"
  Write-Host "  • context ≥ threshold used → one best-effort nudge (fragile — see hooks/README.md)"
}

# ============================================================================
#  WIZARD
# ============================================================================
function Wiz-Ask ([string]$prompt, [string]$def) {
  $suffix = if ($def) { " [$def]" } else { '' }
  $ans = Read-Host "  $prompt$suffix"
  if ([string]::IsNullOrEmpty($ans)) { return $def } else { return $ans }
}
function Wiz-Yn ([string]$prompt, [string]$def='n') {
  $hint = if ($def -match '^[Yy]') { 'Y/n' } else { 'y/N' }
  $ans = Read-Host "  $prompt [$hint]"
  if ([string]::IsNullOrEmpty($ans)) { $ans = $def }
  return ($ans -match '^[Yy]')
}
function Wiz-MultiSelect ([bool]$allowEmpty, [string[]]$items) {
  for ($k = 0; $k -lt $items.Count; $k++) { Write-Host ("    {0}) {1}" -f ($k + 1), $items[$k]) }
  while ($true) {
    $extra = if ($allowEmpty) { ', blank = none' } else { '' }
    $sel = Read-Host "  Numbers (space-separated$extra)"
    if ([string]::IsNullOrWhiteSpace($sel)) { if ($allowEmpty) { return @() } else { Write-Host '  ! pick at least one'; continue } }
    $picks = @(); $okFlag = $true
    foreach ($tok in ($sel -split '\s+' | Where-Object { $_ })) {
      if ($tok -match '^\d+$' -and [int]$tok -ge 1 -and [int]$tok -le $items.Count) { $picks += $items[[int]$tok - 1] } else { $okFlag = $false }
    }
    if ($okFlag) { return $picks } else { Write-Host "  ! use numbers 1-$($items.Count)" }
  }
}
function Wiz-ShowCmd ([bool]$sudo, [string[]]$a) {
  $prefix = if ($sudo) { '    sudo ./setup.ps1' } else { '    ./setup.ps1' }
  $sb = $prefix
  foreach ($x in $a) { if ($x -like '--*') { $sb += " $x" } elseif ($x -match '[\s]') { $sb += " `"$x`"" } else { $sb += " $x" } }
  Write-Host $sb
}

function Wiz-Note ($m) { Write-Host "      $m" -ForegroundColor DarkGray }   # dim, indented plain-English explanation

# Two-tone banner: gold wordmark + coach/rig, white horse, green MODEL, cyan "what the harness is".
# Split each horse/coach line so left (horse) and right (coach) get different colors. Write-Host
# uses the console colour API (no ANSI), so redirected output stays clean.
function Banner {
  $art = @'
      _   ___ ___ _  _ _____ ___ __  __ ___ _____ _  _
     /_\ / __| __| \| |_   _/ __|  \/  |_ _|_   _| || |
    / _ \ (_ | _|| .` | | | \__ \ |\/| || |  | | | __ |
   /_/ \_\___|___|_|\_| |_| |___/_|  |_|___| |_| |_||_|

          ,'|                          ________________
         /   \__                      /_|______________|_\
        ( o     \____________________|    []   []   []   |
         \_      \                   |    AGENTSMITH     |
         / \      \__________________|    the HARNESS    |
        /   |  |\                     \____(O)______(O)__/
       ""  "" ""                        rules . tools . memory . guardrails
         MODEL
'@
  $lines = ($art -replace "`r", '') -split "`n"
  for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    if ($i -le 3) { Write-Host $line -ForegroundColor Yellow }
    elseif ($i -eq 4 -or $line.Length -eq 0) { Write-Host '' }
    elseif ($i -eq 12) { Write-Host $line -ForegroundColor Green }
    else {
      $rc = if ($i -eq 11) { 'Cyan' } else { 'Yellow' }
      $l = if ($line.Length -ge 16) { $line.Substring(0, 16) } else { $line }
      $r = if ($line.Length -ge 16) { $line.Substring(16) } else { '' }
      Write-Host $l -NoNewline -ForegroundColor White
      Write-Host $r -ForegroundColor $rc
    }
  }
}

# Git is a soft prerequisite (guardrail hooks, branching, --self-update all use it). For the
# non-technical operator: explain it plainly and offer to install it, rather than failing later.
function Check-Git {
  if (Have-Cmd git) { return }
  Write-Host ''
  Warn "Git isn't installed — and Agentsmith leans on it for its safety net."
  Wiz-Note 'Git is a free tool that records changes to your files. The harness uses it so you can'
  Wiz-Note 'undo mistakes, and so the guardrails (block a committed password, protect your main'
  Wiz-Note 'branch) can work. You can finish setup without it, but installing it is recommended.'
  Write-Host ''
  if (Have-Cmd winget) {
    Say 'To install git, run:'
    Write-Host '      winget install --id Git.Git -e --source winget'
    if (Wiz-Yn 'Want me to run that for you now?' 'n') {
      try { & winget install --id Git.Git -e --source winget; Ok 'git installed (you may need to reopen the terminal).' }
      catch { Warn "that didn't finish — run the command above yourself, then re-run setup." }
    } else {
      Wiz-Note 'Prefer to do it yourself? Run the line above (or see https://git-scm.com/download/win), then re-run.'
    }
  } else {
    Say 'Install git from:  https://git-scm.com/download/win'
    Wiz-Note 'Run the installer (accept the defaults), then re-run this wizard.'
  }
  Write-Host ''
}

function Run-Wizard {
  Banner
  Write-Host '  Welcome! This wizard sets up Agentsmith — the "house rules" that make your AI coding'
  Write-Host '  assistant (Claude Code) work in a consistent, careful way on your projects.'
  Write-Host "  I'll ask a few short questions, explain each in plain language, show you the exact"
  Write-Host '  command, and change NOTHING until you say yes. Any file I touch is backed up first.'
  Write-Host ''
  Check-Git
  Write-Host '  What would you like to set up?'
  Write-Host '    1) This project        — put the rules in ONE project folder you choose (most common)'
  Write-Host '    2) Everything (global) — one set of rules for every project on this computer'
  Write-Host '    3) Whole machine       — rules for all accounts on a shared computer (needs admin)'
  Write-Host '    4) Just give me text   — a paste-ready block for claude.ai / Cowork (writes no files)'
  Wiz-Note "Not sure? Pick 1 — it's self-contained and the easiest to undo."
  $mc = ''
  while ($mc -notmatch '^[1-4]$') { $mc = Read-Host '  Choose [1-4]'; if ([string]::IsNullOrEmpty($mc)) { Die 'wizard aborted (no input)' } }

  $availProfiles = @(Get-ChildItem (Join-Path $HarnessDir 'profiles') -Filter *.md | Sort-Object Name | ForEach-Object { $_.BaseName })
  $availMcp = @((Get-Content (Join-Path $HarnessDir 'config/mcp.example.json') -Raw | ConvertFrom-Json -AsHashtable)['mcpServers'].Keys | Sort-Object)
  $A = @()
  $wizSkills = 'n'   # init for StrictMode; set to 'y' if the project-mode skill pack is chosen

  switch ($mc) {
    '1' {
      Write-Host ''
      Wiz-Note 'The folder of the project you want the assistant to follow these rules in.'
      $tgt = Wiz-Ask 'Target project directory' (Get-Location).Path
      # validate now, not at the end: a typo'd path shouldn't waste the whole flow
      while (-not (Test-Path $tgt -PathType Container)) {
        if (Wiz-Yn "Directory does not exist: $tgt — create it?" 'y') {
          try { New-Item -ItemType Directory -Force -Path $tgt | Out-Null; Ok "created $tgt"; break } catch { Warn "could not create $tgt — try another path." }
        }
        $tgt = Wiz-Ask 'Target project directory' (Get-Location).Path
      }
      Write-Host ''; Write-Host '  Pick the work-type profile(s):'
      Wiz-Note "A 'profile' tailors the rules to the kind of work — writing code, server setup,"
      Wiz-Note 'writing documents, research, and so on. Pick the closest one (a few is fine).'
      Wiz-Note "tip: this folder looks like a '$(Detect-Profile $tgt)' project."
      $picks = @(Wiz-MultiSelect $false $availProfiles)
      $A += '--profile'; $A += ($picks -join ','); $A += '--target'; $A += $tgt
      $rec = Get-Recommendation ($picks -join ',')   # drives pack defaults + guidance from skills/RECOMMENDED.md
      if ($rec.Packs -or $rec.Skills) {
        Write-Host ''; Say "Recommended for '$($picks[0])':"
        if ($rec.Packs  -and $rec.Packs  -ne '-') { Wiz-Note "• plugin packs: $($rec.Packs)  (I'll pre-select these below)" }
        if ($rec.Skills -and $rec.Skills -ne '-') { Wiz-Note "• skills to add via plugins: $($rec.Skills)" }
        Wiz-Note "• the bundled harness skill pack (/handoff, /verify, /harness-help + 3 more)"
      }
      $poDefault = 'n'
      $globalMd = Join-Path $CcDir 'CLAUDE.md'
      if (Find-ManagedMarks $globalMd) { $poDefault = 'y'; Write-Host ''; Ok "Universal core already installed globally ($globalMd)." }
      Write-Host ''
      Wiz-Note "'Thin' = this project keeps only its profile; the shared core rules live in your"
      Wiz-Note 'global file and load automatically. Recommended once the core is global.'
      if (Wiz-Yn 'Keep the project CLAUDE.md thin (profile only; core stays global)?' $poDefault) { $A += '--profile-only' }
      Write-Host ''
      Wiz-Note 'How careful should the assistant be about running things?'
      Wiz-Note 'Cautious = auto-apply file edits, but ASK before shell commands / network (recommended).'
      Wiz-Note 'Trusted  = run almost everything without asking (only on a computer you fully own).'
      if (Wiz-Yn 'Use cautious mode (ask before shell/network)?' 'y') { $A += '--safety'; $A += 'cautious'; $wizSafety = 'cautious' }
      else { $A += '--safety'; $A += 'trusted'; $wizSafety = 'trusted' }
      Write-Host ''; Write-Host '  Your details (optional — these just personalise the rules):'
      Wiz-Note 'Lets the assistant address you correctly. Leave any blank for sensible defaults.'
      $nm = Wiz-Ask 'Your name' '';                                        if ($nm) { $A += '--operator-name'; $A += $nm }
      $rl = Wiz-Ask "Your role (e.g. 'sysadmin / GTM')" '';                if ($rl) { $A += '--operator-role'; $A += $rl }
      $tk = Wiz-Ask 'Where you track tasks/bugs (linear, github, or a KNOWN-ISSUES.md file)' ''
      if ($tk) {
        $A += '--tracker'; $A += $tk
        Wiz-Note 'That told it WHERE you track work — not that it may write there. By default it'
        Wiz-Note 'drafts the issue and hands it to you to post. Say yes only if it may create and'
        Wiz-Note "comment in $tk on its own. (A file inside this repo is safe to say yes to.)"
        if (Wiz-Yn "Let the assistant write to $tk unprompted?" 'n') { $A += '--tracker-writes'; $A += 'allowed' }
      }
      Write-Host ''
      Wiz-Note 'MCP servers are optional extra tools the assistant can use (a browser, a docs fetcher).'
      Wiz-Note 'Skip if unsure — you can always add them later.'
      if (Wiz-Yn "Add MCP server(s) to this project's .mcp.json?" 'n') { $m = @(Wiz-MultiSelect $true $availMcp); if ($m.Count) { $A += '--with-mcp'; $A += ($m -join ',') } }
      Write-Host ''; Write-Host "  Optional plugin packs (installed via the 'claude' CLI — needs network):"
      Wiz-Note 'Bundles of extra commands/skills. Skip if unsure.'
      Write-Host '    • dev-workflow — feature-dev, frontend-design, workflow plugins'
      Write-Host '    • stack-lsp    — language servers (example pack: Go + TypeScript)'
      $dwDef = if ($rec.Packs -match 'dev-workflow') { 'y' } else { 'n' }
      $slDef = if ($rec.Packs -match 'stack-lsp')    { 'y' } else { 'n' }
      $packs = @()
      if (Wiz-Yn 'Add the dev-workflow pack?' $dwDef) { $packs += 'dev-workflow' }
      if (Wiz-Yn 'Add the stack-lsp pack?' $slDef)    { $packs += 'stack-lsp' }
      if ($packs.Count) { $A += '--with-plugins'; $A += ($packs -join ',') }
      Write-Host ''
      Wiz-Note 'The bundled harness skill pack (/handoff, /verify, /harness-doctor, /harness-help,'
      Wiz-Note '/new-research, /new-feedback) installs into this project .claude/skills/.'
      if (Wiz-Yn 'Copy the bundled harness skill pack into this project?' 'y') { $A += '--with-skills'; $wizSkills = 'y' }
      Write-Host ''
      Wiz-Note 'Git guardrails are automatic safety checks in this project: block committing a'
      Wiz-Note 'password, block committing straight to your main branch, keep commit messages tidy.'
      if (Wiz-Yn 'Install git guardrail hooks (recommended)?' 'y') { $A += '--with-hooks' }
      Wiz-Note 'Handoff hooks help the assistant save its place before it runs low on working memory.'
      if (Wiz-Yn "Install handoff hooks globally ('handoff' keyword + best-effort context nudge)?" 'n') { $A += '--with-handoff-hooks' }
      if (Wiz-Yn 'Also write AGENTS.md (for Codex & other assistants)?' 'n') { $A += '--also-agents-md' }
      if (Wiz-Yn 'Also write GEMINI.md (for the Gemini CLI)?' 'n') { $A += '--also-gemini-md' }
    }
    '2' {
      $A += '--global'
      Write-Host ''; Wiz-Note 'Installs the shared core rules once, for every project on this computer.'
      Write-Host '  Your details (optional — blank = sensible defaults):'
      $nm = Wiz-Ask 'Your name' '';     if ($nm) { $A += '--operator-name'; $A += $nm }
      $rl = Wiz-Ask 'Your role' '';     if ($rl) { $A += '--operator-role'; $A += $rl }
      $tk = Wiz-Ask 'Issue tracker' ''
      if ($tk) {
        $A += '--tracker'; $A += $tk
        Wiz-Note 'Naming it is not permission to write to it — by default the assistant drafts and'
        Wiz-Note 'you post. This applies to every project on this computer.'
        if (Wiz-Yn "Let the assistant write to $tk unprompted?" 'n') { $A += '--tracker-writes'; $A += 'allowed' }
      }
      Write-Host ''; Write-Host "  Optional plugin packs (installed via the 'claude' CLI — needs network):"
      $packs = @()
      if (Wiz-Yn 'Add the dev-workflow pack?' 'n') { $packs += 'dev-workflow' }
      if (Wiz-Yn 'Add the stack-lsp pack?' 'n')    { $packs += 'stack-lsp' }
      if ($packs.Count) { $A += '--with-plugins'; $A += ($packs -join ',') }
      Write-Host ''
      if (Wiz-Yn 'Copy the bundled skills into ~/.claude/skills?' 'n') { $A += '--with-skills' }
      if (Wiz-Yn "Install handoff hooks ('handoff' keyword + best-effort context nudge)?" 'y') { $A += '--with-handoff-hooks' }
    }
    '3' {
      Write-Host ''; Warn 'Machine-wide policy writes managed config as admin. The wizard prints an elevated command for you to run.'
      Wiz-Note 'Use this only on a shared computer where every account should follow the same rules.'
      if (Wiz-Yn 'Bake a profile into the managed core?' 'n') { Write-Host ''; $picks = @(Wiz-MultiSelect $false $availProfiles); $A += '--profile'; $A += ($picks -join ',') }
      $A += '--org-policy'
    }
    '4' {
      Write-Host ''; Write-Host '  Pick the profile(s) to export:'
      Wiz-Note 'Prints a block of text you paste into claude.ai or Cowork. It writes no files.'
      $picks = @(Wiz-MultiSelect $false $availProfiles)
      $A += '--profile'; $A += ($picks -join ','); $A += '--export-instructions'
    }
  }

  if ($mc -eq '1' -or $mc -eq '2') { Write-Host ''; Wiz-Note 'A dry-run shows exactly what would be written, changing nothing.'; if (Wiz-Yn 'Preview only (dry-run: show what would be written, change nothing)?' 'n') { $A += '--dry-run' } }

  if ($mc -eq '1') {
    Write-Host ''; Say "Here's what I found, and what I'll do:"
    Write-Host "      • Folder:      $tgt"
    $md = Join-Path $tgt 'CLAUDE.md'
    if (-not (Test-Path $md)) {
      Write-Host "      • CLAUDE.md:   none yet → I'll create a new one"
    } elseif (Find-ManagedMarks $md) {
      Write-Host "      • CLAUDE.md:   a previous Agentsmith install → I'll update only my section (your edits stay)"
    } else {
      Write-Host "      • CLAUDE.md:   your own file (no Agentsmith section) → I'll add my section at the end,"
      Write-Host "                     after saving a timestamped backup of your original"
    }
    if ($poDefault -eq 'y') {
      Write-Host "      • Core rules:  already global → this project's file stays thin (profile only)"
    } else {
      Write-Host "      • Core rules:  not global yet → this file includes the full core"
    }
    $ws = if ($wizSafety) { $wizSafety } else { 'cautious' }
    $wsNote = if ($ws -eq 'cautious') { 'asks before shell/network' } else { 'runs without asking' }
    Write-Host "      • Safety:      $ws  ($wsNote)"
    if ($wizSkills -eq 'y') { Write-Host "      • Skills:      bundled harness pack → $(Join-Path $tgt '.claude/skills')" }
    Wiz-Note 'Backups are made before any existing file changes. Nothing is written until you confirm.'
  }

  Write-Host ''; Say 'Equivalent command (copy this to repeat the setup non-interactively):'
  Wiz-ShowCmd ($mc -eq '3') $A
  Write-Host ''

  if ($mc -eq '3') { Say "Org policy needs admin — the wizard won't elevate for you. Copy the line above and run it elevated."; return }
  if ($mc -eq '4') { if (-not (Wiz-Yn 'Print the portable instructions now?' 'y')) { Say 'Run the command above when ready.'; return } }
  else             { if (-not (Wiz-Yn 'Run it now?' 'y')) { Say 'Nothing written. Run the command above when ready.'; return } }

  Write-Host ''
  $env:WIZARD_RUN = '1'
  & $PSCommandPath @A
}

# ---- self-update -----------------------------------------------------------
# Pull the latest harness into the checkout this script lives in, then re-assemble
# the managed CLAUDE.md blocks. Remote + auth are configurable; nothing secret is
# ever written to a tracked file (Rule: no live creds in the repo).
function Resolve-SelfUpdateRemote {
  if ($o.SelfUpdateRemote) { return $o.SelfUpdateRemote }
  if ($env:HARNESS_REMOTE) { return $env:HARNESS_REMOTE }
  $rf = Join-Path $HarnessDir '.harness/remote'
  if (Test-Path $rf) {
    $r = @(Get-Content $rf | Where-Object { $_ -and ($_ -notmatch '^\s*#') } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($r.Count -gt 0) { return $r[0] }
  }
  $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
  $origin = (& git -C $HarnessDir remote get-url origin 2>$null)
  $code = $LASTEXITCODE; $ErrorActionPreference = $prev
  if ($code -eq 0 -and $origin) { return (@($origin)[0]).ToString().Trim() }
  return $null
}

# Reverse-recover the four operator fields from an already-rendered managed block,
# so re-assembly with fresh core/ doesn't regress them to [TODO]. Returns $false if
# the identity anchor line is absent.
function Recover-OperatorFields ([string]$file) {
  $lines = @(Get-Content $file)
  $idIdx = -1
  for ($k = 0; $k -lt $lines.Count; $k++) { if ($lines[$k] -match ' is the lead\. Role: ') { $idIdx = $k; break } }
  if ($idIdx -lt 0) { return $false }
  $m = [regex]::Match($lines[$idIdx], '^\*\*(.*)\*\* is the lead\. Role: \*\*(.*)\*\*\.')
  if ($m.Success) { $o.OperatorName = $m.Groups[1].Value; $o.OperatorRole = $m.Groups[2].Value }
  for ($k = $idIdx + 1; $k -lt $lines.Count; $k++) {
    if ($lines[$k] -match 'When you explain anything:') { break }
    if ($lines[$k].Trim()) { $o.OperatorBio = $lines[$k]; break }
  }
  # TRACKER anchor tracks R7's wording — it moved from "File it in **X**" to "The team's record is
  # **X**" when consent was split out (feedback 0002). Match both so a re-assembly over a
  # pre-consent CLAUDE.md recovers the tracker instead of blanking it to [TODO].
  foreach ($ln in $lines) {
    $tm = [regex]::Match($ln, "The team's record is \*\*([^*]+)\*\*")
    if (-not $tm.Success) { $tm = [regex]::Match($ln, 'File it in \*\*([^*]+)\*\*') }
    if ($tm.Success) { $o.Tracker = $tm.Groups[1].Value; break }
  }
  # Fail CLOSED: a pre-consent block has no policy sentence, and the writes it was doing were
  # inferred from a pointer, never granted — an upgrade must not carry them forward.
  $body = $lines -join "`n"
  if     ($body -match 'writes are authorized')     { $o.TrackerWrites = 'allowed' }
  elseif ($body -match 'writes are NOT authorized') { $o.TrackerWrites = 'ask' }
  else {
    $o.TrackerWrites = 'ask'
    if ($body -match 'File it in \*\*') {
      Warn "$(Split-Path $file -Leaf): pre-consent rules — tracker writes now default to 'ask' (agent drafts, you post). Re-run with --tracker-writes allowed to let it write to $($o.Tracker) itself."
    }
  }
  return $true
}

# Fill any operator field still unset with its generic default. Called LAST, after recovery and
# after explicit flags, so '' only ever means "nobody supplied this" — never "blank it".
function Apply-OperatorDefaults {
  if (-not $o.OperatorName)  { $o.OperatorName  = $o.DefaultOperatorName }
  if (-not $o.OperatorRole)  { $o.OperatorRole  = $o.DefaultOperatorRole }
  if (-not $o.OperatorBio)   { $o.OperatorBio   = $o.DefaultOperatorBio }
  if (-not $o.Tracker)       { $o.Tracker       = $o.DefaultTracker }
  if (-not $o.TrackerWrites) { $o.TrackerWrites = $o.DefaultTrackerWrites }
}

# Decide who the operator is for a file we are about to (re)write: recover what is already in it,
# let explicitly-passed flags win, then fall back to defaults. Mirrors setup.sh's
# resolve_operator_identity — feedback 0003.
function Resolve-OperatorIdentity ([string]$dest) {
  # Snapshot what came from the command line BEFORE recovery overwrites $o.
  $x = @{ Name = $o.OperatorName; Role = $o.OperatorRole; Bio = $o.OperatorBio
          Trk  = $o.Tracker;      Writes = $o.TrackerWrites }
  if ((Test-Path $dest) -and (Find-ManagedMarks $dest) -and (Recover-OperatorFields $dest)) {
    Ok "kept the operator identity already in $(Split-Path $dest -Leaf) ($($o.OperatorName) / $($o.OperatorRole)) — pass --operator-name/--operator-role to change it"
  }
  # Explicit flags beat anything recovered: you asked for it by name.
  if ($x.Name)   { $o.OperatorName  = $x.Name }
  if ($x.Role)   { $o.OperatorRole  = $x.Role }
  if ($x.Bio)    { $o.OperatorBio   = $x.Bio }
  if ($x.Trk)    { $o.Tracker       = $x.Trk }
  if ($x.Writes) { $o.TrackerWrites = $x.Writes }
  Apply-OperatorDefaults
}

function Reassemble-One ([string]$file) {
  $lines = @(Get-Content $file)
  $gen = $null
  foreach ($ln in $lines) { if ($ln -match 'Generated\. Profiles:') { $gen = $ln; break } }
  $leaf = Split-Path $file -Leaf
  if (-not $gen) { Warn "${leaf}: managed block lacks generator metadata — skipped (re-run with explicit --profile)."; return $false }
  $pm = [regex]::Match($gen, 'Profiles: ([^.]*)\.')
  $cm = [regex]::Match($gen, 'core=([A-Za-z]+)')
  $profs = if ($pm.Success) { $pm.Groups[1].Value } else { '' }
  if ($profs -eq 'none') { $profs = '' }
  $o.Profiles = $profs
  $script:ProfileArr = @()
  if ($profs) {
    $script:ProfileArr = @($profs.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    foreach ($p in $script:ProfileArr) {
      if (-not (Test-Path (Join-Path $HarnessDir "profiles/$p.md"))) { Warn "${leaf}: profile '$p' no longer ships in the updated harness — skipped."; return $false }
    }
  }
  $includeCore = $true
  if ($cm.Success -and $cm.Groups[1].Value -eq 'false') { $includeCore = $false }
  if (-not (Recover-OperatorFields $file)) { Warn "${leaf}: couldn't recover operator name/role — falling back to the generic defaults." }
  Apply-OperatorDefaults
  Assemble-To $file $includeCore
  return $true
}

function Reassemble-ManagedTargets {
  Say 'Re-assembling managed blocks from the updated harness'
  $here = if ($o.Target) { $o.Target } else { (Get-Location).Path }
  $targets = @()
  $gmd = Join-Path $CcDir 'CLAUDE.md'
  if (Test-Path $gmd) { $targets += $gmd }
  foreach ($f in @('CLAUDE.md','AGENTS.md','GEMINI.md')) { $p = Join-Path $here $f; if (Test-Path $p) { $targets += $p } }
  $seen = @{}; $n = 0
  foreach ($t in $targets) {
    $rp = (Resolve-Path $t).Path
    if ($seen.ContainsKey($rp)) { continue }
    $seen[$rp] = $true
    if (-not (Find-ManagedMarks $t)) { continue }
    if (Reassemble-One $t) { $n++ }
  }
  if ($n -gt 0) { Ok "re-assembled $n managed target(s)." }
  else { Warn "no managed targets found (looked in $CcDir and $here). Re-run setup where your CLAUDE.md lives to refresh it." }
}

function Self-Update {
  if (-not (Have-Cmd git)) { Die '--self-update needs git on PATH.' }
  $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
  try {
    & git -C $HarnessDir rev-parse --is-inside-work-tree *> $null
    if ($LASTEXITCODE -ne 0) { Die "Harness dir is not a git checkout: $HarnessDir — --self-update pulls into the checkout setup.ps1 lives in. Clone the harness as a git repo and run its setup." }

    $remote = Resolve-SelfUpdateRemote
    if (-not $remote) { Die 'No update remote configured. Provide one of: --from <url> | $env:HARNESS_REMOTE | a one-URL .harness/remote file | a git origin on the checkout.' }

    Say "Self-update — harness checkout: $HarnessDir"
    Write-Host "  remote: $remote"

    $dirty = (& git -C $HarnessDir status --porcelain)
    if ($dirty) { Die "Harness checkout has uncommitted changes — commit or stash them first (pull-in-place won't clobber local edits)." }

    $branch = (& git -C $HarnessDir rev-parse --abbrev-ref HEAD).Trim()
    if ($branch -eq 'HEAD') { Die 'Harness checkout is in detached-HEAD state — check out a branch first (e.g. git checkout master).' }

    $scheme = switch -Regex ($remote) { '^(git@|ssh://)' { 'SSH key' } '^https://' { 'HTTPS + $env:HARNESS_GH_TOKEN' } default { 'local/other transport' } }

    if ($o.DryRun) { Say "DRY RUN — would: git -C `"$HarnessDir`" pull --ff-only ($scheme) onto '$branch', then re-assemble managed targets. Nothing pulled or written."; return }

    $before = (& git -C $HarnessDir rev-parse HEAD).Trim()
    if ($remote -match '^(git@|ssh://)') {
      Say 'Auth: SSH key (remote is an SSH URL)'
      $env:GIT_TERMINAL_PROMPT = '0'
      & git -C $HarnessDir pull --ff-only $remote $branch
      $code = $LASTEXITCODE; $env:GIT_TERMINAL_PROMPT = $null
      if ($code -ne 0) { Die 'git pull failed (SSH). Check the box has an SSH key with read access (ssh -T the host) and that a fast-forward is possible.' }
    }
    elseif ($remote -match '^https://') {
      Say 'Auth: HTTPS — token from $env:HARNESS_GH_TOKEN (never written to disk)'
      $token = $env:HARNESS_GH_TOKEN
      if (-not $token) { Die 'HTTPS remote needs a token: set $env:HARNESS_GH_TOKEN=<PAT with read access> and re-run. (Read from env only; never stored.)' }
      $onWindows = ($env:OS -eq 'Windows_NT')
      if ($onWindows) {
        $askpass = [System.IO.Path]::GetTempFileName() + '.cmd'
        Set-Content -Path $askpass -Value '@echo %HARNESS_GH_TOKEN%' -Encoding ascii
      } else {
        $askpass = [System.IO.Path]::GetTempFileName()
        Set-Content -Path $askpass -Value "#!/usr/bin/env bash`nexec printf %s `"`$HARNESS_GH_TOKEN`"" -Encoding ascii -NoNewline
        & chmod 700 $askpass 2>$null
      }
      $authUrl = $remote -replace '^https://', 'https://x-access-token@'
      $env:GIT_ASKPASS = $askpass; $env:GIT_TERMINAL_PROMPT = '0'
      & git -C $HarnessDir -c credential.helper= pull --ff-only $authUrl $branch
      $code = $LASTEXITCODE
      $env:GIT_ASKPASS = $null; $env:GIT_TERMINAL_PROMPT = $null
      Remove-Item $askpass -Force -ErrorAction SilentlyContinue
      if ($code -ne 0) { Die 'git pull failed (HTTPS). Check $env:HARNESS_GH_TOKEN has read access and that a fast-forward is possible.' }
    }
    else {
      Say "Auth: none ($scheme)"
      $env:GIT_TERMINAL_PROMPT = '0'
      & git -C $HarnessDir pull --ff-only $remote $branch
      $code = $LASTEXITCODE; $env:GIT_TERMINAL_PROMPT = $null
      if ($code -ne 0) { Die "git pull failed. Ensure '$remote' is reachable and a fast-forward is possible." }
    }

    $after = (& git -C $HarnessDir rev-parse HEAD).Trim()
    if ($before -eq $after) {
      Ok "Already up to date ($branch @ $($after.Substring(0,9)))."
      Say 'No changes pulled — nothing to re-assemble.'
      return
    }
    $count = (& git -C $HarnessDir rev-list --count "$before..$after").Trim()
    Ok "Updated ${branch}: $($before.Substring(0,9)) → $($after.Substring(0,9)) ($count new commit(s))."

    if ($o.NoReassemble) { Say 'Skipping re-assembly (--no-reassemble). Re-run setup on any target to refresh its managed block.'; return }
    Reassemble-ManagedTargets
  }
  finally { $ErrorActionPreference = $prev }
}

# ============================================================================
#  DISPATCH
# ============================================================================
# The wizard is the DEFAULT: bare `./setup.ps1` (no options) runs it. The WIZARD_RUN
# guard stops a wizard-built re-invocation from looping back in if its arg list were empty.
if ($o.Wizard -or (($args.Count -eq 0) -and ($env:WIZARD_RUN -ne '1'))) {
  if ([Console]::IsInputRedirected) { Say '(reading wizard answers from a pipe — non-interactive)' }
  Run-Wizard
  exit 0
}

if ($o.Doctor) {
  Say "Harness doctor — $CcDir"
  $settings = Join-Path $CcDir 'settings.json'
  if (Test-Path $settings) {
    Ok 'settings.json present'
    try {
      $s = Get-Content $settings -Raw | ConvertFrom-Json -AsHashtable
      foreach ($k in @('statusLine','effortLevel','autoMemoryEnabled','enabledPlugins')) {
        if ($s.ContainsKey($k)) { Ok "settings.$k set" } else { Warn "settings.$k missing" }
      }
    } catch { Warn 'settings.json present but not valid JSON' }
  } else { Warn "no $settings" }
  if (Test-Path (Join-Path $CcDir 'statusline-command.sh')) { Ok 'statusline installed' } else { Warn 'no statusline-command.sh' }
  $gmd = Join-Path $CcDir 'CLAUDE.md'
  if (Test-Path $gmd) {
    Ok "global ~/.claude/CLAUDE.md present ($(@(Get-Content $gmd).Count) lines)"
  } else { Warn 'no global CLAUDE.md (per-project only)' }
  $skills = Join-Path $CcDir 'skills'
  if (Test-Path $skills) { Ok "skills dir: $(@(Get-ChildItem $skills -Directory).Count) skill(s)" } else { Warn 'no ~/.claude/skills' }
  if (Have-Cmd claude) { Ok "'claude' CLI on PATH" } else { Warn "'claude' CLI not on PATH (plugin install/update unavailable from script)" }
  if (Test-Path (Join-Path $CcDir 'plugins')) { Ok 'plugins dir present' } else { Warn 'no ~/.claude/plugins' }
  exit 0
}

if ($o.UpdatePlugins) {
  if (-not (Have-Cmd claude)) { Die "'claude' CLI not on PATH — update in-app with /plugin update." }
  Say 'Updating installed plugins to latest'
  try { claude plugin update *> $null; Ok 'plugins updated' } catch { Warn 'update reported issues — try /plugin update in-app' }
  exit 0
}

if ($o.SelfUpdate) { Self-Update; exit 0 }
if ($o.Export)    { Export-Instructions; exit 0 }
if ($o.OrgPolicy) { OrgPolicy-Install; exit 0 }
if ($o.WithHandoffHooks -and (-not $o.Global) -and (-not $o.Profiles)) { Install-HandoffHooks; exit 0 }

if ($o.Uninstall) {
  if ($o.Global) {
    Say "Uninstall — removing the Agentsmith core from $(Join-Path $CcDir 'CLAUDE.md')"
    Uninstall-From (Join-Path $CcDir 'CLAUDE.md')
    Warn 'Global config (settings.json, plugins) left in place — remove those by hand if you want them gone.'
  } else {
    if (-not $o.Target) { $o.Target = (Get-Location).Path }
    if (-not (Test-Path $o.Target -PathType Container)) { Die "Target dir does not exist: $($o.Target)" }
    $tgt = (Resolve-Path $o.Target).Path
    Say "Uninstall — removing the Agentsmith section from CLAUDE.md/AGENTS.md/GEMINI.md in $tgt"
    Uninstall-From (Join-Path $tgt 'CLAUDE.md')
    Uninstall-From (Join-Path $tgt 'AGENTS.md')
    Uninstall-From (Join-Path $tgt 'GEMINI.md')
    Write-Host ''; Ok 'Done. Scaffolding (scripts/, .harness/, docs/) was left in place — delete it by hand for a full removal.'
    Write-Host '  Your original files (if any) were backed up as *.bak.<timestamp> next to each.'
  }
  exit 0
}

# ---- GLOBAL MODE -----------------------------------------------------------
if ($o.Global) {
  Say "GLOBAL install — universal core → $(Join-Path $CcDir 'CLAUDE.md') (applies to every project)"
  # --target does not constrain --global: the core has exactly one home. Refusing beats warning —
  # the whole of feedback 0003 is that a careful person passed --target BECAUSE it reads as "write
  # over there, not to my real config", and a printed warning is prose in a wall of output.
  if ($o.Target) {
    Die @"
--target is ignored by --global: the core always goes to $(Join-Path $CcDir 'CLAUDE.md'), never to $($o.Target).
  For a project file:   ./setup.ps1 --profile <name> --target $($o.Target)
  For the global core:  ./setup.ps1 --global        (no --target)
"@
  }
  # Likewise --assemble-only reads like "touch nothing" but under --global, CLAUDE.md IS the
  # global file. Say so out loud rather than letting the flag imply a safety it does not provide.
  if ($o.AssembleOnly -and (-not $o.DryRun)) {
    Warn "--assemble-only skips config/plugins but still WRITES $(Join-Path $CcDir 'CLAUDE.md') (a backup is made first). Use --dry-run to write nothing."
  }
  if ($o.WithMcp) { Warn '--with-mcp is project-scoped (writes a project .mcp.json) — ignored in --global mode. Run it per project.' }
  Resolve-OperatorIdentity (Join-Path $CcDir 'CLAUDE.md')
  Assemble-To (Join-Path $CcDir 'CLAUDE.md') $true
  if (-not $o.DryRun) { Report-Todos (Join-Path $CcDir 'CLAUDE.md') }
  if (-not $o.DryRun) { if ($o.AssembleOnly) { Say 'Skipping config/plugins (--assemble-only).' } else { Install-GlobalConfig } }
  Write-Host ''; Say 'Global core installed.'
  Write-Host "  Next per project:  ./setup.ps1 --profile <name> --profile-only --target C:\path\to\project"
  exit 0
}

# ---- PROJECT MODE ----------------------------------------------------------
if (-not $o.Profiles) { Die "Pick a profile: --profile <name[,name]>  (or --global for the core only, or --wizard). See: ls profiles/" }
if (-not $o.Target) { $o.Target = (Get-Location).Path }
if (-not (Test-Path $o.Target)) { Die "Target dir does not exist: $($o.Target)" }
$o.Target = (Resolve-Path $o.Target).Path

$includeCore = -not $o.ProfileOnly
Say "Assembling CLAUDE.md (profiles: $($o.Profiles); core: $includeCore)"
# Same trap as --global, same fix: re-running setup on a project that already has a managed block
# must not silently blank whoever is named in it (feedback 0003).
Resolve-OperatorIdentity (Join-Path $o.Target 'CLAUDE.md')
Assemble-To (Join-Path $o.Target 'CLAUDE.md') $includeCore
if ($o.AlsoAgents -and (-not $o.DryRun)) { Assemble-To (Join-Path $o.Target 'AGENTS.md') $includeCore }
if ($o.AlsoGemini -and (-not $o.DryRun)) { Assemble-To (Join-Path $o.Target 'GEMINI.md') $includeCore }
if ($o.DryRun) { exit 0 }

Say "Scaffolding project structure in $($o.Target)"
foreach ($d in @('docs/research/_archive','docs/feedback/_archive','.planning','.harness/handoffs','scripts','.claude','hooks/git','.harness/templates')) {
  New-Item -ItemType Directory -Force -Path (Join-Path $o.Target $d) | Out-Null
}
function Cpa ($src, $dst) { if (-not (Test-Path $dst)) { Copy-Item $src $dst -Force; Ok "added $($dst.Substring($o.Target.Length).TrimStart('/','\'))" } }
foreach ($s in @('verify.sh','new-research.sh','new-feedback.sh','handoff.sh','secret-scan.sh','install-git-hooks.sh','lint-leanness.sh')) {
  Cpa (Join-Path $HarnessDir "scripts/$s") (Join-Path $o.Target "scripts/$s")
}
Cpa (Join-Path $HarnessDir 'docs/feedback/README.md') (Join-Path $o.Target 'docs/feedback/README.md')
Get-ChildItem (Join-Path $HarnessDir 'hooks/git') -Filter *.sh | ForEach-Object { Cpa $_.FullName (Join-Path $o.Target "hooks/git/$($_.Name)") }
Cpa (Join-Path $HarnessDir '.harness/verify.conf.example') (Join-Path $o.Target '.harness/verify.conf.example')
$verifyConf = Join-Path $o.Target '.harness/verify.conf'
if (Test-Path $verifyConf) { Ok '.harness/verify.conf already present — left as-is' }
else { Build-VerifyConf $verifyConf; Ok "added .harness/verify.conf (preset for: $($o.Profiles) — EDIT to wire real checks)" }
Cpa (Join-Path $HarnessDir 'templates/progress-log.md') (Join-Path $o.Target '.planning/progress-log.md')
Cpa (Join-Path $HarnessDir "config/settings.local.$($o.Safety).json.example") (Join-Path $o.Target '.claude/settings.local.json.example')
Get-ChildItem (Join-Path $HarnessDir 'templates') -Filter *.md | ForEach-Object { Copy-Item $_.FullName (Join-Path $o.Target ".harness/templates/$($_.Name)") -Force }
Ok 'templates in .harness/templates/'
# First-steps card: fill placeholders, write-if-absent (don't clobber a user-edited card)
$firstSteps = Join-Path $o.Target 'FIRST-STEPS.md'
if (Test-Path $firstSteps) { Ok 'FIRST-STEPS.md already present — left as-is' }
else {
  (Get-Content (Join-Path $HarnessDir 'templates/first-steps.md') -Raw).
    Replace('{{PROFILES}}', $(if ($o.Profiles) { $o.Profiles } else { 'none' })).
    Replace('{{SAFETY}}', $o.Safety).
    Replace('{{TARGET_NAME}}', (Split-Path $o.Target -Leaf)) |
    Set-Content $firstSteps -Encoding utf8
  Ok 'added FIRST-STEPS.md (your getting-started card)'
}

if ($o.WithMcp) { Say "Adding MCP server(s) to .mcp.json: $($o.WithMcp)"; Add-McpServers $o.WithMcp }

if ($o.WithHooks) {
  if (Test-Path (Join-Path $o.Target '.git')) {
    Push-Location $o.Target; try { bash scripts/install-git-hooks.sh; Ok 'git guardrails installed (secret-scan + protect-main + conventional)' } catch { Warn 'install-git-hooks.sh needs a POSIX shell (Git Bash/WSL) on PATH' } finally { Pop-Location }
    Write-Host '    add opt-in guards: scripts/install-git-hooks.sh --branch-naming --tests-green'
  } else { Warn "--with-hooks: $($o.Target) is not a git repo — run scripts/install-git-hooks.sh after 'git init'." }
}

if ($o.AssembleOnly) { Say 'Skipping global config (--assemble-only). See INSTALL.md for manual steps.' }
else { $SkillsDest = Join-Path $o.Target '.claude/skills'; Install-GlobalConfig }   # project mode: skill pack is a project file

Write-Host ''; Say 'Done.'
Write-Host "  Profiles:   $($o.Profiles)   (core in this file: $includeCore)"
Write-Host "  CLAUDE.md:  $(Join-Path $o.Target 'CLAUDE.md')"
if ($o.WithSkills) { Write-Host "  Skills:     harness pack → $(Join-Path $o.Target '.claude/skills')  (/handoff · /verify · /harness-help + 3 more)" }
$safetyNote = if ($o.Safety -eq 'cautious') { 'auto-applies edits, asks before shell/network' } else { 'runs almost everything without asking — a machine you fully own' }
Write-Host "  Safety:     $($o.Safety)   ($safetyNote)"
Write-Host '  Next:  1) edit .harness/verify.conf with real checks'
Write-Host '         2) skim CLAUDE.md (resolve any [TODO: …] placeholders)'
Write-Host "         3) copy .claude/settings.local.json.example to settings.local.json (safety: $($o.Safety) — read the permissions note)"
Write-Host '         4) docs/01-harness-philosophy.md · docs/07-how-to-pick-a-profile.md · docs/12-platforms-and-tools.md'
Write-Host ''
Report-Todos (Join-Path $o.Target 'CLAUDE.md')
Write-Host ''
Write-Host '  ▶ First 30 minutes' -ForegroundColor Cyan -NoNewline; Write-Host '  (also saved to FIRST-STEPS.md)'
Write-Host '     1) start:  claude          — run it inside this folder'
Write-Host '     2) ask:    "what does my harness do, and what are my rules?"'
Write-Host '     3) take one small task end-to-end, then say "handoff" to wrap up cleanly'
