"""A launch option that follows the console language.

Some emulators take the language games read ONLY on their command line:
Dolphin's Wii reads its NAND's SYSCONF, which `-C SYSCONF.IPL.LNG=<n>`
overrides for the session, and KytyPS5 reads `--console-language <n>`. A
system declares it with the token `{langue}` in its `launch` and a
`[system.langue]` table: one option string per Steam language name, plus
the `repli` taken for every language the table does not declare.

Everything is resolved HERE, for every Steam language: `lignes_du_plan`
writes one plan line per language, fallback already applied, and the
launcher reads one line and decides nothing — the same rule as the
bootstrap language lines, for the same reason: a launcher that computed a
fallback could pick one `retro status` does not announce.
"""
from __future__ import annotations

from retro import langue as langue_mod

JETON = "{langue}"
PREFIXE_PLAN = "langue_args."


class LangueArgsError(ValueError):
    """A `[system.langue]` table that would fail silently at launch."""


def lire(brut, launch: str) -> tuple[tuple[tuple[str, str], ...], str]:
    """The (language, option) pairs sorted by name, and the fallback.

    `brut` is the raw `[system.langue]` value, None when absent. The token
    and the table go together: a token without a table would reach the
    emulator's command line as is, a table without a token would look like
    a language that follows Steam while nothing reads it.
    """
    if brut is None:
        if JETON in launch:
            raise LangueArgsError(
                f"the launch template holds {JETON} but no [system.langue] "
                "table is declared: the token would reach the emulator's "
                "command line as is.")
        return (), ""
    if not isinstance(brut, dict):
        raise LangueArgsError(
            "'langue' must be the [system.langue] TABLE, one launch option "
            f"per Steam language name — got a {type(brut).__name__}.")
    if JETON not in launch:
        raise LangueArgsError(
            f"a [system.langue] table is declared but the launch template "
            f"has no {JETON}: nothing would read it, and the system would "
            "look like it follows Steam's language.")
    repli = brut.get("repli", "")
    options = {nom: v for nom, v in brut.items() if nom != "repli"}
    mauvais = sorted(n for n, v in options.items() if not isinstance(v, str))
    if mauvais:
        raise LangueArgsError(
            f"{', '.join(mauvais)} — each language carries a launch "
            "option, as TEXT.")
    vides = sorted(n for n, v in options.items() if not v.strip())
    if vides:
        raise LangueArgsError(
            f"{', '.join(vides)} — empty option. The game would start in "
            "the emulator's own language while retro status announces the "
            "table's: leave the language undeclared, it then takes the "
            "fallback.")
    # One plan line per language: a line break inside an option would end
    # the line early, and the launcher would read the rest as another key.
    multiline = sorted(n for n, v in options.items()
                           if "\n" in v or "\r" in v)
    if multiline:
        raise LangueArgsError(
            f"{', '.join(multiline)} — the option holds a line break, "
            "and the plan carries it on ONE line: the launcher would read "
            "the rest as another plan key.")
    inconnues = sorted(n for n in options if n not in langue_mod.LANGUES)
    if inconnues:
        raise LangueArgsError(
            f"{', '.join(inconnues)} — not Steam language names (french, "
            "koreana, brazilian): nobody would ever ask for them.")
    if not options:
        raise LangueArgsError("the table declares no language.")
    if not isinstance(repli, str) or repli not in options:
        raise LangueArgsError(
            f"'repli' is {repli!r}, which is not declared here "
            f"({', '.join(sorted(options))}): the plan's fallback line would "
            "have no option to carry.")
    return tuple(sorted(options.items())), repli


def lignes_du_plan(options: tuple[tuple[str, str], ...],
                   repli: str) -> list[str]:
    """One plan line per Steam language, plus `defaut` for a silent Steam.

    Nothing when the system declares no table: thirty empty lines would
    make the launcher substitute nothing thirty ways.
    """
    if not options:
        return []
    table = dict(options)
    declarees = tuple(table)
    lignes = []
    for voulue in (*langue_mod.LANGUES, ""):
        posee = langue_mod.appliquer(voulue, declarees, repli).langue
        lignes.append(f"{PREFIXE_PLAN}{voulue or 'defaut'}={table[posee]}")
    return lignes
