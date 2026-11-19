import contextlib as Contextlib
import copy as Copy
import io as Io
import json as Json
import tempfile as Tempfile
import unittest as Unittest
from pathlib import Path

import main as Main
import seal as Seal


class SealDocumentTests(Unittest.TestCase):
    def MakeSeal(self, Blob=b"P00P pretend bowl bytes", Entries=3):
        return Seal.BuildSeal(
            ".fake-vault.p00p",
            Blob,
            Entries,
            "2030-04-05T06:07:08+00:00",
        )

    def testSuggestedPathKeepsTheWeirdOriginalSuffix(self):
        self.assertEqual(
            Seal.SuggestedSealPath(Path("/tmp/.fake.poop")),
            Path("/tmp/.fake.poop.seal.json"),
        )

    def testSealRoundTripsThroughStrictJson(self):
        Original = self.MakeSeal()

        Decoded = Seal.DecodeSeal(Seal.EncodeSeal(Original))

        self.assertEqual(Decoded, Original)
        self.assertEqual(Decoded["protocol"], "p00p-bowl-seal")
        self.assertEqual(len(Decoded["vault_sha256"]), 64)

    def testSealContainsMetadataButNotTheBowlBytes(self):
        SecretLookingBlob = b"definitely-not-a-real-secret-password"

        Encoded = Seal.EncodeSeal(self.MakeSeal(SecretLookingBlob))

        self.assertNotIn(SecretLookingBlob, Encoded)
        self.assertIn(b"vault_sha256", Encoded)

    def testMalformedDocumentsGetRejected(self):
        BadDocuments = (
            b"not json",
            Json.dumps([]).encode(),
            Json.dumps({"protocol": "other"}).encode(),
        )
        for Blob in BadDocuments:
            with self.subTest(Blob=Blob):
                with self.assertRaises(Seal.SealError):
                    Seal.DecodeSeal(Blob)

    def testOversizedDocumentGetsRejectedBeforeJsonParsing(self):
        with self.assertRaisesRegex(Seal.SealError, "too large"):
            Seal.DecodeSeal(b"x" * (Seal.MAX_SEAL_BYTES + 1))

    def testDigestMustBeExactlyLowercaseSha256(self):
        for Digest in ("abc", "A" * 64, "g" * 64, 123):
            Broken = self.MakeSeal()
            Broken["vault_sha256"] = Digest
            with self.subTest(Digest=Digest):
                with self.assertRaisesRegex(Seal.SealError, "SHA-256"):
                    Seal.ValidateSeal(Broken)

    def testFilenameCannotSmuggleAPathIntoTheSeal(self):
        Broken = self.MakeSeal()
        Broken["vault_name"] = "somewhere/.fake.p00p"

        with self.assertRaisesRegex(Seal.SealError, "must not contain a path"):
            Seal.ValidateSeal(Broken)


class SealVerificationTests(Unittest.TestCase):
    def setUp(self):
        self.Blob = b"exact pretend vault bytes"
        self.Seal = Seal.BuildSeal(
            ".vault.p00p",
            self.Blob,
            4,
            "2030-04-05T06:07:08+00:00",
        )

    def Verify(self, Blob=None, PathName=".vault.p00p", Entries=4):
        return Seal.VerifySeal(
            self.Seal,
            ".vault.p00p.seal.json",
            PathName,
            self.Blob if Blob is None else Blob,
            Entries,
        )

    def testExactBowlPassesEveryCheck(self):
        Result = self.Verify()

        self.assertTrue(Result.Passed)
        self.assertEqual(len(Result.Checks), 4)
        self.assertTrue(all(Check["passed"] for Check in Result.Checks))

    def testOneChangedByteBreaksTheDigest(self):
        Result = self.Verify(Blob=self.Blob[:-1] + b"X")

        self.assertFalse(Result.Passed)
        DigestCheck = next(Check for Check in Result.Checks if Check["name"] == "SHA-256")
        self.assertFalse(DigestCheck["passed"])

    def testTruncationBreaksSizeAndDigest(self):
        Result = self.Verify(Blob=self.Blob[:-5])
        Failed = {Check["name"] for Check in Result.Checks if not Check["passed"]}

        self.assertEqual(Failed, {"file size", "SHA-256"})

    def testRenamedBowlFailsTheFilenameCheck(self):
        Result = self.Verify(PathName=".renamed.p00p")

        self.assertFalse(Result.Passed)
        self.assertFalse(Result.Checks[0]["passed"])

    def testWrongDecodedEntryCountAlsoBreaksVerification(self):
        Result = self.Verify(Entries=99)

        self.assertFalse(Result.Passed)
        self.assertFalse(Result.Checks[-1]["passed"])

    def testTextAndJsonResultsDoNotContainBowlContents(self):
        Result = self.Verify()
        Rendered = Result.AsText() + Result.AsJson()

        self.assertNotIn(self.Blob.decode(), Rendered)
        self.assertIn("EXACT BOWL MATCH", Rendered)
        self.assertTrue(Json.loads(Result.AsJson())["passed"])

    def testValidationDoesNotMutateTheSeal(self):
        Before = Copy.deepcopy(self.Seal)

        self.Verify()

        self.assertEqual(self.Seal, Before)


#MARK: actual bowl sidecar stuffs
class SealCommandTests(Unittest.TestCase):
    def RunCli(self, *Arguments):
        Output = Io.StringIO()
        Errors = Io.StringIO()
        with Contextlib.redirect_stdout(Output), Contextlib.redirect_stderr(Errors):
            Result = Main.RunApp(Arguments)
        return Result, Output.getvalue(), Errors.getvalue()

    def MakeVault(self, Directory):
        VaultPath = Path(Directory) / ".sealed-demo.p00p"
        Vault = Main.NewVault()
        Vault["entries"]["fake satellite"] = {
            "username": "fake-user",
            "password": "Fake-Seal-Password-864!",
            "notes": "not real",
            "updated_at": Main.CurrentTime(),
        }
        Main.SaveVault(VaultPath, Vault)
        return VaultPath

    def testSealCommandWritesOwnerOnlySidecarWithoutCredentials(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)

            Result, Output, Error = self.RunCli(
                "seal", "--json", "--vault", str(VaultPath)
            )
            Receipt = Json.loads(Output)
            SealPath = Path(Receipt["seal_path"])

            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertTrue(SealPath.is_file())
            self.assertEqual(SealPath.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("Fake-Seal-Password-864!", SealPath.read_text())
            self.assertEqual(Receipt["entry_count"], 1)

    def testFreshlyStampedBowlVerifiesWithSuccessExitCode(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            SealResult, _, _ = self.RunCli("stamp", "--vault", str(VaultPath))

            Result, Output, Error = self.RunCli(
                "verify-seal", "--json", "--vault", str(VaultPath)
            )
            Verification = Json.loads(Output)

            self.assertEqual(SealResult, 0)
            self.assertEqual(Result, 0)
            self.assertEqual(Error, "")
            self.assertTrue(Verification["passed"])

    def testChangedBowlPrintsReportAndUsesMismatchExitCode(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            self.RunCli("seal", "--vault", str(VaultPath))
            Vault = Main.LoadVault(VaultPath)
            Vault["entries"]["fake satellite"]["notes"] = "changed on purpose"
            Main.SaveVault(VaultPath, Vault)

            Result, Output, Error = self.RunCli(
                "check-seal", "--json", "--vault", str(VaultPath)
            )

            self.assertEqual(Result, 2)
            self.assertEqual(Error, "")
            self.assertFalse(Json.loads(Output)["passed"])

    def testExistingSealSurvivesWithoutForce(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            SealPath = Seal.SuggestedSealPath(VaultPath)
            SealPath.write_bytes(b"keep this seal-ish thing")

            Result, _, Error = self.RunCli("seal", "--vault", str(VaultPath))

            self.assertEqual(Result, 1)
            self.assertIn("already exists", Error)
            self.assertEqual(SealPath.read_bytes(), b"keep this seal-ish thing")

    def testSealCannotReplaceItsOwnVaultEvenWithForce(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            Before = VaultPath.read_bytes()

            Result, _, Error = self.RunCli(
                "seal", "--output", str(VaultPath), "--force",
                "--vault", str(VaultPath),
            )

            self.assertEqual(Result, 1)
            self.assertIn("cannot replace the vault", Error)
            self.assertEqual(VaultPath.read_bytes(), Before)

    def testMalformedSealGetsARegularCliError(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            SealPath = Seal.SuggestedSealPath(VaultPath)
            SealPath.write_text("nope", encoding="utf-8")

            Result, _, Error = self.RunCli(
                "verify-seal", "--vault", str(VaultPath)
            )

            self.assertEqual(Result, 1)
            self.assertIn("not valid UTF-8 JSON", Error)


if __name__ == "__main__":
    Unittest.main()
