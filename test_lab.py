import contextlib as Contextlib
import io as Io
import json as Json
import tempfile as Tempfile
import unittest as Unittest
from pathlib import Path

import lab as Lab
import main as Main


def FakeVault():
    Vault = Main.NewVault()
    Vault["entries"]["fake moon station"] = {
        "username": "fake-astronaut",
        "password": "Fake-Lab-Password-246!",
        "notes": "storage experiment only",
        "updated_at": Main.CurrentTime(),
    }
    return Vault


class TickTock:
    def __init__(self, Step=0.00025):
        self.Now = 0.0
        self.Step = Step

    def __call__(self):
        self.Now += self.Step
        return self.Now


class StorageLabTests(Unittest.TestCase):
    def RunRealLab(self, Rounds=8):
        return Lab.RunStorageLab(
            FakeVault(),
            Rounds,
            Main.EncodeVault,
            Main.DecodeVault,
            Main.ParseHeader,
            Clock=TickTock(),
        )

    def testRealFormatMakesFreshSaltAndEnvelopeEveryRound(self):
        Report = self.RunRealLab()

        self.assertTrue(Report.Passed)
        self.assertEqual(Report.UniqueEnvelopes, 8)
        self.assertEqual(Report.UniqueSalts, 8)
        self.assertTrue(Report.CorruptionRejected)
        self.assertEqual(Report.PlaintextEnvelopeHits, 0)

    def testEveryRenderedReportIsCredentialSafe(self):
        Report = self.RunRealLab()
        Rendered = Report.AsText() + Report.AsJson() + Report.Summary()

        self.assertNotIn("fake-astronaut", Rendered)
        self.assertNotIn("Fake-Lab-Password-246!", Rendered)
        self.assertNotIn("storage experiment only", Rendered)
        self.assertIn("format behavior is not proof", Rendered)

    def testJsonCarriesStableSectionsAndTimingNumbers(self):
        Payload = Json.loads(self.RunRealLab().AsJson())

        self.assertEqual(Payload["protocol"], "p00p-storage-lab")
        self.assertEqual(Payload["rounds"], 8)
        self.assertEqual(Payload["encode_timing"]["median_ms"], 0.25)
        self.assertEqual(Payload["decode_timing"]["median_ms"], 0.25)
        self.assertTrue(Payload["passed"])

    def testRoundGuardRejectsTinyHugeAndNonsenseRuns(self):
        for Rounds in (1, Lab.MAX_ROUNDS + 1, "a bunch"):
            with self.subTest(Rounds=Rounds):
                with self.assertRaises(Lab.LabError):
                    Lab.RunStorageLab(
                        FakeVault(), Rounds, Main.EncodeVault,
                        Main.DecodeVault, Main.ParseHeader,
                    )

    def testDecoderThatChangesDataStopsTheLab(self):
        Vault = FakeVault()

        with self.assertRaisesRegex(Lab.LabError, "changed the decoded bowl"):
            Lab.RunStorageLab(
                Vault,
                2,
                Main.EncodeVault,
                lambda _Blob: Main.NewVault(),
                Main.ParseHeader,
                Clock=TickTock(),
            )

    def testRepeatedEnvelopeFailsTheRandomizationResult(self):
        Vault = FakeVault()
        Blob = Main.EncodeVault(Vault, Salt=b"x" * Main.SALT_SIZE)

        Report = Lab.RunStorageLab(
            Vault,
            4,
            lambda _Vault: Blob,
            Main.DecodeVault,
            Main.ParseHeader,
            Clock=TickTock(),
        )

        self.assertFalse(Report.Passed)
        self.assertEqual(Report.UniqueEnvelopes, 1)
        self.assertEqual(Report.UniqueSalts, 1)

    def testPlaintextProbeCounterDoesNotPrintTheProbe(self):
        Vault = FakeVault()
        Counter = iter(range(2, 20))

        def Encode(_Vault):
            Number = next(Counter)
            return b"header" + bytes([Number]) + b"Fake-Lab-Password-246!" + b"payload"

        def Header(Blob):
            return {"salt": Blob[6:7], "header_size": 7, "payload_size": len(Blob) - 7}

        Report = Lab.RunStorageLab(
            Vault,
            2,
            Encode,
            lambda _Blob: Vault,
            Header,
            Clock=TickTock(),
        )

        self.assertEqual(Report.PlaintextEnvelopeHits, 2)
        self.assertFalse(Report.Passed)
        self.assertNotIn("Fake-Lab-Password-246!", Report.AsText())

    def testMissingSaltGetsAUsefulLabError(self):
        Vault = FakeVault()

        with self.assertRaisesRegex(Lab.LabError, "without salt"):
            Lab.RunStorageLab(
                Vault,
                2,
                Main.EncodeVault,
                Main.DecodeVault,
                lambda _Blob: {"salt": b""},
                Clock=TickTock(),
            )


#MARK: science fair command stuffs
class StorageLabCommandTests(Unittest.TestCase):
    def RunCli(self, *Arguments):
        Output = Io.StringIO()
        Errors = Io.StringIO()
        with Contextlib.redirect_stdout(Output), Contextlib.redirect_stderr(Errors):
            Result = Main.RunApp(Arguments)
        return Result, Output.getvalue(), Errors.getvalue()

    def MakeVault(self, Directory):
        VaultPath = Path(Directory) / ".lab-bowl.p00p"
        Main.SaveVault(VaultPath, FakeVault())
        return VaultPath

    def testBenchAliasRunsRealRoundTripsAndPrintsSafeJson(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)

            Result, Output, Error = self.RunCli(
                "bench", "--rounds", "5", "--json", "--vault", str(VaultPath)
            )
            Payload = Json.loads(Output)

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertTrue(Payload["passed"])
            self.assertEqual(Payload["rounds"], 5)
            self.assertNotIn("Fake-Lab-Password-246!", Output)

    def testLabCommandPrintsHumanScienceFairReport(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)

            Result, Output, Error = self.RunCli(
                "lab", "--rounds", "3", "--vault", str(VaultPath)
            )

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertIn("P00P WEIRD STORAGE LAB", Output)
            self.assertIn("unique envelopes:    3/3", Output)

    def testInvalidRoundsBecomeRegularCliError(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)

            Result, Output, Error = self.RunCli(
                "lab", "--rounds", "1", "--vault", str(VaultPath)
            )

            self.assertEqual(Result, 1)
            self.assertEqual(Output, "")
            self.assertIn("rounds must be between", Error)


if __name__ == "__main__":
    Unittest.main()
