"""Regression tests for the portable (PyInstaller) release helpers."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


class TestPaths(unittest.TestCase):
    def test_source_mode(self):
        sys.path.insert(0, str(ROOT))
        from src.utils.paths import app_base, is_frozen, resource_path

        self.assertFalse(is_frozen())
        self.assertEqual(app_base(), ROOT)
        self.assertTrue((resource_path("bin") / "WinDivert.dll").exists())
        self.assertTrue(resource_path("logo netlimiter.png").exists())

    def test_frozen_mode(self):
        sys.path.insert(0, str(ROOT))
        from src.utils.paths import app_base, is_frozen, resource_path

        exe = ROOT / "dist" / "MiniLimiter" / "MiniLimiter.exe"
        meipass = exe.parent / "_internal"
        with mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "_MEIPASS", str(meipass), create=True), \
             mock.patch.object(sys, "executable", str(exe)):
            self.assertTrue(is_frozen())
            self.assertEqual(app_base(), exe.parent)
            self.assertEqual(resource_path("bin", "WinDivert.dll"),
                             meipass / "bin" / "WinDivert.dll")


class TestFrozenElevation(unittest.TestCase):
    def _patched_shell(self, ret):
        sys.path.insert(0, str(ROOT))
        import src.utils.elevation as elev

        exe = ROOT / "dist" / "MiniLimiter" / "MiniLimiter.exe"
        windll = mock.MagicMock()
        windll.shell32.ShellExecuteW.return_value = ret
        return elev, windll, exe

    def test_relaunches_exe_not_python(self):
        elev, windll, exe = self._patched_shell(42)
        exited = False
        with mock.patch.object(elev.ctypes, "windll", windll), \
             mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "_MEIPASS", str(exe.parent / "_internal"), create=True), \
             mock.patch.object(sys, "executable", str(exe)), \
             mock.patch.object(sys, "argv", [str(exe), "--no-elevate"]), \
             mock.patch.object(elev, "is_admin", return_value=False):
            try:
                elev.elevate_and_restart()
            except SystemExit:
                exited = True
        args = windll.shell32.ShellExecuteW.call_args.args
        self.assertEqual(args[2], str(exe))
        self.assertEqual(args[3], "")  # internal flag must not be forwarded
        self.assertEqual(args[4], str(exe.parent))
        self.assertTrue(exited)

    def test_uac_declined_keeps_running(self):
        elev, windll, exe = self._patched_shell(0)
        with mock.patch.object(elev.ctypes, "windll", windll), \
             mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "_MEIPASS", str(exe.parent / "_internal"), create=True), \
             mock.patch.object(sys, "executable", str(exe)), \
             mock.patch.object(sys, "argv", [str(exe)]), \
             mock.patch.object(elev, "is_admin", return_value=False):
            self.assertIsNone(elev.elevate_and_restart())


class TestSingleInstance(unittest.TestCase):
    def test_duplicate_launch_is_blocked(self):
        sys.path.insert(0, str(ROOT))
        from src.utils import single_instance as si

        unique_name = r"Local\MiniLimiter_Test_" + os.urandom(4).hex()
        with mock.patch.object(si, "MUTEX_NAME", unique_name):
            si.release()
            self.assertTrue(si.acquire())
            self.assertFalse(si.acquire())
            si.release()
            self.assertTrue(si.acquire())  # released mutex can be re-acquired
            si.release()


class TestBuildAssets(unittest.TestCase):
    def test_required_assets_present(self):
        for rel in ("logo netlimiter.png", "MiniLimiter.ico",
                    "bin/WinDivert.dll", "bin/WinDivert64.sys",
                    "build_portable.py", "requirements-build.txt",
                    ".github/workflows/release.yml"):
            self.assertTrue((ROOT / rel).exists(), f"missing build asset: {rel}")


if __name__ == "__main__":
    unittest.main()
