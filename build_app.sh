#!/bin/sh
# Önálló asztali app PyInstallerrel (a célgépen nem kell Python).
#   macOS   -> dist/app/InfluenszerRadar.app + dist/InfluenszerRadar-macos-<arch>.zip
#   Windows -> dist/app/InfluenszerRadar/    + dist/InfluenszerRadar-windows-x64.zip
#   Linux   -> dist/app/InfluenszerRadar/    + dist/InfluenszerRadar-linux-<arch>.tar.gz
# Szükséges: pip install -r requirements.txt pyinstaller
set -e
cd "$(dirname "$0")"
mkdir -p build dist
printf 'import sys\nfrom influradar.cli import main\nsys.exit(main())\n' > build/entry.py
PY=${PYTHON:-$(command -v python3 || command -v python)}
VER=$($PY -c 'import influradar;print(influradar.__version__)')
case "$(uname -s)" in
  Darwin) OS=macos ;;
  MINGW*|MSYS*|CYGWIN*|Windows_NT) OS=windows ;;
  *) OS=linux ;;
esac
SEP=":"; ROOT="$(pwd)"
if [ "$OS" = windows ]; then SEP=";"; ROOT=$(cygpath -w "$(pwd)" 2>/dev/null || pwd); fi
PYI=${PYINSTALLER:-"$PY -m PyInstaller"}
$PYI --onedir --console --name InfluenszerRadar --clean --noconfirm --paths . \
     --add-data "$ROOT/data/telepulesek.csv${SEP}data" --add-data "$ROOT/data/import_sablon.csv${SEP}data" \
     --add-data "$ROOT/influradar/ui.html${SEP}influradar" \
     --collect-all ddgs --collect-all primp --hidden-import anthropic \
     --osx-bundle-identifier hu.sadrobot.influradar \
     --distpath dist/app --workpath build/pyi-app --specpath build build/entry.py
if [ "$OS" = macos ]; then
  APP=dist/app/InfluenszerRadar.app
  [ -d "$APP" ] || APP=dist/app/InfluenszerRadar
  codesign --force --deep --sign - "$APP" 2>/dev/null || true
  ZIP="dist/InfluenszerRadar-macos-$(uname -m).zip"; rm -f "$ZIP" && (cd dist/app && ditto -c -k --keepParent "$(basename "$APP")" "../$(basename "$ZIP")")
  echo "built $APP and $ZIP ($(du -sh "$ZIP" | cut -f1))"
elif [ "$OS" = windows ]; then
  $PY -c "import shutil;shutil.make_archive('dist/InfluenszerRadar-windows-x64','zip','dist/app','InfluenszerRadar')" && echo "built dist/InfluenszerRadar-windows-x64.zip"
else
  (cd dist/app && tar czf "../InfluenszerRadar-linux-$(uname -m).tar.gz" InfluenszerRadar) && echo "built dist/InfluenszerRadar-linux-$(uname -m).tar.gz"
fi
