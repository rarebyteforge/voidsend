#!/usr/bin/env bash
# =============================================================================
# VoidSend Dev Helper
# Usage: ./dev.sh <command> [args]
# =============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

# ── Detect environment: Termux or desktop ─────────────────────────────────────
if [ -d "/data/data/com.termux" ]; then
  IS_TERMUX=true
  PYTHON="python"
  PIP="pip"
else
  IS_TERMUX=false
  PYTHON="$VENV_DIR/bin/python"
  PIP="$VENV_DIR/bin/pip"
fi

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}→${RESET} $*"; }
success() { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET} $*"; }
error()   { echo -e "${RED}✗${RESET} $*"; exit 1; }

# ── Commands ──────────────────────────────────────────────────────────────────

cmd_setup() {
  if [ "$IS_TERMUX" = true ]; then
    info "Termux detected — installing to system Python (no venv)..."
    pip install --upgrade pip -q
    pip install -r "$PROJECT_DIR/requirements.txt"
    success "Setup complete. Run './dev.sh run' to start."
  else
    info "Desktop detected — creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    "$PIP" install --upgrade pip -q
    "$PIP" install -r "$PROJECT_DIR/requirements.txt"
    success "Setup complete. Run './dev.sh run' to start."
  fi
}

cmd_run() {
  if [ "$IS_TERMUX" = false ]; then
    _require_venv
  fi
  info "Starting VoidSend..."
  cd "$PROJECT_DIR"
  "$PYTHON" main.py "$@"
}

cmd_test() {
  if [ "$IS_TERMUX" = false ]; then _require_venv; fi
  info "Running tests..."
  cd "$PROJECT_DIR"
  "$PYTHON" -m pytest tests/ -v 2>/dev/null || warn "No tests found yet."
}

cmd_lint() {
  if [ "$IS_TERMUX" = false ]; then _require_venv; fi
  info "Running linter..."
  "$VENV_DIR/bin/ruff" check . 2>/dev/null \
    || "$VENV_DIR/bin/flake8" . 2>/dev/null \
    || warn "No linter installed. Run: pip install ruff"
}

cmd_update() {
  # ── Safe single-command file update ──────────────────────────────────────
  # Usage: ./dev.sh update <relative/path/to/file.py>
  # Then paste new content, press Ctrl+D when done.
  # Performs backup, duplication check, syntax check (for .py), then writes.
  local target="$1"
  local full_path="$PROJECT_DIR/$target"
  local tmp
  tmp=$(mktemp "$TMPDIR/voidsend_update_XXXXXX")

  if [ -z "$target" ]; then
    error "Usage: ./dev.sh update <relative/path/to/file>"
  fi

  echo -e "${YELLOW}Paste new file content. Press Ctrl+D when done.${RESET}"
  cat > "$tmp"

  # Guard: empty paste
  if [ ! -s "$tmp" ]; then
    rm -f "$tmp"
    error "No content received — update cancelled."
  fi

  # Guard: identical to existing file
  if [ -f "$full_path" ] && cmp -s "$tmp" "$full_path"; then
    rm -f "$tmp"
    warn "File is identical to current version — no update needed."
    exit 0
  fi

  # Guard: Python syntax check
  if [[ "$target" == *.py ]]; then
    if ! "$PYTHON" -m py_compile "$tmp" 2>/dev/null; then
      rm -f "$tmp"
      error "Syntax error in pasted Python — update cancelled. Fix and retry."
    fi
    success "Syntax check passed."
  fi

  # Backup existing file
  if [ -f "$full_path" ]; then
    cp "$full_path" "${full_path}.bak"
    info "Backup saved: ${target}.bak"
  fi

  # Create parent dirs if needed
  mkdir -p "$(dirname "$full_path")"

  # Write
  mv "$tmp" "$full_path"
  success "Updated: $target"
}

cmd_restore() {
  # Restore last backup of a file
  local target="$1"
  local full_path="$PROJECT_DIR/$target"
  local backup="${full_path}.bak"
  if [ ! -f "$backup" ]; then
    error "No backup found for $target"
  fi
  cp "$backup" "$full_path"
  success "Restored $target from backup."
}

cmd_cat() {
  local target="$1"
  if [ -z "$target" ]; then error "Usage: ./dev.sh cat <relative/path>"; fi
  cat "$PROJECT_DIR/$target"
}

cmd_status() {
  cd "$PROJECT_DIR"
  git status -s
  echo ""
  git log --oneline -5
}

cmd_push() {
  local msg="${1:-}"
  if [ -z "$msg" ]; then
    error "Usage: ./dev.sh push 'commit message'"
  fi
  cd "$PROJECT_DIR"
  git add .
  git commit -m "$msg" || warn "Nothing new to commit."
  git push
  success "Pushed: $msg"
}

cmd_init_git() {
  cd "$PROJECT_DIR"
  if [ -d .git ]; then
    warn "Git repo already initialized."
    return
  fi
  git init
  git add .
  git commit -m "Initial commit: VoidSend newsletter tool scaffold"
  info "Now add your remote: git remote add origin <url>"
  info "Then push: git push -u origin main"
  success "Git initialized."
}

cmd_tree() {
  if command -v tree &>/dev/null; then
    tree "$PROJECT_DIR" -I '__pycache__|*.pyc|.venv|*.egg-info|.git|*.bak'
  else
    find "$PROJECT_DIR" -not -path '*/__pycache__/*' \
      -not -path '*/.venv/*' \
      -not -path '*/.git/*' \
      -not -name '*.pyc' \
      -not -name '*.bak' \
      | sort | sed "s|$PROJECT_DIR||" | head -60
  fi
}

cmd_clean() {
  find "$PROJECT_DIR" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
  find "$PROJECT_DIR" -name '*.pyc' -delete 2>/dev/null || true
  find "$PROJECT_DIR" -name '*.bak' -delete 2>/dev/null || true
  success "Cleaned build artifacts and backups."
}

cmd_help() {
  echo -e "${BOLD}VoidSend Dev Helper${RESET}"
  echo ""
  echo -e "${CYAN}Setup & Run${RESET}"
  echo "  ./dev.sh setup           → Create venv + install dependencies"
  echo "  ./dev.sh run             → Launch VoidSend TUI"
  echo "  ./dev.sh run -p PASS     → Launch with passphrase (skips prompt)"
  echo ""
  echo -e "${CYAN}Virtual Environment${RESET}"
  echo "  ./dev.sh venv            → Show venv status (active, path, auto-venv)"
  echo "  ./dev.sh venv-on         → Enable auto-activate venv on cd into project"
  echo "  ./dev.sh venv-off        → Disable auto-venv"
  echo ""
  echo -e "${CYAN}File Management${RESET}"
  echo "  ./dev.sh import <file> [dest/] → Copy external file into project"
  echo "  ./dev.sh import ~/Downloads/*.csv data/  → Bulk import CSVs"
  echo "  ./dev.sh update <file>   → Safe file update (paste + Ctrl+D)"
  echo "  ./dev.sh restore <file>  → Restore last backup of a file"
  echo "  ./dev.sh cat <file>      → View file contents"
  echo "  ./dev.sh tree            → Show project structure"
  echo "  ./dev.sh clean           → Remove __pycache__, .pyc, .bak files"
  echo ""
  echo -e "${CYAN}Git${RESET}"
  echo "  ./dev.sh init-git        → Initialize git repo + first commit"
  echo "  ./dev.sh status          → git status + last 5 commits"
  echo "  ./dev.sh push 'msg'      → Add all, commit, push"
  echo ""
  echo -e "${CYAN}Quality${RESET}"
  echo "  ./dev.sh test            → Run test suite"
  echo "  ./dev.sh lint            → Run linter (ruff/flake8)"
  echo ""
  echo -e "${CYAN}Examples${RESET}"
  echo "  ./dev.sh update core/mailer.py   → Update mailer with pasted code"
  echo "  ./dev.sh push 'fix: SMTP timeout retry'"
}


cmd_venv_status() {
  echo -e "${BOLD}Virtual Environment Status${RESET}"
  echo ""
  if [ "$IS_TERMUX" = true ]; then
    echo -e "  Platform     : ${CYAN}Termux (no venv — system Python)${RESET}"
    echo -e "  Python       : $(python --version 2>&1)"
    echo -e "  Pip          : $(pip --version 2>&1 | cut -d' ' -f1-2)"
    echo ""
    echo -e "  ${YELLOW}Note: Termux uses system Python. venv auto-activation not applicable.${RESET}"
    return
  fi

  if [ -d "$VENV_DIR" ]; then
    echo -e "  Venv path    : ${CYAN}$VENV_DIR${RESET}"
    echo -e "  Python       : $("$PYTHON" --version 2>&1)"
    echo -e "  Pip          : $("$PIP" --version 2>&1 | cut -d' ' -f1-2)"

    if [ -n "${VIRTUAL_ENV:-}" ]; then
      echo -e "  Active now   : ${GREEN}YES ✓${RESET}"
    else
      echo -e "  Active now   : ${YELLOW}NO${RESET} (run: source .venv/bin/activate)"
    fi

    # Check auto-venv setting
    local setting
    setting=$(grep -s "VOIDSEND_AUTO_VENV" "$HOME/.bashrc" "$HOME/.zshrc" 2>/dev/null | head -1 || true)
    if echo "$setting" | grep -q "true"; then
      echo -e "  Auto-venv    : ${GREEN}ENABLED${RESET}"
    else
      echo -e "  Auto-venv    : ${YELLOW}DISABLED${RESET} (run: ./dev.sh venv-on)"
    fi
  else
    echo -e "  Venv path    : ${RED}Not created yet${RESET}"
    echo -e "  Run          : ${CYAN}./dev.sh setup${RESET}"
  fi
  echo ""
}

cmd_venv_on() {
  if [ "$IS_TERMUX" = true ]; then
    warn "Termux uses system Python — auto-venv not applicable here."
    info "On Termux, packages are installed globally via: pip install -r requirements.txt"
    info "To jump to project quickly, add this alias to ~/.bashrc:"
    echo ""
    echo "    alias cdv='cd ~/voidsend'"
    echo ""
    return
  fi

  local shell_rc=""
  if [ -n "${ZSH_VERSION:-}" ] || echo "$SHELL" | grep -q zsh; then
    shell_rc="$HOME/.zshrc"
  else
    shell_rc="$HOME/.bashrc"
  fi

  # Check if already installed
  if grep -q "VOIDSEND_AUTO_VENV=true" "$shell_rc" 2>/dev/null; then
    warn "Auto-venv already enabled in $shell_rc"
    return
  fi

  # Remove any old toggle setting first
  sed -i '/VOIDSEND_AUTO_VENV=/d' "$shell_rc" 2>/dev/null || true
  sed -i '/voidsend_env.sh/d' "$shell_rc" 2>/dev/null || true

  cat >> "$shell_rc" << 'SHELLEOF'

# ── VoidSend auto-venv (managed by dev.sh) ────────────────────────────────────
VOIDSEND_AUTO_VENV=true
VOIDSEND_PROJECT_DIR="PLACEHOLDER"
source "PLACEHOLDER_ENV"
# ──────────────────────────────────────────────────────────────────────────────
SHELLEOF

  # Replace placeholders with real paths
  sed -i "s|PLACEHOLDER_ENV|$PROJECT_DIR/voidsend_env.sh|g" "$shell_rc"
  sed -i "s|VOIDSEND_PROJECT_DIR="PLACEHOLDER"|VOIDSEND_PROJECT_DIR="$PROJECT_DIR"|g" "$shell_rc"

  success "Auto-venv enabled in $shell_rc"
  info "Restart your shell or run: source $shell_rc"
}

cmd_venv_off() {
  local shell_rc=""
  if [ -n "${ZSH_VERSION:-}" ] || echo "$SHELL" | grep -q zsh; then
    shell_rc="$HOME/.zshrc"
  else
    shell_rc="$HOME/.bashrc"
  fi

  # Remove the block between the markers
  sed -i '/# ── VoidSend auto-venv/,/# ─────────────────────────────/d' "$shell_rc" 2>/dev/null || true
  sed -i '/VOIDSEND_AUTO_VENV=/d' "$shell_rc" 2>/dev/null || true
  sed -i '/voidsend_env.sh/d' "$shell_rc" 2>/dev/null || true

  success "Auto-venv disabled. Restart shell or run: source $shell_rc"
}

cmd_import() {
  # ── Import external files into the project ───────────────────────────────
  # Usage:
  #   ./dev.sh import /path/to/file.csv
  #   ./dev.sh import /path/to/file.csv data/
  #   ./dev.sh import /path/to/file.html templates/
  #   ./dev.sh import ~/Downloads/*.csv data/
  #
  # - If no destination given, auto-routes by file extension
  # - Detects duplicates (identical content) and skips
  # - Detects name conflicts (different content) and prompts
  # - Never overwrites silently

  if [ $# -eq 0 ]; then
    error "Usage: ./dev.sh import <source_file_or_glob> [destination_subdir/]"
  fi

  # Last arg is destination if it ends with / or is an existing dir
  local dest_sub=""
  local sources=("$@")

  last_arg="${*: -1}"
  if [[ "$last_arg" == */ ]] || [ -d "$PROJECT_DIR/$last_arg" ]; then
    dest_sub="$last_arg"
    sources=("${@:1:$#-1}")  # all args except last
  fi

  if [ ${#sources[@]} -eq 0 ]; then
    error "No source files specified."
  fi

  local imported=0
  local skipped=0

  for src in "${sources[@]}"; do
    # Expand globs
    for file in $src; do
      if [ ! -f "$file" ]; then
        warn "Not found, skipping: $file"
        ((skipped++)) || true
        continue
      fi

      filename="$(basename "$file")"
      ext="${filename##*.}"

      # Auto-route by extension if no destination given
      if [ -z "$dest_sub" ]; then
        case "$ext" in
          csv)               dest_sub="data/" ;;
          html|htm)          dest_sub="templates/" ;;
          txt)               dest_sub="templates/" ;;
          py)                dest_sub="" ;;   # root of project, user should specify
          *)                 dest_sub="" ;;
        esac
      fi

      dest_dir="$PROJECT_DIR/${dest_sub}"
      mkdir -p "$dest_dir"
      dest_file="$dest_dir/$filename"

      # Guard: identical file already exists
      if [ -f "$dest_file" ] && cmp -s "$file" "$dest_file"; then
        warn "Identical file already exists, skipping: ${dest_sub}${filename}"
        ((skipped++)) || true
        continue
      fi

      # Guard: name conflict with different content
      if [ -f "$dest_file" ]; then
        echo -e "${YELLOW}⚠  Conflict:${RESET} ${dest_sub}${filename} already exists with different content."
        echo -n "   Overwrite? [y/N]: "
        read -r answer
        if [[ "$answer" != "y" && "$answer" != "Y" ]]; then
          warn "Skipped: $filename"
          ((skipped++)) || true
          continue
        fi
        # Backup before overwrite
        cp "$dest_file" "${dest_file}.bak"
        info "Backup saved: ${dest_sub}${filename}.bak"
      fi

      cp "$file" "$dest_file"
      success "Imported: $filename → ${dest_sub:-project root}"
      ((imported++)) || true
    done
  done

  echo ""
  info "Done. ${imported} imported, ${skipped} skipped."
}

# ── Internal helpers ───────────────────────────────────────────────────────────

_require_venv() {
  if [ ! -f "$PYTHON" ]; then
    error "Virtual environment not found. Run: ./dev.sh setup"
  fi
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

COMMAND="${1:-help}"
shift || true

case "$COMMAND" in
  setup)      cmd_setup "$@" ;;
  run)        cmd_run "$@" ;;
  test)       cmd_test "$@" ;;
  lint)       cmd_lint "$@" ;;
  update)     cmd_update "$@" ;;
  restore)    cmd_restore "$@" ;;
  cat)        cmd_cat "$@" ;;
  status)     cmd_status ;;
  push)       cmd_push "$@" ;;
  init-git)   cmd_init_git ;;
  tree)       cmd_tree ;;
  venv)       cmd_venv_status ;;
  venv-on)    cmd_venv_on ;;
  venv-off)   cmd_venv_off ;;
  clean)      cmd_clean ;;
  import)     cmd_import "$@" ;;
  help|--help|-h) cmd_help ;;
  *)          error "Unknown command: $COMMAND. Run './dev.sh help'" ;;
esac
