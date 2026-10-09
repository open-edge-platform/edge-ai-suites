# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

#!/usr/bin/env bash
set -euo pipefail

FFMPEG_VERSION="8.1.2"
X264_COMMIT="b35605ace3ddf7c1a5d67a2eb553f034aef41d55"
PYAV_VERSION="18.1.0"
SOURCE_DIR="/copyleft_sources/native/sources"
PYAV_SOURCE_DIR="/copyleft_sources/python/sources"
BUILD_DIR="/tmp/copyleft-media-build"
PREFIX="/opt/ffmpeg"

mkdir -p "$SOURCE_DIR" "$PYAV_SOURCE_DIR" "$BUILD_DIR"
apt-get update
apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    git \
    nasm \
    libssl-dev \
    pkg-config \
    xz-utils \
    yasm

python3 - "$PYAV_VERSION" "$PYAV_SOURCE_DIR" <<'PY'
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import urlopen

version, source_dir = sys.argv[1:]
with urlopen(f"https://pypi.org/pypi/av/{version}/json", timeout=30) as response:
    release = json.load(response)

source = next(
    (item for item in release["urls"] if item["packagetype"] == "sdist"),
    None,
)
if source is None:
    raise SystemExit(f"PyPI has no source distribution for av {version}")

archive_path = Path(source_dir) / source["filename"]
digest = hashlib.sha256()
with urlopen(source["url"], timeout=60) as response, archive_path.open("wb") as archive:
    while chunk := response.read(1024 * 1024):
        digest.update(chunk)
        archive.write(chunk)

expected_digest = source["digests"]["sha256"]
actual_digest = digest.hexdigest()
if actual_digest != expected_digest:
    archive_path.unlink(missing_ok=True)
    raise SystemExit(f"PyAV sdist checksum mismatch: expected {expected_digest}, got {actual_digest}")

(Path(source_dir) / "SHA256SUMS").write_text(
    f"{expected_digest}  {archive_path.name}\n", encoding="ascii"
)
print(f"Verified {archive_path.name} sha256={actual_digest}")
PY

curl --fail --location --retry 5 --retry-all-errors \
    "https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz" \
    --output "$SOURCE_DIR/ffmpeg-${FFMPEG_VERSION}.tar.xz"

git -C "$BUILD_DIR" init x264
git -C "$BUILD_DIR/x264" remote add origin https://code.videolan.org/videolan/x264.git
git -C "$BUILD_DIR/x264" fetch --depth=1 origin "$X264_COMMIT"
git -C "$BUILD_DIR/x264" checkout --detach FETCH_HEAD
git -C "$BUILD_DIR/x264" archive \
    --format=tar.gz \
    --prefix="x264-${X264_COMMIT}/" \
    --output="$SOURCE_DIR/x264-${X264_COMMIT}.tar.gz" \
    "$X264_COMMIT"

tar -xzf "$SOURCE_DIR/x264-${X264_COMMIT}.tar.gz" -C "$BUILD_DIR"
cd "$BUILD_DIR/x264-${X264_COMMIT}"
./configure --prefix="$PREFIX" --enable-shared --enable-pic --disable-cli
make -j"$(nproc)"
make install

tar -xf "$SOURCE_DIR/ffmpeg-${FFMPEG_VERSION}.tar.xz" -C "$BUILD_DIR"
cd "$BUILD_DIR/ffmpeg-${FFMPEG_VERSION}"
PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig" \
LD_LIBRARY_PATH="$PREFIX/lib" \
./configure \
    --prefix="$PREFIX" \
    --enable-gpl \
    --enable-version3 \
    --enable-libx264 \
    --enable-openssl \
    --enable-shared \
    --disable-static \
    --extra-cflags="-I${PREFIX}/include" \
    --extra-ldflags="-L${PREFIX}/lib"
make -j"$(nproc)"
make install

cat > "$SOURCE_DIR/native-build-info.txt" <<EOF
FFmpeg version: ${FFMPEG_VERSION}
FFmpeg source: https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz
FFmpeg configure: --enable-gpl --enable-version3 --enable-libx264 --enable-openssl --enable-shared --disable-static
FFmpeg reported license: GPL version 3 or later
x264 source repository: https://code.videolan.org/videolan/x264.git
x264 commit: ${X264_COMMIT}
x264 license: GPL-2.0-or-later
PyAV version: 18.1.0
PyAV build: source distribution linked against /opt/ffmpeg via pkg-config
EOF

cd "$SOURCE_DIR"
sha256sum \
    "ffmpeg-${FFMPEG_VERSION}.tar.xz" \
    "x264-${X264_COMMIT}.tar.gz" > SHA256SUMS

printf 'Component,Version,License,Source\n' > /copyleft_sources/native/native-components.csv
printf 'FFmpeg,%s,GPL-3.0-or-later,ffmpeg-%s.tar.xz\n' \
    "$FFMPEG_VERSION" "$FFMPEG_VERSION" >> /copyleft_sources/native/native-components.csv
printf 'x264,%s,GPL-2.0-or-later,x264-%s.tar.gz\n' \
    "$X264_COMMIT" "$X264_COMMIT" >> /copyleft_sources/native/native-components.csv

echo "$PREFIX/lib" > /etc/ld.so.conf.d/ffmpeg.conf
ldconfig
"$PREFIX/bin/ffmpeg" -version > "$SOURCE_DIR/ffmpeg-build-version.txt"
"$PREFIX/bin/ffmpeg" -buildconf > "$SOURCE_DIR/ffmpeg-buildconf.txt"