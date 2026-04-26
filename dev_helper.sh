cd \~/voidsend

cat > dev.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
# VoidSend Dev Helper - Streamlined workflow for Termux on Revvl Tab 2

PROJECT="voidsend"
BIN_NAME="voidsend"

case "$1" in
  build)
    echo "→ Building debug (fast, low RAM)..."
    cargo build --jobs 2
    ;;

  release)
    echo "→ Building optimized release (small binary)..."
    cargo build --release --jobs 1
    strip target/release/$BIN_NAME 2>/dev/null || true
    echo "→ Binary ready: target/release/$BIN_NAME"
    ;;

  install)
    echo "→ Installing binary to Termux PATH..."
    cargo install --path . --force --jobs 1
    echo "→ Run with: $BIN_NAME"
    ;;

  run)
    echo "→ Running debug build..."
    cargo run -- --help
    ;;

  clean)
    echo "→ Cleaning build artifacts..."
    cargo clean
    ;;

  status)
    git status -s
    echo "→ Latest commit:"
    git log --oneline -1
    ;;

  push)
    if [ -z "$2" ]; then
      echo "Usage: ./dev.sh push 'commit message'"
      exit 1
    fi
    git add .
    git commit -m "$2" || true
    git push
    ;;

  *)
    echo "VoidSend Dev Commands:"
    echo "  ./dev.sh build      → Fast debug build"
    echo "  ./dev.sh release    → Optimized release build"
    echo "  ./dev.sh install    → Install binary to PATH"
    echo "  ./dev.sh run        → Run with --help"
    echo "  ./dev.sh clean      → Clean artifacts"
    echo "  ./dev.sh status     → Git status + last commit"
    echo "  ./dev.sh push 'msg' → Add, commit & push"
    echo ""
    echo "Available aliases (after sourcing \~/.bashrc):"
    echo "  vb  = cargo build --jobs 2"
    echo "  vr  = cargo build --release --jobs 1 && strip"
    echo "  vi  = cargo install --path . --force"
    echo "  vc  = cargo check --jobs 2"
    echo "  vs  = git status -s"
    echo "  vl  = git log --oneline -5"
    echo "  dev = ./dev.sh"
    echo "  cdv = cd \~/voidsend"
    echo "  cds = cd \~/stealog-forge"
    ;;
esac
EOF

chmod +x dev.sh

# === Safe alias addition (no duplicates) ===
BASHRC="$HOME/.bashrc"

# Add a clean header once
grep -q "# === VoidSend + Rust/Termux Aliases ===" "$BASHRC" 2>/dev/null || {
  echo "" >> "$BASHRC"
  echo "# === VoidSend + Rust/Termux Aliases ===" >> "$BASHRC"
  echo "# Added for VoidSend development workflow" >> "$BASHRC"
}

# Function to add alias only if it doesn't exist
add_alias() {
  local name="$1"
  local value="$2"
  local line="alias $name='$value'"
  
  if ! grep -q "^alias $name=" "$BASHRC" 2>/dev/null; then
    echo "$line" >> "$BASHRC"
    echo "→ Added alias: $name"
  else
    echo "→ Alias $name already exists (skipped)"
  fi
}

add_alias "vb" "cargo build --jobs 2"
add_alias "vr" "cargo build --release --jobs 1 && strip target/release/voidsend 2>/dev/null || true"
add_alias "vi" "cargo install --path . --force --jobs 1"
add_alias "vc" "cargo check --jobs 2"
add_alias "vs" "git status -s"
add_alias "vl" "git log --oneline -5"
add_alias "dev" "./dev.sh"
add_alias "cdv" "cd ~/voidsend"
add_alias "cds" "cd ~/stealog-forge"

# Reload shell
echo "→ Reloading ~/.bashrc..."
source "$BASHRC"

echo ""
echo "✅ Setup complete! Aliases are now added safely (no duplicates)."
echo "Test with: dev"
echo "Switch projects: cdv  or  cds"
