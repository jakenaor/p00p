import contextlib as Contextlib
import io as Io
import os as Os
import tempfile as Tempfile
import unittest as Unittest
from pathlib import Path

import main as Main


def TheatricalVault():
    Vault = Main.NewVault()
    Vault["entries"]["Extremely Fake Bank"] = {
        "username": "fake-bank-user",
        "password": "Excellent-Fake-Password-123!",
        "notes": "this string should disappear from the raw file",
        "updated_at": Main.CurrentTime(),
    }
    return Vault


#MARK: applause meter stuffs
class TheaterTests(Unittest.TestCase):
    def testHiddenOwnerOnlyBowlGetsMaximumTheaterPoints(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".dramatic.p00p"
            Main.SaveVault(FilePath, TheatricalVault())

            Report = Main.SecurityTheaterReport(FilePath)

            self.assertEqual(Report.Score, 100)
            self.assertEqual(Report.Possible, 100)
            self.assertEqual(Report.Rating(), "maximum security theater")

    def testReportNeverPrintsTheCredentialStrings(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".secret.poop"
            Vault = TheatricalVault()
            Main.SaveVault(FilePath, Vault)

            Text = Main.SecurityTheaterReport(FilePath).AsText()

            self.assertNotIn("fake-bank-user", Text)
            self.assertNotIn("Excellent-Fake-Password-123!", Text)
            self.assertNotIn("this string should disappear", Text)
            self.assertIn("not a security score", Text)

    def testVisibleWrongExtensionAndLoosePermissionsLosePoints(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / "obvious-passwords.txt"
            Main.SaveVault(FilePath, TheatricalVault())
            Os.chmod(FilePath, 0o644)

            Report = Main.SecurityTheaterReport(FilePath)
            FailedNames = {Result.Name for Result in Report.Results if not Result.Passed}

            self.assertEqual(Report.Score, 55)
            self.assertIn("dotfile invisibility cloak", FailedNames)
            self.assertIn("wrong-extension mustache", FailedNames)
            self.assertIn("owner-only bathroom lock", FailedNames)

    def testCliPrintsTheSameJokeWarning(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".cli.p00p"
            Main.SaveVault(FilePath, TheatricalVault())
            Output = Io.StringIO()

            with Contextlib.redirect_stdout(Output):
                Result = Main.RunApp(("theater", "--vault", str(FilePath)))

            self.assertEqual(Result, 0)
            self.assertIn("SECURITY THEATER: 100/100", Output.getvalue())
            self.assertIn("only use fake passwords", Output.getvalue())


if __name__ == "__main__":
    Unittest.main()
