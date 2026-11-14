"""An emulator upgrade keeps every file the previous archive did not ship.

Several emulators keep saves, save states, memory cards and installed
firmware INSIDE their install directory. An upgrade that replaces the whole
directory deletes them; these tests pin the contract that replaces it:

- only what the previous version shipped and the new one no longer ships is
  removed, and only what the previous version shipped is overwritten;
- an install made before member lists existed keeps every path the new
  archive does not contain;
- a failure at any point of the changeover is repaired by the next run, which
  ends in the same state as an uninterrupted upgrade.
"""
import hashlib
import json
import os
import zipfile

import pytest

from retro import acquire, manifest

V1 = {
    "truc.exe": "exe v1",
    "lib/dropped.dll": "dropped v1",
    "lib/kept.dll": "kept v1",
    "data/default.cfg": "default v1",
}
V2 = {
    "truc.exe": "exe v2",
    "lib/kept.dll": "kept v1",
    "data/default.cfg": "default v2",
    "data/new.cfg": "new v2",
}
USER_FILES = {
    # A save in a sub-directory the archive never shipped.
    "saves/memcard1.mcd": b"\x00\x01save\xff",
    # A file next to the executable.
    "portable.ini": b"user=1\r\n",
}


def make_zip(path, members):
    with zipfile.ZipFile(path, "w") as z:
        for name, content in members.items():
            z.writestr(name, content)
    return path.read_bytes()


def emulator(blob, version):
    return manifest.Emulator(
        key="truc", name="Truc", version=version,
        url=f"https://example.invalid/truc-{version}.zip",
        sha256=hashlib.sha256(blob).hexdigest(),
        archive="zip", install_dir="Truc", profile="truc",
    )


@pytest.fixture
def archives(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    b1 = make_zip(src / "v1.zip", V1)
    b2 = make_zip(src / "v2.zip", V2)
    return (emulator(b1, "1.0"), b1), (emulator(b2, "2.0"), b2)


def put_user_files(target):
    for rel, content in USER_FILES.items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def tree(target):
    """Every regular file under `target`, as {posix path: bytes}."""
    found = {}
    for root, _dirs, files in os.walk(target):
        for name in files:
            path = os.path.join(root, name)
            rel = os.path.relpath(path, target).replace(os.sep, "/")
            with open(path, "rb") as f:
                found[rel] = f.read()
    return found


def assert_upgraded(target, *, legacy=False):
    files = tree(target)
    for rel, content in USER_FILES.items():
        assert files.get(rel) == content, f"user file {rel} lost or altered"
    for rel, content in V2.items():
        assert files.get(rel) == content.encode(), f"{rel} is not the v2 file"
    if legacy:
        # Nothing says the old archive shipped it: it is kept.
        assert files.get("lib/dropped.dll") == b"dropped v1"
    else:
        assert "lib/dropped.dll" not in files
    assert files[acquire.TEMOIN].decode().strip() == "2.0"


def test_an_upgrade_keeps_user_files_and_drops_only_obsolete_shipped_ones(
        tmp_path, archives):
    (e1, b1), (e2, b2) = archives
    root = tmp_path / "Emulation"
    target = root / "Truc"
    assert acquire.acquire(e1, root, fetch=lambda u: b1) == "installé"
    put_user_files(target)

    assert acquire.acquire(e2, root, fetch=lambda u: b2) == "réinstallé"

    assert_upgraded(target)
    # Nothing staged is left behind next to the install.
    assert sorted(p.name for p in root.iterdir()) == ["Truc"]


def test_an_install_without_member_list_keeps_every_path_not_in_the_archive(
        tmp_path, archives):
    """Every install made before this fix has a witness and no member list."""
    (_e1, _b1), (e2, b2) = archives
    root = tmp_path / "Emulation"
    target = root / "Truc"
    for rel, content in V1.items():
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        (target / rel).write_text(content)
    (target / acquire.TEMOIN).write_text("1.0\n", encoding="utf-8")
    put_user_files(target)

    assert acquire.acquire(e2, root, fetch=lambda u: b2) == "réinstallé"

    assert_upgraded(target, legacy=True)


def test_a_new_shipped_path_never_overwrites_a_file_the_old_archive_lacked(
        tmp_path, archives):
    """`data/new.cfg` appears in v2; a file the owner put there first wins."""
    (e1, b1), (e2, b2) = archives
    root = tmp_path / "Emulation"
    target = root / "Truc"
    acquire.acquire(e1, root, fetch=lambda u: b1)
    (target / "data" / "new.cfg").write_bytes(b"mine")

    result = acquire.acquire(e2, root, fetch=lambda u: b2)

    assert (target / "data" / "new.cfg").read_bytes() == b"mine"
    assert "data/new.cfg" not in result.replaced
    # It is still not ours: the next upgrade must leave it alone too.
    e3 = emulator(b2, "3.0")
    acquire.acquire(e3, root, fetch=lambda u: b2)
    assert (target / "data" / "new.cfg").read_bytes() == b"mine"


def test_the_result_names_what_was_replaced_and_removed(tmp_path, archives):
    (e1, b1), (e2, b2) = archives
    root = tmp_path / "Emulation"
    acquire.acquire(e1, root, fetch=lambda u: b1)
    put_user_files(root / "Truc")

    result = acquire.acquire(e2, root, fetch=lambda u: b2)

    assert result.replaced == frozenset(
        {"truc.exe", "lib/kept.dll", "data/default.cfg"})
    assert result.removed == frozenset({"lib/dropped.dll"})


def test_the_extraction_is_staged_on_the_target_volume(tmp_path, archives,
                                                        monkeypatch):
    """Staged in the system temp directory, the tree sat on another volume
    on the console, and the changeover could only copy."""
    (e1, b1), _ = archives
    root = tmp_path / "Emulation"
    seen = []
    real = acquire.safe_extract

    def spy(archive, kind, destination):
        seen.append(destination)
        return real(archive, kind, destination)

    monkeypatch.setattr(acquire, "safe_extract", spy)
    acquire.acquire(e1, root, fetch=lambda u: b1)
    assert seen and all(d.parent == root for d in seen)


# --- a changeover interrupted anywhere is repaired by the next run -------------

def count_calls(monkeypatch, name, run):
    calls = []
    real = getattr(os, name)

    def counting(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(os, name, counting)
    run()
    monkeypatch.setattr(os, name, real)
    return len(calls)


def fail_at(monkeypatch, name, index):
    """Make the `index`-th call to os.<name> fail like a locked file."""
    real = getattr(os, name)
    calls = []

    def failing(*args, **kwargs):
        calls.append(args)
        if len(calls) == index:
            raise PermissionError(32, "The process cannot access the file "
                                      "because it is being used by another "
                                      "process")
        return real(*args, **kwargs)

    monkeypatch.setattr(os, name, failing)
    return real


def installed_v1(tmp_path, e1, b1, name):
    root = tmp_path / name / "Emulation"
    acquire.acquire(e1, root, fetch=lambda u: b1)
    put_user_files(root / "Truc")
    return root


@pytest.mark.parametrize("primitive", ["replace", "unlink"])
def test_a_failure_at_any_step_then_a_rerun_ends_upgraded(
        tmp_path, archives, monkeypatch, primitive):
    (e1, b1), (e2, b2) = archives
    probe = installed_v1(tmp_path, e1, b1, "probe")
    steps = count_calls(monkeypatch, primitive,
                        lambda: acquire.acquire(e2, probe, fetch=lambda u: b2))
    assert steps > 0, f"the upgrade never calls os.{primitive}"

    failed = []
    for index in range(1, steps + 1):
        root = installed_v1(tmp_path, e1, b1, f"{primitive}-{index}")
        target = root / "Truc"
        real = fail_at(monkeypatch, primitive, index)
        try:
            acquire.acquire(e2, root, fetch=lambda u: b2)
        except acquire.AcquireError as exc:
            failed.append(index)
            assert "Truc" in str(exc), index
        else:
            # Only the tolerated clean-up of the system temp directory may
            # absorb the failure, and then the upgrade must be complete.
            monkeypatch.setattr(os, primitive, real)
            assert_upgraded(target)
            continue
        finally:
            monkeypatch.setattr(os, primitive, real)

        files = tree(target)
        for rel, content in USER_FILES.items():
            assert files.get(rel) == content, (index, rel)
        witness = files.get(acquire.TEMOIN, b"").decode().strip()
        if witness == "1.0":
            # Untouched: the old tree must still be complete.
            for rel, content in V1.items():
                assert files.get(rel) == content.encode(), (index, rel)
        else:
            # Mid-changeover: the install must not claim to be attested.
            assert witness != "2.0", index

        acquire.acquire(e2, root, fetch=lambda u: b2)
        assert_upgraded(target)
        assert sorted(p.name for p in root.iterdir()) == ["Truc"], index
    assert failed, "no injected failure ever reached the changeover"


def test_a_failed_download_leaves_the_old_install_whole(tmp_path, archives):
    (e1, b1), (e2, _b2) = archives
    root = installed_v1(tmp_path, e1, b1, "dl")
    before = tree(root / "Truc")

    def offline(url):
        raise OSError("network unreachable")

    with pytest.raises(acquire.AcquireError):
        acquire.acquire(e2, root, fetch=offline)
    assert tree(root / "Truc") == before


def test_an_interrupted_upgrade_then_a_newer_version_removes_its_leftovers(
        tmp_path, archives, monkeypatch):
    """A file placed by the interrupted v2 changeover is still ours for v3."""
    (e1, b1), (e2, b2) = archives
    root = installed_v1(tmp_path, e1, b1, "v3")
    target = root / "Truc"
    v3 = {"truc.exe": "exe v3"}
    b3 = make_zip(tmp_path / "v3.zip", v3)
    e3 = emulator(b3, "3.0")

    real = os.replace
    placed = []

    def stop_after_new_cfg(src, dst, *args, **kwargs):
        if placed:
            raise PermissionError(32, "locked")
        result = real(src, dst, *args, **kwargs)
        if os.fspath(dst).endswith("new.cfg"):
            placed.append(dst)
        return result

    monkeypatch.setattr(os, "replace", stop_after_new_cfg)
    with pytest.raises(acquire.AcquireError):
        acquire.acquire(e2, root, fetch=lambda u: b2)
    monkeypatch.setattr(os, "replace", real)
    assert placed, "the injected failure never reached data/new.cfg"

    acquire.acquire(e3, root, fetch=lambda u: b3)

    files = tree(target)
    for rel, content in USER_FILES.items():
        assert files.get(rel) == content
    assert files["truc.exe"] == b"exe v3"
    for gone in ("data/new.cfg", "data/default.cfg", "lib/kept.dll",
                 "lib/dropped.dll"):
        assert gone not in files, gone


def test_the_member_list_is_kept_next_to_the_witness(tmp_path, archives):
    (e1, b1), _ = archives
    root = tmp_path / "Emulation"
    acquire.acquire(e1, root, fetch=lambda u: b1)
    listed = json.loads((root / "Truc" / acquire.MEMBRES).read_text(
        encoding="utf-8"))
    assert sorted(listed["files"]) == sorted(V1)


def test_a_shipped_file_where_the_owner_has_a_directory_touches_nothing(
        tmp_path, archives):
    (e1, b1), _ = archives
    root = tmp_path / "Emulation"
    target = root / "Truc"
    acquire.acquire(e1, root, fetch=lambda u: b1)
    put_user_files(target)
    b2 = make_zip(tmp_path / "clash.zip", {"truc.exe": "exe v2",
                                           "saves": "now a file"})
    e2 = emulator(b2, "2.0")
    before = tree(target)
    with pytest.raises(acquire.AcquireError) as exc:
        acquire.acquire(e2, root, fetch=lambda u: b2)
    assert "saves" in str(exc.value)
    assert tree(target) == before
