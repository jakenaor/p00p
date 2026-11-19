import contextlib as Contextlib
import copy as Copy
import io as Io
import json as Json
import tempfile as Tempfile
import unittest as Unittest
from pathlib import Path

import ledger as Ledger
import main as Main


TIME_ONE = "2030-04-05T06:07:08+00:00"
TIME_TWO = "2030-04-05T07:08:09+00:00"


def FakeBlob(Number=1):
    return b"P00P pretend binary bowl " + bytes([Number])


def OneRecord():
    return Ledger.NewRecord(
        VaultPath=".fake.p00p",
        Blob=FakeBlob(),
        EntryCount=3,
        Action="checkpoint",
        RecordedAt=TIME_ONE,
    )


class LedgerDocumentTests(Unittest.TestCase):
    def testSuggestedNameStaysBesideAndKeepsVaultSuffix(self):
        self.assertEqual(
            Ledger.SuggestedLedgerPath(Path("/tmp/.moon.poop")),
            Path("/tmp/.moon.poop.ledger.jsonl"),
        )

    def testTwoRecordsRoundTripThroughJsonLines(self):
        Records, First = Ledger.AppendRecord(
            [], ".fake.p00p", FakeBlob(), 3, "checkpoint", TIME_ONE
        )
        Records, Second = Ledger.AppendRecord(
            Records, ".fake.p00p", FakeBlob(2), 4, "submission", TIME_TWO
        )

        Decoded = Ledger.DecodeLedger(Ledger.EncodeLedger(Records))

        self.assertEqual(Decoded, Records)
        self.assertEqual(First["previous_hash"], Ledger.ZERO_HASH)
        self.assertEqual(Second["previous_hash"], First["record_hash"])
        self.assertEqual(Second["sequence"], 2)

    def testAppendingDoesNotMutateOlderRecordsOrCallerList(self):
        Original = [OneRecord()]
        Before = Copy.deepcopy(Original)

        NewRecords, _ = Ledger.AppendRecord(
            Original, ".fake.p00p", FakeBlob(2), 4, "after-demo", TIME_TWO
        )

        self.assertEqual(Original, Before)
        self.assertEqual(len(Original), 1)
        self.assertEqual(len(NewRecords), 2)

    def testChangingOldActionBreaksItsOwnHash(self):
        Records, _ = Ledger.AppendRecord(
            [], ".fake.p00p", FakeBlob(), 3, "checkpoint", TIME_ONE
        )
        Records[0]["action"] = "submission"

        with self.assertRaisesRegex(Ledger.LedgerError, "hash does not match"):
            Ledger.ValidateLedger(Records)

    def testChangingOldHashBreaksNextLink(self):
        Records, _ = Ledger.AppendRecord(
            [], ".fake.p00p", FakeBlob(), 3, "checkpoint", TIME_ONE
        )
        Records, _ = Ledger.AppendRecord(
            Records, ".fake.p00p", FakeBlob(2), 4, "submission", TIME_TWO
        )
        Records[0]["record_hash"] = "a" * 64

        with self.assertRaises(Ledger.LedgerError):
            Ledger.ValidateLedger(Records)

    def testSequenceCannotJumpOrRepeat(self):
        Record = OneRecord()
        Record["sequence"] = 2
        Record["record_hash"] = Ledger.RecordHash(Record)

        with self.assertRaisesRegex(Ledger.LedgerError, "sequence jumped"):
            Ledger.ValidateLedger([Record])

    def testRecordsCannotQuietlySwitchToAnotherVaultName(self):
        Records, _ = Ledger.AppendRecord(
            [], ".fake.p00p", FakeBlob(), 3, "checkpoint", TIME_ONE
        )

        with self.assertRaisesRegex(Ledger.LedgerError, "switched vault names"):
            Ledger.AppendRecord(
                Records, ".other.p00p", FakeBlob(2), 4, "submission", TIME_TWO
            )

    def testUnknownFieldsAndActionsAreRejected(self):
        Extra = OneRecord()
        Extra["secret_comment"] = "not allowed"
        with self.assertRaisesRegex(Ledger.LedgerError, "unknown fields"):
            Ledger.ValidateLedger([Extra])

        with self.assertRaisesRegex(Ledger.LedgerError, "unknown ledger action"):
            Ledger.NewRecord(
                ".fake.p00p", FakeBlob(), 3, "type any secret here", TIME_ONE
            )

    def testEntryCountDoesNotAcceptBooleanOrNonsense(self):
        for BadCount in (True, None, "three", float("inf")):
            with self.subTest(BadCount=BadCount):
                with self.assertRaisesRegex(Ledger.LedgerError, "plain integer"):
                    Ledger.NewRecord(
                        ".fake.p00p", FakeBlob(), BadCount, "checkpoint", TIME_ONE
                    )

    def testBlankBrokenAndOversizedLedgersAreRejected(self):
        Cases = (
            b"",
            b"\n",
            b"not json\n",
            b"x" * (Ledger.MAX_LEDGER_BYTES + 1),
        )
        for Blob in Cases:
            with self.subTest(Size=len(Blob)):
                with self.assertRaises(Ledger.LedgerError):
                    Ledger.DecodeLedger(Blob)

    def testEncodedLedgerNeverContainsSuppliedBowlBytes(self):
        SecretLookingBlob = b"P00P fake binary with Fake-Password-975!"
        Record = Ledger.NewRecord(
            ".fake.p00p", SecretLookingBlob, 1, "checkpoint", TIME_ONE
        )

        Encoded = Ledger.EncodeLedger([Record])

        self.assertNotIn(b"Fake-Password-975!", Encoded)
        self.assertIn(Ledger.VaultHash(SecretLookingBlob).encode(), Encoded)


class LedgerVerificationTests(Unittest.TestCase):
    def MakeVerification(self, CurrentBlob=None, EntryCount=3, VaultPath=".fake.p00p"):
        SealedBlob = FakeBlob()
        Record = Ledger.NewRecord(
            ".fake.p00p", SealedBlob, 3, "checkpoint", TIME_ONE
        )
        return Ledger.VerifyLedger(
            [Record],
            LedgerPath=".fake.p00p.ledger.jsonl",
            VaultPath=VaultPath,
            Blob=SealedBlob if CurrentBlob is None else CurrentBlob,
            EntryCount=EntryCount,
        )

    def testCurrentBowlPassesEveryCheck(self):
        Report = self.MakeVerification()

        self.assertTrue(Report.Passed)
        self.assertTrue(all(Passed for _Name, Passed in Report.Checks))
        self.assertIn("MATCH", Report.Summary())

    def testChangedBytesMakeLedgerStaleWithoutBreakingChain(self):
        Report = self.MakeVerification(CurrentBlob=FakeBlob(9))

        self.assertFalse(Report.Passed)
        self.assertIn("BOWL CHANGED", Report.AsText())
        self.assertIn("STALE", Report.Summary())

    def testRenamedBowlAndEntryCountMismatchAreSeparateChecks(self):
        Report = self.MakeVerification(EntryCount=99, VaultPath=".renamed.p00p")
        Failed = {Name for Name, Passed in Report.Checks if not Passed}

        self.assertEqual(Failed, {"vault filename", "decoded entry count"})

    def testTextAndJsonContainPaperworkButNoCredentialValues(self):
        Report = self.MakeVerification()
        Rendered = Report.AsText() + Report.AsJson()
        Payload = Json.loads(Report.AsJson())

        self.assertNotIn("Fake-Password-975!", Rendered)
        self.assertEqual(Payload["record_count"], 1)
        self.assertEqual(Payload["last_record"]["action"], "checkpoint")
        self.assertIn("not tamperproof", Payload["security_notice"])


#MARK: real bowl paperwork command stuffs
class LedgerCommandTests(Unittest.TestCase):
    def RunCli(self, *Arguments):
        Output = Io.StringIO()
        Errors = Io.StringIO()
        with Contextlib.redirect_stdout(Output), Contextlib.redirect_stderr(Errors):
            Result = Main.RunApp(Arguments)
        return Result, Output.getvalue(), Errors.getvalue()

    def MakeVault(self, Directory):
        VaultPath = Path(Directory) / ".ledger-demo.p00p"
        Vault = Main.NewVault()
        Vault["entries"]["private fake satellite"] = {
            "username": "ledger-secret-user",
            "password": "Fake-Ledger-Password-864!",
            "notes": "must never enter the paperwork",
            "updated_at": Main.CurrentTime(),
        }
        Main.SaveVault(VaultPath, Vault)
        return VaultPath

    def testRecordCreatesOwnerOnlySafeLedgerThenVerifyReadsIt(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            LedgerPath = Ledger.SuggestedLedgerPath(VaultPath)

            RecordResult, RecordOutput, RecordError = self.RunCli(
                "ledger", "--record", "checkpoint", "--json",
                "--vault", str(VaultPath),
            )
            VerifyResult, VerifyOutput, VerifyError = self.RunCli(
                "logbook", "--json", "--vault", str(VaultPath)
            )

            self.assertEqual(RecordResult, 0)
            self.assertEqual(VerifyResult, 0)
            self.assertEqual(RecordError + VerifyError, "")
            self.assertEqual(LedgerPath.stat().st_mode & 0o777, 0o600)
            self.assertEqual(Json.loads(RecordOutput)["record_count"], 1)
            self.assertTrue(Json.loads(VerifyOutput)["passed"])
            Paperwork = LedgerPath.read_text() + RecordOutput + VerifyOutput
            self.assertNotIn("ledger-secret-user", Paperwork)
            self.assertNotIn("Fake-Ledger-Password-864!", Paperwork)

    def testSecondControlledActionExtendsInsteadOfReplacingChain(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            self.RunCli(
                "ledger", "--record", "checkpoint", "--vault", str(VaultPath)
            )

            Result, Output, Error = self.RunCli(
                "ledger", "--record", "submission", "--json",
                "--vault", str(VaultPath),
            )
            Records = Ledger.ReadLedger(Ledger.SuggestedLedgerPath(VaultPath))

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertEqual(len(Records), 2)
            self.assertEqual(Records[-1]["action"], "submission")
            self.assertEqual(Json.loads(Output)["record_count"], 2)

    def testChangedVaultReturnsAttentionExitWithoutDamagingLedger(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            self.RunCli(
                "ledger", "--record", "checkpoint", "--vault", str(VaultPath)
            )
            LedgerPath = Ledger.SuggestedLedgerPath(VaultPath)
            BeforeLedger = LedgerPath.read_bytes()
            Vault = Main.LoadVault(VaultPath)
            Vault["entries"]["private fake satellite"]["notes"] = "changed"
            Main.SaveVault(VaultPath, Vault)

            Result, Output, Error = self.RunCli(
                "ledger", "--json", "--vault", str(VaultPath)
            )

            self.assertEqual(Result, 2)
            self.assertEqual(Error, "")
            self.assertFalse(Json.loads(Output)["passed"])
            self.assertEqual(LedgerPath.read_bytes(), BeforeLedger)

    def testMalformedExistingLedgerIsNeverOverwrittenByRecord(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            LedgerPath = Ledger.SuggestedLedgerPath(VaultPath)
            LedgerPath.write_bytes(b"broken paperwork\n")

            Result, _, Error = self.RunCli(
                "ledger", "--record", "checkpoint", "--vault", str(VaultPath)
            )

            self.assertEqual(Result, 1)
            self.assertIn("not valid JSON", Error)
            self.assertEqual(LedgerPath.read_bytes(), b"broken paperwork\n")

    def testLedgerCannotReplaceVaultAndMissingLedgerIsRegularError(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            Before = VaultPath.read_bytes()

            SameResult, _, SameError = self.RunCli(
                "ledger", "--record", "checkpoint",
                "--ledger-path", str(VaultPath), "--vault", str(VaultPath),
            )
            MissingResult, _, MissingError = self.RunCli(
                "ledger", "--vault", str(VaultPath)
            )

            self.assertEqual(SameResult, 1)
            self.assertIn("cannot replace the vault", SameError)
            self.assertEqual(MissingResult, 1)
            self.assertIn("ledger not found", MissingError)
            self.assertEqual(VaultPath.read_bytes(), Before)


if __name__ == "__main__":
    Unittest.main()
