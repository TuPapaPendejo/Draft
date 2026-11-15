"""Command-line interface for the Gamdl lyrics retagger."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .auth import open_gamdl_api
from .mp4 import read_catalog_song_id, read_embedded_lyrics
from .update import apply_embedded_lrc, fetch_synchronized_lrc

DEFAULT_DIRECTORY = Path("/mnt/d/Pruebas")
DEFAULT_CONFIG = Path.home() / ".gamdl" / "config.yml"
BACKUP_DIRECTORY_NAME = ".lyrics-retagger-backups"


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
        help="Idioma de metadatos, por ejemplo es-MX; reemplaza auth.language de Gamdl.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Máximo de archivos M4A a revisar; útil para la primera prueba.",
    )
    parser.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Buscar también en subcarpetas (predeterminado: sí).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Escribir cambios. Sin este parámetro solo se ejecuta una simulación.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _find_m4a_files(directory: Path, *, recursive: bool, limit: int | None) -> list[Path]:
    iterator = directory.rglob("*") if recursive else directory.glob("*")
    files = [
        path
        for path in iterator
        if path.is_file()
        and not path.is_symlink()
        and path.suffix.lower() == ".m4a"
        and BACKUP_DIRECTORY_NAME not in path.parts
    ]
    files.sort(key=lambda item: str(item).casefold())
    return files[:limit] if limit is not None else files


async def _run(args: argparse.Namespace) -> int:
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

    files = _find_m4a_files(root, recursive=args.recursive, limit=args.limit)
    if not files:
        print(f"No se encontraron archivos .m4a en: {root}")
        return 0

    print(f"Gamdl Lyrics Retagger {__version__}")
    print(f"Carpeta: {root}")
    print(f"Archivos M4A: {len(files)}")
    print(f"Modo: {'APLICAR' if args.apply else 'SIMULACIÓN (sin cambios)'}")

    try:
        stack, api = await open_gamdl_api(
            config_path, storefront=args.storefront, language=args.language
        )
    except Exception as exc:
        print(f"ERROR de autenticación/configuración: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3

    muxer = None
    if args.apply:
        from gamdl.muxer import Muxer

        muxer = Muxer()

    updated = unchanged = skipped = failed = 0
    backup_root = root / BACKUP_DIRECTORY_NAME

    async with stack:
        for index, path in enumerate(files, start=1):
            relative = path.relative_to(root)
            print(f"[{index}/{len(files)}] {relative}")
            try:
                song_id = read_catalog_song_id(path)
                if song_id is None:
                    print("  OMITIDO: no se encontró cnID (ID de canción Apple Music).")
                    skipped += 1
                    continue

                lrc = await fetch_synchronized_lrc(api, song_id)
                if lrc is None:
                    print(
                        f"  OMITIDO: Apple Music no devolvió letra sincronizada (cnID={song_id})."
                    )
                    skipped += 1
                    continue

                if read_embedded_lyrics(path) == lrc:
                    print("  SIN CAMBIOS: el LRC ya coincide.")
                    unchanged += 1
                    continue

                line_count = sum(1 for line in lrc.splitlines() if line.strip())
                if not args.apply:
                    print(
                        f"  PREVISTO: actualizar ©lyr con LRC ({line_count} líneas; cnID={song_id})."
                    )
                    updated += 1
                    continue

                result = apply_embedded_lrc(
                    path,
                    root=root,
                    lyrics=lrc,
                    muxer=muxer,
                    backup_root=backup_root,
                )
                if result.status == "updated":
                    print(f"  ACTUALIZADO: respaldo: {result.backup}")
                    updated += 1
                else:
                    print(f"  SIN CAMBIOS: {result.detail}")
                    unchanged += 1

            except Exception as exc:
                print(f"  ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
                failed += 1

    print("\nResumen")
    print(f"  {'Se actualizarían' if not args.apply else 'Actualizados'}: {updated}")
    print(f"  Sin cambios: {unchanged}")
    print(f"  Omitidos: {skipped}")
    print(f"  Errores: {failed}")
    if not args.apply:
        print("\nSimulación terminada. Usa --apply para escribir los cambios.")
    return 1 if failed else 0


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
