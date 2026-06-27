# Platform Support

`stellaris-ironman-cheat` is pure Python (standard library only) and operates on raw bytes, so it has no platform-specific code paths.

| Platform | Status | Notes |
| --- | --- | --- |
| Windows 11 | Tested | Developed and verified here (Python 3.12). CI runs on `windows-latest`. |
| Windows 10 | Expected | Same code path as Windows 11. |
| Linux | Expected | Pure stdlib; no OS-specific behavior. |
| macOS | Expected | Pure stdlib; no OS-specific behavior. |

CI exercises Python 3.10–3.13 on `windows-latest`. The package targets Python 3.8+.

**Legend:** "Tested" means verified by a human and/or CI on that platform. "Expected" means there is no platform-specific code and it should work, but it has not been routinely exercised there yet.

Platform reports are welcome via [issues](https://github.com/djdarcy/stellaris-ironman-cheat/issues).
