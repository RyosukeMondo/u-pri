# Experimental Wine 9 compatibility adapters

These are own-source experiments for isolated x64 Wine prefixes. Own compiled
helpers are also provided in the GitHub preview Release. They are
not a complete MDAC/WMI replacement, a supported Japan Post install recipe, or
evidence of working label printing. No vendor binaries/passwords are included.

`bash scripts/build-wine-compat.sh` builds two DLLs and two parser-test executables
using MinGW x64. Output goes to ignored `research/compat/`; the build does not
register anything or modify a Wine prefix.

## ACE connection property

Wine 9's connection parser turns `Jet OLEDB:Database Password` into an extended
provider string. Direct ACE property initialization worked while .NET string
initialization failed. `ace_datainit.cpp` delegates to Wine's original DataLinks/
MSDAINITIALIZE implementation after removing this option, then sets it through
the provider's own property metadata. Only ACE 12/16 strings are transformed.
Malformed/duplicate options and non-ACE providers are passed to the original.
No connection string is logged, and application binaries are unchanged.

The version resource explicitly identifies Upri. Its compatibility file version
2.80.9999 satisfies .NET 2's `CheckVersionMDAC` check on the registered DataLinks
DLL; product version is 0.1. This does not make the shim a full MDAC implementation.

Experimental scope: x64, new datasource objects. Existing-datasource calls pass
through unchanged. Initial requests for other factory interfaces delegate to the
original, but wrapper QueryInterface only exposes IUnknown/IDataInitialize.
Writable application connections remain writable; only the diagnostic requests
read-only access. No registration or authentication check is removed.

## WMI path syntax

`wmi_path.cpp` normalizes exact `Win32_LogicalDisk="C:"`-style paths (any ASCII
drive letter) to `Win32_LogicalDisk.DeviceID="C:"`. Wine 9 otherwise classifies
the shorthand as a class, causing .NET ManagementObject to reject it. Every WMI
method delegates to Wine; no serial number is created or substituted. Wrapper
QueryInterface supports only IUnknown/IWbemPath. Qualified paths pass unchanged.

## Local registration / rollback record

Only `research/wine64` was changed. The x64 `HKLM\Software\Classes\CLSID` keys
below retain `ThreadingModel=Both`; their `InprocServer32` default values now point
to the respective `C:\upri_*.dll` files:

| CLSID | Adapter | Original default value for rollback |
| --- | --- | --- |
| `{2206CDB0-19C1-11D1-89E0-00C04FD7A829}` | `upri_ace_datainit.dll` | `C:\Program Files\Common Files\System\OLE DB\oledb32.dll` |
| `{2206CDB2-19C1-11D1-89E0-00C04FD7A829}` | `upri_ace_datainit.dll` | `C:\Program Files\Common Files\System\OLE DB\oledb32.dll` |
| `{CF4CC405-E2C5-4DDD-B3CE-5E7582D8C9FA}` | `upri_wmi_path.dll` | `C:\windows\system32\wbem\wmiutils.dll` |

Set `WINEPREFIX` explicitly for every command and use `/reg:64` when restoring
these defaults with `wine reg add`. Never apply this record to a normal Windows
installation or another project's prefix. Stop processes in this prefix before
replacing loaded DLLs. Raw registry backups are private ignored research files.

## Evidence and upstream references

The actual read-only .NET database probe succeeded after the ACE adapter. The
actual application subsequently passed its former database error and reached
later initialization checks. Both parser test executables reported zero failures;
independent review found and prompted fixes for apostrophes and malformed quotes.
See [research status](../docs/standalone-verification.md) for remaining gates.

- [Wine 9 OLEDB parser](https://github.com/wine-mirror/wine/blob/wine-9.0/dlls/oledb32/datainit.c)
- [Wine 9 WMI path parser](https://github.com/wine-mirror/wine/blob/wine-9.0/dlls/wmiutils/path.c)
- [Microsoft .NET MDAC version check](https://github.com/microsoft/referencesource/blob/main/System.Data/System/Data/Common/AdapterUtil.cs)
