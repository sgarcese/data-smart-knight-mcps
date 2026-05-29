#!/usr/bin/env bash
#
# Build the OpenContext Lambda deployment package.
#
# Copies only the runtime source (core/plugins/server/custom_plugins) from the
# local OpenContext snapshot into build/package/ and installs the Python
# dependencies from requirements.txt into the same directory, targeting the
# Lambda runtime (Linux x86_64, Python 3.11). Terraform's archive_file then
# zips build/package/ into the deployment artifact.
#
# Running this directly is equivalent to what `terraform apply` triggers via
# the null_resource build step.

set -euo pipefail
cd "$(dirname "$0")"

SRC="../../opencontext"
BUILD_DIR="build"
PACKAGE_DIR="${BUILD_DIR}/package"
PYTHON_VERSION="3.11"
PLATFORM="x86_64-manylinux2014"

if [ ! -d "$SRC" ]; then
  echo "❌ OpenContext source not found at $SRC" >&2
  exit 1
fi

echo "📦 Building Lambda package in ${PACKAGE_DIR}"
rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR"

# Copy runtime source only — tests, client/, docs/, nested terraform/, and
# config.yaml are intentionally excluded to keep the artifact small and avoid
# shipping infrastructure state or local config into the function.
cp -r "$SRC/core" "$PACKAGE_DIR/"
cp -r "$SRC/plugins" "$PACKAGE_DIR/"
cp -r "$SRC/server" "$PACKAGE_DIR/"
if [ -d "$SRC/custom_plugins" ]; then
  cp -r "$SRC/custom_plugins" "$PACKAGE_DIR/"
else
  mkdir -p "$PACKAGE_DIR/custom_plugins"
fi

echo "📥 Installing dependencies for ${PLATFORM} / py${PYTHON_VERSION}"
if command -v uv >/dev/null 2>&1; then
  uv pip install \
    -r "$SRC/requirements.txt" \
    --target "$PACKAGE_DIR" \
    --python-platform "$PLATFORM" \
    --python-version "$PYTHON_VERSION" \
    --no-compile
elif command -v pip3 >/dev/null 2>&1; then
  pip3 install \
    -r "$SRC/requirements.txt" \
    --target "$PACKAGE_DIR" \
    --platform manylinux2014_x86_64 \
    --python-version "$PYTHON_VERSION" \
    --only-binary :all: \
    --no-compile
else
  echo "❌ Neither uv nor pip3 is available to install dependencies." >&2
  exit 1
fi

# Drop bytecode that bloats the zip. dist-info is kept because some packages
# resolve their version via importlib.metadata at runtime.
find "$PACKAGE_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true

echo "✅ Lambda package ready at ${PACKAGE_DIR}"
