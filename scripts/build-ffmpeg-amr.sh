#!/usr/bin/env bash
#
# Build an ffmpeg that can ENCODE AMR-NB, into a local prefix under build/.
#
# Why this exists: the default Homebrew ffmpeg (macOS) and the ffmpeg bundled
# with Home Assistant OS are compiled WITHOUT the AMR encoder, so
# `-c:a libopencore_amrnb` fails with "Unknown encoder 'libopencore_amrnb'".
# `sim800c.call_and_play` needs AMR-NB clips, so this builds a capable ffmpeg
# from source.
#
# Licensing: this builds from source on your machine and redistributes NO
# binaries. opencore-amr is Apache-2.0 (hence ffmpeg's --enable-version3);
# ffmpeg here is GPL. AMR-NB's core patents have largely expired. Not legal
# advice — if in doubt, use the tiny standalone encoder in the README instead.
#
# Usage:
#   scripts/build-ffmpeg-amr.sh            # build into build/ffmpeg-amr
#   FFMPEG_VERSION=7.1 scripts/build-ffmpeg-amr.sh
#   PREFIX=/opt/ffmpeg-amr scripts/build-ffmpeg-amr.sh
set -euo pipefail

FFMPEG_VERSION="${FFMPEG_VERSION:-7.1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PREFIX="${PREFIX:-$ROOT/build/ffmpeg-amr}"
SRC="$ROOT/build/src"
JOBS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"

echo "==> Installing build dependencies (opencore-amr, pkg-config, nasm)"
if command -v brew >/dev/null 2>&1; then
    for pkg in opencore-amr pkg-config nasm; do
        brew list "$pkg" >/dev/null 2>&1 || brew install "$pkg"
    done
    amr_prefix="$(brew --prefix opencore-amr)"
    export PKG_CONFIG_PATH="$amr_prefix/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
elif command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y build-essential nasm pkg-config curl xz-utils \
        libopencore-amrnb-dev libopencore-amrwb-dev
else
    echo "Unsupported OS. Install opencore-amr(-dev), pkg-config and nasm, then re-run." >&2
    exit 1
fi

mkdir -p "$SRC" "$PREFIX"
cd "$SRC"
TARBALL="ffmpeg-$FFMPEG_VERSION.tar.xz"
if [ ! -f "$TARBALL" ]; then
    echo "==> Downloading ffmpeg $FFMPEG_VERSION"
    curl -fL -o "$TARBALL" "https://ffmpeg.org/releases/$TARBALL"
fi
rm -rf "ffmpeg-$FFMPEG_VERSION"
tar xf "$TARBALL"
cd "ffmpeg-$FFMPEG_VERSION"

echo "==> Configuring ffmpeg $FFMPEG_VERSION with opencore-amr"
# --enable-version3 is required: opencore-amr is Apache-2.0, only compatible
# with the v3 licenses. Audio-only build keeps it lean and quick.
./configure \
    --prefix="$PREFIX" \
    --enable-gpl --enable-version3 \
    --enable-libopencore-amrnb --enable-libopencore-amrwb \
    --disable-doc --disable-debug --disable-ffplay

echo "==> Building (-j$JOBS) — this takes a few minutes"
make -j"$JOBS"
make install

BIN="$PREFIX/bin/ffmpeg"
echo
if "$BIN" -hide_banner -encoders 2>/dev/null | grep -qi 'libopencore_amrnb'; then
    echo "==> Success: $BIN (with AMR-NB encoder)"
else
    echo "==> Build finished but the AMR-NB encoder is missing — check the log." >&2
    exit 1
fi
echo
echo "Encode any audio -> AMR-NB (8 kHz, mono) for sim800c.call_and_play:"
echo "  \"$BIN\" -i input.wav -ar 8000 -ac 1 -c:a libopencore_amrnb -b:a 12.2k output.amr"
