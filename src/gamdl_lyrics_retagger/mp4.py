"""Read catalog IDs and verify that MP4 media payloads remain byte-identical."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

from mutagen.mp4 import MP4, MP4StreamInfoError


class Mp4InspectionError(RuntimeError):
    """The file is not a readable MP4/M4A or has an invalid atom layout."""


@dataclass(frozen=True)
class MdatSignature:
    """Digest and total payload size for all top-level MP4 mdat atoms."""

    sha256: str
    payload_bytes: int
    atom_count: int


def read_catalog_song_id(path: Path) -> str | None:
    """Return the Apple catalog song ID from the M4A cnID atom.

    Mutagen represents integer atoms such as cnID as a list of integers.
    Album and artist IDs are intentionally not substituted: lyrics endpoints
    require a song ID.
    """
    try:
        media = MP4(path)
    except (OSError, ValueError, MP4StreamInfoError) as exc:
        raise Mp4InspectionError(f"No se pudo leer el contenedor MP4: {exc}") from exc

    if not media.tags:
        return None

    values = media.tags.get("cnID")
    if values is None:
        return None
    if not isinstance(values, (list, tuple)):
        values = [values]

    for value in values:
        try:
            song_id = int(value)
        except (TypeError, ValueError):
            continue
        if song_id > 0:
            return str(song_id)
    return None


def read_embedded_lyrics(path: Path) -> str | None:
    """Read the first standard MP4 ©lyr text value, if present."""
    try:
        media = MP4(path)
    except (OSError, ValueError, MP4StreamInfoError) as exc:
        raise Mp4InspectionError(f"No se pudieron leer las etiquetas MP4: {exc}") from exc

    if not media.tags:
        return None
    values = media.tags.get("©lyr")
    if not values:
        return None
    first = values[0] if isinstance(values, (list, tuple)) else values
    return first if isinstance(first, str) else None


def mdat_signature(path: Path, *, chunk_size: int = 4 * 1024 * 1024) -> MdatSignature:
    """Hash all top-level mdat payloads without loading them all into RAM.

    Metadata writers may move or resize the moov atom. They must not alter
    encoded media samples in mdat. This signature enforces that invariant
    before the staged file can replace the source.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size debe ser positivo")

    digest = hashlib.sha256()
    payload_total = 0
    atom_count = 0

    try:
        file_size = path.stat().st_size
        with path.open("rb") as stream:
            position = 0
            while position < file_size:
                remaining = file_size - position
                header = stream.read(8)
                if len(header) != 8:
                    raise Mp4InspectionError("Cabecera MP4 incompleta")
                size32, atom_type = struct.unpack(">I4s", header)
                header_size = 8

                if size32 == 1:
                    extended = stream.read(8)
                    if len(extended) != 8:
                        raise Mp4InspectionError("Tamaño extendido MP4 incompleto")
                    atom_size = struct.unpack(">Q", extended)[0]
                    header_size = 16
                elif size32 == 0:
                    atom_size = remaining
                else:
                    atom_size = size32

                if atom_size < header_size or atom_size > remaining:
                    raise Mp4InspectionError(
                        f"Tamaño de átomo MP4 inválido en el desplazamiento {position}"
                    )

                payload_size = atom_size - header_size
                if atom_type == b"mdat":
                    atom_count += 1
                    digest.update(struct.pack(">Q", payload_size))
                    left = payload_size
                    while left:
                        block = stream.read(min(chunk_size, left))
                        if not block:
                            raise Mp4InspectionError("Datos mdat incompletos")
                        digest.update(block)
                        left -= len(block)
                    payload_total += payload_size
                else:
                    stream.seek(payload_size, 1)

                position += atom_size
    except OSError as exc:
        raise Mp4InspectionError(f"No se pudo inspeccionar el M4A: {exc}") from exc

    if atom_count == 0:
        raise Mp4InspectionError("El archivo no contiene ningún átomo mdat")

    return MdatSignature(digest.hexdigest(), payload_total, atom_count)
