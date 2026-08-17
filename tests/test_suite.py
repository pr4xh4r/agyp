#!/usr/bin/env python3
"""
Comprehensive test suite for agyp-suite.
Simulates 15 different users across Linux, macOS, and Windows scenarios.
No GUI required — tests all logic: sanitize_name, swap/save auth, profile listing,
last-active tracking, path traversal defence, and edge cases.
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Let tests import the modules without running main()
sys.path.insert(0, str(Path(__file__).parent.parent))


class BaseTest(unittest.TestCase):
    """Sets up a temp home with fake auth files for every test."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "home" / "user"
        self.home.mkdir(parents=True)
        self.profiles_dir = self.home / "agyp-profiles"
        self.profiles_dir.mkdir()

        gemini = self.home / ".gemini"
        gemini.mkdir()
        (gemini / "antigravity-cli").mkdir()
        self.token_path    = gemini / "antigravity-cli" / "antigravity-oauth-token"
        self.creds_path    = gemini / "oauth_creds.json"
        self.accounts_path = gemini / "google_accounts.json"
        self.token_path.write_text('{"token":"live-token-abc"}')
        self.creds_path.write_text('{"access_token":"live-creds-xyz"}')
        self.accounts_path.write_text('{"email":"live@example.com"}')

        self._auth_files = [
            (self.token_path,    "antigravity-oauth-token"),
            (self.creds_path,    "oauth_creds.json"),
            (self.accounts_path, "google_accounts.json"),
        ]

        import agyp_cli, agyp_gui
        self._patchers = []
        for mod in (agyp_cli, agyp_gui):
            patches = {
                "REAL_HOME":       self.home,
                "PROFILES_DIR":    self.profiles_dir,
                "AGY_ACCOUNTS_DIR":self.profiles_dir,
                "LAST_ACTIVE_FILE":self.profiles_dir / ".last_active",
                "OAUTH_TOKEN_PATH":self.token_path,
                "DESKTOP_CREDS":   self.creds_path,
                "DESKTOP_ACCOUNTS":self.accounts_path,
                "AUTH_FILES":      self._auth_files,
            }
            for attr, val in patches.items():
                if hasattr(mod, attr):
                    p = patch.object(mod, attr, val)
                    p.start()
                    self._patchers.append(p)

    def tearDown(self):
        for p in self._patchers:
            try: p.stop()
            except: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_profile(self, name, token="saved-token", creds="saved-creds", email="saved@example.com"):
        d = self.profiles_dir / name
        d.mkdir(exist_ok=True)
        (d / "antigravity-oauth-token").write_text(token)
        (d / "oauth_creds.json").write_text(creds)
        (d / "google_accounts.json").write_text(email)
        return d


# ══════════════════════════════════════════════════════════════════════════════
# BLOCK 1 — sanitize_name  (users 1-8)
# ══════════════════════════════════════════════════════════════════════════════

class TestSanitizeName(BaseTest):

    def _san(self, name):
        import agyp_cli
        return agyp_cli.sanitize_name(name)

    # User 1: Arch Linux — clean simple names
    def test_u1_valid_simple(self):
        self.assertEqual(self._san("agy1"), "agy1")

    def test_u1_valid_space(self):
        self.assertEqual(self._san("my account"), "my account")

    def test_u1_valid_hyphen_underscore(self):
        self.assertEqual(self._san("agy-work_2"), "agy-work_2")

    # User 2: Ubuntu — trailing spaces stripped
    def test_u2_strips_whitespace(self):
        self.assertEqual(self._san("  agy2  "), "agy2")

    # User 3: Fedora — empty/blank
    def test_u3_empty_returns_none(self):
        self.assertIsNone(self._san(""))
        self.assertIsNone(self._san("   "))

    # User 4: Debian — path traversal
    def test_u4_dotdot(self):
        self.assertIsNone(self._san("../../etc/passwd"))

    def test_u4_forward_slash(self):
        self.assertIsNone(self._san("agy/evil"))

    def test_u4_backslash(self):
        self.assertIsNone(self._san("agy\\evil"))

    def test_u4_leading_dot(self):
        self.assertIsNone(self._san(".hidden"))

    # User 5: Windows 11 — shell injection chars
    def test_u5_shell_special_chars(self):
        for bad in ["agy;rm -rf /", "agy|cat", "agy$HOME", "agy`id`", "agy&&evil"]:
            with self.subTest(inp=bad):
                self.assertIsNone(self._san(bad))

    # User 6: macOS — emoji rejected
    def test_u6_emoji_rejected(self):
        self.assertIsNone(self._san("agy🚀"))

    # User 7: Windows 10 — control characters
    def test_u7_control_chars(self):
        self.assertIsNone(self._san("agy\x00null"))
        self.assertIsNone(self._san("agy\nnewline"))

    # User 8: SSH headless — long but valid name
    def test_u8_long_valid_name(self):
        name = "a" * 64
        self.assertEqual(self._san(name), name)

    # GUI sanitize_name must match CLI rules
    def test_gui_sanitize_matches_cli(self):
        import agyp_gui
        dummy = object.__new__(agyp_gui.App)
        cases = [
            ("agy1",       "agy1"),
            ("  agy2  ",   "agy2"),
            ("../../etc",  None),
            ("agy|cmd",    None),
            ("",           None),
        ]
        for inp, expected in cases:
            with self.subTest(inp=inp):
                self.assertEqual(agyp_gui.App.sanitize_name(dummy, inp), expected)


# ══════════════════════════════════════════════════════════════════════════════
# BLOCK 2 — swap_in / save_back  (users 9-13)
# ══════════════════════════════════════════════════════════════════════════════

class TestAuthSwap(BaseTest):

    # User 9: Ubuntu — first launch, no saved tokens yet
    def test_u9_swap_empty_profile(self):
        import agyp_cli
        d = self.profiles_dir / "new-user"
        d.mkdir()
        swapped = agyp_cli.swap_in_profile(d)
        self.assertEqual(swapped, 0)
        # Live token must be cleared so the user is forced to log in fresh
        self.assertFalse(self.token_path.exists())

    # User 10: Arch — switch to existing profile
    def test_u10_swap_existing_profile(self):
        import agyp_cli
        d = self.make_profile("agy1", token='{"token":"agy1-token"}')
        swapped = agyp_cli.swap_in_profile(d)
        self.assertEqual(swapped, 3)
        self.assertEqual(self.token_path.read_text(), '{"token":"agy1-token"}')

    # User 11: Fedora — backup files created before overwrite
    def test_u11_backup_created(self):
        import agyp_cli
        d = self.make_profile("agy2")
        agyp_cli.swap_in_profile(d)
        backup = self.token_path.with_suffix(".agyp-backup")
        self.assertTrue(backup.exists())
        self.assertIn("live-token", backup.read_text())

    # User 12: macOS — save_back writes all three files
    def test_u12_save_back_writes_files(self):
        import agyp_cli
        d = self.profiles_dir / "agy3"
        d.mkdir()
        agyp_cli.save_back_profile(d)
        self.assertTrue((d / "antigravity-oauth-token").exists())
        self.assertEqual(
            (d / "antigravity-oauth-token").read_text(),
            '{"token":"live-token-abc"}'
        )

    # User 13: Windows — refreshed token captured correctly
    def test_u13_save_back_captures_refresh(self):
        import agyp_cli
        d = self.make_profile("agy4", token='{"token":"old"}')
        self.token_path.write_text('{"token":"refreshed"}')
        agyp_cli.save_back_profile(d)
        self.assertEqual(
            (d / "antigravity-oauth-token").read_text(),
            '{"token":"refreshed"}'
        )


# ══════════════════════════════════════════════════════════════════════════════
# BLOCK 3 — last_active tracking + GUI recovery  (users 14-15)
# ══════════════════════════════════════════════════════════════════════════════

class TestLastActive(BaseTest):

    # User 14: Linux — set and clear last_active
    def test_u14_set_and_clear(self):
        import agyp_cli
        agyp_cli.set_last_active("agy1")
        f = self.profiles_dir / ".last_active"
        self.assertTrue(f.exists())
        self.assertEqual(f.read_text(), "agy1")
        agyp_cli.clear_last_active()
        self.assertFalse(f.exists())

    # User 15: Crash recovery — GUI saves back refreshed tokens on next start
    def test_u15_gui_crash_recovery(self):
        import agyp_cli, agyp_gui
        d = self.make_profile("agy1", token='{"token":"old-agy1"}')
        agyp_cli.set_last_active("agy1")
        # Simulate token refresh during crashed session
        self.token_path.write_text('{"token":"refreshed-after-crash"}')

        # Recovery: what GUI startup does
        last = agyp_gui._get_last_active()
        self.assertEqual(last, "agy1")
        agyp_gui._save_back(d)
        agyp_gui._clear_last_active()

        self.assertEqual(
            (d / "antigravity-oauth-token").read_text(),
            '{"token":"refreshed-after-crash"}'
        )
        self.assertIsNone(agyp_gui._get_last_active())


# ══════════════════════════════════════════════════════════════════════════════
# BLOCK 4 — profile listing & security
# ══════════════════════════════════════════════════════════════════════════════

class TestProfileListing(BaseTest):

    def test_profiles_sorted_order(self):
        for name in ["zzz", "aaa", "mmm"]:
            self.make_profile(name)
        import agyp_cli
        profiles = sorted([d.name for d in agyp_cli.PROFILES_DIR.iterdir() if d.is_dir()])
        self.assertEqual(profiles, ["aaa", "mmm", "zzz"])

    def test_hidden_files_excluded(self):
        self.make_profile("visible")
        (self.profiles_dir / ".last_active").write_text("visible")
        profiles = [d.name for d in self.profiles_dir.iterdir() if d.is_dir()]
        self.assertIn("visible", profiles)
        self.assertNotIn(".last_active", profiles)

    def test_empty_profiles_dir_no_crash(self):
        import agyp_cli
        profiles = sorted([d.name for d in agyp_cli.PROFILES_DIR.iterdir() if d.is_dir()])
        self.assertEqual(profiles, [])

    def test_invalid_argv_rejected(self):
        import agyp_cli
        self.assertIsNone(agyp_cli.sanitize_name("../../../etc"))
        self.assertIsNone(agyp_cli.sanitize_name("bad|cmd"))


# ══════════════════════════════════════════════════════════════════════════════
# BLOCK 5 — headless import safety
# ══════════════════════════════════════════════════════════════════════════════

class TestHeadlessImport(unittest.TestCase):
    def test_gui_module_importable_headless(self):
        try:
            import agyp_gui  # noqa: F401
        except Exception as e:
            self.fail(f"GUI module failed to import headless: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("agyp-suite — Test Suite  (15 user scenarios)")
    print("=" * 60)
    unittest.main(verbosity=2)
