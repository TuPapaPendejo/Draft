"""Fetch synchronized LRC, diagnose missing lyrics, and safely retag M4A files."""

from __future__ import annotations

import logging
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


def _log(logger: logging.Logger | None, level: int, message: str, *args: Any) -> None:
    if logger is not None:
        logger.log(level, message, *args)


def install_lyrics_api_observer(api: Any, logger: logging.Logger) -> None:
    """Log safe response diagnostics around Gamdl's standard lyrics endpoint.

    Response bodies and TTML text are never written to the log. Only resource
    counts, attribute names, TTML presence/length, and safe HTTP status data
    are recorded. Apple Music credentials are not inspected.
    """
    if getattr(api, "_lyrics_retagger_observer_installed", False):
        return

    original_get_lyrics = api.get_lyrics

    async def observed_get_lyrics(song_id: str, *, language: str | None = None):
        logger.info(
            "APPLE_LYRICS_REQUEST song_id=%s storefront=%s language=%s endpoint=standard",
            song_id,
            getattr(api, "storefront", "unknown"),
            language or getattr(api, "language", "default"),
        )
        try:
            payload = await original_get_lyrics(song_id, language=language)
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            api._lyrics_retagger_last_response = {
                "status": "http_error",
                "status_code": status_code,
                "error_type": type(exc).__name__,
            }
            logger.warning(
                "APPLE_LYRICS_HTTP_ERROR song_id=%s error_type=%s status_code=%s",
                song_id,
                type(exc).__name__,
                status_code if status_code is not None else "unknown",
            )
            raise

        data = payload.get("data")
        resources = data if isinstance(data, list) else []
        attributes = (
            resources[0].get("attributes", {})
            if resources and isinstance(resources[0], dict)
            else {}
        )
        if not isinstance(attributes, dict):
            attributes = {}
        raw_ttml = attributes.get("ttml")
        ttml_present = isinstance(raw_ttml, str) and bool(raw_ttml.strip())
        diagnostics = {
            "status": "response",
            "status_code": 200,
            "data_count": len(resources),
            "ttml_present": ttml_present,
            "ttml_chars": len(raw_ttml) if isinstance(raw_ttml, str) else 0,
            "attribute_keys": sorted(str(key) for key in attributes.keys()),
        }
        api._lyrics_retagger_last_response = diagnostics
        logger.info(
            "APPLE_LYRICS_RESPONSE song_id=%s status_code=200 data_count=%d "
            "ttml_present=%s ttml_chars=%d attribute_keys=%s",
            song_id,
            diagnostics["data_count"],
            diagnostics["ttml_present"],
            diagnostics["ttml_chars"],
            ",".join(diagnostics["attribute_keys"]) or "none",
        )
        return payload

    api.get_lyrics = observed_get_lyrics
    api._lyrics_retagger_observer_installed = True
    api._lyrics_retagger_last_response = None


async def fetch_synchronized_lrc(
    api: Any,
    song_id: str,
    *,
    logger: logging.Logger | None = None,
) -> str | None:
    """Ask Gamdl for strict line-synchronized LRC without requesting audio."""
    from gamdl.media import Song
    from gamdl.media.song.lyrics import LyricsFormat

    song = Song.from_id(song_id, api=api, is_library=False)
    metadata = await song.get_metadata()
    attributes = metadata.get("attributes", {}) if isinstance(metadata, dict) else {}
    if not isinstance(attributes, dict):
        attributes = {}

    title = str(attributes.get("name") or "unknown").replace("\n", " ")[:160]
    artist = str(attributes.get("artistName") or "unknown").replace("\n", " ")[:120]
    isrc = attributes.get("isrc") or "unknown"
    has_lyrics = attributes.get("hasLyrics", "not-provided")
    _log(
        logger,
        logging.INFO,
        "CATALOG_METADATA song_id=%s title=%r artist=%r isrc=%s hasLyrics=%s",
        song_id,
        title,
        artist,
        isrc,
        has_lyrics,
    )

    api._lyrics_retagger_last_response = None
    if has_lyrics is False:
        _log(
            logger,
            logging.WARNING,
            "LYRICS_UNAVAILABLE song_id=%s reason=CATALOG_HAS_LYRICS_FALSE",
            song_id,
        )
        return None

    lyrics = await song.get_lyrics(
        syllable=False,
        language=getattr(api, "language", None),
    )
    response = getattr(api, "_lyrics_retagger_last_response", None) or {}

    if lyrics is None:
        status_code = response.get("status_code")
        if status_code == 404:
            reason = "APPLE_LYRICS_ENDPOINT_404"
        elif response.get("status") == "http_error":
            reason = "APPLE_LYRICS_ENDPOINT_ERROR"
        elif response.get("data_count") == 0:
            reason = "EMPTY_LYRICS_DATA"
        elif response.get("ttml_present") is False:
            reason = "RESPONSE_WITHOUT_TTML"
        else:
            reason = "GAMDL_RETURNED_NO_LYRICS"
        _log(
            logger,
            logging.WARNING,
            "LYRICS_UNAVAILABLE song_id=%s reason=%s status_code=%s "
            "data_count=%s ttml_present=%s",
            song_id,
            reason,
            status_code if status_code is not None else "not-observed",
            response.get("data_count", "not-observed"),
            response.get("ttml_present", "not-observed"),
        )
        return None

    nonempty_lines = [line for line in lyrics.lines if line.text.strip()]
    timed_lines = [line for line in nonempty_lines if line.start is not None]
    untimed_lines = len(nonempty_lines) - len(timed_lines)
    if not nonempty_lines:
        _log(
            logger,
            logging.WARNING,
            "LYRICS_UNAVAILABLE song_id=%s reason=TTML_CONTAINS_NO_TEXT_LINES",
            song_id,
        )
        return None
    if untimed_lines:
        _log(
            logger,
            logging.WARNING,
            "LYRICS_UNAVAILABLE song_id=%s reason=PARTIALLY_SYNCHRONIZED "
            "total_lines=%d timed_lines=%d untimed_lines=%d",
            song_id,
            len(nonempty_lines),
            len(timed_lines),
            untimed_lines,
        )
        return None

    # embedded=False is deliberate: Gamdl must not fall back to plain text.
    rendered = lyrics.render(LyricsFormat.LRC, embedded=False)
    rendered = rendered.strip("\ufeff\r\n")
    if not rendered:
        _log(
            logger,
            logging.WARNING,
            "LYRICS_UNAVAILABLE song_id=%s reason=EMPTY_LRC_AFTER_RENDER",
            song_id,
        )
        return None

    _log(
        logger,
        logging.INFO,
        "LYRICS_READY song_id=%s lines=%d timed_lines=%d lrc_chars=%d",
        song_id,
        len(nonempty_lines),
        len(timed_lines),
        len(rendered),
    )
    return rendered


def inspect_local_ttml(
    m4a_path: Path,
    *,
    logger: logging.Logger | None = None,
) -> Path | None:
    """Inspect a same-name TTML sidecar for diagnostic evidence only.

    The sidecar is never used as an automatic fallback: matching file names
    alone are not enough to prove that the TTML belongs to the embedded song ID.
    """
    candidates = (
        m4a_path.with_suffix(".ttml"),
        m4a_path.with_suffix(".TTML"),
    )
    sidecar = next((candidate for candidate in candidates if candidate.is_file()), None)
    if sidecar is None:
        _log(
            logger,
            logging.INFO,
            "LOCAL_TTML sidecar=not-found expected=%s",
            m4a_path.with_suffix(".ttml").name,
        )
        return None

    try:
        from gamdl.media.song.lyrics import Lyrics

        raw_ttml = sidecar.read_text(encoding="utf-8-sig")
        parsed = Lyrics.from_ttml(raw_ttml)
        lines = [line for line in parsed.lines if line.text.strip()]
        timed = [line for line in lines if line.start is not None]
        _log(
            logger,
            logging.INFO,
            "LOCAL_TTML sidecar=%s bytes=%d parsed=true total_lines=%d "
            "timed_lines=%d untimed_lines=%d",
            sidecar.name,
            sidecar.stat().st_size,
            len(lines),
            len(timed),
            len(lines) - len(timed),
        )
    except Exception as exc:
        _log(
            logger,
            logging.WARNING,
            "LOCAL_TTML sidecar=%s parsed=false error_type=%s",
            sidecar.name,
            type(exc).__name__,
        )
    return sidecar


def apply_embedded_lrc(
    path: Path,
    *,
    lyrics: str,
    muxer: Any,
    logger: logging.Logger | None = None,
) -> UpdateResult:
    """Stage and verify a lyrics-only update, without retaining a backup.

    The original is not edited in place. A temporary copy is tagged and
    verified first; os.replace publishes it atomically only after the embedded
    ©lyr value reads back exactly and every top-level mdat payload is identical.
    The temporary copy is deleted on success or failure.
    """
    from gamdl.download import Tags

    source_signature: MdatSignature = mdat_signature(path)
    _log(
        logger,
        logging.INFO,
        "MDAT_BEFORE path=%s sha256=%s payload_bytes=%d atom_count=%d",
        path.name,
        source_signature.sha256,
        source_signature.payload_bytes,
        source_signature.atom_count,
    )
    current = read_embedded_lyrics(path)
    if current == lyrics:
        _log(
            logger,
            logging.INFO,
            "TAG_UNCHANGED path=%s reason=EMBEDDED_LYRICS_ALREADY_MATCH",
            path.name,
        )
        return UpdateResult("unchanged", "La etiqueta ©lyr ya contiene este LRC", lyrics)

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}.lyrics-retagger-", suffix=path.suffix, dir=path.parent
    )
    os.close(file_descriptor)
    temporary = Path(temporary_name)

    try:
        shutil.copy2(path, temporary)
        _log(
            logger,
            logging.INFO,
            "STAGE_CREATED path=%s temporary=%s source_bytes=%d",
            path.name,
            temporary.name,
            path.stat().st_size,
        )

        # All other Tags fields are None; Gamdl preserves existing atoms.
        muxer.tag(temporary, tags=Tags(lyrics=lyrics))

        staged_signature = mdat_signature(temporary)
        mdat_match = staged_signature == source_signature
        _log(
            logger,
            logging.INFO,
            "MDAT_AFTER path=%s sha256=%s payload_bytes=%d atom_count=%d identical=%s",
            path.name,
            staged_signature.sha256,
            staged_signature.payload_bytes,
            staged_signature.atom_count,
            mdat_match,
        )
        if not mdat_match:
            raise RuntimeError(
                "El contenido mdat cambió durante el etiquetado; se descartó el archivo temporal."
            )

        verified_lyrics = read_embedded_lyrics(temporary)
        lyrics_match = verified_lyrics == lyrics
        _log(
            logger,
            logging.INFO,
            "TAG_VERIFY path=%s atom=©lyr matches_expected=%s expected_chars=%d actual_chars=%d",
            path.name,
            lyrics_match,
            len(lyrics),
            len(verified_lyrics) if verified_lyrics is not None else 0,
        )
        if not lyrics_match:
            raise RuntimeError(
                "La verificación posterior no encontró el LRC esperado en ©lyr."
            )

        staged_bytes = temporary.stat().st_size
        os.replace(temporary, path)
        _log(
            logger,
            logging.INFO,
            "FILE_REPLACED path=%s bytes=%d backup=disabled atomic=true",
            path.name,
            staged_bytes,
        )
        return UpdateResult("updated", "Etiqueta ©lyr actualizada; mdat idéntico", lyrics)
    finally:
        temporary.unlink(missing_ok=True)
        _log(
            logger,
            logging.INFO,
            "STAGE_CLEANUP path=%s temporary_exists=%s",
            path.name,
            temporary.exists(),
        )
