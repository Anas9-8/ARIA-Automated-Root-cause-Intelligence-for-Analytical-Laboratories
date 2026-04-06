#!/usr/bin/env bash
# Generate the ARIA dashboard demo GIF.
#
# Usage:
#   bash scripts/generate_demo.sh
#
# What it does:
#   1. Verifies Python and pip are available.
#   2. Installs Playwright and Pillow if not already installed.
#   3. Installs the Chromium browser for Playwright.
#   4. Runs scripts/generate_demo.py from the project root.
#   5. Reports the output path.
#
# The script must be run from the project root directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

# Resolve the Python interpreter. Prefer the project virtualenv.
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
    PIP=".venv/bin/pip"
else
    PYTHON="python3"
    PIP="pip3"
fi

echo "Using Python: ${PYTHON}"

# Install dependencies if not present.
if ! "${PYTHON}" -c "import playwright" 2>/dev/null; then
    echo "Installing Playwright..."
    "${PIP}" install playwright
fi

if ! "${PYTHON}" -c "from PIL import Image" 2>/dev/null; then
    echo "Installing Pillow..."
    "${PIP}" install pillow
fi

# Install Chromium browser (idempotent — skipped if already installed).
echo "Checking Playwright browser installation..."
"${PYTHON}" -m playwright install chromium

echo "Running demo generator..."
"${PYTHON}" scripts/generate_demo.py

echo ""
echo "Done. GIF is at: docs/demo.gif"
