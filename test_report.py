import contextlib as Contextlib
import io as Io
import json as Json
import tempfile as Tempfile
import unittest as Unittest
from pathlib import Path
from unittest import mock as Mock

import main as Main
import report as ReportModule


def ReportVault():
    Vault = Main.NewVault()
    Vault["entries"] = {
        "Private Fake Moon Account": {
            "username": "unique-moon-reporter",
            "password": "Fake-Report-Password-753!",
            "notes": "unique notes that must stay out of the report",
            "updated_at": Main.CurrentTime(),
        },
        "Private Fake Sewer Account": {
            "username": "unique-sewer-reporter",
            "password": "Fake-Sewer-Password-951!",
            "notes": "another unique note that stays hidden",
            "updated_at": Main.CurrentTime(),
        },
    }
    return Vault


def ForbiddenValues(Vault):
    Values = []
    for Name, Entry in Vault["entries"].items():
        Values.append(Name)
        Values.extend(Entry[Field] for Field in ("username", "password", "notes"))
    return tuple(Value for Value in Values if Value)


#MARK: safe report rendering stuffs
class SubmissionRenderingTests(Unittest.TestCase):
    def MakeReport(self, Directory):
        FilePath = Path(Directory) / ".submission.p00p"
        Vault = ReportVault()
        Main.SaveVault(FilePath, Vault)
        return Main.SubmissionReportForVault(FilePath), Vault

    def testEveryFormatLeavesCredentialValuesOut(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Report, Vault = self.MakeReport(Directory)
            Rendered = (Report.AsText(), Report.AsMarkdown(), Report.AsJson())

            for FormatText in Rendered:
                for Value in ForbiddenValues(Vault):
                    self.assertNotIn(Value, FormatText)

    def testJsonCombinesAllFiveReportSections(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Report, _Vault = self.MakeReport(Directory)
            Payload = Json.loads(Report.AsJson())

            self.assertEqual(Payload["protocol"], "p00p-submission-report")
            self.assertEqual(Payload["project_version"], Main.PROJECT_VERSION)
            self.assertIn("anatomy", Payload)
            self.assertIn("doctor", Payload)
            self.assertIn("statistics", Payload)
            self.assertIn("security_theater", Payload)
            self.assertIn("storage_lab", Payload)
            self.assertEqual(Payload["statistics"]["entries"]["total"], 2)
            self.assertEqual(Payload["security_theater"]["possible"], 100)
            self.assertEqual(Payload["storage_lab"]["rounds"], Main.SUBMISSION_LAB_ROUNDS)
            self.assertTrue(Payload["storage_lab"]["passed"])

    def testMarkdownHasUsefulSubmissionTablesAndWarnings(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Report, _Vault = self.MakeReport(Directory)
            Text = Report.AsMarkdown()

            self.assertIn("# P00P vault report", Text)
            self.assertIn("## Binary anatomy", Text)
            self.assertIn("## Vault doctor", Text)
            self.assertIn("## Security theater", Text)
            self.assertIn("## Weird storage lab", Text)
            self.assertIn("| entries | 2 |", Text)
            self.assertIn("camouflage, **not encryption**", Text)
            self.assertTrue(Text.endswith("\n"))

    def testTextVersionIsCompactButStillHonest(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Report, _Vault = self.MakeReport(Directory)
            Text = Report.AsText()

            self.assertIn("P00P SUBMISSION REPORT", Text)
            self.assertIn("BOWL NUMBERS", Text)
            self.assertIn("DOCTOR", Text)
            self.assertIn("SECURITY THEATER", Text)
            self.assertIn("WEIRD STORAGE LAB", Text)
            self.assertIn("contains no credential values", Text)

    def testMarkdownCellEscapesTableBreakers(self):
        self.assertEqual(
            ReportModule.MarkdownCell("left|right\nnext"),
            "left\\|right next",
        )


#MARK: report file writer stuffs
class ReportWriterTests(Unittest.TestCase):
    def testWriterMakesOwnerOnlyFileAndAddsFinalNewline(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / "report.md"

            Written = ReportModule.WriteReport(FilePath, "hello report")

            self.assertEqual(Written, FilePath)
            self.assertEqual(FilePath.read_text(encoding="utf-8"), "hello report\n")
            self.assertEqual(FilePath.stat().st_mode & 0o777, 0o600)

    def testExistingReportSurvivesWithoutForce(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / "report.md"
            FilePath.write_text("keep this\n", encoding="utf-8")

            with self.assertRaisesRegex(ReportModule.ReportError, "already exists"):
                ReportModule.WriteReport(FilePath, "replacement")

            self.assertEqual(FilePath.read_text(encoding="utf-8"), "keep this\n")

    def testForceAtomicallyReplacesExistingReport(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / "report.json"
            FilePath.write_text("old\n", encoding="utf-8")

            ReportModule.WriteReport(FilePath, "new", Force=True)

            self.assertEqual(FilePath.read_text(encoding="utf-8"), "new\n")
            self.assertEqual(FilePath.stat().st_mode & 0o777, 0o600)

    def testFailedAtomicLinkLeavesNoHalfReportBehind(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / "report.md"

            with Mock.patch.object(
                ReportModule.Os,
                "link",
                side_effect=OSError("fake filesystem tantrum"),
            ):
                with self.assertRaisesRegex(ReportModule.ReportError, "could not write"):
                    ReportModule.WriteReport(FilePath, "never lands")

            self.assertEqual(tuple(Path(Directory).iterdir()), ())


#MARK: report command stuffs
class ReportCommandTests(Unittest.TestCase):
    def RunCli(self, *Arguments):
        Output = Io.StringIO()
        Errors = Io.StringIO()
        with Contextlib.redirect_stdout(Output), Contextlib.redirect_stderr(Errors):
            Result = Main.RunApp(Arguments)
        return Result, Output.getvalue(), Errors.getvalue()

    def MakeVault(self, Directory):
        FilePath = Path(Directory) / ".report-cli.p00p"
        Main.SaveVault(FilePath, ReportVault())
        return FilePath

    def testReportDefaultsToMarkdownOnStdout(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)

            Result, Output, Error = self.RunCli(
                "report", "--vault", str(VaultPath)
            )

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertIn("# P00P vault report", Output)
            self.assertNotIn("Fake-Report-Password-753!", Output)

    def testCommandWritesJsonReportInsteadOfPrintingIt(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            ReportPath = Path(Directory) / "submission.json"

            Result, Output, Error = self.RunCli(
                "report", "--format", "json", "--output", str(ReportPath),
                "--vault", str(VaultPath),
            )
            Payload = Json.loads(ReportPath.read_text(encoding="utf-8"))

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertIn("wrote secret-safe json report", Output)
            self.assertEqual(Payload["protocol"], "p00p-submission-report")
            self.assertEqual(ReportPath.stat().st_mode & 0o777, 0o600)

    def testCommandRefusesToReplaceReportWithoutForce(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            ReportPath = Path(Directory) / "keep.md"
            ReportPath.write_text("hand written\n", encoding="utf-8")

            Result, _, Error = self.RunCli(
                "report", "--output", str(ReportPath), "--vault", str(VaultPath)
            )

            self.assertEqual(Result, 1)
            self.assertIn("already exists", Error)
            self.assertEqual(ReportPath.read_text(encoding="utf-8"), "hand written\n")

    def testForceExplicitlyReplacesOldReport(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            ReportPath = Path(Directory) / "replace.txt"
            ReportPath.write_text("old\n", encoding="utf-8")

            Result, _, Error = self.RunCli(
                "report", "--format", "text", "--output", str(ReportPath),
                "--force", "--vault", str(VaultPath),
            )

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertIn("P00P SUBMISSION REPORT", ReportPath.read_text(encoding="utf-8"))


if __name__ == "__main__":
    Unittest.main()
