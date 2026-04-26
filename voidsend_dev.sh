#!/usr/bin/env bash
# voidsend_env.sh
# ─────────────────────────────────────────────────────────────────────────────
# VoidSend auto-venv shell hook.
# SOURCE this file (never execute it directly).
# Managed by: ./dev.sh venv-on / venv-off
#
# What it does:
#   - Overrides `cd` to watch for entry/exit of the VoidSend project directory
#   - On entry: auto-activates .venv if VOIDSEND_AUTO_VENV=true
#   - On exit:  deactivates venv if it was activated by this hook
#   - Works with bash and zsh
#   - No-op on Termux (system Python, no venv needed)
#   - Prints a clear status line when activating/deactivating
# ─────────────────────────────────────────────────────────────────────────────

# Skip entirely on Termux
if [ -d "/data/data/com.termux" ]; then
  return 0 2>/dev/null || true
fi

# ── Colors (safe — only used when terminal is interactive) ───────────────────
_vs_green='\033[0;32m'
_vs_yellow='\033[1;33m'
_vs_cyan='\033[0;36m'
_vs_reset='\033[0m'

# ── Core hook function ────────────────────────────────────────────────────────
_voidsend_check_dir() {
  # Only act if auto-venv is enabled
  [ "${VOIDSEND_AUTO_VENV:-false}" = "true" ] || return 0

  local project="${VOIDSEND_PROJECT_DIR:-}"
  local venv="$project/.venv"
  local activate="$venv/bin/activate"

  # No project dir set — skip
  [ -n "$project" ] || return 0

  local current
  current="$(pwd)"

  # ── Entering the project directory ─────────────────────────────────────────
  if [[ "$current" == "$project" || "$current" == "$project/"* ]]; then
    # Only activate if not already active and venv exists
    if [ -z "${VIRTUAL_ENV:-}" ] && [ -f "$activate" ]; then
      source "$activate"
      _VOIDSEND_VENV_ACTIVATED=true
      echo -e "${_vs_green}⬡  venv activated${_vs_reset} ${_vs_cyan}(VoidSend)${_vs_reset} — python: $(python --version 2>&1)"
    fi
  else
    # ── Leaving the project directory ────────────────────────────────────────
    if [ "${_VOIDSEND_VENV_ACTIVATED:-false}" = "true" ] && [ -n "${VIRTUAL_ENV:-}" ]; then
      deactivate 2>/dev/null || true
      _VOIDSEND_VENV_ACTIVATED=false
      echo -e "${_vs_yellow}⬡  venv deactivated${_vs_reset} (left VoidSend project)"
    fi
  fi
}

# ── Override cd for bash ──────────────────────────────────────────────────────
if [ -z "${ZSH_VERSION:-}" ]; then
  function cd() {
    builtin cd "$@" && _voidsend_check_dir
  }

  # Also check on shell startup (in case shell opens in project dir)
  _voidsend_check_dir

# ── Override cd for zsh ───────────────────────────────────────────────────────
else
  function chpwd() {
    _voidsend_check_dir
  }

  # Check on startup for zsh
  _voidsend_check_dir
fi

# ── cdv alias: jump to project + auto-trigger check ──────────────────────────
alias cdv='cd "${VOIDSEND_PROJECT_DIR:-$HOME/voidsend}"'

