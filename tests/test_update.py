"""Safety tests for staged lyrics-only updates without backup creation."""

from __future__ import annotations

import sys
import tempfile
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from gamdl_lyrics_retagger.mp4 import MdatSignature
from gamdl_lyrics_retagger.update import apply_embedded_lyrics


@dataclass
class FakeTags:
    lyrics: str | None = None


class FakeMuxer:
    def __init__(self, lyrics_by_path: dict[Path, str | None]) -> None:
        self.lyrics_by_path = lyrics_by_path
        self.received_tags: FakeTags | None = None

    def tag(self, path: Path, *, tags: FakeTags) -> None:
        self.received_tags = tags
        self.lyrics_by_path[path] = tags.lyrics


class ApplyLyricsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "album" / "track.m4a"
        self.source.parent.mkdir()
        self.original_bytes = b"original MP4 file fixture"
        self.source.write_bytes(self.original_bytes)
        self.signature = MdatSignature("same-audio-digest", 12345, 1)

    def _install_fake_tags(self):
        gamdl_module = types.ModuleType("gamdl")
        download_module = types.ModuleType("gamdl.download")
        download_module.Tags = FakeTags
        gamdl_module.download = download_module
        return patch.dict(
            sys.modules, {"gamdl": gamdl_module, "gamdl.download": download_module}
        )

    def test_updates_only_lyrics_without_creating_backup(self) -> None:
        existing = {self.source: "Old plain text"}
        muxer = FakeMuxer(existing)

        def read_lyrics(path: Path) -> str | None:
            return existing.get(path)

        with self._install_fake_tags(), patch(
            "gamdl_lyrics_retagger.update.mdat_signature",
            return_value=self.signature,
        ), patch(
            "gamdl_lyrics_retagger.update.read_embedded_lyrics",
            side_effect=read_lyrics,
        ):
            result = apply_embedded_lyrics(
                self.source,
                lyrics="[00:00.50]New synchronized line",
                muxer=muxer,
            )

        self.assertEqual(result.status, "updated")
        self.assertIn("[00:00.50]New synchronized line", existing.values())
        self.assertEqual(
            muxer.received_tags,
            FakeTags(lyrics="[00:00.50]New synchronized line"),
        )
        self.assertEqual(self.source.read_bytes(), self.original_bytes)
        self.assertFalse((self.root / ".lyrics-retagger-backups").exists())
        self.assertFalse(list(self.source.parent.glob(".*.lyrics-retagger-*")))

    def test_rejects_audio_payload_mismatch_without_replacing_source(self) -> None:
        existing = {self.source: "Old lyrics"}
        muxer = FakeMuxer(existing)
        signatures = iter([self.signature, MdatSignature("changed", 12345, 1)])

        with self._install_fake_tags(), patch(
            "gamdl_lyrics_retagger.update.mdat_signature",
            side_effect=lambda _path: next(signatures),
        ), patch(
            "gamdl_lyrics_retagger.update.read_embedded_lyrics",
            side_effect=lambda path: existing.get(path),
        ):
            with self.assertRaisesRegex(RuntimeError, "mdat cambió"):
                apply_embedded_lrc(
                    self.source,
                    lyrics="[00:00.50]New synchronized line",
                    muxer=muxer,
                )

        self.assertEqual(self.source.read_bytes(), self.original_bytes)
        self.assertFalse((self.root / ".lyrics-retagger-backups").exists())
        self.assertFalse(list(self.source.parent.glob(".*.lyrics-retagger-*")))


if __name__ == "__main__":
    unittest.main()
