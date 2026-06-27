#!/usr/bin/env python3
# Copyright (C) 2026 Dustin Darcy
# SPDX-License-Identifier: GPL-3.0-or-later
#
# stellaris_ironman is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version. It is distributed WITHOUT ANY WARRANTY; see the GNU General
# Public License (the LICENSE file) for details.
"""stellaris_ironman.py -- toggle Ironman mode in Stellaris save files.

A Stellaris ".sav" is really a ZIP archive containing two text entries:
"gamestate" and "meta". Each carries an `ironman=yes` / `ironman=no` line.
This tool flips that flag in BOTH entries while preserving the archive layout
Stellaris expects (entry order + per-entry Deflate compression), so the edited
save loads cleanly.

  * disable  -> ironman=no   (lets you open the console with `~` and play normally)
  * enable   -> ironman=yes  (restores Ironman mode)
  * toggle   -> flip whatever the save currently is
  * status   -> report the current flag state without changing anything

Notes
-----
* A non-Ironman save CANNOT earn Steam achievements -- that is the inherent
  trade-off of disabling Ironman, not a bug in this tool.
* By default a NEW file is written and the original is left untouched. Use
  --in-place to edit the original (a ".bak" copy is made first unless
  --no-backup is given).
* Stdlib only. Works on Windows, macOS, and Linux. Operates on raw bytes, so
  non-ASCII empire/system names are preserved exactly.

This tool only flips the `ironman` flag. If you later re-enable Ironman and want
Steam-achievement compatibility restored as well, see the README for the
separate "achievement={...}" restore step -- that is out of scope here.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile

# --------------------------------------------------------------------------- #
# Version (repokit-managed). sync-versions.py edits MAJOR/MINOR/PATCH/PHASE and
# the __version__ build stamp here on each commit; see pyproject.toml
# [tool.repokit-common] version-source = "stellaris_ironman.py".
# --------------------------------------------------------------------------- #
MAJOR = 0
MINOR = 1
PATCH = 0
PHASE = ""  # "" (stable), "alpha", "beta", "rc1", ...
PROJECT_PHASE = ""  # "prealpha", "alpha", "beta", "stable", or ""

# Auto-updated by git hooks -- do not edit manually.
__version__ = "0.1.0"
__app_name__ = "stellaris-ironman-cheat"


def get_version() -> str:
    """Full version string including branch/build metadata (if stamped)."""
    return __version__


def get_base_version() -> str:
    """Semantic version MAJOR.MINOR.PATCH[-PHASE]."""
    if "_" in __version__:
        return __version__.split("_")[0]
    base = f"{MAJOR}.{MINOR}.{PATCH}"
    return f"{base}-{PHASE}" if PHASE else base


def get_display_version() -> str:
    """Human-friendly version, e.g. 'PREALPHA 0.1.0' or '1.0.0'."""
    base = get_base_version()
    if PROJECT_PHASE and PROJECT_PHASE != "stable":
        return f"{PROJECT_PHASE.upper()} {base}"
    return base


def get_pip_version() -> str:
    """PEP 440 version for pip/setuptools (strips build metadata)."""
    base = f"{MAJOR}.{MINOR}.{PATCH}"
    phase_map = {"alpha": "a0", "beta": "b0"}
    if PHASE:
        base += phase_map.get(PHASE, PHASE)
    if "_" not in __version__:
        return base
    parts = __version__.split("_")
    branch = parts[1] if len(parts) > 1 else "unknown"
    if branch == "main":
        return base
    build_info = "_".join(parts[2:]) if len(parts) > 2 else ""
    build_num = build_info.split("-")[0] if "-" in build_info else "0"
    return f"{base}.dev{build_num}"


VERSION = get_version()
BASE_VERSION = get_base_version()
PIP_VERSION = get_pip_version()
DISPLAY_VERSION = get_display_version()


# The two entries inside the .sav zip that carry the ironman flag.
FLAG_ENTRIES = ("gamestate", "meta")

YES = b"ironman=yes"
NO = b"ironman=no"

# Resulting-state labels used throughout.
ON = "on"    # ironman=yes
OFF = "off"  # ironman=no


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


# --------------------------------------------------------------------------- #
# zip helpers
# --------------------------------------------------------------------------- #
def load_zip(path: str):
    """Return (names_in_order, {name: ZipInfo}, {name: bytes})."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"save file not found: {path}")
    try:
        with zipfile.ZipFile(path, "r") as z:
            names = z.namelist()
            infos = {i.filename: i for i in z.infolist()}
            data = {n: z.read(n) for n in names}
    except zipfile.BadZipFile as exc:
        raise ValueError(
            f"not a valid Stellaris save (zip) file: {path} ({exc})"
        ) from exc
    return names, infos, data


def write_zip(path: str, names, infos, data) -> None:
    """Write a zip preserving original entry order and per-entry compression."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name in names:
            src = infos[name]
            zi = zipfile.ZipInfo(filename=name, date_time=src.date_time)
            zi.compress_type = src.compress_type  # preserve method (8 = deflate)
            zi.external_attr = src.external_attr
            z.writestr(zi, data[name])


# --------------------------------------------------------------------------- #
# flag logic
# --------------------------------------------------------------------------- #
def entry_state(blob: bytes) -> str:
    """Classify a single entry's ironman flag.

    Returns one of: "on", "off", "absent", "mixed".
    """
    y = blob.count(YES)
    n = blob.count(NO)
    if y == 1 and n == 0:
        return ON
    if y == 0 and n == 1:
        return OFF
    if y == 0 and n == 0:
        return "absent"
    return "mixed"  # unexpected: multiple flags / both present


def describe_save(names, data) -> dict:
    """Map each present flag-bearing entry to its state."""
    present = [n for n in FLAG_ENTRIES if n in data]
    return {n: entry_state(data[n]) for n in present}


def aggregate_state(states: dict) -> str:
    """Collapse per-entry states into one of on/off/absent/mixed."""
    vals = set(states.values())
    if not vals:
        return "absent"
    if vals == {ON}:
        return ON
    if vals == {OFF}:
        return OFF
    return "mixed"


def apply_target(names, data, target: str) -> int:
    """Flip flag-bearing entries to `target` (ON/OFF). Returns #entries changed.

    Aborts (raises) if any flag-bearing entry is absent or in a "mixed" state,
    since blindly editing those risks corrupting the save.
    """
    src_tok, dst_tok = (YES, NO) if target == OFF else (NO, YES)
    changed = 0
    for name in FLAG_ENTRIES:
        if name not in data:
            raise ValueError(f"entry '{name}' is missing from the save")
        st = entry_state(data[name])
        if st == "absent":
            raise ValueError(
                f"no ironman flag found in '{name}' -- is this a Stellaris save?"
            )
        if st == "mixed":
            raise ValueError(
                f"unexpected ironman flag layout in '{name}' "
                f"({data[name].count(YES)}x yes, {data[name].count(NO)}x no) "
                "-- refusing to edit"
            )
        if st == target:
            continue  # already in the desired state
        data[name] = data[name].replace(src_tok, dst_tok)
        changed += 1
    return changed


def verify_target(path: str, target: str) -> bool:
    """Re-open a written save and confirm every flag entry is at `target`."""
    _, _, data = load_zip(path)
    return all(entry_state(data[n]) == target for n in FLAG_ENTRIES if n in data)


# --------------------------------------------------------------------------- #
# output-path resolution
# --------------------------------------------------------------------------- #
def default_output(inp: str, target: str) -> str:
    root, ext = os.path.splitext(inp)
    if ext.lower() != ".sav":
        # respect whatever extension the user has; default keeps it.
        ext = ext or ".sav"
    suffix = "noironman" if target == OFF else "ironman"
    return f"{root}.{suffix}{ext}"


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_status(args) -> int:
    names, _, data = load_zip(args.save)
    states = describe_save(names, data)
    agg = aggregate_state(states)
    pretty = {ON: "ON  (ironman=yes)", OFF: "OFF (ironman=no)",
              "absent": "absent", "mixed": "MIXED"}
    print(f"Save:    {args.save}")
    print(f"Entries: {names}")
    for n in FLAG_ENTRIES:
        if n in states:
            print(f"  {n:<10} ironman {pretty[states[n]]}")
        else:
            print(f"  {n:<10} (entry not present)")
    print(f"Overall: ironman {pretty.get(agg, agg)}")
    if agg == "mixed":
        eprint("WARNING: gamestate and meta disagree -- run disable/enable to normalize.")
    return 0


def _set_state(args, target: str) -> int:
    inp = args.save
    names, infos, data = load_zip(inp)

    states = describe_save(names, data)
    agg = aggregate_state(states)
    verb = "disable" if target == OFF else "enable"

    if agg == target:
        print(f"Already {('disabled' if target == OFF else 'enabled')}: "
              f"ironman is {'OFF' if target == OFF else 'ON'} in {inp}. Nothing to do.")
        return 0

    # Decide where to write.
    if args.in_place:
        out = inp
    elif getattr(args, "output", None):
        out = args.output
    else:
        out = default_output(inp, target)

    # Plan the change on an in-memory copy.
    changed = apply_target(names, dict(data), target)  # validate first (raises on bad)
    # Re-apply to the real dict now that validation passed.
    changed = apply_target(names, data, target)

    if args.dry_run:
        print(f"[dry-run] would {verb} ironman in {inp}")
        print(f"[dry-run] entries to change: {changed}")
        print(f"[dry-run] would write: {out}")
        if args.in_place and not args.no_backup:
            print(f"[dry-run] would back up original to: {inp}.bak")
        return 0

    # Backups / overwrite guards.
    if args.in_place:
        if not args.no_backup:
            bak = inp + ".bak"
            if os.path.exists(bak) and not args.force:
                eprint(f"ERROR: backup already exists: {bak} (use --force to overwrite, "
                       "or --no-backup to skip).")
                return 2
            shutil.copy2(inp, bak)
            print(f"Backed up original -> {bak}")
    else:
        if os.path.abspath(out) == os.path.abspath(inp):
            eprint("ERROR: output equals input; use --in-place to edit the original.")
            return 2
        if os.path.exists(out) and not args.force:
            eprint(f"ERROR: output already exists: {out} (use --force to overwrite).")
            return 2

    write_zip(out, names, infos, data)

    if not verify_target(out, target):
        eprint(f"ERROR: verification failed -- {out} is not in the expected state.")
        return 3

    print(f"OK: ironman {'disabled' if target == OFF else 'enabled'} -> {out}")
    print(f"    ({changed} entr{'y' if changed == 1 else 'ies'} changed, "
          "format verified)")
    if target == OFF:
        print("    Note: non-Ironman saves cannot earn Steam achievements.")
    return 0


def cmd_disable(args) -> int:
    return _set_state(args, OFF)


def cmd_enable(args) -> int:
    return _set_state(args, ON)


def cmd_toggle(args) -> int:
    names, _, data = load_zip(args.save)
    agg = aggregate_state(describe_save(names, data))
    if agg == ON:
        return _set_state(args, OFF)
    if agg == OFF:
        return _set_state(args, ON)
    eprint(f"ERROR: cannot toggle -- current state is '{agg}'. "
           "Use disable/enable explicitly.")
    return 2


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stellaris_ironman",
        description="Toggle Ironman mode in a Stellaris .sav file.",
        epilog="A .sav is left untouched unless you pass --in-place. "
               "By default a new file is written next to it.",
    )
    p.add_argument("--version", action="version",
                   version=f"%(prog)s {get_display_version()}")
    sub = p.add_subparsers(dest="command", required=True)

    def add_write_opts(sp):
        sp.add_argument("save", help="path to the .sav file")
        sp.add_argument("-o", "--output", help="write the result to this path")
        sp.add_argument("--in-place", action="store_true",
                        help="edit the original file (a .bak is made first)")
        sp.add_argument("--no-backup", action="store_true",
                        help="with --in-place, do not create a .bak copy")
        sp.add_argument("--force", action="store_true",
                        help="overwrite an existing output/backup file")
        sp.add_argument("--dry-run", action="store_true",
                        help="show what would happen, write nothing")

    sp = sub.add_parser("status", help="show current ironman flag state")
    sp.add_argument("save", help="path to the .sav file")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("disable", help="set ironman=no")
    add_write_opts(sp)
    sp.set_defaults(func=cmd_disable)

    sp = sub.add_parser("enable", help="set ironman=yes")
    add_write_opts(sp)
    sp.set_defaults(func=cmd_enable)

    sp = sub.add_parser("toggle", help="flip the current ironman state")
    add_write_opts(sp)
    sp.set_defaults(func=cmd_toggle)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError) as exc:
        eprint(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
