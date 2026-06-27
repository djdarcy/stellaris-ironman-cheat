# stellaris-ironman-cheat

[![CI](https://github.com/djdarcy/stellaris-ironman-cheat/actions/workflows/ci.yml/badge.svg)](https://github.com/djdarcy/stellaris-ironman-cheat/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](docs/platform-support.md)
[![Installs](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/djdarcy/ff418211987c5d581ed195dc9f656177/raw/installs.json)](https://djdarcy.github.io/stellaris-ironman-cheat/stats/)

A tiny command-line tool that flips **Ironman** mode on or off in a Stellaris save file, so you can drop a locked Ironman game into normal mode (and use the in-game console), then flip it back later if you want.

It is a single Python file with **no dependencies** beyond the standard library, and it runs on Windows, macOS, and Linux.

> **Heads up:** A save with Ironman disabled **cannot earn Steam achievements** — that is how Stellaris works, not a limitation of this tool. If you only want to disable Ironman temporarily, keep the original `ironman.sav` so you can flip it back.

## Why this exists

Ironman mode disables the console and most save editing. The usual way to "cheat" in an Ironman game is to turn Ironman off, do what you need in a normal game, and (optionally) turn it back on. Doing that by hand means unzipping the save, editing two files with a very particular text editor, and re-zipping with very particular settings -- get it slightly wrong and Stellaris refuses to load the save. This tool does the same edit reliably and keeps the archive in exactly the layout the game expects.

## How a Stellaris save works

A `.sav` file is actually a ZIP archive containing two text entries:

- `gamestate` — the entire game (large)
- `meta` — the small header the save browser reads (empire name, date, DLC list, flag)

Each carries an `ironman=yes` / `ironman=no` line, except non-Ironman saves omit the flag from `meta` entirely (it lives only in `gamestate`). This tool brings **both** entries to the target state: it flips the line in place where present, and when enabling a save whose `meta` has no flag it appends `ironman=yes` as a final line (matching how Stellaris writes Ironman saves). It then writes the archive back with the original entry order and per-entry Deflate compression preserved. This is what makes the result load properly. It edits raw bytes (never re-encodes text), so empire and system names with non-ASCII characters are left exactly as they were. After writing, it re-opens the file and verifies the flag landed correctly. It does **not** touch checksums, achievements, or anything else -- Stellaris saves are not tamper-protected, which is (theoretically) why this should work.

## Install

No install is required -- it is one file:

```bash
git clone https://github.com/djdarcy/stellaris-ironman-cheat.git
cd stellaris-ironman-cheat
python stellaris_ironman.py status "path/to/ironman.sav"
```

Or install it to get a `stellaris-ironman` command on your PATH:

```bash
pip install -e .
stellaris-ironman status "path/to/ironman.sav"
```

Requires Python 3.8 or newer (standard library only).

## Usage

```
stellaris-ironman status  <save.sav>     # or: python stellaris_ironman.py status <save.sav>
stellaris-ironman disable <save.sav>
stellaris-ironman enable  <save.sav>
stellaris-ironman toggle  <save.sav>
```

By default, **the original file is never changed** -- a new file is written next to it (`save.noironman.sav` for disable, `save.ironman.sav` for enable). Examples:

```bash
# See what state a save is in
python stellaris_ironman.py status "ironman.sav"

# Disable Ironman -> writes "ironman.noironman.sav" beside the original
python stellaris_ironman.py disable "ironman.sav"

# Disable Ironman to a name you choose
python stellaris_ironman.py disable "ironman.sav" -o "play normally.sav"

# Edit the file directly (a .bak copy is made first)
python stellaris_ironman.py disable "ironman.sav" --in-place

# Preview without writing anything
python stellaris_ironman.py disable "ironman.sav" --dry-run
```

### Options (for `disable` / `enable` / `toggle`)

| Option | Effect |
| --- | --- |
| `-o`, `--output PATH` | Write the result to a specific path. |
| `--in-place` | Edit the original file. A `<save>.bak` copy is made first. |
| `--no-backup` | With `--in-place`, skip the `.bak` copy. |
| `--force` | Allow overwriting an existing output or backup file. |
| `--dry-run` | Show what would happen; write nothing. |

The tool refuses to act if a save is already in the requested state (it just says "nothing to do"), if the output would clobber an existing file without `--force`, or if the Ironman flag is missing or looks malformed — rather than risk corrupting a save.

## Where Stellaris saves live

Saves are grouped in a folder per empire. Ironman saves are named `ironman.sav`.

- **Windows:** `%USERPROFILE%\Documents\Paradox Interactive\Stellaris\save games\<empire>\`
- **Linux:** `~/.local/share/Paradox Interactive/Stellaris/save games/<empire>/`
- **macOS:** `~/Documents/Paradox Interactive/Stellaris/save games/<empire>/`

Drop the edited save into the same empire folder and it will appear in the in-game **Load Game** list. Open the console with `~` (or `` ` `` / `Shift+2` / `§` depending on your keyboard).

## Re-enabling Ironman later

Run `enable` (or `toggle`) on the edited save to set `ironman=yes` again. Flipping `disable` then `enable` reproduces the original `gamestate` and `meta` byte-for-byte.

Note that turning Ironman back **on** does not by itself restore Steam-achievement eligibility for that save. Some players additionally restore the save's original `achievement={ ... }` block (saved off before editing) so the game treats the save as achievement-compatible again. That step is game-version-specific and intentionally **out of scope** for this tool, which only manages the `ironman` flag. See the [Stellaris save-game editing wiki](https://stellaris.paradoxwikis.com/Save-game_editing) for details if you need it.

## Safety

- Always keep a copy of your unedited `ironman.sav` until you have confirmed the edited save loads.
- The default behavior writes a new file and leaves your original alone.
- `--in-place` makes a `.bak` first and will not overwrite an existing `.bak` without `--force`.

## Development

```bash
git clone https://github.com/djdarcy/stellaris-ironman-cheat.git
cd stellaris-ironman-cheat
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Tests build a small synthetic save in a temp directory, so they need neither a real save nor Stellaris installed. See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Roadmap](https://github.com/djdarcy/stellaris-ironman-cheat/issues/3).

## Disclaimer

This is an unofficial, fan-made utility and is not affiliated with or endorsed by Paradox Interactive. Editing save files is done at your own risk; back up your saves first. Disabling Ironman disables Steam achievements for that save.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
