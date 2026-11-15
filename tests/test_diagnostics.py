"""Tests for safe API diagnostics and local TTML sidecar inspection."""

from __future__ import annotations

import logging
import sys
import tempfile
import types
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from gamdl_lyrics_retagger.update import (
    install_lyrics_api_observer,
    inspect_local_ttml,
)


class ApiObserverTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.stream = StringIO()
        self.logger = logging.getLogger(f"lyrics-test-{id(self)}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.handler = logging.StreamHandler(self.stream)
        self.logger.addHandler(self.handler)
        self.addCleanup(self.logger.removeHandler, self.handler)
        self.addCleanup(self.handler.close)

    async def test_logs_response_shape_but_not_ttml_content(self) -> None:
        sensitive_lyrics = "<tt><p>PRIVATE LYRIC TEXT</p></tt>"

        class FakeApi:
            storefront = "mx"
            language = "es-MX"

            async def get_lyrics(self, song_id: str, *, language=None):
                return {
                    "data": [
                        {
                            "attributes": {
                                "ttml": sensitive_lyrics,
                                "other": "metadata",
                            }
                        }
                    ]
                }

        api = FakeApi()
        install_lyrics_api_observer(api, self.logger)
        response = await api.get_lyrics("1444116875", language="es-MX")
        output = self.stream.getvalue()

        self.assertEqual(response["data"][0]["attributes"]["ttml"], sensitive_lyrics)
        self.assertIn("APPLE_LYRICS_REQUEST", output)
        self.assertIn("APPLE_LYRICS_RESPONSE", output)
        self.assertIn("ttml_present=True", output)
        self.assertIn("ttml_chars=", output)
        self.assertIn("other,ttml", output)
        self.assertNotIn("PRIVATE LYRIC TEXT", output)

    async def test_observes_syllable_endpoint_separately(self) -> None:
        class FakeApi:
            storefront = "mx"
            language = "en-US"

            async def get_lyrics(self, song_id: str, *, language=None):
                return {"data": []}

            async def get_syllable_lyrics(
                self,
                song_id: str,
                *,
                language=None,
                lyrics_language=None,
                script=None,
                extend=None,
            ):
                return {
                    "data": [
                        {
                            "attributes": {
                                "ttml": "<tt><p begin='1s'>private text</p></tt>"
                            }
                        }
                    ]
                }

        api = FakeApi()
        install_lyrics_api_observer(api, self.logger)
        response = await api.get_syllable_lyrics("1444116875", language="en-US")
        output = self.stream.getvalue()

        self.assertEqual(len(response["data"]), 1)
        self.assertIn("endpoint=syllable", output)
        self.assertIn("LYRICS_RESPONSE", output)
        self.assertIn("ttml_present=True", output)
        self.assertNotIn("private text", output)
        self.assertIn("syllable", api._lyrics_retagger_responses)

    async def test_logs_http_status_without_exposing_exception_body(self) -> None:
        class FakeApiError(Exception):
            status_code = 404

        class FakeApi:
            async def get_lyrics(self, song_id: str, *, language=None):
                raise FakeApiError("private response body should not be logged")

        api = FakeApi()
        install_lyrics_api_observer(api, self.logger)
        with self.assertRaises(FakeApiError):
            await api.get_lyrics("1444116875")
        output = self.stream.getvalue()

        self.assertIn("status_code=404", output)
        self.assertIn("FakeApiError", output)
        self.assertNotIn("private response body", output)


class LocalTtmlDiagnosticsTests(unittest.TestCase):
    def test_detects_and_counts_same_name_ttml_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            m4a_path = Path(directory) / "Baby Come On (Acoustic Version).m4a"
            m4a_path.write_bytes(b"fixture")
            sidecar = m4a_path.with_suffix(".ttml")
            sidecar.write_text(
                '<tt><body><div><p begin="1s">Timed line</p>'
                '<p begin="2s">Another timed line</p></div></body></tt>',
                encoding="utf-8",
            )

            fake_gamdl = types.ModuleType("gamdl")
            fake_media = types.ModuleType("gamdl.media")
            fake_song = types.ModuleType("gamdl.media.song")
            fake_lyrics = types.ModuleType("gamdl.media.song.lyrics")

            class ParsedLine:
                def __init__(self, text: str, start: int | None) -> None:
                    self.text = text
                    self.start = start

            class ParsedLyrics:
                def __init__(self, raw: str) -> None:
                    self.lines = [
                        ParsedLine("Timed line", 1000),
                        ParsedLine("Another timed line", 2000),
                    ]

                @classmethod
                def from_ttml(cls, raw: str):
                    return cls(raw)

            fake_lyrics.Lyrics = ParsedLyrics
            with patch.dict(
                sys.modules,
                {
                    "gamdl": fake_gamdl,
                    "gamdl.media": fake_media,
                    "gamdl.media.song": fake_song,
                    "gamdl.media.song.lyrics": fake_lyrics,
                },
            ):
                found = inspect_local_ttml(m4a_path)

            self.assertEqual(found, sidecar)


if __name__ == "__main__":
    unittest.main()
