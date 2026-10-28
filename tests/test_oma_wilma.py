import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from oma_wilma import bridge, config, models
from oma_wilma.report import format_exams

FAKE = str(Path(__file__).with_name("fake_wilma.py"))
NO_KEYCHAIN = lambda service, account: None  # noqa: E731


class ConfigTest(unittest.TestCase):
    def test_empty_without_tenant_and_username(self):
        self.assertEqual(config.cli_env({}, Path("/nonexistent"), NO_KEYCHAIN), {})

    def test_precedence_environ_then_dotenv_then_keychain(self):
        with tempfile.TemporaryDirectory() as d:
            dotenv = Path(d, ".env")
            dotenv.write_text('WILMA_TENANT="https://a.inschool.fi"\nWILMA_USERNAME=u\nWILMA_PASSWORD=from-file\n# kommentti\n')
            kc = lambda s, a: {"password": "from-kc", "totp-secret": "KCSECRET"}.get(a)  # noqa: E731
            env = config.cli_env({"WILMA_USERNAME": "env-user"}, dotenv, kc)
            self.assertEqual(env, {
                "WILMA_TENANT": "https://a.inschool.fi", "WILMA_USERNAME": "env-user",
                "WILMA_PASSWORD": "from-file", "WILMA_TOTP_SECRET": "KCSECRET",
            })
            env = config.cli_env({"WILMA_PASSWORD": "from-env"}, dotenv, kc)
            self.assertEqual(env["WILMA_PASSWORD"], "from-env")


class BridgeTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"WILMA_BIN": FAKE, "WILMA_PASSWORD": "pw", "WILMA_TENANT": "https://a.inschool.fi", "WILMA_USERNAME": "u"})
        patcher.start()
        self.addCleanup(patcher.stop)
        kc = mock.patch.object(config, "read_keychain", NO_KEYCHAIN)
        kc.start()
        self.addCleanup(kc.stop)
        mock.patch("oma_wilma.bridge.cli_env", lambda: config.cli_env(os.environ, Path("/nonexistent"), NO_KEYCHAIN)).start()
        self.addCleanup(mock.patch.stopall)

    def test_exams_sorted_and_parsed(self):
        exams = models.upcoming_exams("Kiia", 5)
        self.assertEqual([e.date for e in exams], ["2026-10-29", "2026-10-30"])
        self.assertEqual(exams[0].time, "08:30")
        self.assertIsNone(exams[1].time)
        self.assertEqual(exams[0].student.name, "Kiia Virtanen")

    def test_arguments_and_credentials_reach_cli(self):
        data = bridge.run(["exams", "--limit", "5", "--student", "Kiia"])
        self.assertEqual(data["argv"], ["exams", "--limit", "5", "--student", "Kiia", "--json"])
        self.assertEqual(data["password"], "pw")

    def test_error_becomes_exception(self):
        with mock.patch.dict(os.environ, {"FAKE_FAIL": "not_logged_in"}):
            with self.assertRaises(bridge.NotLoggedIn) as cm:
                models.students()
        self.assertEqual(cm.exception.exit_code, 3)

    def test_raw_passthrough(self):
        self.assertEqual(bridge.run(["schedule", "week"], json_output=False).strip(), "raakateksti schedule week")

    def test_missing_binary(self):
        with mock.patch.dict(os.environ, {"WILMA_BIN": "/nonexistent/wilma"}):
            with self.assertRaises(bridge.WilmaError):
                bridge.run(["students"])


class MiscTest(unittest.TestCase):
    def test_version_warning(self):
        self.assertIsNone(bridge.version_warning("2.3.0"))
        self.assertIn("pääversiolle", bridge.version_warning("3.0.0"))
        self.assertIn("npm install", bridge.version_warning(None))

    def test_format_exams(self):
        s = models.Student("1", "Kiia Virtanen")
        out = format_exams([models.Exam(s, "2026-10-29", "08:30", "Englanti", "Unit test", "Units 7-9", "Ek"), models.Exam(s, "2026-10-30", None, "Matikka", "Koe", None, None)])
        self.assertEqual(out, "Kiia Virtanen\n  2026-10-29 08:30  Englanti – Units 7-9 (Ek)\n  2026-10-30  Matikka")
        self.assertEqual(format_exams([]), "(ei tulevia kokeita)")


if __name__ == "__main__":
    unittest.main()
