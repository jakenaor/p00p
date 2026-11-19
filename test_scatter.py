import hashlib as Hashlib
import json as Json
import os as Os
import tempfile as Tempfile
import unittest as Unittest
from pathlib import Path
from unittest import mock as Mock

import scatter as Scatter


def FakeRandom(Count):
    return bytes(((Index * 73) + 19) % 256 for Index in range(Count))


def FakeBowl():
    return (
        b"P00P fake bowl bytes for math testing\x00"
        b"Fake-Scatter-Password-642!\x00"
        b"the end"
    )


class FiniteFieldTests(Unittest.TestCase):
    def testMultiplicationHasTheExpectedFieldIdentities(self):
        for Value in range(256):
            self.assertEqual(Scatter._slow_gf_multiply(Value, 0), 0)
            self.assertEqual(Scatter._slow_gf_multiply(Value, 1), Value)
            self.assertEqual(
                Scatter._slow_gf_multiply(Value, 2),
                Scatter.MultiplicationTable(2)[Value],
            )

    def testEveryNonzeroByteHasAWorkingInverse(self):
        for Value in range(1, 256):
            Inverse = Scatter._gf_inverse(Value)
            self.assertEqual(Scatter._slow_gf_multiply(Value, Inverse), 1)

    def testZeroAndOutOfByteMathGetsRejected(self):
        with self.assertRaises(Scatter.ScatterError):
            Scatter._gf_inverse(0)
        with self.assertRaises(Scatter.ScatterError):
            Scatter._slow_gf_multiply(-1, 4)
        with self.assertRaises(Scatter.ScatterError):
            Scatter.MultiplicationTable(256)


class FragmentEngineTests(Unittest.TestCase):
    def MakeFragments(self, Blob=None):
        return Scatter.SplitBlob(
            FakeBowl() if Blob is None else Blob,
            RandomBytes=FakeRandom,
            SetId=b"S" * Scatter.SET_ID_BYTES,
        )

    def testAnyTwoOfTheThreeRecoverExactOriginal(self):
        self.assertEqual(Scatter.RebuildBlob(*Scatter.SplitBlob(b"x", RandomBytes=FakeRandom, SetId=b"M" * 16)[:2]), b"x")
        self.assertEqual(Scatter.RebuildBlob(*Scatter.SplitBlob(bytes(range(256)), RandomBytes=FakeRandom, SetId=b"B" * 16)[1:]), bytes(range(256)))
        Blob = FakeBowl()
        Fragments = self.MakeFragments(Blob)
        self.assertEqual(Scatter.RepairFragment(Fragments[0], Fragments[2], 2).Encode(), Fragments[1].Encode())
        self.assertEqual(Scatter.RepairFragment(Fragments[1], Fragments[2], 1).Encode(), Fragments[0].Encode())
        self.assertEqual(Scatter.RepairFragment(Fragments[0], Fragments[1], 3).Encode(), Fragments[2].Encode())
        self.assertEqual(Scatter.RepairFragment(Fragments[2], Fragments[0], 2).Encode(), Fragments[1].Encode())

        for LeftIndex, RightIndex in ((0, 1), (0, 2), (1, 2)):
            with self.subTest(Pair=(LeftIndex + 1, RightIndex + 1)):
                self.assertEqual(
                    Scatter.RebuildBlob(
                        Fragments[LeftIndex], Fragments[RightIndex]
                    ),
                    Blob,
                )

    def testOneFragmentDoesNotContainOriginalByteSequence(self):
        Blob = FakeBowl()
        Fragments = self.MakeFragments(Blob)

        for FragmentThing in Fragments:
            Encoded = FragmentThing.Encode()
            self.assertNotEqual(FragmentThing.Payload, Blob)
            self.assertNotIn(b"Fake-Scatter-Password-642!", Encoded)

    def testFragmentsRoundTripThroughStrictBinaryEnvelope(self):
        for Original in self.MakeFragments():
            Decoded = Scatter.DecodeFragment(Original.Encode())

            self.assertEqual(Decoded.Index, Original.Index)
            self.assertEqual(Decoded.SetId, Original.SetId)
            self.assertEqual(Decoded.OriginalDigest, Original.OriginalDigest)
            self.assertEqual(Decoded.Payload, Original.Payload)

    def testPayloadCorruptionGetsCaughtBeforeRebuilding(self):
        Encoded = bytearray(self.MakeFragments()[0].Encode())
        Encoded[-1] ^= 0x80

        with self.assertRaisesRegex(Scatter.ScatterError, "payload SHA-256"):
            Scatter.DecodeFragment(Encoded)

    def testHeaderShapeVersionAndSchemeAreStrict(self):
        Good = self.MakeFragments()[0].Encode()
        Cases = []
        for Offset, Value in ((0, ord("X")), (8, 9), (9, 0), (10, 3), (11, 9)):
            Broken = bytearray(Good)
            Broken[Offset] = Value
            Cases.append(bytes(Broken))
        Cases.extend((b"", Good[:Scatter.HEADER.size - 1], Good[:-1]))

        for Blob in Cases:
            with self.subTest(Size=len(Blob), Prefix=Blob[:12]):
                with self.assertRaises(Scatter.ScatterError):
                    Scatter.DecodeFragment(Blob)

    def testDuplicateAndMixedSetPairsAreRejected(self):
        First = self.MakeFragments()
        Second = Scatter.SplitBlob(
            FakeBowl(), RandomBytes=FakeRandom, SetId=b"T" * Scatter.SET_ID_BYTES
        )

        with self.assertRaisesRegex(Scatter.ScatterError, "still only one point"):
            Scatter.RebuildBlob(First[0], First[0])
        with self.assertRaisesRegex(Scatter.ScatterError, "different scatter sets"):
            Scatter.RebuildBlob(First[0], Second[1])
        with self.assertRaisesRegex(Scatter.ScatterError, "still only one point"): Scatter.RepairFragment(First[0], First[1], 1)
        with self.assertRaisesRegex(Scatter.ScatterError, "index must"): Scatter.RepairFragment(First[0], First[1], 4)
        with self.assertRaisesRegex(Scatter.ScatterError, "different scatter sets"): Scatter.RepairFragment(First[0], Second[1], 3)

    def testDishonestOriginalDigestBreaksTheFinalPromise(self):
        Left, Right, _Third = self.MakeFragments()
        Lie = Scatter.Fragment(
            Right.Index,
            Right.SetId,
            Right.OriginalSize,
            b"L" * 32,
            Right.Payload,
        )

        with self.assertRaisesRegex(Scatter.ScatterError, "disagree.*SHA-256"):
            Scatter.RebuildBlob(Left, Lie)

        BothLieLeft = Scatter.Fragment(
            Left.Index, Left.SetId, Left.OriginalSize, b"L" * 32, Left.Payload
        )
        with self.assertRaisesRegex(Scatter.ScatterError, "rebuilt bowl SHA-256"):
            Scatter.RebuildBlob(BothLieLeft, Lie)

    def testSizeSetIdAndRandomSourceGuardsAreBoringAndLoud(self):
        with self.assertRaises(Scatter.ScatterError): Scatter.SplitBlob(b"x" * (Scatter.MAX_FRAGMENT_PAYLOAD + 1))
        with self.assertRaises(Scatter.ScatterError):
            Scatter.SplitBlob(b"")
        with self.assertRaisesRegex(Scatter.ScatterError, "set id"):
            Scatter.SplitBlob(b"abc", SetId=b"short")
        with self.assertRaisesRegex(Scatter.ScatterError, "random source"):
            Scatter.SplitBlob(b"abc", RandomBytes=lambda Count: b"x", SetId=b"S" * 16)


class FragmentFileTests(Unittest.TestCase):
    def MakeEncoded(self):
        return tuple(
            FragmentThing.Encode()
            for FragmentThing in Scatter.SplitBlob(
                FakeBowl(), RandomBytes=FakeRandom, SetId=b"F" * 16
            )
        )

    def testSuggestedNamesKeepTheWeirdVaultNameVisible(self):
        Paths = Scatter.SuggestedFragmentPaths(Path("/tmp/.moon.poop"))

        self.assertEqual(
            Paths[0], Path("/tmp/.moon.poop.fragment.1-of-3.p00pshard")
        )
        self.assertEqual(Paths[-1].name, ".moon.poop.fragment.3-of-3.p00pshard")

    def testThreeFileCrateIsOwnerOnlyAndReadable(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Paths = tuple(Path(Directory) / f"part-{Index}" for Index in (1, 2, 3))

            Scatter.WriteFragmentSet(Paths, self.MakeEncoded())

            self.assertTrue(all(PathThing.is_file() for PathThing in Paths))
            self.assertTrue(all(PathThing.stat().st_mode & 0o777 == 0o600 for PathThing in Paths))
            self.assertEqual(
                Scatter.RebuildBlob(
                    Scatter.ReadFragment(Paths[0]),
                    Scatter.ReadFragment(Paths[2]),
                ),
                FakeBowl(),
            )

    def testExistingDestinationStopsBeforeAnyOtherFileAppears(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Paths = tuple(Path(Directory) / f"part-{Index}" for Index in (1, 2, 3))
            Paths[1].write_bytes(b"keep me")

            with self.assertRaisesRegex(Scatter.ScatterError, "already exists"):
                Scatter.WriteFragmentSet(Paths, self.MakeEncoded())

            self.assertFalse(Paths[0].exists())
            self.assertEqual(Paths[1].read_bytes(), b"keep me")
            self.assertFalse(Paths[2].exists())

    def testPublishFailureRollsBackEarlierPublishedFragment(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Paths = tuple(Path(Directory) / f"part-{Index}" for Index in (1, 2, 3))
            RealLink = Os.link
            LinkCount = 0

            def FlakyLink(Source, Destination):
                nonlocal LinkCount
                LinkCount += 1
                if LinkCount == 2:
                    raise OSError("pretend second disk fell into toilet")
                return RealLink(Source, Destination)

            with Mock.patch.object(Scatter.Os, "link", side_effect=FlakyLink):
                with self.assertRaisesRegex(Scatter.ScatterError, "could not publish"):
                    Scatter.WriteFragmentSet(Paths, self.MakeEncoded())

            self.assertFalse(any(PathThing.exists() for PathThing in Paths))
            self.assertEqual(list(Path(Directory).glob("*.scattering")), [])

    def testReceiptIsUsefulWithoutContainingTheOriginalBytes(self):
        Fragments = Scatter.SplitBlob(
            FakeBowl(), RandomBytes=FakeRandom, SetId=b"R" * 16
        )
        Paths = tuple(Path(f"part-{Index}") for Index in (1, 2, 3))
        Receipt = Scatter.ScatterReceipt(".fake.p00p", Paths, Fragments)
        Rendered = Receipt.AsText() + Receipt.AsJson()
        Parsed = Json.loads(Receipt.AsJson())

        self.assertEqual(Parsed["needed"], 2)
        self.assertEqual(Parsed["created"], 3)
        self.assertEqual(Parsed["vault_sha256"], Hashlib.sha256(FakeBowl()).hexdigest())
        self.assertNotIn("Fake-Scatter-Password-642!", Rendered)


if __name__ == "__main__":
    Unittest.main()
