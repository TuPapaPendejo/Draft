"""Tests for the metadata-only Gamdl lyrics request and LRC conversion."""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from gamdl_lyrics_retagger.update import fetch_synchronized_lrc


class FakeLyricLine:
    def __init__(self, text: str, start: int | None) -> None:
        self.text = text
        self.start = start


class FakeLyrics:
    def __init__(self, lines: list[FakeLyricLine]) -> None:
        self.lines = lines
        self.rendered = False

    def render(self, format_value: str, *, embedded: bool) -> str:
        self.rendered = True
        if format_value != "lrc" or embedded:
            raise AssertionError("The updater must request strict standard LRC")
        return "[00:00.50]Timed line\n[00:02.00]Second line"


class FakeSongInstance:
    def __init__(self, lyrics: FakeLyrics | None) -> None:
        self.lyrics = lyrics
        self.get_lyrics_kwargs = None

    async def get_lyrics(self, **kwargs):
        self.get_lyrics_kwargs = kwargs
        return self.lyrics


class FakeSong:
    instance: FakeSongInstance | None = None
    arguments = None

    @classmethod
    def from_id(cls, song_id: str, *, api, is_library: bool):
        cls.arguments = (song_id, api, is_library)
        return cls.instance


class FetchSynchronizedLyricsTests(unittest.IsolatedAsyncioTestCase):
    def _install_fake_gamdl(self):
        gamdl_module = types.ModuleType("gamdl")
        media_module = types.ModuleType("gamdl.media")
        media_module.Song = FakeSong
        song_module = types.ModuleType("gamdl.media.song")
        lyrics_module = types.ModuleType("gamdl.media.song.lyrics")
        lyrics_module.LyricsFormat = types.SimpleNamespace(LRC="lrc")
        gamdl_module.media = media_module
        media_module.song = song_module
        song_module.lyrics = lyrics_module
        return patch.dict(
            sys.modules,
            {
                "gamdl": gamdl_module,
                "gamdl.media": media_module,
                "gamdl.media.song": song_module,
                "gamdl.media.song.lyrics": lyrics_module,
            },
        )

    async def test_requests_standard_lrc_using_configured_language(self) -> None:
        api = types.SimpleNamespace(language="es-MX")
        lyrics = FakeLyrics(
            [FakeLyricLine("Timed line", 500), FakeLyricLine("Second line", 2000)]
        )
        FakeSong.instance = FakeSongInstance(lyrics)
        with self._install_fake_gamdl():
            result = await fetch_synchronized_lrc(api, "6805195215")

        self.assertEqual(FakeSong.arguments, ("6805195215", api, False))
        self.assertEqual(
            FakeSong.instance.get_lyrics_kwargs,
            {"syllable": False, "language": "es-MX"},
        )
        self.assertTrue(lyrics.rendered)
        self.assertEqual(result, "[00:00.50]Timed line\n[00:02.00]Second line")

    async def test_skips_partially_synchronized_lyrics(self) -> None:
        api = types.SimpleNamespace(language="en-US")
        lyrics = FakeLyrics(
            [FakeLyricLine("Timed line", 500), FakeLyricLine("Untimed line", None)]
        )
        FakeSong.instance = FakeSongInstance(lyrics)
        with self._install_fake_gamdl():
            result = await fetch_synchronized_lrc(api, "123")

        self.assertIsNone(result)
        self.assertFalse(lyrics.rendered)

    async def test_skips_missing_lyrics(self) -> None:
        api = types.SimpleNamespace(language="en-US")
        FakeSong.instance = FakeSongInstance(None)
        with self._install_fake_gamdl():
            result = await fetch_synchronized_lrc(api, "123")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
