# Gamdl Lyrics Retagger

Refresh synchronized LRC lyrics inside existing Apple Music `.m4a` files without downloading or re-encoding audio.

Version: `0.1.0` · Target: Gamdl `4.x` · Primary environment: openSUSE Tumbleweed under WSL.

## Purpose

The program reads each song catalog ID from the M4A `cnID` atom, reuses the authentication configuration at `~/.gamdl/config.yml`, fetches only the lyrics through Gamdl's asynchronous Python API, converts Apple's TTML to standard line-synchronized LRC, and updates only the embedded `©lyr` atom.

It does not request audio playback, download media bytes, decrypt streams, remux tracks, or transcode audio. Files without a usable `cnID`, without synchronized lyrics, or that fail validation are skipped.

## Safety model

- Simulation is the default; writing requires `--apply`.
- Each update is staged in the same directory as the original.
- The staged `©lyr` value is read back and compared with the generated LRC.
- SHA-256, byte count, and atom count of all top-level `mdat` payloads must remain identical.
- A non-overwriting original-file backup is created before atomic replacement.

## Prerequisites

- Python 3.10+.
- `uv`.
- A working Gamdl 4.x Apple Music authentication configuration.
- Existing `.m4a` files containing Apple song catalog IDs in `cnID`.

## Install in WSL

```bash
git clone https://github.com/TuPapaPendejo/Draft.git
cd Draft
uv sync
uv run gamdl-lyrics-retagger --version
```

Configure authentication using Gamdl itself if necessary:

```bash
uv run gamdl auth
```

The retagger supports Gamdl's `cookies`, `media-user-token`, and `wrapper` auth modes. It never prints or stores token values.

## First run: no changes

The default input folder is `/mnt/d/Pruebas`.

```bash
uv run gamdl-lyrics-retagger --directory /mnt/d/Pruebas --limit 1
uv run gamdl-lyrics-retagger --directory /mnt/d/Pruebas
```

## Apply

After reviewing the simulation:

```bash
uv run gamdl-lyrics-retagger --directory /mnt/d/Pruebas --limit 1 --apply
uv run gamdl-lyrics-retagger --directory /mnt/d/Pruebas --apply
```

Backups are placed under `.lyrics-retagger-backups/` within the selected folder. Existing backups are never overwritten.

## CLI reference

| Option | Meaning | Default |
|---|---|---|
| `--directory PATH` | M4A folder | `/mnt/d/Pruebas` |
| `--config PATH` | Gamdl YAML config | `~/.gamdl/config.yml` |
| `--storefront XX` | Override Apple storefront | Gamdl config/default |
| `--language TAG` | Override metadata language | Gamdl config, then `en-US` |
| `--limit N` | Maximum files to inspect | All files |
| `--recursive` / `--no-recursive` | Include/exclude subfolders | Recursive |
| `--apply` | Write verified changes | Off (simulation) |
| `--version` | Show version | — |

## Notes

- `cnID` is the track/song catalog ID. Album (`plID`) or artist (`atID`) IDs are not valid substitutes for the song lyrics endpoint.
- Gamdl's standard `LyricsFormat.LRC` emits line timestamps. `enhanced-lrc` is not selected in this first version.
- Embedded LRC is stored in the standard MP4 `©lyr` atom. Some players may display timestamps literally rather than implement synchronized highlighting.
- No external `.lrc` sidecar is written in version 0.1.0.
- If Apple Music does not return synchronized lyrics for the current storefront, the file is skipped.

See `docs/` for architecture and API notes, `CHANGELOG.md` for version history, and commit messages for the description of each repository change.

## Tests

```bash
uv run python -m unittest discover -s tests -v
```
