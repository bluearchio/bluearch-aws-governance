#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 ZIP_PATH PUBLIC_BINARY_NAME EXPECTED_VERSION" >&2
  exit 2
fi

ZIP_PATH="$1"
PUBLIC_BINARY_NAME="$2"
EXPECTED_VERSION="$3"

[[ -f "$ZIP_PATH" ]] || {
  echo "Missing macOS archive: $ZIP_PATH" >&2
  exit 1
}
[[ "$PUBLIC_BINARY_NAME" == "bluearch-aws-governance" ]] || {
  echo "Unexpected public binary name: $PUBLIC_BINARY_NAME" >&2
  exit 1
}
[[ "$EXPECTED_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "Expected version must be a bare semantic version: $EXPECTED_VERSION" >&2
  exit 1
}

python3 - "$ZIP_PATH" "$PUBLIC_BINARY_NAME" <<'PY'
import stat
import sys
import zipfile

archive_path, public_binary = sys.argv[1:]
try:
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
except (OSError, zipfile.BadZipFile) as exc:
    raise SystemExit(f"Unable to inspect macOS archive: {exc}")

if len(members) != 1 or members[0].filename != public_binary:
    raise SystemExit(f"Archive must contain exactly one root file named {public_binary}")
mode = (members[0].external_attr >> 16) & 0xFFFF
if not stat.S_ISREG(mode) or stat.S_ISLNK(mode):
    raise SystemExit(f"Archive member {public_binary} must be a regular file")
PY

VERIFY_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$VERIFY_DIR"
}
trap cleanup EXIT

ditto -x -k "$ZIP_PATH" "$VERIFY_DIR"
BINARY_PATH="$VERIFY_DIR/$PUBLIC_BINARY_NAME"
ROOT_ENTRY_COUNT="$(find "$VERIFY_DIR" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')"
[[ "$ROOT_ENTRY_COUNT" == "1" ]] || {
  echo "Archive must contain only $PUBLIC_BINARY_NAME at its root." >&2
  exit 1
}
[[ -f "$BINARY_PATH" && ! -L "$BINARY_PATH" && -x "$BINARY_PATH" ]] || {
  echo "Archive must contain one executable named $PUBLIC_BINARY_NAME at its root." >&2
  exit 1
}

codesign --verify --deep --strict --verbose=2 "$BINARY_PATH"
spctl --assess --type execute --verbose=4 "$BINARY_PATH"

ARCHITECTURES="$(lipo -archs "$BINARY_PATH")"
[[ "$ARCHITECTURES" == "arm64" ]] || {
  echo "Expected an arm64-only binary, found: $ARCHITECTURES" >&2
  exit 1
}

[[ "$("$BINARY_PATH" --version)" == "$EXPECTED_VERSION" ]] || {
  echo "Artifact version does not match expected version $EXPECTED_VERSION" >&2
  exit 1
}
"$BINARY_PATH" --help >/dev/null
"$BINARY_PATH" catalog verify
