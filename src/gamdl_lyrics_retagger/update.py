"""Fetch LRC through Gamdl and safely replace only the embedded lyrics atom."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .mp4 import MdatSignature, mdat_signature, read_embedded_lyrics


@dataclass(frozen=True)
class UpdateResult:
    status: str
    detail: str
    lyrics: str | None = None
    backup: Path | None = None


async def fetch_synchronized_lrc(api: Any, song_id: str) -> str | None:
    """Ask Gamdl for standard line-synchronized lyrics; never request audio."""
    from gamdl.media import Song
    from gamdl.media.song.lyrics import LyricsFormat

    song = Song.from_id(song_id, api=api, is_library=False)
    lyrics = await song.get_lyrics(
        syllable=False,
        language=getattr(api, "language", None),
    )
    if lyrics is None:
        return None
    timed_lines = [line for line in lyrics.lines if line.text.strip()]
    if not timed_lines or any(line.start is None for line in timed_lines):
        # Do not label a partially timed transcript as fully synchronized.
        return None

    # embedded=False is deliberate: do not silently fall back to plain text.
    rendered = lyrics.render(LyricsFormat.LRC, embedded=False)
    rendered = rendered.strip("\ufeff\r\n")
    return rendered or None


def _backup_path(backup_root: Path, relative_path: Path) -> Path:
    candidate = backup_root / relative_path
    candidate.parent.mkdir(parents=True, exist_ok=True)
    if not candidate.exists():
        return candidate
    index = 1
    while True:
        alternative = candidate.with_name(f"{candidate.name}.{index}")
        if not alternative.exists():
            return alternative
        index += 1


def apply_embedded_lrc(
    path: Path,
    *,
    root: Path,
    lyrics: str,
    muxer: Any,
    backup_root: Path,
) -> UpdateResult:
    """Stage and verify a tag update before atomically replacing the M4A.

    A copy of the original is placed under backup_root. The staged file is
    published only when the embedded ©lyr value reads back exactly and the
    payload signature of every top-level mdat atom is unchanged.
    """
    from gamdl.download import Tags

    source_signature: MdatSignature = mdat_signature(path)
    current = read_embedded_lyrics(path)
    if current == lyrics:
        return UpdateResult("unchanged", "La etiqueta ©lyr ya contiene este LRC", lyrics)

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}.lyrics-retagger-", suffix=path.suffix, dir=path.parent
    )
    os.close(file_descriptor)
    temporary = Path(temporary_name)

    try:
        shutil.copy2(path, temporary)
        # All other Tags fields are None; Gamdl preserves existing atoms.
        muxer.tag(temporary, tags=Tags(lyrics=lyrics))

        staged_signature = mdat_signature(temporary)
        if staged_signature != source_signature:
            raise RuntimeError(
                "El contenido mdat cambió durante el etiquetado; se descartó el archivo temporal."
            )

        if read_embedded_lyrics(temporary) != lyrics:
            raise RuntimeError(
                "La verificación posterior no encontró el LRC esperado en ©lyr."
            )

        relative_path = path.resolve().relative_to(root.resolve())
        backup = _backup_path(backup_root, relative_path)
        shutil.copy2(path, backup)
        os.replace(temporary, path)
        return UpdateResult("updated", "Etiqueta ©lyr actualizada; mdat idéntico", lyrics, backup)
    finally:
        temporary.unlink(missing_ok=True)
