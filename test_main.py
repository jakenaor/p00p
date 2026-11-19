import contextlib as Contextlib
import io as Io
import string as String
import tempfile as Tempfile
import unittest as Unittest
from types import SimpleNamespace
from unittest import mock as Mock
from pathlib import Path

import main as Main


#MARK: file format stuffs
class FormatTests(Unittest.TestCase):
    def testRoundTrip(self):
        Vault = Main.NewVault()
        Vault["entries"]["example.com"] = {
            "username": "fake-user",
            "password": "fake-password",
            "notes": "demo only",
        }

        Encoded = Main.EncodeVault(Vault, Salt=b"0" * Main.SALT_SIZE)
        Decoded = Main.DecodeVault(Encoded)

        self.assertEqual(Decoded, Vault)
        self.assertNotIn(b"fake-password", Encoded)
        self.assertNotIn(b"example.com", Encoded)

    def testCorruptionIsDetected(self):
        Encoded = bytearray(Main.EncodeVault(Main.NewVault()))
        Encoded[-Main.DIGEST_SIZE - 1] ^= 1

        with self.assertRaisesRegex(Main.P00PError, "integrity check failed"):
            Main.DecodeVault(bytes(Encoded))

    def testInvalidFileIsRejected(self):
        with self.assertRaisesRegex(Main.P00PError, "not a valid"):
            Main.DecodeVault(b"definitely not p00p")

    def testHeaderCanBeInspected(self):
        Encoded = Main.EncodeVault(Main.NewVault(), Salt=b"s" * Main.SALT_SIZE)
        Header = Main.ParseHeader(Encoded)

        self.assertEqual(Header["version"], Main.VERSION)
        self.assertEqual(Header["salt"], b"s" * Main.SALT_SIZE)
        self.assertEqual(Header["file_size"], len(Encoded))
        self.assertEqual(
            Header["header_size"] + Header["payload_size"] + Main.DIGEST_SIZE,
            len(Encoded),
        )

    def testMalformedEntryIsRejected(self):
        Vault = Main.NewVault()
        Vault["entries"]["broken"] = {"password": 12345}

        with self.assertRaisesRegex(Main.P00PError, "invalid password"):
            Main.EncodeVault(Vault)


#MARK: password stuffs
class PasswordTests(Unittest.TestCase):
    def testTheWholeCommonPasswordWallLoaded(self):
        self.assertEqual(len(Main.COMMON_PASSWORDS), 10_000)
        self.assertIn("password", Main.COMMON_PASSWORDS)

    def testCommonPasswordLoaderCleansUpTheList(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / "bad-ideas.txt"
            FilePath.write_text(" Password \nPASSWORD\n\nQwErTy\n", encoding="utf-8")

            Loaded = Main.LoadCommonPasswords(FilePath)

        self.assertEqual(Loaded, frozenset({"password", "qwerty"}))

    def testMissingCommonPasswordWallDoesNotBrickTheApp(self):
        Missing = Path("definitely-not-a-real-common-password-file.txt")

        self.assertEqual(Main.LoadCommonPasswords(Missing), frozenset())

    def testCommonPasswordCheckIgnoresCase(self):
        Issues = Main.PasswordIssues("PASSWORD")

        self.assertTrue(any("common-password" in Issue for Issue in Issues))

    def testGeneratedPasswordHasAllTheStuffs(self):
        Password = Main.GeneratePassword(40)

        self.assertEqual(len(Password), 40)
        self.assertTrue(any(Character.islower() for Character in Password))
        self.assertTrue(any(Character.isupper() for Character in Password))
        self.assertTrue(any(Character.isdigit() for Character in Password))
        self.assertTrue(any(Character in Main.PASSWORD_SYMBOLS for Character in Password))

    def testGeneratedPasswordCanSkipSymbols(self):
        Password = Main.GeneratePassword(32, Symbols=False)
        AllowedCharacters = String.ascii_letters + String.digits

        self.assertTrue(all(Character in AllowedCharacters for Character in Password))

    def testGeneratedPasswordLengthIsLimited(self):
        with self.assertRaisesRegex(Main.P00PError, "between"):
            Main.GeneratePassword(Main.MIN_PASSWORD_LENGTH - 1)
        with self.assertRaisesRegex(Main.P00PError, "between"):
            Main.GeneratePassword(Main.MAX_PASSWORD_LENGTH + 1)

    def testAuditFindsBadPasswordStuffs(self):
        Issues = Main.PasswordIssues("password")

        self.assertTrue(any("common-password" in Issue for Issue in Issues))
        self.assertTrue(any("shorter" in Issue for Issue in Issues))
        self.assertTrue(any("no uppercase" in Issue for Issue in Issues))


#MARK: saving stuffs
class StorageTests(Unittest.TestCase):
    def testSaveAndLoad(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".test.p00p"
            Vault = Main.NewVault()
            Main.SaveVault(FilePath, Vault)

            self.assertEqual(Main.LoadVault(FilePath)["entries"], {})
            self.assertEqual(FilePath.stat().st_mode & 0o777, 0o600)


#MARK: command stuffs
class CommandTests(Unittest.TestCase):
    def RunCli(self, *Arguments):
        Output = Io.StringIO()
        Errors = Io.StringIO()
        with Contextlib.redirect_stdout(Output), Contextlib.redirect_stderr(Errors):
            Result = Main.RunApp(Arguments)
        return Result, Output.getvalue(), Errors.getvalue()

    def testExpandedWorkflow(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".workflow.p00p"
            VaultArgument = ("--vault", str(FilePath))

            self.assertEqual(self.RunCli("init", *VaultArgument)[0], 0)
            Result, GeneratedOutput, _ = self.RunCli(
                "add", "Example", "--username", "demo-user",
                "--notes", "space service", "--generate", "20", *VaultArgument,
            )
            self.assertEqual(Result, 0)
            self.assertIn("generated password:", GeneratedOutput)
            Password = Main.LoadVault(FilePath)["entries"]["Example"]["password"]
            self.assertEqual(len(Password), 20)

            Result, SearchOutput, _ = self.RunCli("search", "SPACE", *VaultArgument)
            self.assertEqual(Result, 0)
            self.assertIn("Example\tdemo-user", SearchOutput)

            Result, _, _ = self.RunCli("rename", "example", "Moon Base", *VaultArgument)
            self.assertEqual(Result, 0)
            self.assertIn("Moon Base", Main.LoadVault(FilePath)["entries"])

            Result, AuditOutput, _ = self.RunCli("audit", *VaultArgument)
            self.assertEqual(Result, 0)
            Password = Main.LoadVault(FilePath)["entries"]["Moon Base"]["password"]
            self.assertNotIn(Password, AuditOutput)

            Result, AnatomyOutput, _ = self.RunCli("anatomy", *VaultArgument)
            self.assertEqual(Result, 0)
            self.assertIn("integrity check passed", AnatomyOutput)

    def testNoSymbolsRequiresGeneration(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".test.p00p"
            self.RunCli("init", "--vault", str(FilePath))

            Result, _, Error = self.RunCli(
                "add", "Example", "--password", "not-a-secret", "--no-symbols",
                "--vault", str(FilePath),
            )

            self.assertEqual(Result, 1)
            self.assertIn("requires --generate", Error)

    def testGuiCommandUsesTheNormalVaultArgument(self):
        Args = Main.BuildParser().parse_args(("gui", "--vault", ".test.poop"))

        self.assertIs(Args.handler, Main.CommandGui)
        self.assertEqual(Args.vault, Path(".test.poop"))

    def testTkVersionsAreParsedWithoutExploding(self):
        self.assertEqual(Main.ParseTkVersion("8.6"), (8, 6))
        self.assertEqual(Main.ParseTkVersion("9.0.1"), (9, 0))
        self.assertEqual(Main.ParseTkVersion("uh oh"), (0, 0))

    def testGuiCandidatesIncludeTheOfficialMacPythonInstaller(self):
        Candidates = tuple(Main.GuiPythonCandidates())

        self.assertEqual(
            Candidates[0],
            Path(Main.__file__).resolve().parent / ".venv" / "bin" / "python",
        )
        self.assertIn(
            Path("/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"),
            Candidates,
        )

    def testOldMacTkGetsAUsefulInstallMessage(self):
        Args = SimpleNamespace(vault=Path(".test.p00p"))
        with Mock.patch.object(Main.Sys, "platform", "darwin"), \
             Mock.patch.object(Main, "CurrentTkVersion", return_value=(8, 5)), \
             Mock.patch.object(Main, "FindCompatibleGuiPython", return_value=None):
            with self.assertRaisesRegex(Main.P00PError, "requirements.txt"):
                Main.CommandGui(Args)

    def testOldMacTkHandsOffToANewerPython(self):
        Args = SimpleNamespace(vault=Path(".test.p00p"))
        BetterPython = Path("/opt/homebrew/bin/python3.13")
        with Mock.patch.object(Main.Sys, "platform", "darwin"), \
             Mock.patch.object(Main, "CurrentTkVersion", return_value=(8, 5)), \
             Mock.patch.object(Main, "FindCompatibleGuiPython", return_value=BetterPython), \
             Mock.patch.object(Main.Os, "execv") as Exec:
            Main.CommandGui(Args)

        Exec.assert_called_once()
        Arguments = Exec.call_args.args
        self.assertEqual(Arguments[0], str(BetterPython))
        self.assertEqual(Arguments[1][-3:], ("gui", "--vault", ".test.p00p"))


if __name__ == "__main__":
    Unittest.main()
