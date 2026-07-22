#!/usr/bin/env bash
# ============================================================================
#  Agentsmith — the universal agent harness — setup
#  Assembles a lean CLAUDE.md from core/ + chosen profiles, and (optionally)
#  installs global config, plugins, and skills on this machine.
#
#  DEFAULT — just run it. With no options, the interactive wizard walks you through
#  everything (and prints the exact command it runs, so you learn the flags):
#    ./setup.sh                         # ← the wizard (same as --wizard)
#
#  Everything below is the non-interactive path — pass options to skip the wizard.
#
#  Per-project (self-contained CLAUDE.md = core + profile):
#    ./setup.sh --profile software-dev --target /path/to/project
#    ./setup.sh --profile devops-setup,software-dev --operator-name "Your Name" \
#               --operator-role "sysadmin / GTM" --tracker linear --target .
#
#  Layered (recommended): install the core ONCE globally, thin profile per project:
#    ./setup.sh --global --operator-name "Your Name"      # core -> ~/.claude/CLAUDE.md + config
#    ./setup.sh --profile software-dev --profile-only --target /path/to/project
#
#  About --global: it writes ~/.claude/CLAUDE.md and nothing else can redirect it — --target is
#  refused, and --assemble-only only skips config/plugins, it does NOT make the run local. A
#  re-run keeps the operator name/role/tracker already in the file unless you pass new ones, so
#  `--global` on its own is safe to repeat. Use --dry-run to write nothing at all.
#
#  Other options:
#    ./setup.sh --tracker linear --tracker-writes ask|allowed
#                                       # --tracker says WHERE the team tracks work. It does NOT
#                                       #   grant write access — that's --tracker-writes:
#                                       #   ask (default) = the agent drafts the issue, you post it;
#                                       #   allowed = it may file/comment in the tracker itself.
#                                       #   Availability is not authorization (core/10, feedback 0002).
#    ./setup.sh --safety cautious|trusted  # cautious = auto-apply edits, ask before shell/network;
#                                       #   trusted = run almost everything without asking (default
#                                       #   on the flag path; the wizard defaults to cautious)
#    ./setup.sh --assemble-only ...     # skip the config/plugins install; still writes CLAUDE.md
#                                       #   (under --global that IS ~/.claude/CLAUDE.md — see above)
#    ./setup.sh --with-plugins dev-workflow,stack-lsp ...   # opt-in plugin packs (latest)
#    ./setup.sh --with-rtk | --no-rtk   # rtk CLI-output compressor (default: ON for software-dev/devops-setup)
#    ./setup.sh --with-mcp playwright,context7 ...   # add named MCP server(s) to project .mcp.json
#    ./setup.sh --with-skills ...       # install the bundled skill pack (handoff, verify,
#                                       #   harness-doctor, new-research, new-feedback, harness-help);
#                                       #   project mode → <project>/.claude/skills, --global → ~/.claude/skills
#    ./setup.sh --with-hooks ...        # install git guardrails (secret-scan+protect-main+conventional) in --target
#    ./setup.sh --update-plugins        # update installed plugins to latest, then exit
#    ./setup.sh --doctor                # print install health, then exit
#    ./setup.sh --profile X --export-instructions > inst.md   # paste-ready blob for web/Cowork
#    sudo ./setup.sh --org-policy       # machine-wide managed CLAUDE.md + hardened (no-bypass) settings
#    ./setup.sh --with-handoff-hooks    # install reliable 'handoff' keyword hook (+ best-effort ctx-% nudge)
#    ./setup.sh --design-system skip|stub|catalog:<slug>|generate   # software-dev UI projects: establish a
#                                       #   design system. stub = scaffold DESIGN.md to fill in; catalog:stripe =
#                                       #   pull a ready-made one from the awesome-design-md catalog; generate =
#                                       #   print the ui-ux-pro-max steps. default = skip (no DESIGN.md).
#    ./setup.sh --with-ui-design-hook   # global PreToolUse nudge: consult DESIGN.md when editing UI files
#    ./setup.sh --self-update           # pull the latest harness into this checkout + re-assemble managed CLAUDE.md
#                                       #   remote: --from <url> | $HARNESS_REMOTE | .harness/remote | the checkout's origin
#                                       #   auth:   git@/ssh:// → SSH key; https:// → $HARNESS_GH_TOKEN (never stored)
#                                       #   add --no-reassemble to fetch only; --dry-run to preview without pulling
#    ./setup.sh --profile auto --target .   # auto-detect the profile from the project's files
#    ./setup.sh --uninstall --target .  # remove the harness section (auto-backup first); --global for the core
#    ./setup.sh --help
#
#  Idempotent. Never clobbers your files without --force.
# ============================================================================
set -euo pipefail

HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CC_DIR="$HOME/.claude"

# ---- defaults --------------------------------------------------------------
PROFILES=""
TARGET=""
# Operator identity starts EMPTY on purpose. Empty means "the flag was not passed" — which is the
# only thing that lets a re-run tell "leave this alone" apart from "set it to exactly this". The
# real defaults are DEFAULT_* below, applied LAST, after any recovery from an existing block.
# Feedback 0003: these used to default straight to the rendered text, so nothing downstream could
# distinguish a fresh install from a re-run, and every re-run of --global overwrote the operator's
# real identity with "the project lead". Twice, to the person who wrote the warning about it.
OPERATOR_NAME=""
OPERATOR_ROLE=""
OPERATOR_BIO=""
TRACKER=""
TRACKER_WRITES=""

DEFAULT_OPERATOR_NAME="the project lead"
DEFAULT_OPERATOR_ROLE="owner / decision-maker"
DEFAULT_OPERATOR_BIO="They decide direction and accept the risk; you are the technical co-pilot — proactive, evidence-driven, and honest about trade-offs."
DEFAULT_TRACKER="your project's tracker (or a KNOWN-ISSUES.md at the repo root)"
# Consent, not inference: naming a tracker says WHERE the team tracks work, never that the agent
# may write there (feedback 0002). Default is ask; --tracker-writes allowed is a deliberate opt-in.
# The two rendered sentences are also the recovery anchors in recover_operator_fields() — the
# substrings "writes are NOT authorized" / "writes are authorized" must stay stable and distinct.
DEFAULT_TRACKER_WRITES="ask"
TRACKER_POLICY_ASK="**writes are NOT authorized** — draft the entry and surface it for the operator to post; never create or comment on items yourself. Offer once; if they say yes, that's durable for this session."
TRACKER_POLICY_ALLOWED="**writes are authorized** (the operator opted in at setup) — file it directly, and make agent work visible there (a note when work starts and when it lands)."
GLOBAL=false
PROFILE_ONLY=false
ASSEMBLE_ONLY=false
FORCE=false
DRY_RUN=false
ALSO_AGENTS_MD=false
ALSO_GEMINI_MD=false
WITH_SKILLS=false
SKILLS_DEST=""            # empty → install_skills defaults to global ~/.claude/skills; project mode sets $TARGET/.claude/skills
WITH_HOOKS=false
WITH_HANDOFF_HOOKS=false
WITH_UI_DESIGN_HOOK=false
DESIGN_SYSTEM=""          # "" / skip = no DESIGN.md; stub | catalog:<slug> | generate for a UI project
WITH_PLUGINS=""
WITH_RTK="auto"           # auto = install rtk for code profiles (software-dev/devops-setup); --with-rtk forces on, --no-rtk off
WITH_MCP=""
DO_UPDATE_PLUGINS=false
DO_DOCTOR=false
DO_EXPORT=false
DO_ORG_POLICY=false
DO_WIZARD=false
DO_SELF_UPDATE=false
SELF_UPDATE_REMOTE=""
NO_REASSEMBLE=false
DO_UNINSTALL=false
SAFETY="trusted"      # trusted = bypassPermissions (today's flag-path default); cautious = acceptEdits.
                     # The wizard defaults its answer to cautious; direct flag runs stay trusted.

BEGIN_MARK="<!-- BEGIN AGENTSMITH — universal agent harness (managed by setup.sh — edit core/profiles, not here) -->"
END_MARK="<!-- END AGENTSMITH -->"
# Legacy pre-rebrand ("Universal Claude Harness") markers: read-only aliases so installs made
# before the Agentsmith rename are still found by update/reassemble/uninstall. Never written.
LEGACY_BEGIN_MARK="<!-- BEGIN UNIVERSAL CLAUDE HARNESS (managed by setup.sh — edit core/profiles, not here) -->"
LEGACY_END_MARK="<!-- END UNIVERSAL CLAUDE HARNESS -->"
ALL_BEGIN_MARKS=("$BEGIN_MARK" "$LEGACY_BEGIN_MARK")   # newest first; index-paired with ALL_END_MARKS
ALL_END_MARKS=("$END_MARK" "$LEGACY_END_MARK")

locate_managed_block() {  # <file> -> sets FOUND_BEGIN/FOUND_END to the marker pair present; rc=1 if none
  local f="$1" i
  [ -f "$f" ] || return 1
  for i in "${!ALL_BEGIN_MARKS[@]}"; do
    if grep -qF "${ALL_BEGIN_MARKS[$i]}" "$f" 2>/dev/null; then
      FOUND_BEGIN="${ALL_BEGIN_MARKS[$i]}"; FOUND_END="${ALL_END_MARKS[$i]}"; return 0
    fi
  done
  return 1
}

c() { if [ -t 1 ]; then printf '\033[%sm%s\033[0m' "$1" "$2"; else printf '%s' "$2"; fi; }
say()  { echo "$(c '1;36' '»') $*"; }
ok()   { echo "  $(c '0;32' '✓') $*"; }
warn() { echo "  $(c '0;33' '!') $*"; }
die()  { echo "$(c '0;31' '✗') $*" >&2; exit 1; }
usage() { sed -n '2,/^# ====/p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

# ---- profile auto-detect + uninstall (used by --profile auto, the wizard, --uninstall) -----
_has() {  # <dir> <glob...> -> 0 if any glob matches an existing entry (glob-safe under set -e)
  local d="$1"; shift; local p f
  for p in "$@"; do for f in "$d"/$p; do [ -e "$f" ] && return 0; done; done
  return 1
}
detect_profile() {  # <dir> -> best-guess profile name from the files present (first strong signal wins)
  local d="$1"
  _has "$d" go.mod package.json tsconfig.json Cargo.toml pyproject.toml requirements.txt pom.xml 'build.gradle*' '*.csproj' Gemfile composer.json && { echo software-dev; return; }
  { _has "$d" Dockerfile 'docker-compose.y*ml' '*.tf' ansible.cfg Vagrantfile || [ -d "$d/ansible" ] || [ -d "$d/terraform" ] || [ -d "$d/k8s" ]; } && { echo devops-setup; return; }
  { _has "$d" '*.ipynb' '*.csv' '*.parquet' || [ -d "$d/notebooks" ]; } && { echo data-crunching; return; }
  { _has "$d" mkdocs.yml 'docusaurus.config.*' _config.yml '*.tex' || { [ -d "$d/docs" ] && _has "$d/docs" '*.md'; }; } && { echo document-creation; return; }
  # Weak signal, checked LAST: loose source files with no manifest still make this a code project.
  # Deliberately below data/doc so a manifest-less notebook or docs tree still wins over a stray script.
  _has "$d" '*.py' '*.js' '*.mjs' '*.ts' '*.tsx' '*.jsx' '*.go' '*.rs' '*.rb' '*.java' '*.kt' '*.php' '*.c' '*.cc' '*.cpp' '*.cs' '*.swift' '*.scala' && { echo software-dev; return; }
  # One level deep: a monorepo often keeps its manifest in a subdir (e.g. backend/requirements.txt).
  # Lowest priority — only rescues what would otherwise be general-admin; never overrides a root
  # data/doc/devops signal. Immediate subdirs only (bounded); the glob skips dotdirs like .git/.venv.
  local _sub
  for _sub in "$d"/*/; do
    [ -d "$_sub" ] || continue
    if _has "$_sub" go.mod package.json tsconfig.json Cargo.toml pyproject.toml requirements.txt pom.xml 'build.gradle*' '*.csproj' Gemfile composer.json; then
      echo software-dev; return
    fi
  done
  echo general-admin
}
uninstall_from() {  # <file> -> back it up, strip the managed block; delete the file if nothing else remains
  local f="$1"
  locate_managed_block "$f" || return 0
  local bak; bak="$(backup_file "$f")"
  awk -v b="$FOUND_BEGIN" -v e="$FOUND_END" '$0==b{skip=1} skip!=1{print} $0==e{skip=0}' "$f" > "$f.new"
  if grep -q '[^[:space:]]' "$f.new" 2>/dev/null; then
    mv "$f.new" "$f"; ok "removed the harness section from $(basename "$f") (backup: $(basename "$bak"))"
  else
    rm -f "$f.new" "$f"; ok "removed $(basename "$f") — it only held the harness section (backup: $(basename "$bak"))"
  fi
}

# ---- interactive wizard helpers -------------------------------------------
# These only ASK questions and build a setup.sh argument list. Nothing is
# written until the user confirms; then we re-exec this same script with the
# assembled flags (so the wizard teaches the flags instead of hiding them).
wiz_ask() {  # <out_var> <prompt> <default>
  local __var="$1" __prompt="$2" __def="${3:-}" __ans
  if [ -n "$__def" ]; then printf '  %s [%s]: ' "$__prompt" "$__def"
  else printf '  %s: ' "$__prompt"; fi
  read -r __ans || true
  [ -z "$__ans" ] && __ans="$__def"
  printf -v "$__var" '%s' "$__ans"
}

wiz_yn() {  # <prompt> <default:y|n>  -> returns 0 for yes
  local __prompt="$1" __def="${2:-n}" __ans __hint
  case "$__def" in y|Y) __hint="Y/n";; *) __hint="y/N";; esac
  printf '  %s [%s]: ' "$__prompt" "$__hint"
  read -r __ans || true
  [ -z "$__ans" ] && __ans="$__def"
  case "$__ans" in [Yy]*) return 0;; *) return 1;; esac
}

wiz_multiselect() {  # <out_var> <allow_empty:0|1> <item...>  -> sets out_var to comma-joined picks
  local __var="$1" __allow="$2"; shift 2
  local __items=("$@") __sel __picks __i __n __okflag
  for __i in "${!__items[@]}"; do printf '    %d) %s\n' "$((__i+1))" "${__items[$__i]}"; done
  while :; do
    printf '  Numbers (space-separated%s): ' "$([ "$__allow" = 1 ] && echo ', blank = none')"
    read -r __sel || die "wizard aborted (no input)"
    __picks=(); __okflag=1
    if [ -z "$__sel" ]; then
      [ "$__allow" = 1 ] && break
      echo "  ! pick at least one"; continue
    fi
    for __n in $__sel; do
      if [[ "$__n" =~ ^[0-9]+$ ]] && [ "$__n" -ge 1 ] && [ "$__n" -le "${#__items[@]}" ]; then
        __picks+=("${__items[$((__n-1))]}")
      else __okflag=0; fi
    done
    [ "$__okflag" = 1 ] && break || echo "  ! use numbers 1-${#__items[@]}"
  done
  printf -v "$__var" '%s' "$(IFS=,; echo "${__picks[*]}")"
}

# NOTE: these picker functions are called bare (not in an &&/||/if context), so
# under `set -e` they MUST end with a zero status — a trailing `return 0` keeps a
# "no thanks" answer from looking like a script failure and aborting the wizard.
wiz_pick_profiles() {  # sets WIZ_PROFILES (comma-joined, ≥1)
  local __avail=() __f
  for __f in "$HARNESS_DIR"/profiles/*.md; do __avail+=("$(basename "$__f" .md)"); done
  wiz_multiselect WIZ_PROFILES 0 "${__avail[@]}"
  return 0
}

wiz_pick_mcp() {  # sets WIZ_MCP (comma-joined or empty)
  WIZ_MCP=""
  if ! command -v jq >/dev/null 2>&1; then
    warn "jq not installed — skipping MCP picker (add servers later with --with-mcp)"; return 0
  fi
  local __avail=() __name
  while IFS= read -r __name; do [ -n "$__name" ] && __avail+=("$__name"); done \
    < <(jq -r '.mcpServers|keys[]' "$HARNESS_DIR/config/mcp.example.json" 2>/dev/null)
  [ "${#__avail[@]}" -gt 0 ] || return 0
  wiz_yn "Add MCP server(s) to this project's .mcp.json?" n || return 0
  wiz_multiselect WIZ_MCP 1 "${__avail[@]}"
  return 0
}

wiz_pick_plugins() {  # sets WIZ_PLUGINS (comma-joined or empty); pre-checks defaults from REC_PACKS
  WIZ_PLUGINS=""
  local dw=n sl=n
  case ",${REC_PACKS:-}," in *,dev-workflow,*) dw=y;; esac
  case ",${REC_PACKS:-}," in *,stack-lsp,*)    sl=y;; esac
  echo "  Optional plugin packs (installed via the 'claude' CLI — needs network):"
  echo "    • dev-workflow — feature-dev, frontend-design, workflow plugins"
  echo "    • stack-lsp    — language servers (example pack: Go + TypeScript)"
  wiz_yn "Add the dev-workflow pack?" "$dw" && WIZ_PLUGINS="dev-workflow"
  if wiz_yn "Add the stack-lsp pack?" "$sl"; then
    [ -n "$WIZ_PLUGINS" ] && WIZ_PLUGINS="$WIZ_PLUGINS,stack-lsp" || WIZ_PLUGINS="stack-lsp"
  fi
  return 0
}

# recommend_for <profile> — parse the "<!-- MAP <profile> | packs: ... | skills: ... -->" line
# from skills/RECOMMENDED.md (single source of truth). Sets REC_PACKS and REC_SKILLS:
# '-' means "none recommended", '' means the profile isn't mapped (wizard falls back to generic).
recommend_for() {
  REC_PACKS=""; REC_SKILLS=""
  local prof="${1%%,*}" f="$HARNESS_DIR/skills/RECOMMENDED.md" line
  [ -n "$prof" ] && [ -f "$f" ] || return 0
  line="$(grep -E "MAP[[:space:]]+${prof}[[:space:]]*\|" "$f" 2>/dev/null | head -1)" || true
  [ -n "$line" ] || return 0
  REC_PACKS="$(printf '%s' "$line"  | sed -E 's/.*packs:[[:space:]]*([^|]*)\|.*/\1/'  | sed -E 's/[[:space:]]+$//;s/^[[:space:]]+//')"
  REC_SKILLS="$(printf '%s' "$line" | sed -E 's/.*skills:[[:space:]]*(.*)-->.*/\1/'    | sed -E 's/[[:space:]]+$//;s/^[[:space:]]+//')"
  return 0
}

wiz_show_cmd() {  # <sudo:0|1> <arg...>  -> print the equivalent setup.sh invocation
  local __sudo="$1"; shift
  [ "$__sudo" = 1 ] && printf '    sudo ./setup.sh' || printf '    ./setup.sh'
  local __a
  for __a in "$@"; do
    case "$__a" in --*) printf ' %s' "$__a";; *) printf ' %q' "$__a";; esac
  done
  echo
}

wiz_note() { echo "      $(c '0;90' "$*")"; }   # dim, indented plain-English explanation

# Two-tone banner: gold wordmark + coach/rig, white horse, green MODEL, cyan "what the harness is".
# Split each horse/coach line at a fixed column so the left (horse) and right (coach) get different
# colors. Colors are empty on a non-tty (piped/redirected), so nothing leaks into captured output.
banner() {
  local Y='' C='' W='' G='' R=''
  if [ -t 1 ]; then Y=$'\033[1;33m'; C=$'\033[1;36m'; W=$'\033[0;37m'; G=$'\033[1;32m'; R=$'\033[0m'; fi
  local i=0 line
  while IFS= read -r line; do
    case $i in
      0|1|2|3) printf '%s%s%s\n' "$Y" "$line" "$R" ;;                                  # gold wordmark
      4)       printf '\n' ;;
      11)      printf '%s%s%s%s%s\n' "$W" "${line:0:16}" "$C" "${line:16}" "$R" ;;      # hooves | cyan label
      12)      printf '%s%s%s\n' "$G" "$line" "$R" ;;                                   # green MODEL
      *)       printf '%s%s%s%s%s\n' "$W" "${line:0:16}" "$Y" "${line:16}" "$R" ;;      # white horse | gold coach
    esac
    i=$((i+1))
  done <<'BANNER'
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
BANNER
}

# Git is a soft prerequisite (guardrail hooks, branching, --self-update all use it). For the
# non-technical operator: explain it plainly and offer to install it, rather than failing later.
check_git() {
  command -v git >/dev/null 2>&1 && return 0
  echo
  warn "Git isn't installed — and Agentsmith leans on it for its safety net."
  wiz_note "Git is a free tool that records changes to your files. The harness uses it so you can"
  wiz_note "undo mistakes, and so the guardrails (block a committed password, protect your main"
  wiz_note "branch) can work. You can finish setup without it, but installing it is recommended."
  echo
  local cmd=''
  case "$(uname -s 2>/dev/null)" in
    Darwin) cmd='xcode-select --install' ;;
    Linux)
      if   command -v apt-get >/dev/null 2>&1; then cmd='sudo apt-get update && sudo apt-get install -y git'
      elif command -v dnf     >/dev/null 2>&1; then cmd='sudo dnf install -y git'
      elif command -v yum     >/dev/null 2>&1; then cmd='sudo yum install -y git'
      elif command -v pacman  >/dev/null 2>&1; then cmd='sudo pacman -S --noconfirm git'
      elif command -v zypper  >/dev/null 2>&1; then cmd='sudo zypper install -y git'
      elif command -v apk     >/dev/null 2>&1; then cmd='sudo apk add git'
      fi ;;
  esac
  if [ -n "$cmd" ]; then
    say "To install git, run:"
    echo "      $cmd"
    if [ -t 0 ] && wiz_yn "Want me to run that for you now?" n; then
      if eval "$cmd"; then ok "git installed."; else warn "that didn't finish — run the command above yourself, then re-run setup."; fi
    else
      wiz_note "Prefer to do it yourself? Run the line above (or see https://git-scm.com/downloads), then re-run."
    fi
  else
    say "Install git from:  https://git-scm.com/downloads"
    wiz_note "Then re-run this wizard."
  fi
  echo
}

run_wizard() {
  banner
  echo "  Welcome! This wizard sets up Agentsmith — the \"house rules\" that make your AI coding"
  echo "  assistant (Claude Code) work in a consistent, careful way on your projects."
  echo "  I'll ask a few short questions, explain each in plain language, show you the exact"
  echo "  command, and change NOTHING until you say yes. Any file I touch is backed up first."
  echo
  check_git
  echo "  What would you like to set up?"
  echo "    1) This project        — put the rules in ONE project folder you choose (most common)"
  echo "    2) Everything (global) — one set of rules for every project on this computer"
  echo "    3) Whole machine       — rules for all accounts on a shared computer (needs admin)"
  echo "    4) Just give me text   — a paste-ready block for claude.ai / Cowork (writes no files)"
  wiz_note "Not sure? Pick 1 — it's self-contained and the easiest to undo."
  local mc; while :; do printf '  Choose [1-4]: '; read -r mc || die "wizard aborted (no input)"; [[ "$mc" =~ ^[1-4]$ ]] && break; echo "  ! enter 1-4"; done

  local -a A=()
  local oname orole otrack target po_default

  case "$mc" in
    1)  # ---- per-project --------------------------------------------------
      echo; wiz_note "The folder of the project you want the assistant to follow these rules in."
      wiz_ask target "Target project directory" "$(pwd)"
      # validate now, not at the end: a typo'd path shouldn't waste the whole flow
      while [ ! -d "$target" ]; do
        if wiz_yn "Directory does not exist: $target — create it?" y; then
          mkdir -p "$target" 2>/dev/null && { ok "created $target"; break; }
          warn "could not create $target — try another path."
        fi
        wiz_ask target "Target project directory" "$(pwd)"
      done
      echo; echo "  Pick the work-type profile(s):"
      wiz_note "A 'profile' tailors the rules to the kind of work — writing code, server setup,"
      wiz_note "writing documents, research, and so on. Pick the closest one (a few is fine)."
      wiz_note "tip: this folder looks like a '$(detect_profile "$target")' project."
      wiz_pick_profiles
      A+=(--profile "$WIZ_PROFILES" --target "$target")
      recommend_for "$WIZ_PROFILES"   # sets REC_PACKS/REC_SKILLS from skills/RECOMMENDED.md (drives defaults + guidance)
      if [ -n "$REC_PACKS$REC_SKILLS" ]; then
        echo; say "Recommended for '${WIZ_PROFILES%%,*}':"
        { [ -n "$REC_PACKS" ]  && [ "$REC_PACKS"  != "-" ]; } && wiz_note "• plugin packs: $REC_PACKS  (I'll pre-select these below)"
        { [ -n "$REC_SKILLS" ] && [ "$REC_SKILLS" != "-" ]; } && wiz_note "• skills to add via plugins: $REC_SKILLS"
        wiz_note "• the bundled harness skill pack (/handoff, /verify, /harness-help + 3 more)"
      fi
      po_default=n
      if locate_managed_block "$CC_DIR/CLAUDE.md"; then
        po_default=y
        echo; ok "Universal core already installed globally ($CC_DIR/CLAUDE.md)."
      fi
      echo
      wiz_note "'Thin' = this project keeps only its profile; the shared core rules live in your"
      wiz_note "global file and load automatically. Recommended once the core is global."
      wiz_yn "Keep the project CLAUDE.md thin (profile only; core stays global)?" "$po_default" && A+=(--profile-only)
      echo
      wiz_note "How careful should the assistant be about running things?"
      wiz_note "Cautious = auto-apply file edits, but ASK before shell commands / network (recommended)."
      wiz_note "Trusted  = run almost everything without asking (only on a computer you fully own)."
      if wiz_yn "Use cautious mode (ask before shell/network)?" y; then A+=(--safety cautious); wiz_safety=cautious
      else A+=(--safety trusted); wiz_safety=trusted; fi
      echo; echo "  Your details (optional — these just personalise the rules):"
      wiz_note "Lets the assistant address you correctly. Leave any blank for sensible defaults."
      wiz_ask oname  "Your name" "";                                    [ -n "$oname" ]  && A+=(--operator-name "$oname")
      wiz_ask orole  "Your role (e.g. 'sysadmin / GTM')" "";            [ -n "$orole" ]  && A+=(--operator-role "$orole")
      wiz_ask otrack "Where you track tasks/bugs (linear, github, or a KNOWN-ISSUES.md file)" ""
      if [ -n "$otrack" ]; then
        A+=(--tracker "$otrack")
        wiz_note "That told it WHERE you track work — not that it may write there. By default it"
        wiz_note "drafts the issue and hands it to you to post. Say yes only if it may create and"
        wiz_note "comment in $otrack on its own. (A file inside this repo is safe to say yes to.)"
        wiz_yn "Let the assistant write to $otrack unprompted?" n && A+=(--tracker-writes allowed)
      fi
      echo; wiz_note "MCP servers are optional extra tools the assistant can use (e.g. a web browser,"
      wiz_note "a docs fetcher). Skip if unsure — you can always add them later."
      wiz_pick_mcp;     [ -n "$WIZ_MCP" ]     && A+=(--with-mcp "$WIZ_MCP")
      echo; wiz_note "Plugin packs are optional bundles of extra commands/skills. Skip if unsure."
      wiz_pick_plugins; [ -n "$WIZ_PLUGINS" ] && A+=(--with-plugins "$WIZ_PLUGINS")
      echo
      wiz_note "The bundled harness skill pack (/handoff, /verify, /harness-doctor, /harness-help,"
      wiz_note "/new-research, /new-feedback) installs into this project's .claude/skills/."
      if wiz_yn "Copy the bundled harness skill pack into this project?" y; then A+=(--with-skills); wiz_skills=y; fi
      echo
      wiz_note "Git guardrails are automatic safety checks in this project: block committing a"
      wiz_note "password, block committing straight to your main branch, keep commit messages tidy."
      wiz_yn "Install git guardrail hooks (recommended)?" y && A+=(--with-hooks)
      # Design system: only meaningful for software-dev projects with a UI.
      case ",$WIZ_PROFILES," in *,software-dev,*)
        echo
        wiz_note "If this project has a UI, its design system lives in DESIGN.md — the assistant reads it"
        wiz_note "before building any screen and matches it, so the UI isn't built ad-hoc and off-brand."
        if wiz_yn "Does this project have a UI (web/app frontend)?" n; then
          echo "      Establish the design system:"
          echo "        1) Scaffold a DESIGN.md template to fill in yourself (bring your brand)   [default]"
          echo "        2) Start from a ready-made one in the awesome-design-md catalog"
          echo "        3) Generate one with the ui-ux-pro-max skill"
          local dsc; while :; do printf '      Choose [1-3, default 1]: '; read -r dsc || dsc=1; [ -z "$dsc" ] && dsc=1; [[ "$dsc" =~ ^[1-3]$ ]] && break; echo "      ! enter 1-3"; done
          case "$dsc" in
            1) A+=(--design-system stub);;
            2) local dslug; wiz_ask dslug "Brand slug (e.g. stripe, linear, vercel, notion)" "stripe"; A+=(--design-system "catalog:$dslug");;
            3) A+=(--design-system generate);;
          esac
          wiz_note "The nudge hook reminds the assistant to consult DESIGN.md whenever it edits a UI file."
          wiz_yn "Install the UI-edit nudge hook globally?" y && A+=(--with-ui-design-hook)
        fi
        ;;
      esac
      wiz_note "Handoff hooks help the assistant save its place before it runs low on working memory."
      wiz_yn "Install handoff hooks globally ('handoff' keyword + best-effort context nudge)?" n && A+=(--with-handoff-hooks)
      wiz_yn "Also write AGENTS.md (for Codex & other assistants)?" n && A+=(--also-agents-md)
      wiz_yn "Also write GEMINI.md (for the Gemini CLI)?" n && A+=(--also-gemini-md)
      ;;
    2)  # ---- global core --------------------------------------------------
      A+=(--global)
      echo; wiz_note "Installs the shared core rules once, for every project on this computer."
      echo "  Your details (optional — blank = sensible defaults):"
      wiz_ask oname  "Your name" "";          [ -n "$oname" ]  && A+=(--operator-name "$oname")
      wiz_ask orole  "Your role" "";          [ -n "$orole" ]  && A+=(--operator-role "$orole")
      wiz_ask otrack "Issue tracker" ""
      if [ -n "$otrack" ]; then
        A+=(--tracker "$otrack")
        wiz_note "Naming it is not permission to write to it — by default the assistant drafts and"
        wiz_note "you post. This applies to every project on this computer."
        wiz_yn "Let the assistant write to $otrack unprompted?" n && A+=(--tracker-writes allowed)
      fi
      echo; wiz_pick_plugins; [ -n "$WIZ_PLUGINS" ] && A+=(--with-plugins "$WIZ_PLUGINS")
      echo
      wiz_yn "Copy the bundled skills into ~/.claude/skills?" n && A+=(--with-skills)
      wiz_yn "Install handoff hooks ('handoff' keyword + best-effort context nudge)?" y && A+=(--with-handoff-hooks)
      ;;
    3)  # ---- org policy ---------------------------------------------------
      echo; warn "Machine-wide policy writes managed config as root. The wizard prints a sudo command for you to run."
      wiz_note "Use this only on a shared computer where every account should follow the same rules."
      if wiz_yn "Bake a profile into the managed core?" n; then
        echo; wiz_pick_profiles; A+=(--profile "$WIZ_PROFILES")
      fi
      A+=(--org-policy)
      ;;
    4)  # ---- portable export ----------------------------------------------
      echo; echo "  Pick the profile(s) to export:"
      wiz_note "Prints a block of text you paste into claude.ai or Cowork. It writes no files."
      wiz_pick_profiles
      A+=(--profile "$WIZ_PROFILES" --export-instructions)
      ;;
  esac

  # dry-run preview only makes sense for the file-writing modes
  if [ "$mc" = 1 ] || [ "$mc" = 2 ]; then
    echo
    wiz_note "A dry-run shows exactly what would be written, changing nothing."
    wiz_yn "Preview only (dry-run: show what would be written, change nothing)?" n && A+=(--dry-run)
  fi

  if [ "$mc" = 1 ]; then
    echo; say "Here's what I found, and what I'll do:"
    echo "      • Folder:      $target"
    local md="$target/CLAUDE.md"
    if [ ! -f "$md" ]; then
      echo "      • CLAUDE.md:   none yet → I'll create a new one"
    elif locate_managed_block "$md"; then
      echo "      • CLAUDE.md:   a previous Agentsmith install → I'll update only my section (your edits stay)"
    else
      echo "      • CLAUDE.md:   your own file (no Agentsmith section) → I'll add my section at the end,"
      echo "                     after saving a timestamped backup of your original"
    fi
    if [ "$po_default" = y ]; then
      echo "      • Core rules:  already global → this project's file stays thin (profile only)"
    else
      echo "      • Core rules:  not global yet → this file includes the full core"
    fi
    echo "      • Safety:      ${wiz_safety:-cautious}  ($([ "${wiz_safety:-cautious}" = cautious ] && echo 'asks before shell/network' || echo 'runs without asking'))"
    [ "${wiz_skills:-n}" = y ] && echo "      • Skills:      bundled harness pack → $target/.claude/skills/"
    wiz_note "Backups are made before any existing file changes. Nothing is written until you confirm."
  fi

  echo; say "Equivalent command (copy this to repeat the setup non-interactively):"
  wiz_show_cmd "$([ "$mc" = 3 ] && echo 1 || echo 0)" "${A[@]}"
  echo

  if [ "$mc" = 3 ]; then
    say "Org policy needs root — the wizard won't sudo for you. Copy the line above and run it."
    return 0
  fi

  if [ "$mc" = 4 ]; then
    wiz_yn "Print the portable instructions now?" y || { say "Run the command above when ready."; return 0; }
  else
    wiz_yn "Run it now?" y || { say "Nothing written. Run the command above when ready."; return 0; }
  fi

  echo
  WIZARD_RUN=1 exec bash "${BASH_SOURCE[0]}" "${A[@]}"
}

ORIG_ARGC=$#      # remembered so a bare invocation (no options) defaults to the wizard
while [ $# -gt 0 ]; do
  case "$1" in
    --profile) shift; PROFILES="${1:-}";;
    --target) shift; TARGET="${1:-}";;
    --operator-name) shift; OPERATOR_NAME="${1:-}";;
    --operator-role) shift; OPERATOR_ROLE="${1:-}";;
    --operator-bio) shift; OPERATOR_BIO="${1:-}";;
    --tracker) shift; TRACKER="${1:-}";;
    --tracker-writes) shift; TRACKER_WRITES="${1:-}"
      case "$TRACKER_WRITES" in
        ask|allowed) ;;
        *) die "--tracker-writes must be 'ask' (default: agent drafts, you post) or 'allowed' (agent may write to the tracker itself); got '$TRACKER_WRITES'";;
      esac;;
    --global) GLOBAL=true;;
    --profile-only) PROFILE_ONLY=true;;
    --with-plugins) shift; WITH_PLUGINS="${1:-}";;
    --with-rtk) WITH_RTK=true;;
    --no-rtk) WITH_RTK=false;;
    --with-mcp) shift; WITH_MCP="${1:-}";;
    --with-skills) WITH_SKILLS=true;;
    --with-hooks) WITH_HOOKS=true;;
    --with-handoff-hooks) WITH_HANDOFF_HOOKS=true;;
    --with-ui-design-hook) WITH_UI_DESIGN_HOOK=true;;
    --design-system) shift; DESIGN_SYSTEM="${1:-}"
      case "$DESIGN_SYSTEM" in
        skip|stub|generate|catalog:?*) ;;
        *) die "--design-system must be skip | stub | catalog:<slug> | generate (got '$DESIGN_SYSTEM')";;
      esac;;
    --update-plugins) DO_UPDATE_PLUGINS=true;;
    --doctor) DO_DOCTOR=true;;
    --export-instructions) DO_EXPORT=true;;
    --org-policy) DO_ORG_POLICY=true;;
    --wizard) DO_WIZARD=true;;
    --self-update) DO_SELF_UPDATE=true;;
    --from) shift; SELF_UPDATE_REMOTE="${1:-}";;
    --no-reassemble) NO_REASSEMBLE=true;;
    --uninstall) DO_UNINSTALL=true;;
    --safety) shift; SAFETY="${1:-}";;
    --assemble-only) ASSEMBLE_ONLY=true;;
    --also-agents-md) ALSO_AGENTS_MD=true;;
    --also-gemini-md) ALSO_GEMINI_MD=true;;
    --force) FORCE=true;;
    --dry-run) DRY_RUN=true;;
    --help|-h) usage;;
    *) die "Unknown option: $1 (try --help)";;
  esac
  shift
done

# ---- wizard (interactive front-end; re-execs this script with built flags) -
# The wizard is the DEFAULT: bare `./setup.sh` (no options) runs it. The WIZARD_RUN
# guard stops a wizard-built re-exec from looping back in if its arg list were empty.
if $DO_WIZARD || { [ "$ORIG_ARGC" -eq 0 ] && [ "${WIZARD_RUN:-}" != 1 ]; }; then
  [ -t 0 ] || say "(reading wizard answers from a pipe — non-interactive)"
  run_wizard
  exit 0
fi

case "$SAFETY" in cautious|trusted) ;; *) die "--safety must be 'cautious' or 'trusted' (got: '$SAFETY')";; esac

# ---- standalone actions ----------------------------------------------------
if $DO_DOCTOR; then
  say "Harness doctor — $CC_DIR"
  [ -f "$CC_DIR/settings.json" ] && ok "settings.json present" || warn "no ~/.claude/settings.json"
  if [ -f "$CC_DIR/settings.json" ] && command -v jq >/dev/null 2>&1; then
    for k in statusLine effortLevel autoMemoryEnabled enabledPlugins; do
      v=$(jq -r ".${k} // empty" "$CC_DIR/settings.json" 2>/dev/null)
      [ -n "$v" ] && ok "settings.$k set" || warn "settings.$k missing"
    done
  fi
  [ -f "$CC_DIR/statusline-command.sh" ] && ok "statusline installed" || warn "no statusline-command.sh"
  if [ -f "$CC_DIR/CLAUDE.md" ]; then
    ok "global ~/.claude/CLAUDE.md present ($(wc -l < "$CC_DIR/CLAUDE.md") lines)"
    [ -f "$HARNESS_DIR/scripts/lint-leanness.sh" ] && bash "$HARNESS_DIR/scripts/lint-leanness.sh" "$CC_DIR/CLAUDE.md" 2>/dev/null | sed 's/^/  /'
  else
    warn "no global CLAUDE.md (per-project only)"
  fi
  [ -d "$CC_DIR/skills" ] && ok "skills dir: $(ls -1 "$CC_DIR/skills" 2>/dev/null | wc -l | tr -d ' ') skill(s)" || warn "no ~/.claude/skills"
  if command -v claude >/dev/null 2>&1; then ok "'claude' CLI on PATH"; else warn "'claude' CLI not on PATH (plugin install/update unavailable from script)"; fi
  [ -d "$CC_DIR/plugins" ] && ok "plugins dir present" || warn "no ~/.claude/plugins"
  exit 0
fi

if $DO_UPDATE_PLUGINS; then
  command -v claude >/dev/null 2>&1 || die "'claude' CLI not on PATH — update in-app with /plugin update."
  say "Updating installed plugins to latest"
  claude plugin update >/dev/null 2>&1 && ok "plugins updated" || warn "update reported issues — try /plugin update in-app"
  exit 0
fi

# ---- helpers ---------------------------------------------------------------
# Resolve --profile auto by inspecting the target project (before validation).
if [ "${PROFILES:-}" = auto ]; then
  _autodir="${TARGET:-$(pwd)}"
  PROFILES="$(detect_profile "$_autodir")"
  say "auto-detected profile: $(c '1;36' "$PROFILES")  (from the files in $_autodir)"
fi
PROFILE_ARR=()
if [ -n "$PROFILES" ]; then
  IFS=',' read -r -a PROFILE_ARR <<< "$PROFILES"
  for p in "${PROFILE_ARR[@]}"; do
    [ -f "$HARNESS_DIR/profiles/$p.md" ] || die "No such profile: '$p'. Available: $(cd "$HARNESS_DIR/profiles" && ls *.md | sed 's/\.md//' | tr '\n' ' ')"
  done
fi

# assemble_block <include_core:true|false>  -> prints managed block to stdout (with placeholders raw)
assemble_block() {
  local include_core="$1"
  echo "$BEGIN_MARK"
  echo "<!-- Generated. Profiles: ${PROFILES:-none}. core=$include_core. Edit core/ or profiles/, then re-run setup.sh. -->"
  echo
  if [ "$include_core" = true ]; then
    for f in "$HARNESS_DIR"/core/*.md; do cat "$f"; echo; echo; done
  fi
  if [ ${#PROFILE_ARR[@]} -gt 0 ]; then
    echo "---"; echo
    echo "# Work-Type Profile(s): $PROFILES"; echo
    for p in "${PROFILE_ARR[@]}"; do cat "$HARNESS_DIR/profiles/$p.md"; echo; echo; done
  fi
  echo "$END_MARK"
}

fill_placeholders() {  # in-place on a file
  local tracker_policy
  case "$TRACKER_WRITES" in
    allowed) tracker_policy="$TRACKER_POLICY_ALLOWED";;
    *)       tracker_policy="$TRACKER_POLICY_ASK";;
  esac
  sed -i \
    -e "s|{{OPERATOR_NAME}}|$OPERATOR_NAME|g" \
    -e "s|{{OPERATOR_ROLE}}|$OPERATOR_ROLE|g" \
    -e "s|{{OPERATOR_BIO}}|$OPERATOR_BIO|g" \
    -e "s|{{TRACKER}}|$TRACKER|g" \
    -e "s|{{TRACKER_POLICY}}|$tracker_policy|g" \
    "$1"
  sed -i -E 's/\{\{([A-Z_]+)\}\}/[TODO: set \1]/g' "$1"
}

# Name the placeholders the human still has to fill, instead of hoping they skim for them.
# Deliberately generic (any {{TOKEN}} with no flag renders as "[TODO: set TOKEN]"), so a new
# placeholder is surfaced the day it is added rather than the day someone notices it shipped blank.
# Today that means BRAND_PALETTE/BRAND_FONT under creative-design: an agent reading "[TODO: set
# BRAND_PALETTE]" as its brand rule will either stop and ask or quietly invent one, and a silent
# "resolve any [TODO]" in a wall of next-steps is how it stays unfilled.
report_todos() {  # <rendered-file>
  local f="$1" todos
  [ -f "$f" ] || return 0
  todos="$(grep -oE '\[TODO: set [A-Z_]+\]' "$f" 2>/dev/null \
           | sed -E 's/\[TODO: set ([A-Z_]+)\]/\1/' | sort -u | tr '\n' ' ' | sed 's/ *$//')" || true
  [ -n "$todos" ] || return 0
  echo
  warn "$(basename "$f") is missing $(printf '%s' "$todos" | wc -w | tr -d ' ') value(s) only you can give: $todos"
  echo "      They render as [TODO: set …] inside the rules, so the assistant will ask you for them"
  echo "      (or guess). Fill them in: $f"
}

backup_file() {  # <path> -> if it exists, save a timestamped copy beside it; echo the backup path
  [ -f "$1" ] || return 0
  local bak; bak="$1.bak.$(date +%Y%m%d-%H%M%S)"
  cp "$1" "$bak" && printf '%s' "$bak"
}

write_first_steps() {  # <dest> — the "first 30 minutes" card, filled + write-if-absent (don't clobber edits)
  local dest="$1"
  [ -e "$dest" ] && { ok "FIRST-STEPS.md already present — left as-is"; return 0; }
  sed -e "s|{{PROFILES}}|${PROFILES:-none}|g" \
      -e "s|{{SAFETY}}|$SAFETY|g" \
      -e "s|{{TARGET_NAME}}|$(basename "$TARGET")|g" \
      "$HARNESS_DIR/templates/first-steps.md" > "$dest" && ok "added FIRST-STEPS.md (your getting-started card)"
}

write_managed() {  # <dest> <tmpfile-with-block>
  local dest="$1" TMP="$2"
  if [ -f "$dest" ] && locate_managed_block "$dest"; then
    # Existing harness install: replace ONLY our managed block (old or new markers) — your
    # other edits are left alone. The block, markers included, is swapped for the new one.
    awk -v b="$FOUND_BEGIN" -v e="$FOUND_END" -v repl="$TMP" '
      $0==b && !done {while((getline line < repl)>0) print line; done=1; skip=1; next}
      $0==e && skip  {skip=0; next}
      skip!=1 {print}
    ' "$dest" > "$dest.new"
    grep -qF "$END_MARK" "$dest.new" || echo "$END_MARK" >> "$dest.new"
    mv "$dest.new" "$dest"; ok "updated the harness section in $(basename "$dest") (your other content left untouched)"
    [ "$FOUND_BEGIN" = "$BEGIN_MARK" ] || ok "migrated the section markers to the Agentsmith brand"
  elif [ -f "$dest" ] && ! $FORCE; then
    # You already have your own file with no harness section: back it up, then add ours at the end.
    local bak; bak="$(backup_file "$dest")"
    { echo; cat "$TMP"; } >> "$dest"
    ok "added the harness section to your existing $(basename "$dest")"
    [ -n "$bak" ] && ok "backup of the original saved: $(basename "$bak")"
  else
    # New file, or --force replacing a file that has no harness section.
    if [ -f "$dest" ]; then
      local bak; bak="$(backup_file "$dest")"
      warn "--force replaced the ENTIRE $(basename "$dest") — original backed up to $(basename "$bak")"
    fi
    cp "$TMP" "$dest"; ok "wrote $(basename "$dest")"
  fi
}

assemble_to() {  # <dest> <include_core>
  local dest="$1" include_core="$2"
  local TMP; TMP="$(mktemp)"
  assemble_block "$include_core" > "$TMP"
  fill_placeholders "$TMP"
  if $DRY_RUN; then say "DRY RUN — $(basename "$dest") would be $(wc -l < "$TMP") lines (core=$include_core, profiles=${PROFILES:-none})"; head -n 30 "$TMP"; rm -f "$TMP"; return; fi
  mkdir -p "$(dirname "$dest")"
  write_managed "$dest" "$TMP"
  rm -f "$TMP"
}

install_marketplace() { command -v claude >/dev/null 2>&1 && claude plugin marketplace add "$1" >/dev/null 2>&1 && ok "marketplace $1" || warn "add later: /plugin marketplace add $1"; }
install_plugin()      { command -v claude >/dev/null 2>&1 && claude plugin install "$1" >/dev/null 2>&1 && ok "plugin $1" || warn "install later: /plugin install $1"; }

install_global_config() {
  say "Installing global config into $CC_DIR"
  mkdir -p "$CC_DIR"
  [ -e "$CC_DIR/statusline-command.sh" ] || { cp "$HARNESS_DIR/config/statusline-command.sh" "$CC_DIR/statusline-command.sh"; chmod +x "$CC_DIR/statusline-command.sh" 2>/dev/null || true; ok "statusline installed"; }
  if [ -f "$CC_DIR/settings.json" ]; then
    cp "$CC_DIR/settings.json" "$CC_DIR/settings.json.bak.$$"
    if command -v jq >/dev/null 2>&1; then
      jq -s '.[0] * .[1]' "$CC_DIR/settings.json" "$HARNESS_DIR/config/settings.json" > "$CC_DIR/settings.json.merged" \
        && mv "$CC_DIR/settings.json.merged" "$CC_DIR/settings.json" && ok "merged settings.json (backup: settings.json.bak.$$)"
    else
      warn "jq not found — settings.json left as-is. Merge config/settings.json by hand (INSTALL.md)."
    fi
  else
    cp "$HARNESS_DIR/config/settings.json" "$CC_DIR/settings.json"; ok "wrote settings.json"
  fi
  # Cautious safety: don't leave the dangerous-mode confirmation silently disabled globally.
  # (config/settings.json ships skipDangerousModePermissionPrompt:true for the trusted box.)
  if [ "$SAFETY" = cautious ] && [ -f "$CC_DIR/settings.json" ]; then
    if command -v jq >/dev/null 2>&1; then
      jq '.skipDangerousModePermissionPrompt=false' "$CC_DIR/settings.json" > "$CC_DIR/settings.json.tmp" \
        && mv "$CC_DIR/settings.json.tmp" "$CC_DIR/settings.json" \
        && ok "cautious: kept the dangerous-mode confirmation ON (skipDangerousModePermissionPrompt=false)"
    else
      warn "cautious: install jq (or hand-set skipDangerousModePermissionPrompt:false in ~/.claude/settings.json)"
    fi
  fi
  # universal marketplaces + plugins
  install_marketplace thedotmack/claude-mem
  install_marketplace openai/codex-plugin-cc
  for spec in superpowers@claude-plugins-official code-review@claude-plugins-official claude-mem@thedotmack codex@openai-codex; do install_plugin "$spec"; done
  # opt-in packs
  if [ -z "$WITH_PLUGINS" ] && [ -t 0 ] && [ "${WIZARD_RUN:-}" != 1 ]; then
    printf '  Optional plugin packs? Enter any of: dev-workflow stack-lsp (space-separated, blank=none): '
    read -r WITH_PLUGINS || true
  fi
  case ",$WITH_PLUGINS," in *dev-workflow*)
    say "Plugin pack: dev-workflow (latest from source)"
    install_marketplace shinpr/claude-code-workflows
    for spec in dev-workflows@claude-code-workflows dev-workflows-frontend@claude-code-workflows feature-dev@claude-plugins-official frontend-design@claude-plugins-official qodo-skills@claude-plugins-official; do install_plugin "$spec"; done ;;
  esac
  case ",$WITH_PLUGINS," in *stack-lsp*)
    say "Plugin pack: stack-lsp (example: Go + web — swap LSPs for your languages)"
    install_marketplace gopherguides/gopher-ai
    install_marketplace Piebald-AI/claude-code-lsps
    for spec in go-dev@gopher-ai tailwind@gopher-ai gopls@claude-code-lsps typescript-lsp@claude-plugins-official gopls-lsp@claude-plugins-official; do install_plugin "$spec"; done ;;
  esac
  # rtk — token-compressing CLI proxy (github.com/rtk-ai/rtk). Default-ON for code profiles; --no-rtk opts out.
  rtk_wanted && install_rtk
  $WITH_SKILLS && install_skills "$SKILLS_DEST"
  $WITH_HANDOFF_HOOKS && install_handoff_hooks
  $WITH_UI_DESIGN_HOOK && install_ui_design_hook
  return 0   # never let a false trailing `&&` (both hooks/skills off) abort the caller under set -e
}

install_skills() {  # [dest] — default global ~/.claude/skills; project mode passes $TARGET/.claude/skills
  local dest="${1:-$CC_DIR/skills}"
  mkdir -p "$dest"
  local n=0
  for d in "$HARNESS_DIR"/skills/*/; do
    [ -f "$d/SKILL.md" ] || continue
    local name; name="$(basename "$d")"
    if [ -e "$dest/$name" ] && ! $FORCE; then warn "skill '$name' exists — skipped (use --force)"; continue; fi
    cp -r "$d" "$dest/$name"; ok "skill $name"; n=$((n+1))
  done
  ok "skills installed: $n (into $dest/)"
}

rtk_wanted() {  # install rtk? explicit flag wins; else auto = only for code profiles (software-dev/devops-setup)
  case "$WITH_RTK" in true) return 0;; false) return 1;; esac
  local p
  for p in "${PROFILE_ARR[@]:-}"; do
    case "$p" in software-dev|devops-setup) return 0;; esac
  done
  return 1
}

install_rtk() {  # install the rtk binary (per-OS), then let rtk wire its own Claude Code hook
  if command -v rtk >/dev/null 2>&1; then
    ok "rtk already installed ($(rtk --version 2>/dev/null || echo present))"
  else
    say "Installing rtk — token-compressing CLI proxy (github.com/rtk-ai/rtk)"
    if command -v brew >/dev/null 2>&1; then
      brew install rtk >/dev/null 2>&1 || { warn "rtk: 'brew install rtk' failed — install by hand: https://github.com/rtk-ai/rtk#installation"; return 0; }
    else
      curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/master/install.sh | sh >/dev/null 2>&1 \
        || { warn "rtk: installer failed — install by hand: https://github.com/rtk-ai/rtk#installation"; return 0; }
    fi
  fi
  command -v rtk >/dev/null 2>&1 || { warn "rtk installed but not on PATH — add \$HOME/.local/bin to PATH, then run: rtk init -g --auto-patch"; return 0; }
  command -v rg  >/dev/null 2>&1 || warn "rtk: ripgrep (rg) not on PATH — some filters need it (install ripgrep via brew/apt/winget)"
  # rtk writes its own PreToolUse hook + RTK.md + settings.json entry + @RTK.md import — idempotent, no prompt
  if rtk init -g --auto-patch >/dev/null 2>&1; then ok "rtk wired into Claude Code (hook + RTK.md) — restart Claude Code to load it"
  else warn "rtk: 'rtk init -g --auto-patch' failed — run it by hand to wire the hook"; fi
  return 0
}

build_verify_conf() {  # <dest> — generate .harness/verify.conf from the chosen profile preset(s)
  local dest="$1"
  {
    echo "# .harness/verify.conf — generated for profile(s): $PROFILES"
    echo "# One phase per line:  Label :: shell command. Runs in order; first failure stops the run."
    echo "# This is YOUR definition of \"shippable\". Uncomment + edit the phases that fit this project,"
    echo "# then DELETE the placeholder line below once at least one real phase is active."
    echo
    local p preset
    for p in "${PROFILE_ARR[@]}"; do
      preset="$HARNESS_DIR/config/verify-presets/$p.conf"
      [ -f "$preset" ] && { cat "$preset"; echo; }
    done
    echo "# Placeholder that FAILS ON PURPOSE, so verify.sh stays RED until you wire real phases."
    echo "# A green verify that checks nothing is worse than none — it lies. Make the presets above"
    echo "# real (uncomment + edit), then DELETE this line:"
    echo "unwired :: echo \"verify.conf ($PROFILES) has only this placeholder — wire real build/test/lint phases in .harness/verify.conf, then delete this line\" >&2; exit 1"
  } > "$dest"
}

add_mcp_servers() {  # merge chosen servers from config/mcp.example.json into <TARGET>/.mcp.json
  local names="$1" src="$HARNESS_DIR/config/mcp.example.json" dest="$TARGET/.mcp.json"
  local have; have="$(command -v jq >/dev/null 2>&1 && jq -r '.mcpServers|keys|join(", ")' "$src" 2>/dev/null || echo '')"
  if ! command -v jq >/dev/null 2>&1; then
    warn "--with-mcp needs jq. Copy the blocks you want from config/mcp.example.json into $dest by hand."
    return
  fi
  [ -f "$dest" ] || echo '{ "mcpServers": {} }' > "$dest"
  local n added=0 arr=(); IFS=',' read -r -a arr <<< "$names"
  for n in "${arr[@]}"; do
    n="$(echo "$n" | tr -d '[:space:]')"; [ -z "$n" ] && continue
    local block; block="$(jq -c --arg k "$n" '.mcpServers[$k] // empty | del(._use)' "$src" 2>/dev/null)"
    if [ -z "$block" ]; then warn "no MCP server '$n' in mcp.example.json (available: $have)"; continue; fi
    jq --arg k "$n" --argjson v "$block" '.mcpServers[$k] = $v' "$dest" > "$dest.tmp" \
      && mv "$dest.tmp" "$dest" && { ok "MCP server '$n' → .mcp.json"; added=$((added+1)); } \
      || { warn "failed to merge '$n' (left .mcp.json unchanged)"; rm -f "$dest.tmp"; }
  done
  [ "$added" -gt 0 ] && ok ".mcp.json now serves: $(jq -r '.mcpServers|keys|join(", ")' "$dest")"
}

export_instructions() {  # print a portable, paste-ready instructions blob to STDOUT
  [ -n "$PROFILES" ] || die "Pick a profile to export: --profile <name[,name]> --export-instructions"
  local TMP; TMP="$(mktemp)"
  {
    echo "<!-- Agentsmith — universal agent harness — portable instructions (core + ${PROFILES}). -->"
    echo "<!-- Paste this WHOLE block into a surface that has no on-disk CLAUDE.md: a claude.ai -->"
    echo "<!-- Project's custom-instructions box, Claude Cowork, or any assistant's system-prompt -->"
    echo "<!-- field. On-disk Claude Code should run setup.sh for a real CLAUDE.md instead. To -->"
    echo "<!-- change this, edit core/ or profiles/ and re-export — don't hand-edit the paste. -->"
    echo
    for f in "$HARNESS_DIR"/core/*.md; do cat "$f"; echo; echo; done
    echo "---"; echo
    echo "# Work-Type Profile(s): $PROFILES"; echo
    for p in "${PROFILE_ARR[@]}"; do cat "$HARNESS_DIR/profiles/$p.md"; echo; echo; done
  } > "$TMP"
  fill_placeholders "$TMP"
  cat "$TMP"
  local lines; lines="$(wc -l < "$TMP" | tr -d ' ')"; rm -f "$TMP"
  # Guidance on STDERR so a plain `> file` redirect captures only the blob.
  { echo; say "Exported portable instructions ($lines lines) to stdout."
    echo "  Save:   ./setup.sh --profile $PROFILES --export-instructions > harness-instructions.md"
    echo "  Copy:   ./setup.sh --profile $PROFILES --export-instructions | pbcopy   # (xclip/clip on Linux/Windows)"
    echo "  Then paste into the project's custom-instructions / system-prompt box."; } >&2
}

org_policy_install() {  # machine-wide managed CLAUDE.md + hardened settings (all users on this box)
  local org_dir
  case "$(uname -s)" in
    Linux*)               org_dir="/etc/claude-code" ;;
    Darwin*)              org_dir="/Library/Application Support/ClaudeCode" ;;
    CYGWIN*|MINGW*|MSYS*) org_dir="/c/Program Files/ClaudeCode" ;;   # best-effort; prefer setup.ps1 on Windows
    *)                    org_dir="/etc/claude-code" ;;
  esac
  org_dir="${HARNESS_ORG_DIR:-$org_dir}"   # override target dir (non-standard installs / testing)
  local org_md="$org_dir/CLAUDE.md" org_settings="$org_dir/managed-settings.json"
  local hardened="$HARNESS_DIR/config/managed-settings.hardened.json"

  say "Org-policy install — applies to EVERY user + project on this machine"
  echo "  managed CLAUDE.md : $org_md   (loads before user/project CLAUDE.md, cannot be excluded)"
  echo "  managed settings  : $org_settings   (highest precedence; CLI/user/project cannot override)"
  echo "  hardening         : disableBypassPermissionsMode + disableAutoMode  (no dangerous/auto mode)"
  [ -n "$PROFILES" ] && echo "  profile(s) baked in: $PROFILES" || echo "  content: universal core only (add --profile to bake one in)"

  if $DRY_RUN; then say "DRY RUN — nothing written."; return; fi

  if ! mkdir -p "$org_dir" 2>/dev/null; then
    die "cannot write $org_dir — managed config needs root. Re-run: sudo ./setup.sh --org-policy${PROFILES:+ --profile $PROFILES}"
  fi

  # 1) managed org CLAUDE.md = core (+ optional profile), via the same managed-block writer
  assemble_to "$org_md" true

  # 2) hardened managed settings — merge into any existing org policy, don't clobber allow/deny
  if [ -f "$org_settings" ] && command -v jq >/dev/null 2>&1; then
    cp "$org_settings" "$org_settings.bak.$$"
    if jq -s '.[0] * .[1]' "$org_settings" "$hardened" > "$org_settings.merged" 2>/dev/null; then
      mv "$org_settings.merged" "$org_settings"; ok "merged hardening into existing managed-settings.json (backup: .bak.$$)"
    else
      rm -f "$org_settings.merged"; warn "could not merge — left existing managed-settings.json as-is; apply $hardened by hand"
    fi
  else
    cp "$hardened" "$org_settings"; ok "wrote hardened managed-settings.json"
  fi
  echo; say "$(c '1;32' 'Org policy in force.')"
  echo "  Verify on this box:  claude  (then /status — bypass/dangerous mode should be unavailable)"
  echo "  Admins: extend $org_settings with org allow/deny rules as needed."
}

install_handoff_hooks() {  # global: 'handoff' keyword hook (reliable) + best-effort ctx-% Stop nudge
  command -v jq >/dev/null 2>&1 || die "--with-handoff-hooks needs jq (it edits settings.json)."
  mkdir -p "$CC_DIR/hooks"
  cp "$HARNESS_DIR/hooks/handoff-on-keyword.sh"   "$CC_DIR/hooks/handoff-on-keyword.sh"
  cp "$HARNESS_DIR/hooks/context-budget-nudge.sh" "$CC_DIR/hooks/context-budget-nudge.sh"
  chmod +x "$CC_DIR/hooks/"*.sh 2>/dev/null || true
  ok "handoff hook scripts → $CC_DIR/hooks/"
  # refresh the statusline so it persists the context-% signal the Stop hook reads
  cp "$HARNESS_DIR/config/statusline-command.sh" "$CC_DIR/statusline-command.sh"; chmod +x "$CC_DIR/statusline-command.sh" 2>/dev/null || true
  [ -f "$CC_DIR/settings.json" ] || echo '{}' > "$CC_DIR/settings.json"
  local kw="bash ~/.claude/hooks/handoff-on-keyword.sh"
  local st="bash ~/.claude/hooks/context-budget-nudge.sh"
  if grep -qF "$kw" "$CC_DIR/settings.json" 2>/dev/null; then
    ok "handoff hooks already wired in settings.json"
  else
    cp "$CC_DIR/settings.json" "$CC_DIR/settings.json.bak.$$"
    if jq --arg kw "$kw" --arg st "$st" '
        .statusLine = (.statusLine // {type:"command", command:"bash ~/.claude/statusline-command.sh"})
        | .hooks.UserPromptSubmit = ((.hooks.UserPromptSubmit // []) + [{hooks:[{type:"command", command:$kw}]}])
        | .hooks.Stop = ((.hooks.Stop // []) + [{hooks:[{type:"command", command:$st}]}])
      ' "$CC_DIR/settings.json" > "$CC_DIR/settings.json.new"; then
      mv "$CC_DIR/settings.json.new" "$CC_DIR/settings.json"; ok "wired handoff hooks into settings.json (backup .bak.$$)"
    else
      rm -f "$CC_DIR/settings.json.new"; warn "jq merge failed — add the snippet from hooks/README.md by hand"
    fi
  fi
  echo; say "$(c '1;32' 'Handoff hooks installed.')"
  echo "  • 'handoff' / 'wrap up' in a prompt → injects the safe-state + recall-prompt protocol (reliable)"
  echo "  • context ≥ ${HANDOFF_PCT_THRESHOLD:-30}% used → one best-effort nudge to hand off early (fragile — see hooks/README.md)"
}

# ---- design system (software-dev UI projects) ------------------------------
# Establish a design system so UI isn't built ad-hoc and off-brand. The durable artifact is a
# project-root DESIGN.md the agent reads before every UI change; the software-dev profile points at
# it every turn, and (optionally) the ui-design-reminder hook nudges on UI edits.
print_design_sources() {
  echo "      Fill DESIGN.md three ways (also in its header):"
  echo "        • bring your brand — transcribe your brand guide + assets into it"
  echo "        • pick a ready-made one — https://github.com/VoltAgent/awesome-design-md (design-md/<brand>/DESIGN.md)"
  echo "        • generate one — /plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill"
  echo "                         /plugin install ui-ux-pro-max@ui-ux-pro-max-skill   (needs Python 3)"
}
scaffold_design_system() {  # honor --design-system for a UI project. Idempotent: never overwrites a DESIGN.md.
  case "$DESIGN_SYSTEM" in ""|skip) return 0 ;; esac
  local dest="$TARGET/DESIGN.md"
  if [ -e "$dest" ]; then ok "DESIGN.md already present — left as-is"; return 0; fi
  case "$DESIGN_SYSTEM" in
    stub)
      cp "$HARNESS_DIR/templates/design-system.md" "$dest"; ok "added DESIGN.md (design-system template — fill in the [TODO]s)"
      print_design_sources ;;
    catalog:*)
      local slug="${DESIGN_SYSTEM#catalog:}"
      local url="https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/${slug}/DESIGN.md"
      say "Fetching a starter DESIGN.md for '$slug' from the awesome-design-md catalog…"
      # Degrade gracefully (infra idempotency): offline or an unknown slug falls back to the template.
      if command -v curl >/dev/null 2>&1 && curl -fsSL "$url" -o "$dest" 2>/dev/null && [ -s "$dest" ]; then
        ok "added DESIGN.md from catalog:$slug (review + adapt it to your brand)"
      else
        rm -f "$dest"
        warn "could not fetch catalog:$slug (offline, or no such brand) — using the template instead."
        echo "      Browse brands: https://github.com/VoltAgent/awesome-design-md/tree/main/design-md"
        cp "$HARNESS_DIR/templates/design-system.md" "$dest"; ok "added DESIGN.md (template fallback)"
      fi ;;
    generate)
      # setup.sh (bash) CANNOT run Claude Code /plugin commands — never a silent half-install; scaffold
      # the template so there's always a DESIGN.md, and print the exact generate steps to run yourself.
      cp "$HARNESS_DIR/templates/design-system.md" "$dest"; ok "added DESIGN.md (template — ui-ux-pro-max will fill it)"
      say "Generate the design system with ui-ux-pro-max, then it lands in DESIGN.md:"
      echo "        /plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill"
      echo "        /plugin install ui-ux-pro-max@ui-ux-pro-max-skill"
      echo "        …then ask the assistant to generate a design system into DESIGN.md."
      echo "      Or via its npm CLI (needs Node + Python 3):  npm i -g ui-ux-pro-max-cli && uipro" ;;
  esac
}
install_ui_design_hook() {  # global PreToolUse nudge; warn-and-skip (don't abort setup) if jq is missing
  if ! command -v jq >/dev/null 2>&1; then
    warn "UI design-system hook needs jq to edit settings.json — skipped (install jq, then --with-ui-design-hook)."
    return 0
  fi
  mkdir -p "$CC_DIR/hooks"
  cp "$HARNESS_DIR/hooks/ui-design-reminder.sh" "$CC_DIR/hooks/ui-design-reminder.sh"
  chmod +x "$CC_DIR/hooks/ui-design-reminder.sh" 2>/dev/null || true
  [ -f "$CC_DIR/settings.json" ] || echo '{}' > "$CC_DIR/settings.json"
  local cmd="bash ~/.claude/hooks/ui-design-reminder.sh"
  if grep -qF "$cmd" "$CC_DIR/settings.json" 2>/dev/null; then
    ok "UI design-system hook already wired in settings.json"; return 0
  fi
  cp "$CC_DIR/settings.json" "$CC_DIR/settings.json.bak.$$"
  if jq --arg c "$cmd" '.hooks.PreToolUse = ((.hooks.PreToolUse // []) + [{matcher:"Edit|Write|MultiEdit", hooks:[{type:"command", command:$c}]}])' \
       "$CC_DIR/settings.json" > "$CC_DIR/settings.json.new"; then
    mv "$CC_DIR/settings.json.new" "$CC_DIR/settings.json"; ok "wired UI design-system hook into settings.json (backup .bak.$$)"
  else
    rm -f "$CC_DIR/settings.json.new"; warn "jq merge failed — add the PreToolUse snippet from hooks/README.md by hand"
  fi
}

# ---- self-update -----------------------------------------------------------
# Pull the latest harness into the checkout this script lives in, then re-assemble
# the managed CLAUDE.md blocks. Remote resolution + auth are configurable; nothing
# secret is ever written to a tracked file (Rule: no live creds in the repo).
resolve_self_update_remote() {  # echoes the remote URL, or returns 1
  if [ -n "$SELF_UPDATE_REMOTE" ]; then echo "$SELF_UPDATE_REMOTE"; return 0; fi
  if [ -n "${HARNESS_REMOTE:-}" ]; then echo "$HARNESS_REMOTE"; return 0; fi
  if [ -f "$HARNESS_DIR/.harness/remote" ]; then
    local r; r="$(grep -vE '^[[:space:]]*(#|$)' "$HARNESS_DIR/.harness/remote" 2>/dev/null | head -n1 | tr -d '[:space:]')"
    [ -n "$r" ] && { echo "$r"; return 0; }
  fi
  local o; o="$(git -C "$HARNESS_DIR" remote get-url origin 2>/dev/null || true)"
  [ -n "$o" ] && { echo "$o"; return 0; }
  return 1
}

# Reverse-recover the operator fields from an already-rendered managed block, so re-assembly
# with fresh core/ doesn't regress them to [TODO]. Anchors are the stable identity/tracker lines
# in core/. Returns 1 if the identity line is absent.
# NOTE: the TRACKER anchor tracks R7's wording — it moved from "File it in **X**" to
# "The team's record is **X**" when consent was split out (feedback 0002). Both are matched so a
# re-assembly over a pre-consent CLAUDE.md still recovers the tracker instead of blanking it.
recover_operator_fields() {  # <rendered-file>
  local file="$1" line bio trk
  line="$(grep -m1 ' is the lead\. Role: ' "$file" 2>/dev/null || true)"
  [ -n "$line" ] || return 1
  OPERATOR_NAME="$(printf '%s' "$line" | sed -E 's/^\*\*(.*)\*\* is the lead\. Role: \*\*(.*)\*\*\..*/\1/')"
  OPERATOR_ROLE="$(printf '%s' "$line" | sed -E 's/^\*\*(.*)\*\* is the lead\. Role: \*\*(.*)\*\*\..*/\2/')"
  # BIO = first non-blank line between the identity line and "When you explain anything:"
  bio="$(awk '/ is the lead\. Role: /{f=1; next} f && /When you explain anything:/{exit} f && NF {print; exit}' "$file")"
  [ -n "$bio" ] && OPERATOR_BIO="$bio"
  # TRACKER = the text inside the bold marker on R7's record line. Current wording first
  # ("The team's record is **X**"), then pre-consent wording ("File it in **X**").
  trk="$(grep -m1 "The team's record is \*\*" "$file" 2>/dev/null | sed -E "s/.*The team's record is \*\*([^*]+)\*\*.*/\1/")"
  [ -n "$trk" ] || trk="$(grep -m1 'File it in \*\*' "$file" 2>/dev/null | sed -E 's/.*File it in \*\*([^*]+)\*\*.*/\1/')"
  [ -n "$trk" ] && TRACKER="$trk"
  # TRACKER_WRITES = which policy sentence R7 rendered. Fail CLOSED: a pre-consent block has no
  # policy sentence, and the writes it was doing were inferred from a pointer, never granted
  # (feedback 0002) — so an upgrade must NOT silently carry that forward. Re-ask instead.
  if grep -q 'writes are authorized' "$file" 2>/dev/null; then
    TRACKER_WRITES=allowed
  elif grep -q 'writes are NOT authorized' "$file" 2>/dev/null; then
    TRACKER_WRITES=ask
  else
    TRACKER_WRITES=ask
    grep -q 'File it in \*\*' "$file" 2>/dev/null && \
      warn "$(basename "$file"): pre-consent rules — tracker writes now default to 'ask' (agent drafts, you post). Re-run with --tracker-writes allowed to let it write to $TRACKER itself."
  fi
  return 0
}

# Fill any operator field still unset with its generic default. Called LAST, after recovery and
# after explicit flags, so "" only ever means "nobody supplied this" — never "blank it".
apply_operator_defaults() {
  [ -n "$OPERATOR_NAME" ]   || OPERATOR_NAME="$DEFAULT_OPERATOR_NAME"
  [ -n "$OPERATOR_ROLE" ]   || OPERATOR_ROLE="$DEFAULT_OPERATOR_ROLE"
  [ -n "$OPERATOR_BIO" ]    || OPERATOR_BIO="$DEFAULT_OPERATOR_BIO"
  [ -n "$TRACKER" ]         || TRACKER="$DEFAULT_TRACKER"
  [ -n "$TRACKER_WRITES" ]  || TRACKER_WRITES="$DEFAULT_TRACKER_WRITES"
}

# Decide who the operator is for a file we are about to (re)write: recover what is already in it,
# let explicitly-passed flags win, then fall back to defaults. Feedback 0003 — the harness already
# knew how to do this (reassemble_one has called recover_operator_fields since forever, so that
# re-assembly "doesn't regress them to [TODO]"), it just never did it on the two paths a user
# actually re-runs. The information was sitting in the file being overwritten.
resolve_operator_identity() {  # <dest-file>
  local dest="$1"
  # Snapshot what came from the command line BEFORE recovery overwrites the globals.
  local x_name="$OPERATOR_NAME" x_role="$OPERATOR_ROLE" x_bio="$OPERATOR_BIO" \
        x_trk="$TRACKER" x_writes="$TRACKER_WRITES"
  if [ -f "$dest" ] && locate_managed_block "$dest" && recover_operator_fields "$dest"; then
    ok "kept the operator identity already in $(basename "$dest") ($OPERATOR_NAME / $OPERATOR_ROLE) — pass --operator-name/--operator-role to change it"
  fi
  # Explicit flags beat anything recovered: you asked for it by name.
  [ -n "$x_name" ]   && OPERATOR_NAME="$x_name"
  [ -n "$x_role" ]   && OPERATOR_ROLE="$x_role"
  [ -n "$x_bio" ]    && OPERATOR_BIO="$x_bio"
  [ -n "$x_trk" ]    && TRACKER="$x_trk"
  [ -n "$x_writes" ] && TRACKER_WRITES="$x_writes"
  apply_operator_defaults
}

reassemble_one() {  # <rendered-file-with-managed-block>
  local file="$1" gen profs core include_core p
  gen="$(grep -m1 'Generated\. Profiles:' "$file" 2>/dev/null || true)"
  if [ -z "$gen" ]; then
    warn "$(basename "$file"): managed block lacks generator metadata — skipped (re-run setup.sh with explicit --profile)."
    return 1
  fi
  profs="$(printf '%s' "$gen" | sed -E 's/.*Profiles: ([^.]*)\..*/\1/')"
  core="$(printf '%s' "$gen" | sed -E 's/.*core=([A-Za-z]+).*/\1/')"
  [ "$profs" = "none" ] && profs=""
  PROFILES="$profs"; PROFILE_ARR=()
  if [ -n "$PROFILES" ]; then
    IFS=',' read -r -a PROFILE_ARR <<< "$PROFILES"
    for p in "${PROFILE_ARR[@]}"; do
      [ -f "$HARNESS_DIR/profiles/$p.md" ] || { warn "$(basename "$file"): profile '$p' no longer ships in the updated harness — skipped."; return 1; }
    done
  fi
  include_core=true; [ "$core" = "false" ] && include_core=false
  recover_operator_fields "$file" || warn "$(basename "$file"): couldn't recover operator name/role — falling back to the generic defaults."
  apply_operator_defaults
  assemble_to "$file" "$include_core"
}

reassemble_managed_targets() {
  say "Re-assembling managed blocks from the updated harness"
  local here t n=0 targets=() seen=" " f
  here="${TARGET:-$(pwd)}"
  [ -f "$CC_DIR/CLAUDE.md" ] && targets+=("$CC_DIR/CLAUDE.md")
  for f in CLAUDE.md AGENTS.md GEMINI.md; do [ -f "$here/$f" ] && targets+=("$here/$f"); done
  for t in "${targets[@]}"; do
    case "$seen" in *" $t "*) continue;; esac
    seen="$seen$t "
    locate_managed_block "$t" || continue
    reassemble_one "$t" && n=$((n+1)) || true
  done
  if [ "$n" -gt 0 ]; then ok "re-assembled $n managed target(s)."
  else warn "no managed targets found (looked in $CC_DIR and $here). Re-run setup.sh where your CLAUDE.md lives to refresh it."; fi
}

self_update() {
  command -v git >/dev/null 2>&1 || die "--self-update needs git on PATH."
  git -C "$HARNESS_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || die "Harness dir is not a git checkout: $HARNESS_DIR — --self-update pulls into the checkout setup.sh lives in. Clone the harness as a git repo and run its setup.sh."

  local remote
  remote="$(resolve_self_update_remote)" || die "No update remote configured. Provide one of: --from <url> | HARNESS_REMOTE=<url> env | a one-URL .harness/remote file | a git 'origin' on the checkout."

  say "Self-update — harness checkout: $HARNESS_DIR"
  echo "  remote: $remote"

  [ -z "$(git -C "$HARNESS_DIR" status --porcelain 2>/dev/null)" ] \
    || die "Harness checkout has uncommitted changes — commit or stash them first (pull-in-place won't clobber local edits). See: git -C \"$HARNESS_DIR\" status"

  local branch; branch="$(git -C "$HARNESS_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"
  [ "$branch" = "HEAD" ] && die "Harness checkout is in detached-HEAD state — check out a branch first (e.g. git -C \"$HARNESS_DIR\" checkout master)."

  local scheme; case "$remote" in
    git@*|ssh://*) scheme="SSH key" ;;
    https://*)     scheme="HTTPS + \$HARNESS_GH_TOKEN" ;;
    *)             scheme="local/other transport" ;;
  esac

  if $DRY_RUN; then
    say "DRY RUN — would: git -C \"$HARNESS_DIR\" pull --ff-only ($scheme) onto '$branch', then re-assemble managed targets. Nothing pulled or written."
    return 0
  fi

  local before; before="$(git -C "$HARNESS_DIR" rev-parse HEAD)"
  case "$remote" in
    git@*|ssh://*)
      say "Auth: SSH key (remote is an SSH URL)"
      GIT_TERMINAL_PROMPT=0 git -C "$HARNESS_DIR" pull --ff-only "$remote" "$branch" \
        || die "git pull failed (SSH). Check the box has an SSH key with read access (ssh -T the host) and that a fast-forward is possible (no diverging local commits)." ;;
    https://*)
      say "Auth: HTTPS — token from \$HARNESS_GH_TOKEN (never written to disk)"
      [ -n "${HARNESS_GH_TOKEN:-}" ] || die "HTTPS remote needs a token: export HARNESS_GH_TOKEN=<PAT with read access> and re-run. (Read from env only; never stored.)"
      local askpass auth_url
      askpass="$(mktemp)"; printf '#!/usr/bin/env bash\nexec printf %%s "$HARNESS_GH_TOKEN"\n' > "$askpass"; chmod 700 "$askpass"
      auth_url="$(printf '%s' "$remote" | sed -E 's#^https://#https://x-access-token@#')"
      if GIT_ASKPASS="$askpass" GIT_TERMINAL_PROMPT=0 git -C "$HARNESS_DIR" -c credential.helper= pull --ff-only "$auth_url" "$branch"; then
        rm -f "$askpass"
      else
        rm -f "$askpass"; die "git pull failed (HTTPS). Check HARNESS_GH_TOKEN has read access and that a fast-forward is possible."
      fi ;;
    *)
      say "Auth: none ($scheme)"
      GIT_TERMINAL_PROMPT=0 git -C "$HARNESS_DIR" pull --ff-only "$remote" "$branch" \
        || die "git pull failed. Ensure '$remote' is reachable and a fast-forward is possible." ;;
  esac
  local after; after="$(git -C "$HARNESS_DIR" rev-parse HEAD)"

  if [ "$before" = "$after" ]; then
    ok "Already up to date ($branch @ ${after:0:9})."
    say "No changes pulled — nothing to re-assemble."
    return 0
  fi
  ok "Updated $branch: ${before:0:9} → ${after:0:9} ($(git -C "$HARNESS_DIR" rev-list --count "$before..$after" 2>/dev/null || echo '?') new commit(s))."

  if $NO_REASSEMBLE; then
    say "Skipping re-assembly (--no-reassemble). Re-run setup.sh on any target to refresh its managed block."
    return 0
  fi
  reassemble_managed_targets
}

# ---- standalone actions needing assembled content -------------------------
if $DO_SELF_UPDATE; then self_update; exit 0; fi
if $DO_EXPORT; then export_instructions; exit 0; fi
if $DO_ORG_POLICY; then org_policy_install; exit 0; fi
if $WITH_HANDOFF_HOOKS && ! $GLOBAL && [ -z "$PROFILES" ]; then install_handoff_hooks; exit 0; fi
if $WITH_UI_DESIGN_HOOK && ! $GLOBAL && [ -z "$PROFILES" ]; then install_ui_design_hook; exit 0; fi

if $DO_UNINSTALL; then
  if $GLOBAL; then
    say "Uninstall — removing the Agentsmith core from $CC_DIR/CLAUDE.md"
    uninstall_from "$CC_DIR/CLAUDE.md"
    warn "Global config (settings.json, plugins) left in place — remove those by hand if you want them gone."
    command -v rtk >/dev/null 2>&1 && say "rtk hook left in place. Remove it with:  rtk init -g --uninstall   (then remove the binary via brew/cargo/rm)."
  else
    [ -n "$TARGET" ] || TARGET="$(pwd)"
    [ -d "$TARGET" ] || die "Target dir does not exist: $TARGET"
    TARGET="$(cd "$TARGET" && pwd)"
    say "Uninstall — removing the Agentsmith section from CLAUDE.md/AGENTS.md/GEMINI.md in $TARGET"
    uninstall_from "$TARGET/CLAUDE.md"
    uninstall_from "$TARGET/AGENTS.md"
    uninstall_from "$TARGET/GEMINI.md"
    echo; ok "Done. Scaffolding (scripts/, .harness/, docs/) was left in place — delete it by hand for a full removal."
    echo "  Your original files (if any) were backed up as *.bak.<timestamp> next to each."
  fi
  exit 0
fi

# ============================================================================
#  GLOBAL MODE — core rules to ~/.claude/CLAUDE.md + machine config
# ============================================================================
if $GLOBAL; then
  say "GLOBAL install — universal core → $CC_DIR/CLAUDE.md (applies to every project)"
  # --target does not constrain --global: the core has exactly one home. Refusing beats warning —
  # the whole of feedback 0003 is that a careful person passed --target BECAUSE it reads as "write
  # over there, not to my real config", and a printed warning is prose in a wall of output.
  [ -n "$TARGET" ] && die "--target is ignored by --global: the core always goes to $CC_DIR/CLAUDE.md, never to $TARGET.
  For a project file:   ./setup.sh --profile <name> --target $TARGET
  For the global core:  ./setup.sh --global        (no --target)"
  # Likewise --assemble-only reads like "touch nothing" but under --global, CLAUDE.md IS the
  # global file. Say so out loud rather than letting the flag imply a safety it does not provide.
  $ASSEMBLE_ONLY && ! $DRY_RUN && warn "--assemble-only skips config/plugins but still WRITES $CC_DIR/CLAUDE.md (a backup is made first). Use --dry-run to write nothing."
  [ -n "$WITH_MCP" ] && warn "--with-mcp is project-scoped (writes a project .mcp.json) — ignored in --global mode. Run it per project."
  resolve_operator_identity "$CC_DIR/CLAUDE.md"
  assemble_to "$CC_DIR/CLAUDE.md" true
  $DRY_RUN || report_todos "$CC_DIR/CLAUDE.md"
  $DRY_RUN || { $ASSEMBLE_ONLY && say "Skipping config/plugins (--assemble-only)." || install_global_config; }
  echo; say "$(c '1;32' 'Global core installed.')"
  echo "  Next per project:  ./setup.sh --profile <name> --profile-only --target /path/to/project"
  echo "  (the project CLAUDE.md will carry just the profile; the core is now global)"
  exit 0
fi

# ============================================================================
#  PROJECT MODE
# ============================================================================
[ -n "$PROFILES" ] || die "Pick a profile: --profile <name[,name]>  (or use --global for the core only). See: ls profiles/"
[ -n "$TARGET" ] || TARGET="$(pwd)"
[ -d "$TARGET" ] || die "Target dir does not exist: $TARGET"
TARGET="$(cd "$TARGET" && pwd)"

INCLUDE_CORE=true; $PROFILE_ONLY && INCLUDE_CORE=false
say "Assembling CLAUDE.md (profiles: $PROFILES; core: $INCLUDE_CORE)"
# Same trap as --global, same fix: re-running setup on a project that already has a managed block
# must not silently blank whoever is named in it. Feedback 0003 was reported against --global, but
# the mechanism is in assemble_to, so project mode had the identical bug on the identical line.
resolve_operator_identity "$TARGET/CLAUDE.md"
assemble_to "$TARGET/CLAUDE.md" "$INCLUDE_CORE"
$ALSO_AGENTS_MD && ! $DRY_RUN && assemble_to "$TARGET/AGENTS.md" "$INCLUDE_CORE"
$ALSO_GEMINI_MD && ! $DRY_RUN && assemble_to "$TARGET/GEMINI.md" "$INCLUDE_CORE"
if $DRY_RUN; then
  echo
  say "DRY RUN — nothing was written. A real run would ALSO scaffold into $TARGET:"
  echo "    + scripts/        verify.sh, handoff.sh, new-research.sh, new-feedback.sh, secret-scan.sh, install-git-hooks.sh, lint-leanness.sh"
  echo "    + hooks/git/      managed git hooks (secret-scan, protect-main, conventional-commits)"
  echo "    + .harness/       verify.conf (+ .example), templates/, handoffs/"
  echo "    + .planning/      progress-log.md"
  if $ASSEMBLE_ONLY; then
    echo "    + .claude/        settings.local.json.example"
  else
    echo "    + .claude/        settings.local.json.example, skills/ pack (/handoff, /verify, /harness-help + 3 more)"
  fi
  echo "    + docs/           feedback/README.md, research/ (+ _archive dirs)"
  echo "    + FIRST-STEPS.md"
  if [ -n "$DESIGN_SYSTEM" ] && [ "$DESIGN_SYSTEM" != skip ]; then echo "    + DESIGN.md       (--design-system $DESIGN_SYSTEM)"; fi
  if $ALSO_AGENTS_MD; then echo "    + AGENTS.md       (--also-agents-md)"; fi
  if $ALSO_GEMINI_MD; then echo "    + GEMINI.md       (--also-gemini-md)"; fi
  if [ -n "$WITH_MCP" ]; then echo "    + .mcp.json       (--with-mcp: $WITH_MCP)"; fi
  if $WITH_HOOKS; then echo "    ~ git hooks installed via scripts/install-git-hooks.sh (--with-hooks)"; fi
  echo
  say "Re-run without --dry-run to write these."
  exit 0
fi

say "Scaffolding project structure in $TARGET"
mkdir -p "$TARGET/docs/research/_archive" "$TARGET/docs/feedback/_archive" "$TARGET/.planning" "$TARGET/.harness/handoffs" "$TARGET/scripts" "$TARGET/.claude"
cpa() { [ -e "$2" ] || { cp "$1" "$2"; ok "added ${2#$TARGET/}"; }; }
cpa "$HARNESS_DIR/scripts/verify.sh"            "$TARGET/scripts/verify.sh"
cpa "$HARNESS_DIR/scripts/new-research.sh"      "$TARGET/scripts/new-research.sh"
cpa "$HARNESS_DIR/scripts/new-feedback.sh"      "$TARGET/scripts/new-feedback.sh"
cpa "$HARNESS_DIR/scripts/handoff.sh"           "$TARGET/scripts/handoff.sh"
cpa "$HARNESS_DIR/scripts/secret-scan.sh"       "$TARGET/scripts/secret-scan.sh"
cpa "$HARNESS_DIR/scripts/install-git-hooks.sh" "$TARGET/scripts/install-git-hooks.sh"
cpa "$HARNESS_DIR/scripts/lint-leanness.sh"     "$TARGET/scripts/lint-leanness.sh"
chmod +x "$TARGET/scripts/"*.sh 2>/dev/null || true
cpa "$HARNESS_DIR/docs/feedback/README.md"      "$TARGET/docs/feedback/README.md"
mkdir -p "$TARGET/hooks/git"
for g in "$HARNESS_DIR"/hooks/git/*.sh; do cpa "$g" "$TARGET/hooks/git/$(basename "$g")"; done
chmod +x "$TARGET/hooks/git/"*.sh 2>/dev/null || true
cpa "$HARNESS_DIR/.harness/verify.conf.example" "$TARGET/.harness/verify.conf.example"
if [ -e "$TARGET/.harness/verify.conf" ]; then
  ok ".harness/verify.conf already present — left as-is"
else
  build_verify_conf "$TARGET/.harness/verify.conf"
  ok "added .harness/verify.conf (preset for: $PROFILES — EDIT to wire real checks)"
fi
cpa "$HARNESS_DIR/templates/progress-log.md"    "$TARGET/.planning/progress-log.md"
cpa "$HARNESS_DIR/config/settings.local.$SAFETY.json.example" "$TARGET/.claude/settings.local.json.example"
mkdir -p "$TARGET/.harness/templates"; cp "$HARNESS_DIR"/templates/*.md "$TARGET/.harness/templates/" 2>/dev/null || true; ok "templates in .harness/templates/"
write_first_steps "$TARGET/FIRST-STEPS.md"
scaffold_design_system   # honors --design-system for a UI project (no-op on the default/backend path)

if [ -n "$WITH_MCP" ]; then
  say "Adding MCP server(s) to .mcp.json: $WITH_MCP"
  add_mcp_servers "$WITH_MCP"
fi

if $WITH_HOOKS; then
  if git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1; then
    ( cd "$TARGET" && bash scripts/install-git-hooks.sh ) && ok "git guardrails installed (secret-scan + protect-main + conventional)"
    echo "    add opt-in guards: scripts/install-git-hooks.sh --branch-naming --tests-green"
  else
    warn "--with-hooks: $TARGET is not a git repo — run scripts/install-git-hooks.sh after 'git init'."
  fi
fi

if $ASSEMBLE_ONLY; then
  say "Skipping global config (--assemble-only). See INSTALL.md for manual steps."
else
  SKILLS_DEST="$TARGET/.claude/skills"   # project mode: the bundled skill pack is a project file, not global
  install_global_config
fi

echo
say "$(c '1;32' 'Done.')"
echo "  Profiles:   $PROFILES   (core in this file: $INCLUDE_CORE)"
echo "  CLAUDE.md:  $TARGET/CLAUDE.md"
$WITH_SKILLS && echo "  Skills:     harness pack → $TARGET/.claude/skills/  (/handoff · /verify · /harness-help + 3 more)"
[ -n "$WITH_MCP" ] && [ -f "$TARGET/.mcp.json" ] && echo "  .mcp.json:   $(command -v jq >/dev/null 2>&1 && jq -r '.mcpServers|keys|join(\", \")' "$TARGET/.mcp.json" 2>/dev/null)"
echo "  Safety:     $SAFETY   ($([ "$SAFETY" = cautious ] && echo 'auto-applies edits, asks before shell/network' || echo 'runs almost everything without asking — a machine you fully own'))"
echo "  Next:  1) edit .harness/verify.conf with real checks"
echo "         2) skim CLAUDE.md (resolve any [TODO: …] placeholders — named below if there are any)"
echo "         3) cp .claude/settings.local.json.example .claude/settings.local.json (safety: $SAFETY — read the permissions note)"
echo "         4) docs/01-harness-philosophy.md · docs/07-how-to-pick-a-profile.md · docs/13-platforms-and-tools.md"
echo
report_todos "$TARGET/CLAUDE.md"
report_todos "$TARGET/DESIGN.md"   # names DESIGN_SYSTEM when a design system was scaffolded but not filled
echo
echo "  $(c '1;36' '▶ First 30 minutes')  (also saved to FIRST-STEPS.md)"
echo "     1) start:  claude          — run it inside this folder"
echo "     2) ask:    \"what does my harness do, and what are my rules?\""
echo "     3) take one small task end-to-end, then say \"handoff\" to wrap up cleanly"
