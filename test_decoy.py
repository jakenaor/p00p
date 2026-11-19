import contextlib as Contextlib
import io as Io
import json as Json
import tempfile as Tempfile
import unittest as Unittest
from pathlib import Path

import decoy as Decoy
import main as Main


FIXED_TIME = "2030-04-05T06:07:08+00:00"


def EmptyVault():
    return {
        "protocol": "p00p",
        "created_at": FIXED_TIME,
        "updated_at": FIXED_TIME,
        "entries": {},
    }


#MARK: fake credential assembly line stuffs
class DecoyFactoryTests(Unittest.TestCase):
    def testSeededFoundryMakesTheExactSameBatchTwice(self):
        Left = Decoy.PopulateVault(
            EmptyVault(), 25, lambda: FIXED_TIME, Seed="sewer moon 7"
        )
        Right = Decoy.PopulateVault(
            EmptyVault(), 25, lambda: FIXED_TIME, Seed="sewer moon 7"
        )

        self.assertEqual(Left, Right)

    def testDifferentSeedsActuallyChangeTheDecoys(self):
        Left = Decoy.PopulateVault(EmptyVault(), 8, lambda: FIXED_TIME, Seed="left")
        Right = Decoy.PopulateVault(EmptyVault(), 8, lambda: FIXED_TIME, Seed="right")

        self.assertNotEqual(Left["entries"], Right["entries"])

    def testLargeBatchKeepsEveryNameUnique(self):
        Vault = Decoy.PopulateVault(
            EmptyVault(), 200, lambda: FIXED_TIME, Seed="crowded fake bowl"
        )
        Names = tuple(Vault["entries"])

        self.assertEqual(len(Names), 200)
        self.assertEqual(len({Name.casefold() for Name in Names}), 200)

    def testEverythingIsLoudlyFakeButPassesBasicPasswordChecks(self):
        Vault = Decoy.PopulateVault(
            EmptyVault(), 40, lambda: FIXED_TIME, Seed="fake means fake"
        )

        for Name, Entry in Vault["entries"].items():
            with self.subTest(name=Name):
                self.assertIn("DEMO", Name)
                self.assertTrue(Entry["username"].endswith("@demo.invalid"))
                self.assertTrue(Entry["password"].startswith("FAKE-"))
                self.assertIn("DEMO ONLY", Entry["notes"])
                self.assertIn("DOES NOT UNLOCK", Entry["notes"])
                self.assertEqual(Main.PasswordIssues(Entry["password"]), [])

    def testCountGuardStopsAccidentalFiveMillionEntryBowl(self):
        for BadCount in (0, -1, Decoy.MAX_DECOY_COUNT + 1, "potato"):
            with self.subTest(count=BadCount):
                with self.assertRaises(Decoy.DecoyError):
                    Decoy.DecoyRecipe(BadCount)

    def testFoundryRefusesToMixDecoysIntoExistingEntries(self):
        Vault = EmptyVault()
        Vault["entries"]["keep me"] = {"password": "fake"}

        with self.assertRaisesRegex(Decoy.DecoyError, "brand-new empty"):
            Decoy.PopulateVault(Vault, 2, lambda: FIXED_TIME, Seed="no mixing")

    def testReceiptContainsStatsButNoGeneratedCredentialValues(self):
        Vault = Decoy.PopulateVault(
            EmptyVault(), 3, lambda: FIXED_TIME, Seed="receipt"
        )
        Receipt = Decoy.DecoyReceipt(".demo.p00p", 3, True)
        Text = Receipt.AsText() + Receipt.AsJson()

        self.assertIn("EXTREMELY FAKE", Text)
        self.assertNotIn(next(iter(Vault["entries"])), Text)
        self.assertNotIn(next(iter(Vault["entries"].values()))["password"], Text)


#MARK: terminal foundry stuffs
class DecoyCommandTests(Unittest.TestCase):
    def RunCli(self, *Arguments):
        Output = Io.StringIO()
        Errors = Io.StringIO()
        with Contextlib.redirect_stdout(Output), Contextlib.redirect_stderr(Errors):
            Result = Main.RunApp(Arguments)
        return Result, Output.getvalue(), Errors.getvalue()

    def testDecoyCommandMakesAValidOwnerOnlyVault(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".showcase.p00p"

            Result, Output, Error = self.RunCli(
                "decoy", "--count", "17", "--seed", "screenshot one",
                "--vault", str(FilePath),
            )
            Vault = Main.LoadVault(FilePath)

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertIn("17", Output)
            self.assertEqual(len(Vault["entries"]), 17)
            self.assertEqual(FilePath.stat().st_mode & 0o777, 0o600)

    def testDemoAliasCanEmitAJsonReceipt(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".json-demo.poop"

            Result, Output, _ = self.RunCli(
                "demo", "--count", "4", "--json", "--vault", str(FilePath)
            )
            Payload = Json.loads(Output)

            self.assertEqual(Result, 0)
            self.assertEqual(Payload["protocol"], "p00p-decoy-foundry")
            self.assertEqual(Payload["entries"], 4)
            self.assertFalse(Payload["contains_real_credentials"])

    def testExistingVaultSurvivesWithoutForce(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".occupied.p00p"
            Original = Main.NewVault()
            Original["entries"]["survivor"] = {
                "username": "keep",
                "password": "Fake-Survivor-Password-123!",
                "notes": "keep",
            }
            Main.SaveVault(FilePath, Original)
            Before = FilePath.read_bytes()

            Result, _, Error = self.RunCli(
                "decoy", "--count", "2", "--vault", str(FilePath)
            )

            self.assertEqual(Result, 1)
            self.assertIn("already exists", Error)
            self.assertEqual(FilePath.read_bytes(), Before)

    def testForceExplicitlyReplacesAnExistingVault(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".replace-me.p00p"
            Main.SaveVault(FilePath, Main.NewVault())

            Result, _, Error = self.RunCli(
                "decoy", "--count", "6", "--seed", "replacement", "--force",
                "--vault", str(FilePath),
            )

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertEqual(len(Main.LoadVault(FilePath)["entries"]), 6)


if __name__ == "__main__":
    Unittest.main()
