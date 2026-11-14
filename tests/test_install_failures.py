"""A filesystem failure on one emulator is that emulator's failure only.

`retro install` exits 2 when it could not read the manifest, and the suite's
installer reads exit 2 as "no emulator is installed". Any exception that
escapes `install_all` lands there; a full disk or a locked file while
installing ONE emulator must instead be recorded against it, and the others
still processed, so the command prints its report and exits 1.
"""
import errno
import hashlib
import os
import pathlib
import zipfile

import pytest

from retro import acquire, cli, install, manifest


def make_zip(path, members):
    with zipfile.ZipFile(path, "w") as z:
        for name, content in members.items():
            z.writestr(name, content)
    return path.read_bytes()


def emulator(key, blob, version="1.0"):
    return manifest.Emulator(
        key=key, name=key.title(), version=version,
        url=f"https://example.invalid/{key}-{version}.zip",
        sha256=hashlib.sha256(blob).hexdigest(),
        archive="zip", install_dir=key.title(), profile=key,
    )


@pytest.fixture
def two_emulators(tmp_path):
    """"a" installed at 1.0 with a save in it, "b" not installed yet."""
    b1 = make_zip(tmp_path / "a1.zip", {"a.exe": "a v1"})
    b2 = make_zip(tmp_path / "a2.zip", {"a.exe": "a v2"})
    bb = make_zip(tmp_path / "b.zip", {"b.exe": "b v1"})
    root = tmp_path / "Emulation"
    acquire.acquire(emulator("a", b1), root, fetch=lambda u: b1)
    save = root / "A" / "saves" / "slot1.sav"
    save.parent.mkdir(parents=True)
    save.write_bytes(b"\x00progress")
    blobs = {"a-2.0": b2, "b-1.0": bb}

    def fetch(url):
        return blobs[url.rsplit("/", 1)[1].removesuffix(".zip")]

    batch = {"a": emulator("a", b2, "2.0"), "b": emulator("b", bb)}
    return root, batch, fetch


def snapshot(directory):
    return {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in sorted(directory.rglob("*")) if p.is_file()}


def disk_full_on(monkeypatch, name):
    real = pathlib.Path.write_bytes

    def write_bytes(self, data):
        if self.name == name:
            raise OSError(errno.ENOSPC, "No space left on device", str(self))
        return real(self, data)

    monkeypatch.setattr(pathlib.Path, "write_bytes", write_bytes)


def test_a_full_disk_on_one_emulator_is_recorded_and_the_next_installs(
        two_emulators, monkeypatch):
    root, batch, fetch = two_emulators
    before = snapshot(root / "A")
    disk_full_on(monkeypatch, "a.zip")

    results = dict(install.install_all(batch, root, fetch=fetch))

    assert results["a"].startswith("ÉCHEC"), results["a"]
    assert "A" in results["a"] and "No space left" in results["a"]
    assert results["b"] == "installé"
    assert (root / "B" / "b.exe").read_text() == "b v1"
    assert snapshot(root / "A") == before


def test_a_stale_staging_that_cannot_be_removed_is_that_emulators_failure(
        two_emulators, monkeypatch):
    root, batch, fetch = two_emulators
    before = snapshot(root / "A")
    stale = root / f".A{acquire.STAGING_SUFFIX}"
    stale.mkdir()
    (stale / "left.dll").write_bytes(b"x")
    real = os.unlink

    def locked(path, *args, **kwargs):
        if os.path.basename(os.fspath(path)) == "left.dll":
            raise PermissionError(errno.EACCES, "Access is denied", path)
        return real(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", locked)

    results = dict(install.install_all(batch, root, fetch=fetch))

    assert results["a"].startswith("ÉCHEC"), results["a"]
    assert results["b"] == "installé"
    assert snapshot(root / "A") == before


def test_retro_install_prints_its_report_and_exits_1(
        tmp_path, two_emulators, monkeypatch, capsys):
    """Through the real command, without editing it: exit 1, not 2."""
    root, batch, fetch = two_emulators
    monkeypatch.setattr(cli.manifest, "load_manifest", lambda *a, **k: batch)
    real = acquire.acquire
    monkeypatch.setattr(acquire, "acquire",
                        lambda emu, r, **_: real(emu, r, fetch=fetch))
    disk_full_on(monkeypatch, "a.zip")

    code = cli.main(["install", "--manifest", str(tmp_path / "m.toml"),
                     "--emulation-root", str(root)])

    out, err = capsys.readouterr()
    assert code == 1, err
    assert "a : ÉCHEC" in out and "b : installé" in out
