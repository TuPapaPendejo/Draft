# Changelog

All notable changes to this project are documented here. Version entries describe release scope; individual repository commits describe each change.

## [0.1.0] - 2026-11-14

### Added

- Initial project for refreshing embedded synchronized LRC lyrics in existing Gamdl M4A files.
- Reads Apple Music song catalog IDs from the MP4 cnID atom.
- Reuses existing Gamdl 4.x authentication for cookies, Media User Token, or Wrapper v2.
- Uses Gamdl's asynchronous song/lyrics API and native MP4 tag writer; no audio stream is downloaded or encoded.
- Default simulation mode; changes require the explicit --apply flag.
- Creates non-overwriting backups before replacement.
- Verifies the embedded ©lyr atom and byte-identical mdat payloads before publishing a staged file.
- Rejects transcripts with any non-empty line lacking a timestamp; does not downgrade partially synchronized text to LRC.
- Includes WSL/uv installation instructions, CLI reference, troubleshooting notes, and 13 unit tests for catalog ID extraction, lyrics retrieval policy, backups, and integrity guards.

### Known limitations

- Processes .m4a files with a readable cnID only.
- Requires Apple Music to return fully line-synchronized lyrics; it skips text-only, partially synchronized, or unavailable lyrics.
- Does not create external .lrc sidecar files.
- API integration tests against a real Apple Music account remain a manual validation step.
