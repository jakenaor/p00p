import contextlib as Contextlib
import io as Io
import json as Json
import tempfile as Tempfile
import unittest as Unittest
from pathlib import Path
from unittest import mock as Mock

import lifeboat as Lifeboat
import main as Main
import reroll as Reroll


def SoupVault():
    Vault = Main.NewVault()
    Vault["entries"]["Fake Soup Login"] = {
        "username": "soup-goblin",
        "password": "Fake-Soup-Password-357!",
        "notes": "stir clockwise for more security theater",
        "updated_at": Main.CurrentTime(),
    }
    return Vault


#MARK: salt dice stuffs
class RerollUnitTests(Unittest.TestCase):
    def testFreshSaltRefusesTheOldValueThenAcceptsANewOne(self):
        Old = b"o" * 16
        Rolls = iter((Old, b"n" * 16))

        New = Reroll.FreshSalt(Old, 16, RandomBytes=lambda _Size: next(Rolls))

        self.assertEqual(New, b"n" * 16)

    def testBrokenSaltGoblinGetsAUsefulError(self):
        with self.assertRaisesRegex(Reroll.RerollError, "other than 16 bytes"):
            Reroll.FreshSalt(b"o" * 16, 16, RandomBytes=lambda _Size: b"tiny")

    def testEightIdenticalRollsDoNotLoopForever(self):
        Old = b"s" * 16

        with self.assertRaisesRegex(Reroll.RerollError, "eight times"):
            Reroll.FreshSalt(Old, 16, RandomBytes=lambda _Size: Old)


#MARK: real bowl reroll stuffs
class RerollStorageTests(Unittest.TestCase):
    def testRerollChangesEnvelopeButNotDecodedVault(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".soup.p00p"
            Vault = SoupVault()
            Main.SaveVault(FilePath, Vault)
            BeforeBlob = FilePath.read_bytes()
            BeforeVault = Main.LoadVault(FilePath)
            BeforeHeader = Main.ParseHeader(BeforeBlob)

            Receipt = Main.RerollVault(FilePath)
            AfterBlob = FilePath.read_bytes()
            AfterHeader = Main.ParseHeader(AfterBlob)

            self.assertNotEqual(AfterBlob, BeforeBlob)
            self.assertNotEqual(AfterHeader["salt"], BeforeHeader["salt"])
            self.assertEqual(Main.LoadVault(FilePath), BeforeVault)
            self.assertTrue(Receipt.Changed)
            self.assertEqual(FilePath.stat().st_mode & 0o777, 0o600)

    def testRerollReceiptContainsNoCredentialValues(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".receipt.p00p"
            Main.SaveVault(FilePath, SoupVault())

            Receipt = Main.RerollVault(FilePath)
            Text = Receipt.AsText() + Receipt.AsJson()

            self.assertNotIn("Fake Soup Login", Text)
            self.assertNotIn("soup-goblin", Text)
            self.assertNotIn("Fake-Soup-Password-357!", Text)
            self.assertIn("still not encryption", Text)

    def testFailedAtomicDockLeavesOriginalBytesUntouched(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".unsinkable.p00p"
            Main.SaveVault(FilePath, SoupVault())
            Before = FilePath.read_bytes()

            with Mock.patch.object(
                Lifeboat.AtomicDock,
                "Install",
                side_effect=Lifeboat.LifeboatError("dock fell over"),
            ):
                with self.assertRaisesRegex(Lifeboat.LifeboatError, "dock fell over"):
                    Main.RerollVault(FilePath)

            self.assertEqual(FilePath.read_bytes(), Before)


#MARK: terminal soup stuffs
class RerollCommandTests(Unittest.TestCase):
    def RunCli(self, *Arguments):
        Output = Io.StringIO()
        Errors = Io.StringIO()
        with Contextlib.redirect_stdout(Output), Contextlib.redirect_stderr(Errors):
            Result = Main.RunApp(Arguments)
        return Result, Output.getvalue(), Errors.getvalue()

    def testRerollCommandPrintsHumanReceipt(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".cli.p00p"
            Main.SaveVault(FilePath, SoupVault())

            Result, Output, Error = self.RunCli(
                "reroll", "--vault", str(FilePath)
            )

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertIn("CAMOUFLAGE REROLLED", Output)
            self.assertIn("decoded data:  unchanged", Output)

    def testRepackAliasCanPrintJson(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".json.p00p"
            Main.SaveVault(FilePath, SoupVault())

            Result, Output, _ = self.RunCli(
                "repack", "--json", "--vault", str(FilePath)
            )
            Payload = Json.loads(Output)

            self.assertEqual(Result, 0)
            self.assertTrue(Payload["changed"])
            self.assertNotEqual(Payload["before"]["salt"], Payload["after"]["salt"])
            self.assertEqual(Payload["entries"], 1)


if __name__ == "__main__":
    Unittest.main()
