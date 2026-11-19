import contextlib as Contextlib
import io as Io
import json as Json
import tempfile as Tempfile
import unittest as Unittest
from pathlib import Path

import bowlstats as BowlStats
import main as Main


def StatisticalVault():
    Vault = Main.NewVault()
    SharedPassword = "Fake-Good-Password-123!"
    Vault["entries"] = {
        "Fake Moon One": {
            "username": "moon-one",
            "password": SharedPassword,
            "notes": "demo one",
        },
        "Fake Moon Two": {
            "username": "moon-two",
            "password": SharedPassword,
            "notes": "demo two",
        },
        "Fake Weak Thing": {
            "username": "weak-user",
            "password": "zzweakzz",
            "notes": "",
        },
        "Fake Empty Thing": {
            "username": "",
            "password": "",
            "notes": "",
        },
    }
    return Vault


#MARK: tiny histogram stuffs
class StatisticsHelperTests(Unittest.TestCase):
    def testEveryLengthBoundaryLandsInTheExpectedBucket(self):
        Expected = {
            0: "EMPTY",
            1: "1-7",
            7: "1-7",
            8: "8-11",
            11: "8-11",
            12: "12-19",
            19: "12-19",
            20: "20-31",
            31: "20-31",
            32: "32+",
            9000: "32+",
        }
        for Length, Label in Expected.items():
            with self.subTest(length=Length):
                self.assertEqual(BowlStats.LengthBucket(Length), Label)

    def testTinyBarHandlesEmptyAndFullBuckets(self):
        self.assertEqual(BowlStats.TinyBar(0, 0, Width=5), ".....")
        self.assertEqual(BowlStats.TinyBar(5, 5, Width=5), "#####")
        self.assertEqual(BowlStats.TinyBar(2, 4, Width=6), "###...")


#MARK: real bowl counting stuffs
class BowlStatisticsTests(Unittest.TestCase):
    def MakeReport(self, Directory):
        FilePath = Path(Directory) / ".stats.p00p"
        Main.SaveVault(FilePath, StatisticalVault())
        return Main.BowlStatisticsReport(FilePath)

    def testCountsHealthReuseAndOptionalFields(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Report = self.MakeReport(Directory)

            self.assertEqual(Report.EntryCount, 4)
            self.assertEqual(Report.WithUsernames, 3)
            self.assertEqual(Report.WithNotes, 2)
            self.assertEqual(Report.HealthyEntries, 2)
            self.assertEqual(Report.EntriesNeedingAttention, 2)
            self.assertEqual(Report.ReusedGroups, 1)
            self.assertEqual(Report.ReusedEntries, 2)
            self.assertEqual(Report.LengthCounts["EMPTY"], 1)
            self.assertEqual(Report.LengthCounts["8-11"], 1)
            self.assertEqual(Report.LengthCounts["20-31"], 2)

    def testStorageNumbersComeFromTheRealEnvelope(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Report = self.MakeReport(Directory)

            self.assertGreater(Report.FileBytes, Report.PayloadBytes)
            self.assertGreater(Report.RawJsonBytes, Report.PayloadBytes)
            self.assertGreater(Report.CompressionRatio, 1)
            self.assertGreater(Report.BytesPerEntry, 0)

    def testReportsNeverContainNamesUsernamesPasswordsOrNotes(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Report = self.MakeReport(Directory)
            Text = Report.AsText() + Report.AsJson()

            for Name, Entry in StatisticalVault()["entries"].items():
                self.assertNotIn(Name, Text)
                for Field in ("username", "password", "notes"):
                    Value = Entry[Field]
                    if Value:
                        self.assertNotIn(Value, Text)

    def testJsonHasStableMachineReadableSections(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Payload = Json.loads(self.MakeReport(Directory).AsJson())

            self.assertEqual(Payload["protocol"], "p00p-bowl-statistics")
            self.assertEqual(Payload["entries"]["total"], 4)
            self.assertEqual(Payload["entries"]["reused_groups"], 1)
            self.assertIn("password_length_buckets", Payload)
            self.assertIn("storage", Payload)


#MARK: stats command stuffs
class StatisticsCommandTests(Unittest.TestCase):
    def RunCli(self, *Arguments):
        Output = Io.StringIO()
        Errors = Io.StringIO()
        with Contextlib.redirect_stdout(Output), Contextlib.redirect_stderr(Errors):
            Result = Main.RunApp(Arguments)
        return Result, Output.getvalue(), Errors.getvalue()

    def testStatsCommandPrintsHistogramWithoutSecrets(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".cli-stats.p00p"
            Main.SaveVault(FilePath, StatisticalVault())

            Result, Output, Error = self.RunCli(
                "stats", "--vault", str(FilePath)
            )

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertIn("PASSWORD LENGTH BUCKETS", Output)
            self.assertIn("compression ratio", Output)
            self.assertNotIn("Fake-Good-Password-123!", Output)

    def testCountAliasCanEmitJson(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".json-stats.p00p"
            Main.SaveVault(FilePath, StatisticalVault())

            Result, Output, _ = self.RunCli(
                "count", "--json", "--vault", str(FilePath)
            )
            Payload = Json.loads(Output)

            self.assertEqual(Result, 0)
            self.assertEqual(Payload["entries"]["total"], 4)


if __name__ == "__main__":
    Unittest.main()
