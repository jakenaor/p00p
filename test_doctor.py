import contextlib as Contextlib
import io as Io
import json as Json
import os as Os
import tempfile as Tempfile
import unittest as Unittest
from datetime import datetime as DateTime, timezone as Timezone
from pathlib import Path

import doctor as Doctor
import main as Main


def HealthyFakeVault():
    Vault = Main.NewVault()
    Vault["entries"]["Fake Lunar Payroll"] = {
        "username": "moon-intern",
        "password": "Entirely-Fake-Moon-Paycheck-482!",
        "notes": "demonstration credentials that do not unlock anything",
        "updated_at": Main.CurrentTime(),
    }
    Vault["entries"]["Fake Martian Weather"] = {
        "username": "dust-reporter",
        "password": "Definitely-Fake-Dust-Storm-951!",
        "notes": "also fake",
        "updated_at": Main.CurrentTime(),
    }
    return Vault


def FindingByCode(Report, Code):
    return next(Finding for Finding in Report.Findings if Finding.Code == Code)


#MARK: full diagnostic report stuffs
class DoctorReportTests(Unittest.TestCase):
    def testHealthyHiddenBowlPassesTheSeriousChecks(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".patient.p00p"
            Main.SaveVault(FilePath, HealthyFakeVault())

            Report = Main.VaultDoctorReport(FilePath)

            self.assertTrue(Report.Healthy)
            self.assertEqual(Report.Count(Doctor.LEVEL_ERROR), 0)
            self.assertEqual(Report.Count(Doctor.LEVEL_WARNING), 0)
            self.assertEqual(len(Report.Findings), 12)
            self.assertEqual(FindingByCode(Report, "format.integrity").Level, "ok")

    def testReportNeverPrintsStoredCredentialValues(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".private.poop"
            Vault = HealthyFakeVault()
            Main.SaveVault(FilePath, Vault)

            Text = Main.VaultDoctorReport(FilePath).AsText()

            for Name, Entry in Vault["entries"].items():
                self.assertNotIn(Name, Text)
                self.assertNotIn(Entry["username"], Text)
                self.assertNotIn(Entry["password"], Text)
                self.assertNotIn(Entry["notes"], Text)
            self.assertIn("not encryption", Text)

    def testVisibleLooseBowlWithWeakReusedPasswordsGetsWarnings(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / "passwords.txt"
            Vault = Main.NewVault()
            Vault["entries"] = {
                "one": {"username": "", "password": "password", "notes": ""},
                "two": {"username": "", "password": "password", "notes": ""},
            }
            Main.SaveVault(FilePath, Vault)
            Os.chmod(FilePath, 0o644)

            Report = Main.VaultDoctorReport(FilePath)

            self.assertFalse(Report.Healthy)
            self.assertEqual(FindingByCode(Report, "file.hidden").Level, "warning")
            self.assertEqual(FindingByCode(Report, "file.extension").Level, "warning")
            Permission = FindingByCode(Report, "file.permissions")
            self.assertEqual(Permission.Level, "warning")
            self.assertTrue(Permission.Repairable)
            self.assertEqual(FindingByCode(Report, "entries.passwords").Level, "warning")
            self.assertEqual(FindingByCode(Report, "entries.reuse").Level, "warning")
            self.assertEqual(FindingByCode(Report, "entries.usernames").Level, "note")

    def testBrokenEntryChronologyIsReportedWithoutItsName(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".timey.p00p"
            Vault = HealthyFakeVault()
            Vault["entries"]["Fake Lunar Payroll"]["updated_at"] = "last thursday-ish"
            Main.SaveVault(FilePath, Vault)

            Finding = FindingByCode(Main.VaultDoctorReport(FilePath), "vault.timestamps")

            self.assertEqual(Finding.Level, "warning")
            self.assertIn("1 entry timestamp", Finding.Detail)
            self.assertNotIn("Fake Lunar Payroll", Finding.Detail)

    def testJsonReportIsStructuredAndStillDoesNotLeakPasswords(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".json.p00p"
            Vault = HealthyFakeVault()
            Main.SaveVault(FilePath, Vault)

            Text = Main.VaultDoctorReport(FilePath).AsJson()
            Payload = Json.loads(Text)

            self.assertEqual(Payload["protocol"], "p00p-doctor")
            self.assertTrue(Payload["healthy"])
            self.assertEqual(len(Payload["findings"]), 12)
            self.assertNotIn("Entirely-Fake-Moon-Paycheck-482!", Text)


#MARK: individual clipboard stuffs
class DoctorUnitTests(Unittest.TestCase):
    def MakeContext(self, FilePath, Vault=None):
        Vault = Vault or HealthyFakeVault()
        Main.SaveVault(FilePath, Vault)
        Blob = Main.ReadVaultBlob(FilePath)
        return Doctor.DoctorContext(
            FilePath=FilePath,
            Blob=Blob,
            Header=Main.ParseHeader(Blob),
            Vault=Main.DecodeVault(Blob),
            PasswordIssueFinder=Main.PasswordIssues,
            ExpectedVersion=Main.VERSION,
            MaximumFileSize=Main.MAX_VAULT_FILE_SIZE,
            Now=DateTime.now(Timezone.utc),
        )

    def testOneFallenCheckDoesNotCancelTheRestOfTheWard(self):
        class FallenCheck(Doctor.DoctorCheck):
            Code = "test.fallen"
            Title = "banana peel inspection"

            def Examine(self, Context):
                raise RuntimeError("secret internal detail")

        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".fallen.p00p"
            Context = self.MakeContext(FilePath)
            Ward = Doctor.DiagnosticWard((
                FallenCheck(),
                Doctor.HiddenFilenameCheck(),
            ))

            Report = Ward.Admit(Context)

            self.assertEqual(len(Report.Findings), 2)
            self.assertEqual(Report.Findings[0].Level, "error")
            self.assertIn("RuntimeError", Report.Findings[0].Detail)
            self.assertNotIn("secret internal detail", Report.Findings[0].Detail)
            self.assertEqual(Report.Findings[1].Level, "ok")

    def testPermissionRepairOnlyChangesTheRequestedFileMode(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".repair.p00p"
            Main.SaveVault(FilePath, HealthyFakeVault())
            Os.chmod(FilePath, 0o666)

            Mode = Doctor.RepairOwnerOnlyPermissions(FilePath)

            self.assertEqual(Mode, 0o600)
            self.assertEqual(Main.LoadVault(FilePath)["entries"], HealthyFakeVault()["entries"])

    def testNaiveTimestampIsAcceptedAsUtcForOldDemoFiles(self):
        Parsed = Doctor.ParseTimestamp("2030-01-02T03:04:05")

        self.assertEqual(Parsed.tzinfo, Timezone.utc)
        self.assertEqual(Parsed.year, 2030)


#MARK: terminal command stuffs
class DoctorCommandTests(Unittest.TestCase):
    def RunCli(self, *Arguments):
        Output = Io.StringIO()
        Errors = Io.StringIO()
        with Contextlib.redirect_stdout(Output), Contextlib.redirect_stderr(Errors):
            Result = Main.RunApp(Arguments)
        return Result, Output.getvalue(), Errors.getvalue()

    def testDoctorCommandPrintsTextReport(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".cli.p00p"
            Main.SaveVault(FilePath, HealthyFakeVault())

            Result, Output, Error = self.RunCli("doctor", "--vault", str(FilePath))

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertIn("P00P VAULT DOCTOR", Output)
            self.assertIn("checksum and decoder pulse", Output)

    def testDoctorCommandCanRepairPermissionsThenEmitJson(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".repair-cli.p00p"
            Main.SaveVault(FilePath, HealthyFakeVault())
            Os.chmod(FilePath, 0o644)

            Result, Output, _ = self.RunCli(
                "doctor", "--json", "--fix-permissions", "--vault", str(FilePath)
            )
            Payload = Json.loads(Output)

            self.assertEqual(Result, 0)
            self.assertEqual(FilePath.stat().st_mode & 0o777, 0o600)
            self.assertEqual(Payload["summary"]["warning"], 0)


if __name__ == "__main__":
    Unittest.main()
