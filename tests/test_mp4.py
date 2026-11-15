"""Unit tests for the MP4 payload-integrity guard."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from gamdl_lyrics_retagger.mp4 import Mp4InspectionError, mdat_signature


def atom(atom_type: bytes, payload: bytes) -> bytes:
    return struct.pack(">I4s", 8 + len(payload), atom_type) + payload


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
