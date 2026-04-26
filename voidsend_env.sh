#!/usr/bin/env bash
# voidsend_env.sh - Auto-venv shell hook. SOURCE this, never execute it.

if [ -d "/data/data/com.termux" ]; then
  return 0 2>/dev/null || true
fi

_vs_green='\033[0;32m'
_vs_yellow='\033[1;33m'
_vs_cyan='\033[0;36m'
_vs_reset='\033[0m'

_voidsend_check_dir() {
  [ "${VOIDSEND_AUTO_VENV:-false}" = "true" ] || return 0
  local project="${VOIDSEND_PROJECT_DIR:-}"
  local activate="$project/.venv/bin/activate"
  [ -n "$project" ] || return 0
  local current
  current="$(pwd)"

  if [[ "$current" == "$project" || "$current" == "$project/"* ]]; then
    if [ -z "${VIRTUAL_ENV:-}" ] && [ -f "$activate" ]; then
      source "$activate"
      _VOIDSEND_VENV_ACTIVATED=true
      echo -e "${_vs_green}⬡  venv activated${_vs_reset} ${_vs_cyan}(VoidSend)${_vs_reset} — python: $(python --version 2>&1)"
    fi
  else
    if [ "${_VOIDSEND_VENV_ACTIVATED:-false}" = "true" ] && [ -n "${VIRTUAL_ENV:-}" ]; then
      deactivate 2>/dev/null || true
      _VOIDSEND_VENV_ACTIVATED=false
      echo -e "${_vs_yellow}⬡  venv deactivated${_vs_reset} (left VoidSend project)"
    fi
  fi
}

if [ -z "${ZSH_VERSION:-}" ]; then
  function cd() {
    builtin cd "$@" && _voidsend_check_dir
  }
  _voidsend_check_dir
else
  function chpwd() {
    _voidsend_check_dir
  }
  _voidsend_check_dir
fi

alias cdv='cd "${VOIDSEND_PROJECT_DIR:-$HOME/voidsend}"'
