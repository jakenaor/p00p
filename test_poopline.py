import hashlib as Hashlib
import json as Json
import struct as Struct
import unittest as Unittest
import zlib as Zlib

import main as Main
import poopline as Poopline


def TinyVault():
    return {
        "protocol": "p00p",
        "created_at": "2030-01-01T00:00:00+00:00",
        "updated_at": "2030-01-01T00:00:00+00:00",
        "entries": {
            "Definitely Fake": {
                "username": "fake-user",
                "password": "fake-password-123!",
                "notes": "testing the toilet pipeline",
            },
        },
    }


def OldBoringPayload(Vault, Salt):
    Raw = Json.dumps(Vault, separators=(",", ":"), sort_keys=True).encode("utf-8")
    Compressed = Zlib.compress(Raw, level=9)
    Stream = Hashlib.shake_256(Main.CAMOUFLAGE_KEY + Salt).digest(len(Compressed))
    return bytes(Left ^ Right for Left, Right in zip(Compressed, Stream))


#MARK: proving the enormous machine still does the tiny job
class PooplineTests(Unittest.TestCase):
    def testPipelineMatchesTheOriginalThreeLinesExactly(self):
        Salt = b"s" * Main.SALT_SIZE

        Ceremonial = Poopline.EncodePayload(TinyVault(), Salt, Main.CAMOUFLAGE_KEY)
        Boring = OldBoringPayload(TinyVault(), Salt)

        self.assertEqual(Ceremonial, Boring)

    def testPipelineWalksBackwardsOutOfTheBowl(self):
        Salt = b"b" * Main.SALT_SIZE
        Payload = Poopline.EncodePayload(TinyVault(), Salt, Main.CAMOUFLAGE_KEY)

        self.assertEqual(
            Poopline.DecodePayload(Payload, Salt, Main.CAMOUFLAGE_KEY),
            TinyVault(),
        )

    def testReceiptsExplainTheNonsenseWithoutLeakingSecrets(self):
        Receipts = Poopline.InspectPayloadRitual(
            TinyVault(), b"r" * Main.SALT_SIZE, Main.CAMOUFLAGE_KEY
        )
        Report = repr(Receipts)

        self.assertEqual(
            [Receipt["stage"] for Receipt in Receipts],
            ["json goblin", "trash compactor", "toilet curtain"],
        )
        self.assertTrue(all(Receipt["before_size"] > 0 for Receipt in Receipts))
        self.assertNotIn("fake-password-123!", Report)

    def testBrokenPayloadNamesTheGoblinThatFellOver(self):
        with self.assertRaisesRegex(Poopline.PooplineError, "trash compactor"):
            Poopline.DecodePayload(
                b"this was never a compressed payload",
                b"x" * Main.SALT_SIZE,
                Main.CAMOUFLAGE_KEY,
            )

    def testWholeVersionOneEnvelopeIsStillByteCompatible(self):
        Salt = b"0" * Main.SALT_SIZE
        Payload = OldBoringPayload(TinyVault(), Salt)
        Header = Main.MAGIC + bytes([Main.VERSION]) + Salt + Struct.pack(">I", len(Payload))
        Digest = Hashlib.sha256(Header + Payload).digest()[:Main.DIGEST_SIZE]

        self.assertEqual(Main.EncodeVault(TinyVault(), Salt=Salt), Header + Payload + Digest)


if __name__ == "__main__":
    Unittest.main()
