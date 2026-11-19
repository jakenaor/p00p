import contextlib as Contextlib
import copy as Copy
import io as Io
import json as Json
import tempfile as Tempfile
import unittest as Unittest
from pathlib import Path

import main as Main
import merge as Merge


FIXED_TIME = "2030-04-05T06:07:08+00:00"


def Entry(Username, Password, Notes=""):
    return {
        "username": Username,
        "password": Password,
        "notes": Notes,
        "updated_at": FIXED_TIME,
    }


def Vault(**Entries):
    return {
        "protocol": "p00p",
        "created_at": FIXED_TIME,
        "updated_at": FIXED_TIME,
        "entries": Entries,
    }


#MARK: bowl pouring engine stuffs
class MergeEngineTests(Unittest.TestCase):
    def RunMerge(self, Left, Right, Policy=Merge.POLICY_ERROR):
        return Merge.MergeVaults(Left, Right, Policy, lambda: FIXED_TIME)

    def testDifferentNamesPourTogetherWithoutConflict(self):
        Left = Vault(left=Entry("l", "Fake-Left-Password-123!"))
        Right = Vault(right=Entry("r", "Fake-Right-Password-456!"))

        Plan, Combined = self.RunMerge(Left, Right)

        self.assertEqual(set(Combined["entries"]), {"left", "right"})
        self.assertEqual(Plan.Added, 1)
        self.assertEqual(Plan.Conflicts, 0)
        self.assertEqual(Plan.Identical, 0)

    def testIdenticalDuplicateIgnoresTimestampDifference(self):
        LeftEntry = Entry("same", "Fake-Same-Password-123!", "same")
        RightEntry = Copy.deepcopy(LeftEntry)
        RightEntry["updated_at"] = "2099-01-01T00:00:00+00:00"

        Plan, Combined = self.RunMerge(
            Vault(Account=LeftEntry),
            Vault(account=RightEntry),
        )

        self.assertEqual(tuple(Combined["entries"]), ("Account",))
        self.assertEqual(Plan.Identical, 1)
        self.assertEqual(Plan.Conflicts, 0)

    def testDefaultPolicyStopsOnRealConflict(self):
        Left = Vault(bank=Entry("left", "Fake-Left-Password-123!"))
        Right = Vault(BANK=Entry("right", "Fake-Right-Password-456!"))

        with self.assertRaisesRegex(Merge.MergeError, "1 conflicting"):
            self.RunMerge(Left, Right)

    def testKeepLeftPreservesOriginalCredential(self):
        LeftEntry = Entry("left", "Fake-Left-Password-123!")
        RightEntry = Entry("right", "Fake-Right-Password-456!")

        Plan, Combined = self.RunMerge(
            Vault(bank=LeftEntry),
            Vault(BANK=RightEntry),
            Merge.POLICY_KEEP_LEFT,
        )

        self.assertEqual(Combined["entries"]["bank"], LeftEntry)
        self.assertEqual(Plan.KeptLeft, 1)
        self.assertEqual(Plan.Conflicts, 1)

    def testKeepRightReplacesSpellingAndCredential(self):
        LeftEntry = Entry("left", "Fake-Left-Password-123!")
        RightEntry = Entry("right", "Fake-Right-Password-456!")

        Plan, Combined = self.RunMerge(
            Vault(bank=LeftEntry),
            Vault(BANK=RightEntry),
            Merge.POLICY_KEEP_RIGHT,
        )

        self.assertNotIn("bank", Combined["entries"])
        self.assertEqual(Combined["entries"]["BANK"], RightEntry)
        self.assertEqual(Plan.KeptRight, 1)

    def testRenameRightKeepsBothAndAvoidsAnotherCollision(self):
        Left = Vault(
            bank=Entry("left", "Fake-Left-Password-123!"),
            **{
                "BANK (RIGHT COPY)": Entry("old-copy", "Fake-Old-Copy-789!"),
            },
        )
        RightEntry = Entry("right", "Fake-Right-Password-456!")

        Plan, Combined = self.RunMerge(
            Left,
            Vault(BANK=RightEntry),
            Merge.POLICY_RENAME_RIGHT,
        )

        self.assertEqual(len(Combined["entries"]), 3)
        self.assertEqual(
            Combined["entries"]["BANK (RIGHT COPY 2)"],
            RightEntry,
        )
        self.assertEqual(Plan.RenamedRight, 1)

    def testInputsAreNotMutatedByMerge(self):
        Left = Vault(left=Entry("l", "Fake-Left-Password-123!"))
        Right = Vault(right=Entry("r", "Fake-Right-Password-456!"))
        BeforeLeft = Copy.deepcopy(Left)
        BeforeRight = Copy.deepcopy(Right)

        self.RunMerge(Left, Right)

        self.assertEqual(Left, BeforeLeft)
        self.assertEqual(Right, BeforeRight)

    def testReceiptContainsCountsButNoCredentials(self):
        Left = Vault(left=Entry("unique-left-user", "Fake-Left-Password-123!"))
        Right = Vault(right=Entry("unique-right-user", "Fake-Right-Password-456!"))
        Plan, _Combined = self.RunMerge(Left, Right)

        Receipt = Plan.Receipt("left.p00p", "right.p00p", "merged.p00p")
        Text = Receipt.AsText() + Receipt.AsJson()
        Payload = Json.loads(Receipt.AsJson())

        self.assertEqual(Payload["counts"]["final_entries"], 2)
        self.assertNotIn("unique-left-user", Text)
        self.assertNotIn("Fake-Right-Password-456!", Text)


#MARK: real file merge stuffs
class MergeCommandTests(Unittest.TestCase):
    def RunCli(self, *Arguments):
        Output = Io.StringIO()
        Errors = Io.StringIO()
        with Contextlib.redirect_stdout(Output), Contextlib.redirect_stderr(Errors):
            Result = Main.RunApp(Arguments)
        return Result, Output.getvalue(), Errors.getvalue()

    def SaveInputs(self, Directory, Conflict=False):
        LeftPath = Path(Directory) / ".left.p00p"
        RightPath = Path(Directory) / ".right.p00p"
        Left = Main.NewVault()
        Left["entries"]["left"] = Entry("left-user", "Fake-Left-Password-123!")
        Right = Main.NewVault()
        RightName = "LEFT" if Conflict else "right"
        Right["entries"][RightName] = Entry("right-user", "Fake-Right-Password-456!")
        Main.SaveVault(LeftPath, Left)
        Main.SaveVault(RightPath, Right)
        return LeftPath, RightPath

    def testCommandCreatesLoadableOwnerOnlyThirdVault(self):
        with Tempfile.TemporaryDirectory() as Directory:
            LeftPath, RightPath = self.SaveInputs(Directory)
            OutputPath = Path(Directory) / ".combined.p00p"

            Result, Output, Error = self.RunCli(
                "merge", str(RightPath), "--output", str(OutputPath),
                "--vault", str(LeftPath),
            )

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertIn("MERGE COMPLETE", Output)
            self.assertEqual(set(Main.LoadVault(OutputPath)["entries"]), {"left", "right"})
            self.assertEqual(OutputPath.stat().st_mode & 0o777, 0o600)

    def testConflictStopsBeforeOutputExists(self):
        with Tempfile.TemporaryDirectory() as Directory:
            LeftPath, RightPath = self.SaveInputs(Directory, Conflict=True)
            OutputPath = Path(Directory) / ".never-made.p00p"

            Result, _, Error = self.RunCli(
                "merge", str(RightPath), "--output", str(OutputPath),
                "--vault", str(LeftPath),
            )

            self.assertEqual(Result, 1)
            self.assertIn("conflicting entry", Error)
            self.assertFalse(OutputPath.exists())

    def testRenamePolicyKeepsBothConflictingEntries(self):
        with Tempfile.TemporaryDirectory() as Directory:
            LeftPath, RightPath = self.SaveInputs(Directory, Conflict=True)
            OutputPath = Path(Directory) / ".renamed.p00p"

            Result, Output, Error = self.RunCli(
                "combine", str(RightPath), "--output", str(OutputPath),
                "--conflict", "rename-right", "--json", "--vault", str(LeftPath),
            )
            Payload = Json.loads(Output)
            Entries = Main.LoadVault(OutputPath)["entries"]

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertEqual(len(Entries), 2)
            self.assertIn("LEFT (RIGHT COPY)", Entries)
            self.assertEqual(Payload["counts"]["renamed_right"], 1)

    def testExistingOutputSurvivesWithoutForce(self):
        with Tempfile.TemporaryDirectory() as Directory:
            LeftPath, RightPath = self.SaveInputs(Directory)
            OutputPath = Path(Directory) / ".occupied.p00p"
            OutputPath.write_bytes(b"keep this exact thing")

            Result, _, Error = self.RunCli(
                "merge", str(RightPath), "--output", str(OutputPath),
                "--vault", str(LeftPath),
            )

            self.assertEqual(Result, 1)
            self.assertIn("already exists", Error)
            self.assertEqual(OutputPath.read_bytes(), b"keep this exact thing")

    def testOutputCannotPointAtEitherInputEvenWithForce(self):
        with Tempfile.TemporaryDirectory() as Directory:
            LeftPath, RightPath = self.SaveInputs(Directory)
            BeforeLeft = LeftPath.read_bytes()
            BeforeRight = RightPath.read_bytes()

            LeftResult, _, LeftError = self.RunCli(
                "merge", str(RightPath), "--output", str(LeftPath), "--force",
                "--vault", str(LeftPath),
            )
            RightResult, _, RightError = self.RunCli(
                "merge", str(RightPath), "--output", str(RightPath), "--force",
                "--vault", str(LeftPath),
            )

            self.assertEqual(LeftResult, 1)
            self.assertEqual(RightResult, 1)
            self.assertIn("left input", LeftError)
            self.assertIn("right input", RightError)
            self.assertEqual(LeftPath.read_bytes(), BeforeLeft)
            self.assertEqual(RightPath.read_bytes(), BeforeRight)

    def testBrokenRightInputDoesNotCreateOutput(self):
        with Tempfile.TemporaryDirectory() as Directory:
            LeftPath, _RightPath = self.SaveInputs(Directory)
            BrokenPath = Path(Directory) / ".broken.p00p"
            BrokenPath.write_bytes(b"not a bowl")
            OutputPath = Path(Directory) / ".output.p00p"

            Result, _, Error = self.RunCli(
                "merge", str(BrokenPath), "--output", str(OutputPath),
                "--vault", str(LeftPath),
            )

            self.assertEqual(Result, 1)
            self.assertIn("not a valid", Error)
            self.assertFalse(OutputPath.exists())


if __name__ == "__main__":
    Unittest.main()
