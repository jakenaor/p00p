import contextlib as Contextlib
import io as Io
import json as Json
import os as Os
import tempfile as Tempfile
import unittest as Unittest
from datetime import datetime as DateTime, timezone as Timezone
from pathlib import Path
from unittest import mock as Mock

import lifeboat as Lifeboat
import main as Main


def CargoVault():
    Vault = Main.NewVault()
    Vault["entries"]["Fake Cargo Manifest"] = {
        "username": "deck-goblin",
        "password": "Fake-Lifeboat-Password-846!",
        "notes": "nothing aboard this boat is a real credential",
        "updated_at": Main.CurrentTime(),
    }
    return Vault


#MARK: tiny navigation instruments
class LifeboatNamingTests(Unittest.TestCase):
    def testSnapshotStemRemovesDotAndPoopExtension(self):
        self.assertEqual(Lifeboat.SnapshotStem(".passwords.p00p"), "passwords")
        self.assertEqual(Lifeboat.SnapshotStem(".space bowl.poop"), "space-bowl")
        self.assertEqual(Lifeboat.SnapshotStem(".p00p"), "vault")

    def testSuggestedPathIsHiddenTimestampedAndCollisionProof(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Source = Path(Directory) / ".cargo.p00p"
            Moment = DateTime(2030, 4, 5, 6, 7, 8, tzinfo=Timezone.utc)
            First = Lifeboat.SuggestedSnapshotPath(Source, Now=Moment)
            First.touch()
            Second = Lifeboat.SuggestedSnapshotPath(Source, Now=Moment)

            self.assertEqual(First.name, ".cargo.lifeboat-20300405T060708Z.p00p")
            self.assertEqual(Second.name, ".cargo.lifeboat-20300405T060708Z-2.p00p")


#MARK: atomic dock stuffs
class AtomicDockTests(Unittest.TestCase):
    def testLaunchMakesExactOwnerOnlyLoadableCopy(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Source = Path(Directory) / ".source.p00p"
            Destination = Path(Directory) / ".destination.poop"
            Main.SaveVault(Source, CargoVault())
            Blob = Source.read_bytes()

            Receipt = Lifeboat.Launch(
                Source,
                Destination,
                Blob,
                EntryCount=1,
            )

            self.assertEqual(Destination.read_bytes(), Blob)
            self.assertEqual(Destination.stat().st_mode & 0o777, 0o600)
            self.assertEqual(Main.LoadVault(Destination)["entries"], CargoVault()["entries"])
            self.assertEqual(Receipt.ByteCount, len(Blob))
            self.assertEqual(len(Receipt.Digest), 64)

    def testExistingDestinationIsNotTouchedWithoutForce(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Source = Path(Directory) / ".source.p00p"
            Destination = Path(Directory) / ".occupied.p00p"
            Main.SaveVault(Source, CargoVault())
            Destination.write_bytes(b"do not sink me")

            with self.assertRaisesRegex(Lifeboat.LifeboatError, "already exists"):
                Lifeboat.Launch(Source, Destination, Source.read_bytes(), 1)

            self.assertEqual(Destination.read_bytes(), b"do not sink me")

    def testForceAtomicallyReplacesExistingDestination(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Source = Path(Directory) / ".source.p00p"
            Destination = Path(Directory) / ".occupied.p00p"
            Main.SaveVault(Source, CargoVault())
            Destination.write_bytes(b"old boat")

            Lifeboat.Launch(
                Source,
                Destination,
                Source.read_bytes(),
                EntryCount=1,
                Force=True,
            )

            self.assertEqual(Destination.read_bytes(), Source.read_bytes())
            self.assertEqual(Destination.stat().st_mode & 0o777, 0o600)

    def testSourceCannotBeItsOwnDestination(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Source = Path(Directory) / ".source.p00p"
            Main.SaveVault(Source, CargoVault())

            with self.assertRaisesRegex(Lifeboat.LifeboatError, "same vault"):
                Lifeboat.Launch(Source, Source, Source.read_bytes(), 1, Force=True)

    def testFailedDockCleansTemporaryRowingFile(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Destination = Path(Directory) / ".destination.p00p"
            Dock = Lifeboat.AtomicDock(Destination)

            with Mock.patch.object(Lifeboat.Os, "link", side_effect=OSError("dock broke")):
                with self.assertRaisesRegex(Lifeboat.LifeboatError, "dock snapshot"):
                    Dock.Install(b"fake but valid enough for the dock")

            self.assertEqual(tuple(Path(Directory).iterdir()), ())

    def testReceiptDoesNotContainVaultContents(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Source = Path(Directory) / ".source.p00p"
            Destination = Path(Directory) / ".copy.p00p"
            Main.SaveVault(Source, CargoVault())

            Receipt = Lifeboat.Launch(Source, Destination, Source.read_bytes(), 1)
            Text = Receipt.AsText() + Receipt.AsJson()

            self.assertNotIn("Fake Cargo Manifest", Text)
            self.assertNotIn("deck-goblin", Text)
            self.assertNotIn("Fake-Lifeboat-Password-846!", Text)


#MARK: CLI voyage stuffs
class LifeboatCommandTests(Unittest.TestCase):
    def RunCli(self, *Arguments):
        Output = Io.StringIO()
        Errors = Io.StringIO()
        with Contextlib.redirect_stdout(Output), Contextlib.redirect_stderr(Errors):
            Result = Main.RunApp(Arguments)
        return Result, Output.getvalue(), Errors.getvalue()

    def testBackupCommandAcceptsAnExplicitDestination(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Source = Path(Directory) / ".source.p00p"
            Destination = Path(Directory) / ".backup.p00p"
            Main.SaveVault(Source, CargoVault())

            Result, Output, Error = self.RunCli(
                "backup", str(Destination), "--vault", str(Source)
            )

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertIn("P00P LIFEBOAT LAUNCHED", Output)
            self.assertEqual(Destination.read_bytes(), Source.read_bytes())

    def testBackupAliasCanEmitAJsonReceipt(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Source = Path(Directory) / ".source.p00p"
            Destination = Path(Directory) / ".backup.p00p"
            Main.SaveVault(Source, CargoVault())

            Result, Output, _ = self.RunCli(
                "lifeboat", str(Destination), "--json", "--vault", str(Source)
            )
            Payload = Json.loads(Output)

            self.assertEqual(Result, 0)
            self.assertEqual(Payload["action"], "backup")
            self.assertEqual(Payload["entries"], 1)

    def testRestoreRefusesToOverwriteThenForceRestoresExactBytes(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Snapshot = Path(Directory) / ".snapshot.p00p"
            Target = Path(Directory) / ".target.p00p"
            Main.SaveVault(Snapshot, CargoVault())
            Main.SaveVault(Target, Main.NewVault())
            OriginalSnapshot = Snapshot.read_bytes()

            Result, _, Error = self.RunCli(
                "restore", str(Snapshot), "--vault", str(Target)
            )
            self.assertEqual(Result, 1)
            self.assertIn("already exists", Error)

            Result, Output, Error = self.RunCli(
                "restore", str(Snapshot), "--force", "--vault", str(Target)
            )

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertIn("P00P LIFEBOAT DOCKED", Output)
            self.assertEqual(Target.read_bytes(), OriginalSnapshot)

    def testRestoreValidatesSnapshotBeforeTouchingTarget(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Snapshot = Path(Directory) / ".broken.p00p"
            Target = Path(Directory) / ".target.p00p"
            Snapshot.write_bytes(b"absolutely not a vault")
            Target.write_bytes(b"keep this")

            Result, _, Error = self.RunCli(
                "restore", str(Snapshot), "--force", "--vault", str(Target)
            )

            self.assertEqual(Result, 1)
            self.assertIn("not a valid", Error)
            self.assertEqual(Target.read_bytes(), b"keep this")


if __name__ == "__main__":
    Unittest.main()
