"""Write a file so that a reader sees the old content or the new, never a part.

`Path.write_text` truncates the target and then writes: a crash, a full disk
or a VM cut in the middle leaves a fragment under the real name. Here the data
goes to a sibling temporary file, is flushed to disk, and replaces the target
in one `os.replace`. A failure removes the temporary file and leaves the target
as it was.
"""
from __future__ import annotations

import os
import pathlib


def write(path: pathlib.Path, data: str | bytes, encoding: str = "utf-8") -> None:
    """Replace ``path`` with ``data`` (text is written with ``encoding``).

    The temporary name keeps the target's name inside a leading dot and a
    `.tmp` suffix, so its stem never equals a stem the callers look up.
    """
    temporaire = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        if isinstance(data, bytes):
            with open(temporaire, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
        else:
            with open(temporaire, "w", encoding=encoding) as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
        os.replace(temporaire, path)
    except BaseException:
        temporaire.unlink(missing_ok=True)
        raise
