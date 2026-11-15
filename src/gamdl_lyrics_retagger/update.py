"""Fetch synchronized LRC with standard-to-syllable fallback and safe diagnostics."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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
    """Observe both Gamdl lyrics endpoints without logging response bodies."""
    if getattr(api, "_lyrics_retagger_observer_installed", False):
        return

    responses: dict[str, dict[str, Any]] = {}
    for method_name, endpoint in (
        ("get_lyrics", "standard"),
        ("get_syllable_lyrics", "syllable"),
    ):
        original = getattr(api, method_name, None)
        if not callable(original):
            continue

        def make_observer(
            original_method: Callable[..., Any],
            endpoint_name: str,
        ) -> Callable[..., Any]:
            async def observed(song_id: str, **kwargs: Any):
                language = kwargs.get("language") or getattr(api, "language", "default")
                logger.info(
                    "APPLE_LYRICS_REQUEST song_id=%s storefront=%s language=%s endpoint=%s",
                    song_id,
                    getattr(api, "storefront", "unknown"),
                    language,
                    endpoint_name,
                )
                try:
                    payload = await original_method(song_id, **kwargs)
                except Exception as exc:
                    status_code = getattr(exc, "status_code", None)
                    diagnostics = {
                        "status": "http_error",
                        "status_code": status_code,
                        "error_type": type(exc).__name__,
                    }
                    responses[endpoint_name] = diagnostics
                    api._lyrics_retagger_last_response = diagnostics
                    logger.warning(
                        "APPLE_LYRICS_HTTP_ERROR song_id=%s endpoint=%s "
                        "error_type=%s status_code=%s",
                        song_id,
                        endpoint_name,
                        type(exc).__name__,
                        status_code if status_code is not None else "unknown",
                    )
                    raise

                resources_value = payload.get("data") if isinstance(payload, dict) else None
                resources = resources_value if isinstance(resources_value, list) else []
                attributes = (
                    resources[0].get("attributes", {})
                    if resources and isinstance(resources[0], dict)
                    else {}
                )
                if not isinstance(attributes, dict):
                    attributes = {}

                raw_ttml = attributes.get("ttml")
                ttml_source = "ttml"
                if not isinstance(raw_ttml, str) or not raw_ttml.strip():
                    localizations = attributes.get("ttmlLocalizations")
                    if isinstance(localizations, str):
                        raw_ttml = localizations
                        ttml_source = "ttmlLocalizations"
                    elif isinstance(localizations, dict):
                        raw_ttml = next(
                            (value for value in localizations.values() if isinstance(value, str)),
                            None,
                        )
                        ttml_source = "ttmlLocalizations"
                ttml_present = isinstance(raw_ttml, str) and bool(raw_ttml.strip())

                diagnostics = {
                    "status": "response",
                    "status_code": 200,
                    "data_count": len(resources),
                    "ttml_present": ttml_present,
                    "ttml_chars": len(raw_ttml) if isinstance(raw_ttml, str) else 0,
                    "ttml_source": ttml_source if ttml_present else "none",
                    "attribute_keys": sorted(str(key) for key in attributes.keys()),
                }
                responses[endpoint_name] = diagnostics
                api._lyrics_retagger_last_response = diagnostics
                logger.info(
                    "APPLE_LYRICS_RESPONSE song_id=%s endpoint=%s status_code=200 "
                    "data_count=%d ttml_present=%s ttml_source=%s ttml_chars=%d "
                    "attribute_keys=%s",
                    song_id,
                    endpoint_name,
                    diagnostics["data_count"],
                    diagnostics["ttml_present"],
                    diagnostics["ttml_source"],
                    diagnostics["ttml_chars"],
                    ",".join(diagnostics["attribute_keys"]) or "none",
                )
                return payload

            return observed

        setattr(api, method_name, make_observer(original, endpoint))

    api._lyrics_retagger_responses = responses
    api._lyrics_retagger_observer_installed = True
    api._lyrics_retagger_last_response = None


def _lyrics_timing(lyrics: Any) -> tuple[int, int, int]:
    lines = [line for line in lyrics.lines if line.text.strip()]
    timed = [line for line in lines if line.start is not None]
    return len(lines), len(timed), len(lines) - len(timed)


def _response_reason(response: dict[str, Any]) -> str:
    status_code = response.get("status_code")
    if status_code == 404:
        return "APPLE_LYRICS_ENDPOINT_404"
    if response.get("status") == "http_error":
        return "APPLE_LYRICS_ENDPOINT_ERROR"
    if response.get("data_count") == 0:
        return "EMPTY_LYRICS_DATA"
    if response.get("ttml_present") is False:
        return "RESPONSE_WITHOUT_TTML"
    return "GAMDL_RETURNED_NO_LYRICS"


async def fetch_synchronized_lrc(
    api: Any,
    song_id: str,
    *,
    logger: logging.Logger | None = None,
) -> str | None:
    """Fetch LRC using standard lyrics first, then syllable-timed TTML.

    The second endpoint is attempted when standard TTML is missing or does not
    time every non-empty line. Regardless of source granularity, output remains
    standard line-level LRC (not enhanced word/syllable LRC).
    """
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

    if has_lyrics is False:
        _log(
            logger,
            logging.WARNING,
            "LYRICS_UNAVAILABLE song_id=%s reason=CATALOG_HAS_LYRICS_FALSE",
            song_id,
        )
        return None

    language = getattr(api, "language", None)
    responses = getattr(api, "_lyrics_retagger_responses", {})

    # First use the standard endpoint. It is often sufficient for line LRC.
    standard = await song.get_lyrics(syllable=False, language=language)
    total, timed, untimed = _lyrics_timing(standard) if standard is not None else (0, 0, 0)

    if standard is not None and total > 0 and untimed == 0:
        selected = standard
        selected_endpoint = "standard"
    else:
        if standard is None:
            response = responses.get("standard", getattr(api, "_lyrics_retagger_last_response", {}) or {})
            _log(
                logger,
                logging.WARNING,
                "STANDARD_LYRICS_UNAVAILABLE song_id=%s reason=%s status_code=%s "
                "data_count=%s ttml_present=%s",
                song_id,
                _response_reason(response),
                response.get("status_code", "not-observed"),
                response.get("data_count", "not-observed"),
                response.get("ttml_present", "not-observed"),
            )
        elif total == 0:
            _log(
                logger,
                logging.WARNING,
                "STANDARD_LYRICS_UNAVAILABLE song_id=%s reason=TTML_CONTAINS_NO_TEXT_LINES",
                song_id,
            )
        else:
            _log(
                logger,
                logging.WARNING,
                "STANDARD_LYRICS_UNAVAILABLE song_id=%s reason=NOT_FULLY_SYNCHRONIZED "
                "total_lines=%d timed_lines=%d untimed_lines=%d",
                song_id,
                total,
                timed,
                untimed,
            )

        _log(
            logger,
            logging.INFO,
            "LYRICS_FALLBACK_ATTEMPT song_id=%s endpoint=syllable",
            song_id,
        )
        responses.pop("syllable", None)
        selected = await song.get_lyrics(syllable=True, language=language)
        selected_endpoint = "syllable"

        if selected is None:
            response = responses.get("syllable", getattr(api, "_lyrics_retagger_last_response", {}) or {})
            _log(
                logger,
                logging.WARNING,
                "SYLLABLE_LYRICS_UNAVAILABLE song_id=%s reason=%s status_code=%s "
                "data_count=%s ttml_present=%s",
                song_id,
                _response_reason(response),
                response.get("status_code", "not-observed"),
                response.get("data_count", "not-observed"),
                response.get("ttml_present", "not-observed"),
            )
            return None

        total, timed, untimed = _lyrics_timing(selected)
        if total == 0 or untimed:
            _log(
                logger,
                logging.WARNING,
                "SYLLABLE_LYRICS_UNAVAILABLE song_id=%s reason=NOT_FULLY_SYNCHRONIZED "
                "total_lines=%d timed_lines=%d untimed_lines=%d",
                song_id,
                total,
                timed,
                untimed,
            )
            return None

        _log(
            logger,
            logging.INFO,
            "LYRICS_FALLBACK_SUCCESS song_id=%s endpoint=syllable total_lines=%d "
            "timed_lines=%d",
            song_id,
            total,
            timed,
        )

    # Explicit standard LRC rendering is used even when the source has
    # word/syllable timing. Gamdl uses each line's first timestamp for LRC.
    rendered = selected.render(LyricsFormat.LRC, embedded=False)
    rendered = rendered.strip("\ufeff\r\n")
    if not rendered:
        _log(
            logger,
            logging.WARNING,
            "LYRICS_UNAVAILABLE song_id=%s endpoint=%s reason=EMPTY_LRC_AFTER_RENDER",
            song_id,
            selected_endpoint,
        )
        return None

    _log(
        logger,
        logging.INFO,
        "LYRICS_READY song_id=%s endpoint=%s lines=%d timed_lines=%d lrc_chars=%d format=lrc",
        song_id,
        selected_endpoint,
        total,
        timed,
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
