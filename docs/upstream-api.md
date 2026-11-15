# Gamdl 4.x API integration notes

This project targets Gamdl's `4.0` source line (the inspected package metadata reports `4.0.1`). It deliberately calls the higher-level media API instead of recreating Apple Music authentication or parsing TTML itself.

## Upstream entry points

- [Gamdl 4.0 README — Python API](https://github.com/glomatico/gamdl/blob/4.0/README.md#-python-api): documents asynchronous `AppleMusicApi`, `MediaResolver`, and `Song` usage.
- [Apple Music catalog endpoints](https://github.com/glomatico/gamdl/blob/4.0/src/gamdl/api/apple_music/catalog.py): exposes `get_lyrics(song_id, language=...)` and `get_syllable_lyrics(...)`.
- [Song media model](https://github.com/glomatico/gamdl/blob/4.0/src/gamdl/media/song/media.py): `Song.get_lyrics()` resolves the catalog ID, fetches the TTML lyrics response, and returns a parsed `Lyrics` model without requesting an audio stream.
- [Lyrics parser and exporters](https://github.com/glomatico/gamdl/blob/4.0/src/gamdl/media/song/lyrics.py): parses TTML and renders standard or enhanced LRC.
- [Native MP4 tag interface](https://github.com/glomatico/gamdl/blob/4.0/src/gamdl/muxer/muxer.py): `Muxer.tag()` accepts a `gamdl.download.Tags` instance; unset fields remain untouched.
- [Native MP4 atom mapping](https://github.com/glomatico/gamdl/blob/4.0/native/src/tags.rs): maps the `lyrics` field to the MP4 `©lyr` atom and the song `title_id` to `cnID`.

## Exact data flow

1. Mutagen reads `cnID` from the local M4A. This is the Apple catalog **song** ID. Album and artist IDs are not accepted as substitutes.
2. `Song.from_id(song_id, api=api)` creates a lazy media object. This does not resolve or download audio.
3. `await song.get_lyrics(syllable=False, language=api.language)` asks Gamdl for standard TTML lyrics. It is a metadata/lyrics request only.
4. `Lyrics.render(LyricsFormat.LRC, embedded=False)` converts line-level TTML timing into ordinary `[mm:ss.xx]` LRC timestamps. With `embedded=False`, Gamdl raises when the source cannot produce synchronized LRC rather than falling back to plain text.
5. `Muxer.tag(staged_path, tags=Tags(lyrics=lrc))` writes only the lyrics field. Other fields are `None`, which the Gamdl tag writer treats as unspecified/preserve.
6. The program reads the lyric atom back, verifies `mdat` payload identity, saves a backup, and only then replaces the original path.

## Authentication reuse

The integration reads the existing `~/.gamdl/config.yml` and supports these Gamdl 4.x `auth.mode` values:

- `cookies`: `AppleMusicApi.from_cookies(auth.cookies_path, ...)`.
- `media-user-token`: `AppleMusicApi.create(media_user_token=..., ...)`.
- `wrapper`: `WrapperApi.create(...)`, then `AppleMusicApi.from_wrapper(...)`.

Credentials are only held in memory while the process runs. The retagger does not change Gamdl's configuration or write tokens to logs.

## Availability and private endpoint caveats

Gamdl's catalog lyrics implementation calls Apple's AMP catalog lyrics endpoint (`/v1/catalog/{storefront}/songs/{song_id}/lyrics`). The corresponding upstream code itself notes that this endpoint is private and may change independently of Gamdl's supported API surface. Lyrics also vary by song, storefront, account access and language. The program treats no response, no TTML, or TTML without line timing as a skip; it never synthesizes timestamps.

The first project version asks for standard line timing (`syllable=False`) and creates embedded standard LRC, not enhanced word/syllable LRC. It never falls back to text-only lyrics.

## Version compatibility

The dependency range is `gamdl>=4.0.1,<5`. If Gamdl changes the `Song`, `Lyrics`, authentication or `Muxer` interface within a future 4.x release, the unit suite and manual one-file Apple Music test should be run before upgrading the lockfile.