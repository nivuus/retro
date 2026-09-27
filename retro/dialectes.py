"""The two configuration dialects the bootstrap merges: INI and YAML.

Pure parsers only. Which dialect a target speaks is decided by its
extension in `profiles.dialecte`, which raises the profile error; the
launcher mirrors every rule here in C# (retro-launch.cs, retro-yaml.cs).
"""
from __future__ import annotations

import json
import pathlib
import xml.etree.ElementTree as ElementTree


def cles_ini(fragment: str) -> list[tuple[str, str]]:
    """The (section, key) pairs of an INI fragment, in order.

    Public on purpose: `retro status` counts what the console imposes, and
    counting elsewhere would make two parsers that part ways at the first
    unusual format.

    Comments are NOT keys. A line "; Scaling = ..." must not pass for the
    setting it explains — the launcher's merge follows the same rule, and
    contradicting it would make the report call a key imposed when it is
    not.
    """
    section, keys = "", []
    for line in fragment.splitlines():
        bare = line.strip()
        if not bare or bare[0] in ";#":
            continue
        if bare.startswith("[") and bare.endswith("]"):
            section = bare[1:-1].strip()
        elif "=" in bare:
            keys.append((section, bare.split("=", 1)[0].strip()))
    return keys


# The extensions whose content is YAML. Vita3K's config.yml is a flat map of
# scalars plus a few sequences (CONFIG_VECTOR,
# vita3k/config/include/config/config.h); RPCS3's config.yml is a map of
# maps. Both are created by the emulator at first launch, so "si-absent"
# would never fire: the only regime that applies is the one that reads and
# merges.
_YAML = (".yml", ".yaml")

# The extensions whose content is INI — "key = value", with or without
# sections. They are LISTED rather than assumed: the merge treats as INI
# whatever is not YAML, so an unknown extension would be merged as INI
# WITHOUT ANYONE DECIDING IT. If the file is not INI, no key is posed, no
# message is produced, and the setting is never imposed — the quietest
# failure of this mechanism.
#
# .cfg is retroarch.cfg, .opt a libretro core's options file: two
# "key = value" formats without sections, checked on the console.
_INI = (".ini", ".cfg", ".opt", ".toml")

# The extensions whose content is JSON: shadPS4's user/config.json and
# another emulator's Config.json. Merged by retro-json.cs, which replaces the value
# of each imposed leaf in place and leaves every other byte of the file as
# the emulator wrote it.
_JSON = (".json",)

# The extensions whose content is XML: Cemu's settings.xml. Merged by
# retro-xml.cs, which sets the text of each imposed leaf element and leaves
# the rest of the document as the emulator wrote it.
_XML = (".xml",)


def cles_yaml(fragment: str) -> list[tuple[str, str]]:
    """The (section, key) pairs of a YAML fragment, on TWO levels.

    Level one is what the flat dialect always read: a top-level
    "key: value" lives under the empty section. Level two is a top-level
    mapping of mappings — RPCS3's config.yml, "System:" then
    "  Language: French" — read as section "System", key "Language".

    A top-level "name:" with nothing after the colon is a SECTION only when
    the next meaningful line is indented and is itself "key: value" or
    "key:" — not a "- item". Otherwise it stays a flat key: "lle-modules:"
    followed by "  - libscemp4" is one key holding a sequence, exactly as
    before. Deeper lines ("    Adapter: X" under "  Vulkan:") belong to
    the level-two key above them and are never keys of the section:
    counting them would report as imposed a key no YAML reader attaches
    there — the silent failure this repository refuses.

    The launcher's merge (retro-yaml.cs) reads the very same two levels,
    by the very same rule.
    """
    return [(section, key) for section, key, _ in lignes_yaml(fragment)]


def lignes_yaml(text: str) -> list[tuple[str, str, int]]:
    """(section, key, line index) of every key line of a two-level YAML."""
    lines = text.splitlines()
    found = []
    section, indent = "", None
    for n, line in enumerate(lines):
        bare = line.strip()
        if not bare or bare.startswith("#"):
            continue
        depth = len(line) - len(line.lstrip())
        if depth == 0:
            section, indent = "", None
            if bare.startswith("-") or ":" not in bare:
                continue
            key, value = (x.strip() for x in bare.split(":", 1))
            if not value and _opens_a_section(lines, n):
                section = key
                continue
            found.append(("", key, n))
            continue
        if not section:
            continue
        if indent is None:
            indent = depth
        if depth != indent or bare.startswith("-") or ":" not in bare:
            continue
        found.append((section, bare.split(":", 1)[0].strip(), n))
    return found


def _opens_a_section(lines: list[str], n: int) -> bool:
    """Whether the top-level "name:" at line `n` opens a mapping."""
    for following in lines[n + 1:]:
        bare = following.strip()
        if not bare or bare.startswith("#"):
            continue
        return (following[:1].isspace() and not bare.startswith("-")
                and ":" in bare)
    return False


def valider_json(fragment: str) -> None:
    """Raise ValueError unless `fragment` is a JSON object of objects and
    scalars. An array leaf is refused: the merge would replace it WHOLE,
    dropping whatever the emulator keeps in it."""
    def refuse_constant(name):
        # NaN and Infinity are not JSON: Python accepts them by default,
        # the launcher's reader does not, and the profile would load here
        # to fail at launch on the console.
        raise ValueError(f"{name} is not a JSON value")

    try:
        root = json.loads(fragment, parse_constant=refuse_constant)
    except json.JSONDecodeError as exc:
        raise ValueError(f"not JSON: {exc}") from exc
    if not isinstance(root, dict):
        raise ValueError("a JSON fragment must be an object")

    def walk(node, path):
        for key, value in node.items():
            if "/" in key:
                # The "/"-joined section of `cles_json` would confuse
                # {"a/b": ...} with {"a": {"b": ...}}, and the overlap guards
                # would compare two different paths as one.
                raise ValueError(
                    f"{'/'.join((*path, key))}: a key holding \"/\" cannot "
                    "be told apart from a nested path")
            if isinstance(value, list):
                raise ValueError(
                    f"{'/'.join((*path, key))} is an array: the merge "
                    "would replace it whole")
            if isinstance(value, dict):
                walk(value, (*path, key))
    walk(root, ())


def cles_json(fragment: str) -> list[tuple[str, str]]:
    """The (section, key) pairs of a JSON fragment: every scalar leaf, its
    section the "/"-joined path of the objects above it. Invalid JSON gives
    no key — `valider_json` is what refuses it, with the reason."""
    try:
        root = json.loads(fragment)
    except json.JSONDecodeError:
        return []
    keys = []

    def walk(node, path):
        for key, value in node.items():
            if isinstance(value, dict):
                walk(value, (*path, key))
            elif not isinstance(value, list):
                keys.append(("/".join(path), key))
    if isinstance(root, dict):
        walk(root, ())
    return keys


def valider_xml(fragment: str, merged: bool = True) -> None:
    """Raise ValueError unless `fragment` is a well-formed XML document.

    A MERGED fragment (enforced, language) must also hold at least one child
    element under its root. The root itself is never a leaf: `cles_xml` and
    the launcher both read the leaves BELOW it, so a bare
    "<setting>true</setting>" would pose nothing, and say nothing. A file
    posed once ('content') is written as is, and may be a bare root."""
    try:
        root = ElementTree.fromstring(fragment)
    except ElementTree.ParseError as exc:
        raise ValueError(f"not XML: {exc}") from exc
    if merged and not len(root):
        raise ValueError(
            f"<{root.tag}> holds no child element: nothing would be posed")


def cles_xml(fragment: str) -> list[tuple[str, str]]:
    """The (section, key) pairs of an XML fragment: every element with no
    child element, its section the "/"-joined path of the elements above
    it, root included. Invalid XML gives no key — `valider_xml` is what
    refuses it, with the reason."""
    try:
        root = ElementTree.fromstring(fragment)
    except ElementTree.ParseError:
        return []
    keys = []

    def walk(node, path):
        for child in node:
            if len(child):
                walk(child, (*path, child.tag))
            else:
                keys.append(("/".join(path), child.tag))
    walk(root, (root.tag,))
    return keys


def cles_de(target: str, fragment: str) -> list[tuple[str, str]]:
    """The (section, key) pairs of a fragment, in its TARGET's dialect.

    The dialect follows the EXTENSION of the file aimed at, never a declared
    field: a field could contradict what the fragment holds, an extension
    cannot.

    Without it, a line "warn-missing-firmware: false" brought to a YAML
    would have posed NOTHING, without a word: `cles_ini` wants an "=",
    returns an empty list, and every guard built on it then guards nothing.
    """
    suffix = pathlib.PureWindowsPath(target).suffix.lower()
    if suffix in _JSON:
        return cles_json(fragment)
    if suffix in _XML:
        return cles_xml(fragment)
    return cles_yaml(fragment) if suffix in _YAML else cles_ini(fragment)
