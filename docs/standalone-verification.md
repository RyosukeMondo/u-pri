# Standalone setup verification

Desired state: API, dashboard, data, MCP and local desktop trial on the user's one computer.
Raw inputs: local.py, desktop.py, real Mac GUI and Ubuntu HTTP/DB/UI probes.
Baseline: native API verified on Ubuntu; Mac client previously depended on Ubuntu; 0 verified shipping labels.
Target: same-machine setup + authenticated API/CSV/restart + real local app authentication screen. Cold install time target: unknown until measured.
Outside judge: real HTTP/restart smoke, native app DB/identity/UI probes, fresh-context release review and CI.

Windows shipping, Japan Post authentication, official label generation, physical printing and Claude Desktop UI integration remain unverified.

## 2026-10-25 initial public package

- Ubuntu: 35 tests passed. Real HTTP 100 rows × 99 columns; restart persistence,
  identical retry and history reconciliation passed (21.0 ms create/download in one run, not an SLA).
- Mac M4 / macOS 26.1: a new Python3.12 environment installed on the Mac itself.
  Local API, authenticated capabilities, demo page and embedded-Japanese-font PDF passed.
  23 API/dashboard/setup tests passed before the later absent-gallery regression was added.
  Real HTTP 100 rows × 99 columns, restart and retry passed (6.75 ms in one run).
- Mac MCP → Mac 127.0.0.1 API: SDK discovery and create/retry/download passed.
  SSH was the test controller only; the API, client, database and processing ran on Mac.
- New desktop.py installer on Mac: freshly extracted Wine bundle, fresh Wine prefix,
  DB open, identity checks and actual registration-window probe passed. Official
  installer archives and own helper ZIP were cached and rehashed. No installed .NET
  components or Windows prefix were copied from another PC. Rosetta was already present.
- The trial uses an external APFS work volume. It is not a measurement of first-time
  Rosetta setup, initial network download time, or every Mac hardware/OS version.
- Independent review found missing optional-gallery assets, stale/private doc links,
  and Windows default-encoding exposure. Corrected with conditional gallery display,
  public doc links and explicit UTF-8; no obvious credentials/vendor binaries in source.
- Windows CI and the generic fresh Linux desktop installer are pending at this initial commit.
