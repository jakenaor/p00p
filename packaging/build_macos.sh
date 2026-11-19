#!/bin/zsh
set -euo pipefail

PROJECT_DIR="${0:A:h:h}"
PACKAGE_DIR="$PROJECT_DIR/packaging"
DIST_DIR="$PROJECT_DIR/dist"
BUILD_DIR="$PROJECT_DIR/build"
ICONSET_DIR="$PACKAGE_DIR/P00P.iconset"
DMG_ROOT="$BUILD_DIR/dmg-root"
VERSION="0.2.0"

cd "$PROJECT_DIR"

"$PROJECT_DIR/.venv/bin/python" "$PACKAGE_DIR/make_icon.py"
mkdir -p "$ICONSET_DIR"

sips -z 16 16 "$PACKAGE_DIR/P00P-1024.png" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
sips -z 32 32 "$PACKAGE_DIR/P00P-1024.png" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
sips -z 32 32 "$PACKAGE_DIR/P00P-1024.png" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
sips -z 64 64 "$PACKAGE_DIR/P00P-1024.png" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
sips -z 128 128 "$PACKAGE_DIR/P00P-1024.png" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
sips -z 256 256 "$PACKAGE_DIR/P00P-1024.png" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
sips -z 256 256 "$PACKAGE_DIR/P00P-1024.png" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
sips -z 512 512 "$PACKAGE_DIR/P00P-1024.png" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
sips -z 512 512 "$PACKAGE_DIR/P00P-1024.png" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
cp "$PACKAGE_DIR/P00P-1024.png" "$ICONSET_DIR/icon_512x512@2x.png"
iconutil -c icns "$ICONSET_DIR" -o "$PACKAGE_DIR/P00P.icns"

rm -rf "$BUILD_DIR/P00P" "$DIST_DIR/P00P" "$DIST_DIR/P00P.app"
"$PROJECT_DIR/.venv/bin/pyinstaller" \
    --noconfirm \
    --clean \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR/P00P" \
    "$PACKAGE_DIR/P00P.spec"

codesign --force --deep --sign - "$DIST_DIR/P00P.app"
codesign --verify --deep --strict --verbose=2 "$DIST_DIR/P00P.app"

rm -rf "$DMG_ROOT"
mkdir -p "$DMG_ROOT"
cp -R "$DIST_DIR/P00P.app" "$DMG_ROOT/P00P.app"
ln -s /Applications "$DMG_ROOT/Applications"
rm -f "$DIST_DIR/P00P-$VERSION-macOS-arm64.dmg"
hdiutil create \
    -volname "P00P $VERSION" \
    -srcfolder "$DMG_ROOT" \
    -ov \
    -format UDZO \
    "$DIST_DIR/P00P-$VERSION-macOS-arm64.dmg"

echo "$DIST_DIR/P00P.app"
echo "$DIST_DIR/P00P-$VERSION-macOS-arm64.dmg"
