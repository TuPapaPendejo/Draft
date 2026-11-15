# Architecture and processing flow

    M4A folder
       |
       +--> Mutagen reads cnID (song catalog ID)
                 |
                 v
          Gamdl 4.x AppleMusicApi
                 |
                 +--> Song.from_id(cnID)
                 |
                 +--> Song.get_lyrics(syllable=False)
                            |
                            v
                     TTML -> Gamdl Lyrics -> standard line LRC
                            |
                            v
              Stage-copy M4A -> Gamdl Muxer.tag(Tags(lyrics=LRC))
                            |
                            +--> verify ©lyr read-back
                            +--> verify mdat SHA-256 and byte count
                            +--> backup original
                            +--> atomic replace

## Boundaries

- Catalog ID extraction and MP4 payload verification live in mp4.py.
- Existing Gamdl authentication is translated to AppleMusicApi / WrapperApi constructors in auth.py.
- fetch_synchronized_lrc() delegates TTML parsing and LRC rendering to Gamdl itself.
- apply_embedded_lrc() changes only the lyrics field in a gamdl.download.Tags instance. Other fields are None and are preserved by Gamdl's tag writer.
- The CLI owns discovery, dry-run/apply selection, and per-file reporting.

## Failure policy

The updater fails closed. Missing IDs, absent lyrics, unsynchronized lyrics, invalid atoms, a mismatch in the resulting embedded text, or a changed mdat signature prevent replacement. Temporary files are removed in a finally block. The original file is backed up before its staged replacement is atomically published.
