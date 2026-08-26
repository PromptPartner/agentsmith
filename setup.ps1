#!/usr/bin/env pwsh
# Thin PowerShell launcher for the shared Python runtime. No installer behavior lives here.
$ErrorActionPreference = 'Stop'
$agentsmithDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$agentsmithCore = Join-Path $agentsmithDir 'agentsmith.py'

function Find-AgentsmithPython {
  foreach ($candidate in @(
      @{ Command = 'python3'; Prefix = @() },
      @{ Command = 'python';  Prefix = @() },
      @{ Command = 'py';      Prefix = @('-3') }
    )) {
    if (Get-Command $candidate.Command -ErrorAction SilentlyContinue) { return $candidate }
  }
  return $null
}

$runtime = Find-AgentsmithPython
if (-not $runtime) {
  [Console]::Error.WriteLine('Agentsmith requires Python 3.11+.')
  [Console]::Error.WriteLine('Install Python, then rerun this exact command. Tried: python3, python, py -3.')
  exit 127
}

& $runtime.Command @($runtime.Prefix) $agentsmithCore @args
exit $LASTEXITCODE
