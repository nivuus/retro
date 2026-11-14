"""An entry without a pinned checksum is skipped by design, not failed.

The shipped manifest deliberately carries one entry whose SHA256 is not yet
recorded. Refusing to download it is right; reporting the refusal as a
failure made `retro install` exit 1 on every rebuild, so the provisioning
step recorded "partial" whether or not anything had failed.
"""
import dataclasses
import hashlib
import pathlib
import zipfile

from retro import acquire, cli, install, manifest

CORE = pathlib.Path(cli.DEFAULT_MANIFEST)


def no_download(url):
    raise AssertionError(f"downloaded {url}")


def test_the_shipped_manifest_alone_exits_0_and_names_the_skipped_entry(
        tmp_path, capsys, monkeypatch):
    shipped = manifest.load_manifest(CORE)
    unpinned = sorted(k for k, e in shipped.items() if not e.sha256.strip())
    assert unpinned, "the shipped manifest no longer has an unpinned entry"
    root = tmp_path / "Emulation"
    # Every pinned emulator already attested at its version: the real
    # `acquire` answers "à jour" without downloading anything, and the stub
    # fetch fails the test if anything is downloaded at all.
    for key, emu in shipped.items():
        if key not in unpinned:
            target = install.install_path(root, emu.install_dir)
            target.mkdir(parents=True)
            (target / acquire.TEMOIN).write_text(emu.version + "\n",
                                                 encoding="utf-8")
    real = acquire.acquire
    monkeypatch.setattr(acquire, "acquire",
                        lambda emu, r, **_: real(emu, r, fetch=no_download))

    code = cli.main(["install", "--emulation-root", str(root)])

    out, err = capsys.readouterr()
    assert code == 0, out + err
    for key in unpinned:
        line = next(l for l in out.splitlines() if f" {key} : " in l)
        assert line.split(" : ", 1)[1].startswith(install.UNPINNED), line
        assert key in out.splitlines()[-1], "the summary does not name it"
    assert "ÉCHEC" not in out


def make_zip(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("t.exe", "binary")
    return path.read_bytes()


def emulator(key, sha):
    return manifest.Emulator(
        key=key, name=key.title(), version="1.0" if sha else "",
        url=f"https://example.invalid/{key}.zip", sha256=sha,
        archive="zip", install_dir=key.title(), profile=key,
    )


def test_an_unpinned_entry_is_never_downloaded_and_the_others_install(
        tmp_path):
    blob = make_zip(tmp_path / "t.zip")
    calls = []

    def fetch(url):
        calls.append(url)
        return blob

    batch = {"pinned": emulator("pinned", hashlib.sha256(blob).hexdigest()),
             "unpinned": emulator("unpinned", "")}
    results = dict(install.install_all(batch, tmp_path / "Emu", fetch=fetch))
    assert results["pinned"] == "installé"
    assert results["unpinned"].startswith(install.UNPINNED)
    assert calls == ["https://example.invalid/pinned.zip"]
    assert not (tmp_path / "Emu" / "Unpinned").exists()


def test_an_unpinned_entry_is_not_counted_as_a_failure_in_the_report():
    text = install.format_install_report(
        [("a", "installé"), ("v", f"{install.UNPINNED} : no checksum")])
    assert "ÉCHEC" not in text and "non installé" not in text
    assert "v" in text


def test_a_wrong_checksum_is_still_a_failure(tmp_path):
    """The skip is for an EMPTY checksum only: a mismatch stays a failure."""
    blob = make_zip(tmp_path / "t.zip")
    bad = dataclasses.replace(emulator("bad", "0" * 64))
    results = dict(install.install_all({"bad": bad}, tmp_path / "Emu",
                                       fetch=lambda u: blob))
    assert results["bad"].startswith("ÉCHEC")
