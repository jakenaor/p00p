import contextlib as Contextlib
import copy as Copy
import io as Io
import json as Json
import tempfile as Tempfile
import unittest as Unittest
from pathlib import Path

import compare as Compare
import main as Main


def ComparisonVault():
    Vault = Main.NewVault()
    Vault["entries"] = {
        "Fake Bank": {
            "username": "fake-banker",
            "password": "Fake-Bank-Password-123!",
            "notes": "fake money only",
            "updated_at": Main.CurrentTime(),
        },
        "Moon Base": {
            "username": "moon-worker",
            "password": "Fake-Moon-Password-456!",
            "notes": "bring cheese",
            "updated_at": Main.CurrentTime(),
        },
        "Unchanged Thing": {
            "username": "same-person",
            "password": "Fake-Unchanged-Password-789!",
            "notes": "same notes",
            "updated_at": Main.CurrentTime(),
        },
    }
    return Vault


def DeltaByStatus(Difference, Status):
    return [Delta for Delta in Difference.Deltas if Delta.Status == Status]


#MARK: comparison engine stuffs
class ComparisonTests(Unittest.TestCase):
    def testDifferentlySaltedFilesWithSameContentsCompareIdentically(self):
        Left = ComparisonVault()
        Right = Copy.deepcopy(Left)

        Difference = Compare.CompareVaults(Left, Right)

        self.assertTrue(Difference.Identical)
        self.assertEqual(len(Difference.UnchangedNames), 3)
        self.assertIn("decoded credential contents are identical", Difference.AsText())

    def testAddedRemovedChangedAndRenamedAreSeparated(self):
        Left = ComparisonVault()
        Right = Copy.deepcopy(Left)
        Right["entries"]["Fake Bank"]["password"] = "Different-Fake-Password-321!"
        Right["entries"]["Fake Bank"]["notes"] = "changed fake money"
        Right["entries"]["Cheese Station"] = Right["entries"].pop("Moon Base")
        del Right["entries"]["Unchanged Thing"]
        Right["entries"]["New Fake Login"] = {
            "username": "new-person",
            "password": "Fake-New-Password-654!",
            "notes": "new notes",
        }

        Difference = Compare.CompareVaults(Left, Right)

        self.assertEqual(Difference.Count("changed"), 1)
        self.assertEqual(Difference.Count("renamed"), 1)
        self.assertEqual(Difference.Count("removed"), 1)
        self.assertEqual(Difference.Count("added"), 1)
        Changed = DeltaByStatus(Difference, "changed")[0]
        self.assertEqual(Changed.Name, "Fake Bank")
        self.assertEqual(Changed.Fields, ("password", "notes"))
        Renamed = DeltaByStatus(Difference, "renamed")[0]
        self.assertEqual((Renamed.OldName, Renamed.NewName), ("Moon Base", "Cheese Station"))

    def testTimestampOnlyChangesDoNotPretendCredentialsChanged(self):
        Left = ComparisonVault()
        Right = Copy.deepcopy(Left)
        Right["entries"]["Fake Bank"]["updated_at"] = "2099-01-01T00:00:00+00:00"
        Right["updated_at"] = "2099-01-01T00:00:00+00:00"

        Difference = Compare.CompareVaults(Left, Right)

        self.assertTrue(Difference.Identical)

    def testDuplicateContentRenamePairingIsDeterministic(self):
        Entry = {
            "username": "clone",
            "password": "Fake-Clone-Password-852!",
            "notes": "same",
        }
        Left = Main.NewVault()
        Left["entries"] = {"A": Copy.deepcopy(Entry), "B": Copy.deepcopy(Entry)}
        Right = Main.NewVault()
        Right["entries"] = {"C": Copy.deepcopy(Entry), "D": Copy.deepcopy(Entry)}

        Difference = Compare.CompareVaults(Left, Right)
        Pairs = [(Delta.OldName, Delta.NewName) for Delta in Difference.Deltas]

        self.assertEqual(Pairs, [("A", "C"), ("B", "D")])

    def testTextReportNeverPrintsChangedValues(self):
        Left = ComparisonVault()
        Right = Copy.deepcopy(Left)
        Secret = "Brand-New-Fake-Password-963!"
        Right["entries"]["Fake Bank"]["password"] = Secret
        Right["entries"]["Fake Bank"]["username"] = "new-secret-username"

        Text = Compare.CompareVaults(Left, Right).AsText()

        self.assertIn("username, password", Text)
        self.assertNotIn(Secret, Text)
        self.assertNotIn("new-secret-username", Text)
        self.assertNotIn("Fake-Bank-Password-123!", Text)

    def testAnonymousReportAlsoHidesEntryNames(self):
        Left = ComparisonVault()
        Right = Copy.deepcopy(Left)
        Right["entries"]["Fake Bank"]["notes"] = "changed"

        Text = Compare.CompareVaults(Left, Right).AsText(Anonymous=True)
        Payload = Json.loads(
            Compare.CompareVaults(Left, Right).AsJson(Anonymous=True)
        )

        self.assertNotIn("Fake Bank", Text)
        self.assertEqual(Payload["deltas"][0], {
            "fields": ["notes"],
            "status": "changed",
        })

    def testCanonicalFingerprintIgnoresDictionaryInsertionOrder(self):
        Left = {"username": "a", "password": "b", "notes": "c"}
        Right = {"notes": "c", "password": "b", "username": "a"}

        self.assertEqual(Compare.EntryFingerprint(Left), Compare.EntryFingerprint(Right))


#MARK: CLI comparison stuffs
class ComparisonCommandTests(Unittest.TestCase):
    def RunCli(self, *Arguments):
        Output = Io.StringIO()
        Errors = Io.StringIO()
        with Contextlib.redirect_stdout(Output), Contextlib.redirect_stderr(Errors):
            Result = Main.RunApp(Arguments)
        return Result, Output.getvalue(), Errors.getvalue()

    def testDiffCommandComparesTwoRealVaultFiles(self):
        with Tempfile.TemporaryDirectory() as Directory:
            LeftPath = Path(Directory) / ".left.p00p"
            RightPath = Path(Directory) / ".right.p00p"
            Left = ComparisonVault()
            Right = Copy.deepcopy(Left)
            Right["entries"]["Fake Bank"]["password"] = "Different-Fake-Password-741!"
            Main.SaveVault(LeftPath, Left)
            Main.SaveVault(RightPath, Right)

            Result, Output, Error = self.RunCli(
                "diff", str(RightPath), "--vault", str(LeftPath)
            )

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertIn("1 changed", Output)
            self.assertIn("password", Output)
            self.assertNotIn("Different-Fake-Password-741!", Output)

    def testCompareAliasSupportsAnonymousJson(self):
        with Tempfile.TemporaryDirectory() as Directory:
            LeftPath = Path(Directory) / ".left.p00p"
            RightPath = Path(Directory) / ".right.p00p"
            Left = ComparisonVault()
            Right = Copy.deepcopy(Left)
            Right["entries"]["Fake Bank"]["notes"] = "something else"
            Main.SaveVault(LeftPath, Left)
            Main.SaveVault(RightPath, Right)

            Result, Output, _ = self.RunCli(
                "compare",
                str(RightPath),
                "--anonymous",
                "--json",
                "--vault",
                str(LeftPath),
            )
            Payload = Json.loads(Output)

            self.assertEqual(Result, 0)
            self.assertTrue(Payload["anonymous"])
            self.assertEqual(Payload["summary"]["changed"], 1)
            self.assertNotIn("Fake Bank", Output)


if __name__ == "__main__":
    Unittest.main()
