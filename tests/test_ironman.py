"""Functional tests for the ironman flag-flipping tool.

These build a small synthetic .sav (a zip with `gamestate` + `meta`) in a temp
dir, so they need neither the real (large) save nor Stellaris installed.
"""
import subprocess
import sys
import zipfile

import pytest

import stellaris_ironman as si


def make_save(path, state="on", meta_flag=True, order=("gamestate", "meta"),
              method=zipfile.ZIP_DEFLATED):
    """Write a synthetic Stellaris-like save and return its raw entry bytes.

    Ironman saves carry the flag in BOTH entries; real non-Ironman saves carry
    ironman=no in gamestate and OMIT it from meta (set meta_flag=False to model
    that). meta ends with a top-level key, matching Stellaris layout.
    """
    flag = b"ironman=yes" if state == "on" else b"ironman=no"
    meta = b'version="Test"\nname="Synthetic Empire"\nmeta_planets=1\n'
    if meta_flag:
        meta += flag + b"\n"
    blobs = {
        "gamestate": b'version="Test"\nname="Synthetic Empire"\n\t' + flag + b"\n",
        "meta": meta,
    }
    with zipfile.ZipFile(path, "w", compression=method) as z:
        for name in order:
            z.writestr(name, blobs[name])
    return blobs


def entries(path):
    with zipfile.ZipFile(path) as z:
        return z.namelist()


def methods(path):
    with zipfile.ZipFile(path) as z:
        return {i.filename: i.compress_type for i in z.infolist()}


def read_entry(path, name):
    with zipfile.ZipFile(path) as z:
        return z.read(name)


# --------------------------------------------------------------------------- #
# state detection
# --------------------------------------------------------------------------- #
def test_entry_state():
    assert si.entry_state(b"x\nironman=yes\n") == si.ON
    assert si.entry_state(b"x\nironman=no\n") == si.OFF
    assert si.entry_state(b"no flag here") == "absent"
    assert si.entry_state(b"ironman=yes\nironman=no\n") == "mixed"


def test_status_detects_on(tmp_path):
    save = tmp_path / "ironman.sav"
    make_save(save, "on")
    names, _, data = si.load_zip(str(save))
    assert si.overall_state(si.describe_save(names, data)) == si.ON


# --------------------------------------------------------------------------- #
# disable / enable / round-trip
# --------------------------------------------------------------------------- #
def test_disable_flips_and_preserves_layout(tmp_path):
    save = tmp_path / "ironman.sav"
    make_save(save, "on")
    out = tmp_path / "out.sav"
    rc = si.main(["disable", str(save), "-o", str(out)])
    assert rc == 0
    # layout preserved: same order, all deflate
    assert entries(str(out)) == ["gamestate", "meta"]
    assert set(methods(str(out)).values()) == {zipfile.ZIP_DEFLATED}
    for name in si.FLAG_ENTRIES:
        d = read_entry(str(out), name)
        assert d.count(b"ironman=yes") == 0
        assert d.count(b"ironman=no") == 1


def test_roundtrip_byte_identical(tmp_path):
    save = tmp_path / "ironman.sav"
    orig = make_save(save, "on")
    disabled = tmp_path / "disabled.sav"
    enabled = tmp_path / "enabled.sav"
    assert si.main(["disable", str(save), "-o", str(disabled)]) == 0
    assert si.main(["enable", str(disabled), "-o", str(enabled)]) == 0
    for name in si.FLAG_ENTRIES:
        assert read_entry(str(enabled), name) == orig[name]


def test_toggle(tmp_path):
    save = tmp_path / "ironman.sav"
    make_save(save, "on")
    assert si.main(["toggle", str(save), "--in-place", "--no-backup"]) == 0
    assert read_entry(str(save), "meta").count(b"ironman=no") == 1


def test_idempotent_disable_writes_nothing(tmp_path):
    save = tmp_path / "ironman.sav"
    make_save(save, "off")  # already disabled
    out = tmp_path / "out.sav"
    rc = si.main(["disable", str(save), "-o", str(out)])
    assert rc == 0
    assert not out.exists()  # no-op: nothing written


def test_in_place_makes_backup(tmp_path):
    save = tmp_path / "ironman.sav"
    orig = make_save(save, "on")
    assert si.main(["disable", str(save), "--in-place"]) == 0
    bak = tmp_path / "ironman.sav.bak"
    assert bak.exists()
    assert read_entry(str(bak), "gamestate") == orig["gamestate"]
    assert read_entry(str(save), "meta").count(b"ironman=no") == 1


def test_overwrite_guard(tmp_path):
    save = tmp_path / "ironman.sav"
    make_save(save, "on")
    out = tmp_path / "out.sav"
    out.write_bytes(b"existing")
    assert si.main(["disable", str(save), "-o", str(out)]) != 0  # refuses
    assert si.main(["disable", str(save), "-o", str(out), "--force"]) == 0


# --------------------------------------------------------------------------- #
# real-world asymmetry: non-Ironman saves omit the flag from meta
# (regression for: `enable` erroring with "no ironman flag found in 'meta'")
# --------------------------------------------------------------------------- #
def test_enable_on_normal_save_appends_meta_flag(tmp_path):
    save = tmp_path / "2200.01.01 - autosave.sav"
    make_save(save, state="off", meta_flag=False)  # gamestate=no, meta has no flag
    assert b"ironman" not in read_entry(str(save), "meta")  # precondition
    out = tmp_path / "out.sav"
    assert si.main(["enable", str(save), "-o", str(out)]) == 0
    assert read_entry(str(out), "gamestate").count(b"ironman=yes") == 1
    meta = read_entry(str(out), "meta")
    assert meta.count(b"ironman=yes") == 1
    assert meta.endswith(b"ironman=yes\n")  # appended as final top-level line


def test_disable_on_normal_save_is_noop(tmp_path):
    save = tmp_path / "normal.sav"
    make_save(save, state="off", meta_flag=False)  # already non-Ironman
    out = tmp_path / "out.sav"
    assert si.main(["disable", str(save), "-o", str(out)]) == 0
    assert not out.exists()  # nothing to do -> no file written


def test_status_normal_save_reads_off(tmp_path):
    save = tmp_path / "normal.sav"
    make_save(save, state="off", meta_flag=False)
    names, _, data = si.load_zip(str(save))
    states = si.describe_save(names, data)
    assert states["meta"] == "absent"
    assert si.overall_state(states) == si.OFF


def test_toggle_normal_save_enables(tmp_path):
    save = tmp_path / "normal.sav"
    make_save(save, state="off", meta_flag=False)
    assert si.main(["toggle", str(save), "--in-place", "--no-backup"]) == 0
    assert read_entry(str(save), "gamestate").count(b"ironman=yes") == 1
    assert read_entry(str(save), "meta").endswith(b"ironman=yes\n")


# --------------------------------------------------------------------------- #
# guards against malformed saves
# --------------------------------------------------------------------------- #
def test_apply_target_rejects_absent():
    data = {"gamestate": b"no flag", "meta": b"ironman=yes"}
    with pytest.raises(ValueError):
        si.apply_target(["gamestate", "meta"], data, si.OFF)


def test_apply_target_rejects_mixed():
    data = {"gamestate": b"ironman=yes\nironman=no", "meta": b"ironman=yes"}
    with pytest.raises(ValueError):
        si.apply_target(["gamestate", "meta"], data, si.OFF)


def test_load_zip_rejects_non_zip(tmp_path):
    bad = tmp_path / "bad.sav"
    bad.write_bytes(b"not a zip")
    with pytest.raises(ValueError):
        si.load_zip(str(bad))


# --------------------------------------------------------------------------- #
# CLI entry point (run the module file directly, like an end user)
# --------------------------------------------------------------------------- #
def test_cli_status(tmp_path):
    save = tmp_path / "ironman.sav"
    make_save(save, "on")
    r = subprocess.run([sys.executable, si.__file__, "status", str(save)],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "ironman ON" in r.stdout


def test_cli_version():
    r = subprocess.run([sys.executable, si.__file__, "--version"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert si.get_base_version() in r.stdout
