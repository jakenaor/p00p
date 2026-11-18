import tempfile
import unittest
from pathlib import Path

import main


class FormatTests(unittest.TestCase):
    def test_round_trip(self):
        vault = main.new_vault()
        vault["entries"]["example.com"] = {
            "username": "fake-user",
            "password": "fake-password",
            "notes": "demo only",
        }

        encoded = main.encode_vault(vault, salt=b"0" * main.SALT_SIZE)
        decoded = main.decode_vault(encoded)

        self.assertEqual(decoded, vault)
        self.assertNotIn(b"fake-password", encoded)
        self.assertNotIn(b"example.com", encoded)

    def test_corruption_is_detected(self):
        encoded = bytearray(main.encode_vault(main.new_vault()))
        encoded[-main.DIGEST_SIZE - 1] ^= 1

        with self.assertRaisesRegex(main.P00PError, "integrity check failed"):
            main.decode_vault(bytes(encoded))

    def test_invalid_file_is_rejected(self):
        with self.assertRaisesRegex(main.P00PError, "not a valid"):
            main.decode_vault(b"definitely not p00p")


class StorageTests(unittest.TestCase):
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".test.p00p"
            vault = main.new_vault()
            main.save_vault(path, vault)

            self.assertEqual(main.load_vault(path)["entries"], {})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
