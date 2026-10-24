#!/usr/bin/env bash
# Build only our own helpers on the development machine; no Microsoft/JP binaries.
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
out="$root/research/mac-trial-tools"
mkdir -p "$out"
bash "$root/scripts/build-wine-compat.sh"
cp "$root/research/compat/upri_ace_datainit.dll" "$root/research/compat/upri_wmi_path.dll" "$out/"
x86_64-w64-mingw32-g++ -municode -O2 -static-libgcc -static-libstdc++ "$root/scripts/mac-trial/register-framework-gac.cpp" -o "$out/register-framework-gac.exe"
x86_64-w64-mingw32-gcc "$root/scripts/wine_ui_probe.c" -o "$out/wine_ui_probe.exe"
mcs -sdk:2 -platform:x64 -target:winexe -r:System.Data -out:"$out/mac-runtime-probe.exe" "$root/scripts/mac-trial/runtime-probe.cs"
mcs -sdk:2 -platform:x64 -target:winexe -r:System.Data -r:System.Xml -out:"$out/mac-db64.exe" "$root/scripts/wine_db_probe.cs"
mcs -sdk:2 -platform:x64 -target:winexe -r:System.Management -out:"$out/mac-identity.exe" "$root/scripts/wine_identity_probe.cs"
echo "Own helper binaries: $out"
