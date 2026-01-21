#!/usr/bin/env bash
set -euo pipefail

# Run the validation steps locally.
# Usage: ./scripts/run_validate_locally.sh [--dry-run] [--skip-system-deps]

DRY_RUN=0
SKIP_SYSTEM_DEPS=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --skip-system-deps) SKIP_SYSTEM_DEPS=1; shift ;;
    -h|--help)
      cat <<EOF
Usage: $0 [--dry-run] [--skip-system-deps]

--dry-run          Print actions but do not install or run commands.
--skip-system-deps Skip installing apt/brew system packages (useful on CI or managed dev boxes). Default: skip system deps.
EOF
      exit 0
      ;;
    *) echo "Unknown arg: $1"; exit 2 ;;
  esac
done

echo "Run Validate Locally - dry_run=$DRY_RUN skip_system_deps=$SKIP_SYSTEM_DEPS"

OS_NAME=$(uname -s)
PY="python3"
VENV_DIR=".venv"

# System dependencies (only if not skipped)
if [[ $SKIP_SYSTEM_DEPS -eq 0 ]]; then
  if [[ "$OS_NAME" == "Linux" ]]; then
    echo "Linux detected - will attempt to install apt packages: python3-dev, build-essential, gcc"
    if [[ $DRY_RUN -eq 1 ]]; then
      echo "DRY RUN: sudo apt-get update && sudo apt-get install -y python3-dev build-essential gcc"
    else
      sudo apt-get update
      sudo apt-get install -y python3-dev build-essential gcc
    fi
  elif [[ "$OS_NAME" == "Darwin" ]]; then
    echo "macOS detected - ensure Xcode Command Line Tools are installed (xcode-select --install)"
    if ! xcode-select -p >/dev/null 2>&1; then
      echo "Xcode Command Line Tools not found. Run: xcode-select --install"
    else
      echo "Xcode Command Line Tools present"
    fi
    echo "On macOS you may also need Homebrew packages if building certain native deps. Install brew packages manually if needed."
  else
    echo "Unknown OS: $OS_NAME. Please ensure build tools and Python headers are installed." 
  fi
fi

# Create virtualenv
if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: $PY -m venv $VENV_DIR"
else
  if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating virtualenv in $VENV_DIR"
    $PY -m venv "$VENV_DIR"
  fi
fi

# Activate venv for subsequent commands
ACTIVATE="$VENV_DIR/bin/activate"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: source $ACTIVATE"
else
  # shellcheck disable=SC1090
  source "$ACTIVATE"
fi

# Prepare build tooling
if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: python -m pip install --upgrade pip"
  echo "DRY RUN: python -m pip install --upgrade setuptools wheel build"
  echo "DRY RUN: python -m pip cache purge || true"
else
  python -m pip install --upgrade pip
  python -m pip install --upgrade setuptools wheel build
  python -m pip cache purge || true
fi

# Install Python requirements
if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: pip install -r requirements_test.txt"
else
  pip install -r requirements_test.txt
fi

# Lint (flake8)
if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics"
  echo "DRY RUN: flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics"
else
  flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics || true
  flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
fi

# Type check (mypy)
if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: mypy custom_components/hangar_assistant --ignore-missing-imports"
else
  mypy custom_components/hangar_assistant --ignore-missing-imports || true
fi

# Tests
if [[ $DRY_RUN -eq 1 ]]; then
  echo "DRY RUN: pytest tests/"
else
  pytest tests/
fi

echo "Local validate wrapper completed."
