"""Unit tests for MP4 IDs, lyrics atoms and the audio-payload integrity guard."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gamdl_lyrics_retagger.mp4 import (
    Mp4InspectionError,
    mdat_signature,
    read_catalog_song_id,
    read_embedded_lyrics,
)


def atom(atom_type: bytes, payload: bytes) -> bytes:
    return struct.pack(">I4s", 8 + len(payload), atom_type) + payload


class Mp4TagReadTests(unittest.TestCase):
    def test_reads_catalog_song_id_from_cnid(self) -> None:
        fake_mp4 = type("FakeMp4", (), {"tags": {"cnID": [6805195215]}})()
        with patch("gamdl_lyrics_retagger.mp4.MP4", return_value=fake_mp4):
            self.assertEqual(read_catalog_song_id(Path("track.m4a")), "6805195215")

    def test_does_not_substitute_album_or_artist_ids(self) -> None:
        fake_mp4 = type("FakeMp4", (), {"tags": {"plID": [123], "atID": [456]}})()
        with patch("gamdl_lyrics_retagger.mp4.MP4", return_value=fake_mp4):
            self.assertIsNone(read_catalog_song_id(Path("track.m4a")))

    def test_reads_embedded_lyrics_from_lyr_atom(self) -> None:
        expected = "[00:01.23]Synchronized line"
        fake_mp4 = type("FakeMp4", (), {"tags": {"©lyr": [expected]}})()
        with patch("gamdl_lyrics_retagger.mp4.MP4", return_value=fake_mp4):
            self.assertEqual(read_embedded_lyrics(Path("track.m4a")), expected)


class MdatSignatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "sample.m4a"

    def test_ignores_metadata_atoms_and_hashes_mdat_payload(self) -> None:
        self.path.write_bytes(
            atom(b"ftyp", b"M4A ")
            + atom(b"moov", b"metadata before")
            + atom(b"mdat", b"ALAC encoded frames")
        )
        before = mdat_signature(self.path)
        self.path.write_bytes(
            atom(b"ftyp", b"M4A ")
            + atom(b"moov", b"different lyrics metadata")
            + atom(b"mdat", b"ALAC encoded frames")
        )
        after = mdat_signature(self.path)
        self.assertEqual(before, after)

    def test_detects_modified_audio_payload(self) -> None:
        self.path.write_bytes(atom(b"mdat", b"original audio"))
        before = mdat_signature(self.path)
        self.path.write_bytes(atom(b"mdat", b"modified audio"))
        after = mdat_signature(self.path)
        self.assertNotEqual(before, after)

    def test_handles_multiple_mdat_atoms(self) -> None:
        self.path.write_bytes(atom(b"mdat", b"part one") + atom(b"mdat", b"part two"))
        signature = mdat_signature(self.path)
        self.assertEqual(signature.atom_count, 2)
        self.assertEqual(signature.payload_bytes, len(b"part onepart two"))

    def test_rejects_invalid_atom_size(self) -> None:
        self.path.write_bytes(struct.pack(">I4s", 2, b"mdat"))
        with self.assertRaises(Mp4InspectionError):
            mdat_signature(self.path)

    def test_rejects_file_without_mdat(self) -> None:
        self.path.write_bytes(atom(b"ftyp", b"M4A "))
        with self.assertRaises(Mp4InspectionError):
            mdat_signature(self.path)


if __name__ == "__main__":
    unittest.main()
