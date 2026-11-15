"""CLI filtering and default log argument tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gamdl_lyrics_retagger.cli import _find_m4a_files, build_parser
from gamdl_lyrics_retagger.update import can_write_plain_text_fallback


class CliFilterTests(unittest.TestCase):
    def test_filters_by_case_insensitive_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "Album" / "Baby Come On (Acoustic Version).m4a"
            other = root / "Album" / "Baby Come On.m4a"
            target.parent.mkdir()
            target.write_bytes(b"")
            other.write_bytes(b"")

            result = _find_m4a_files(
                root,
                recursive=True,
                limit=None,
                match="baby come on (ACOUSTIC VERSION)",
            )

        self.assertEqual(result, [target])

    def test_keeps_default_recursive_discovery_and_skips_old_backup_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            track = root / "Album" / "track.m4a"
            backup = root / ".lyrics-retagger-backups" / "track.m4a"
            track.parent.mkdir()
            backup.parent.mkdir()
            track.write_bytes(b"")
            backup.write_bytes(b"")

            result = _find_m4a_files(root, recursive=True, limit=None)

        self.assertEqual(result, [track])

    def test_plain_text_fallback_requires_missing_atom(self) -> None:
        self.assertTrue(can_write_plain_text_fallback(None))
        self.assertFalse(can_write_plain_text_fallback(""))
        self.assertFalse(can_write_plain_text_fallback("Existing lyrics"))

    def test_parser_accepts_match_and_log_file(self) -> None:
        args = build_parser().parse_args(
            [
                "--directory",
                "/mnt/d/Pruebas",
                "--match",
                "Baby Come On (Acoustic Version)",
                "--log-file",
                "/tmp/retagger.log",
            ]
        )
        self.assertEqual(args.match, "Baby Come On (Acoustic Version)")
        self.assertEqual(args.log_file, Path("/tmp/retagger.log"))


if __name__ == "__main__":
    unittest.main()
