"""Command-line interface for the Gamdl lyrics retagger."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Sequence

from . import __version__
from .auth import open_gamdl_api
from .mp4 import read_catalog_song_id, read_embedded_lyrics
from .update import (
    apply_embedded_lrc,
    fetch_synchronized_lrc,
    inspect_local_ttml,
    install_lyrics_api_observer,
)

DEFAULT_DIRECTORY = Path("/mnt/d/Pruebas")
DEFAULT_CONFIG = Path.home() / ".gamdl" / "config.yml"


def _create_logger(log_path: Path) -> tuple[logging.Logger, logging.FileHandler]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("gamdl_lyrics_retagger")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in tuple(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s.%(msecs)03d | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    return logger, handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gamdl-lyrics-retagger",
        description=(
            "Recupera LRC sincronizado con Gamdl 4.x y actualiza únicamente "
            "el átomo ©lyr de M4A existentes. No descarga ni recodifica audio."
        ),
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=DEFAULT_DIRECTORY,
        help=f"Carpeta que contiene los M4A (predeterminada: {DEFAULT_DIRECTORY}).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Config YAML de Gamdl (predeterminada: {DEFAULT_CONFIG}).",
    )
    parser.add_argument(
        "--storefront",
        help="Storefront de Apple Music (dos letras), reemplaza auth.storefront de Gamdl.",
    )
    parser.add_argument(
        "--language",
        help="Idioma de metadatos/letras, por ejemplo es-MX; reemplaza auth.language de Gamdl.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Máximo de archivos M4A a revisar; útil para la primera prueba.",
    )
    parser.add_argument(
        "--match",
        help="Filtra por una parte del nombre o ruta relativa del archivo (sin distinguir mayúsculas).",
    )
    parser.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Buscar también en subcarpetas (predeterminado: sí).",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Ruta del LOG detallado. Por defecto: <directory>/.lyrics-retagger.log.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Escribir cambios. Sin este parámetro solo se ejecuta una simulación.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _find_m4a_files(
    directory: Path,
    *,
    recursive: bool,
    limit: int | None,
    match: str | None = None,
) -> list[Path]:
    iterator = directory.rglob("*") if recursive else directory.glob("*")
    files = [
        path
        for path in iterator
        if path.is_file()
        and not path.is_symlink()
        and path.suffix.lower() == ".m4a"
        and ".lyrics-retagger-backups" not in path.parts
    ]
    if match:
        needle = match.casefold()
        files = [
            path
            for path in files
            if needle in path.relative_to(directory).as_posix().casefold()
        ]
    files.sort(key=lambda item: str(item).casefold())
    return files[:limit] if limit is not None else files


async def _run(args: argparse.Namespace) -> int:
    started = time.monotonic()
    root = args.directory.expanduser().resolve()
    config_path = args.config.expanduser().resolve()

    if not root.is_dir():
        print(f"ERROR: la carpeta no existe o no es un directorio: {root}", file=sys.stderr)
        return 2
    if args.limit is not None and args.limit < 1:
        print("ERROR: --limit debe ser mayor que cero.", file=sys.stderr)
        return 2
    if args.storefront and (
        len(args.storefront) != 2
        or not args.storefront.isascii()
        or not args.storefront.isalpha()
    ):
        print("ERROR: --storefront debe ser un código de dos letras.", file=sys.stderr)
        return 2

    files = _find_m4a_files(
        root,
        recursive=args.recursive,
        limit=args.limit,
        match=args.match,
    )
    if not files:
        print(f"No se encontraron archivos .m4a en: {root}")
        return 0

    log_path = args.log_file.expanduser() if args.log_file else root / ".lyrics-retagger.log"
    if not log_path.is_absolute():
        log_path = root / log_path
    log_path = log_path.resolve()
    try:
        logger, log_handler = _create_logger(log_path)
    except OSError as exc:
        print(f"ERROR: no se pudo crear el LOG {log_path}: {exc}", file=sys.stderr)
        return 4

    updated = unchanged = skipped = failed = 0
    print(f"Gamdl Lyrics Retagger {__version__}")
    print(f"Carpeta: {root}")
    print(f"Archivos M4A: {len(files)}")
    print(f"Modo: {'APLICAR' if args.apply else 'SIMULACIÓN (sin cambios)'}")
    print(f"LOG: {log_path}")

    logger.info(
        "RUN_START version=%s directory=%s config=%s mode=%s file_count=%d "
        "storefront_override=%s language_override=%s match_filter=%s backups=disabled",
        __version__,
        root,
        config_path,
        "apply" if args.apply else "dry-run",
        len(files),
        args.storefront or "config/default",
        args.language or "config/default",
        args.match or "none",
    )

    try:
        try:
            stack, api = await open_gamdl_api(
                config_path, storefront=args.storefront, language=args.language
            )
        except Exception as exc:
            logger.error(
                "AUTHENTICATION_FAILED error_type=%s status_code=%s",
                type(exc).__name__,
                getattr(exc, "status_code", "unknown"),
            )
            print(
                f"ERROR de autenticación/configuración: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 3

        install_lyrics_api_observer(api, logger)
        logger.info(
            "AUTHENTICATED mode=%s storefront=%s language=%s credentials_logged=false",
            (getattr(api, "_retagger_auth_mode", None) or "configured"),
            getattr(api, "storefront", "unknown"),
            getattr(api, "language", "unknown"),
        )

        muxer = None
        if args.apply:
            from gamdl.muxer import Muxer

            muxer = Muxer()

        async with stack:
            for index, path in enumerate(files, start=1):
                relative = path.relative_to(root)
                print(f"[{index}/{len(files)}] {relative}")
                logger.info("FILE_START index=%d total=%d path=%s", index, len(files), relative)

                try:
                    song_id = read_catalog_song_id(path)
                    if song_id is None:
                        logger.warning(
                            "FILE_SKIPPED path=%s reason=CNID_NOT_FOUND",
                            relative,
                        )
                        print("  OMITIDO: no se encontró cnID (ID de canción Apple Music).")
                        skipped += 1
                        continue

                    logger.info("CATALOG_ID path=%s cnID=%s", relative, song_id)
                    lrc = await fetch_synchronized_lrc(api, song_id, logger=logger)
                    if lrc is None:
                        inspect_local_ttml(path, logger=logger)
                        logger.warning(
                            "FILE_SKIPPED path=%s cnID=%s reason=NO_USABLE_APPLE_LYRICS",
                            relative,
                            song_id,
                        )
                        print(
                            f"  OMITIDO: no se obtuvo LRC sincronizado (cnID={song_id}); "
                            "consulta el LOG para conocer el motivo."
                        )
                        skipped += 1
                        continue

                    current_lyrics = read_embedded_lyrics(path)
                    if current_lyrics == lrc:
                        logger.info(
                            "FILE_UNCHANGED path=%s cnID=%s reason=LYRICS_ALREADY_MATCH",
                            relative,
                            song_id,
                        )
                        print("  SIN CAMBIOS: el LRC ya coincide.")
                        unchanged += 1
                        continue

                    line_count = sum(1 for line in lrc.splitlines() if line.strip())
                    if not args.apply:
                        logger.info(
                            "DRY_RUN_WOULD_UPDATE path=%s cnID=%s lines=%d lrc_chars=%d",
                            relative,
                            song_id,
                            line_count,
                            len(lrc),
                        )
                        print(
                            f"  PREVISTO: actualizar ©lyr con LRC "
                            f"({line_count} líneas; cnID={song_id})."
                        )
                        updated += 1
                        continue

                    result = apply_embedded_lrc(
                        path,
                        lyrics=lrc,
                        muxer=muxer,
                        logger=logger,
                    )
                    if result.status == "updated":
                        print("  ACTUALIZADO: ©lyr escrito; mdat verificado; sin respaldo.")
                        updated += 1
                    else:
                        print(f"  SIN CAMBIOS: {result.detail}")
                        unchanged += 1

                except Exception as exc:
                    logger.error(
                        "FILE_ERROR path=%s error_type=%s status_code=%s",
                        relative,
                        type(exc).__name__,
                        getattr(exc, "status_code", "unknown"),
                    )
                    print(f"  ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
                    failed += 1
                finally:
                    logger.info("FILE_END path=%s", relative)

        elapsed = time.monotonic() - started
        logger.info(
            "RUN_END updated=%d unchanged=%d skipped=%d failed=%d elapsed_seconds=%.2f",
            updated,
            unchanged,
            skipped,
            failed,
            elapsed,
        )
        print("\nResumen")
        print(f"  {'Se actualizarían' if not args.apply else 'Actualizados'}: {updated}")
        print(f"  Sin cambios: {unchanged}")
        print(f"  Omitidos: {skipped}")
        print(f"  Errores: {failed}")
        print(f"  LOG: {log_path}")
        if not args.apply:
            print("\nSimulación terminada. Usa --apply para escribir los cambios.")
        return 1 if failed else 0
    finally:
        logger.info("LOG_CLOSED")
        log_handler.close()
        logger.removeHandler(log_handler)


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
