#!/usr/bin/env bash
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
out_dir="$repo_dir/research/compat"
mkdir -p "$out_dir"
cxx=x86_64-w64-mingw32-g++
flags=(-std=c++17 -O2 -static-libgcc -static-libstdc++)
x86_64-w64-mingw32-windres "$repo_dir/compat/ace_datainit.rc" -o "$out_dir/ace_version.o"
"$cxx" "${flags[@]}" -shared "$repo_dir/compat/ace_datainit.cpp" "$out_dir/ace_version.o" -o "$out_dir/upri_ace_datainit.dll" -lole32 -loleaut32 -luuid
"$cxx" "${flags[@]}" -shared "$repo_dir/compat/wmi_path.cpp" -o "$out_dir/upri_wmi_path.dll" -lole32 -luuid
"$cxx" "${flags[@]}" "$repo_dir/tests/ace_parser.cpp" -o "$out_dir/ace_parser_test.exe" -lole32 -loleaut32 -luuid
"$cxx" "${flags[@]}" "$repo_dir/tests/wmi_path.cpp" -o "$out_dir/wmi_path_test.exe" -lole32 -luuid
printf 'Built experimental compatibility DLLs and tests in %s\n' "$out_dir"
