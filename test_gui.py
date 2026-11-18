import tempfile as Tempfile
import unittest as Unittest
from pathlib import Path

import gui as Gui
import main as Main


#MARK: fake vault stuffs
def ExampleVault():
    Vault = Main.NewVault()
    Vault["entries"] = {
        "Moon Base": {
            "username": "astronaut",
            "password": "Good-Fake-Password-123!",
            "notes": "space service",
            "updated_at": Main.CurrentTime(),
        },
        "Bad Bank": {
            "username": "villain",
            "password": "password",
            "notes": "definitely legitimate",
            "updated_at": Main.CurrentTime(),
        },
        "Worse Bank": {
            "username": "henchperson",
            "password": "password",
            "notes": "also legitimate",
            "updated_at": Main.CurrentTime(),
        },
    }
    return Vault


#MARK: filtering stuffs
class FilterTests(Unittest.TestCase):
    def testEmptySearchReturnsSortedNames(self):
        self.assertEqual(
            Gui.FilterEntryNames(ExampleVault()),
            ["Bad Bank", "Moon Base", "Worse Bank"],
        )

    def testSearchChecksNameUsernameAndNotes(self):
        Vault = ExampleVault()

        self.assertEqual(Gui.FilterEntryNames(Vault, "moon"), ["Moon Base"])
        self.assertEqual(Gui.FilterEntryNames(Vault, "ASTRONAUT"), ["Moon Base"])
        self.assertEqual(Gui.FilterEntryNames(Vault, "space service"), ["Moon Base"])
        self.assertEqual(Gui.FilterEntryNames(Vault, "the password itself"), [])


#MARK: list view stuffs
class ListViewTests(Unittest.TestCase):
    def testIssueCountsIncludeWeakMissingAndReusedPasswords(self):
        Vault = ExampleVault()
        Vault["entries"]["Moon Base"]["username"] = ""

        Counts = Gui.EntryIssueCounts(Vault)

        self.assertEqual(Counts["Moon Base"], 1)
        self.assertGreater(Counts["Bad Bank"], 1)
        self.assertEqual(Counts["Bad Bank"], Counts["Worse Bank"])

    def testRowsCanSortWithoutPuttingPasswordsInTheViewModel(self):
        Rows = Gui.EntryRows(ExampleVault(), SortColumn="name", Descending=True)

        self.assertEqual([Row["name"] for Row in Rows],
                         ["Worse Bank", "Moon Base", "Bad Bank"])
        self.assertTrue(all("password" not in Row for Row in Rows))

    def testRowsKeepSearchAndHealthSortingTogether(self):
        Rows = Gui.EntryRows(ExampleVault(), Query="bank", SortColumn="health")

        self.assertEqual({Row["name"] for Row in Rows}, {"Bad Bank", "Worse Bank"})
        self.assertTrue(all(Row["health"] > 0 for Row in Rows))

    def testVaultSummaryCountsShownAndUnhealthyEntries(self):
        Summary = Gui.VaultSummary(ExampleVault(), Query="moon")

        self.assertEqual(Summary["total"], 3)
        self.assertEqual(Summary["shown"], 1)
        self.assertEqual(Summary["needs_work"], 2)
        self.assertGreater(Summary["issues"], 2)

    def testPasswordMaskDoesNotLeakPasswordLength(self):
        self.assertEqual(Gui.PasswordMask("tiny"), "•" * 12)
        self.assertEqual(Gui.PasswordMask("ridiculously-long-fake-password"), "•" * 12)
        self.assertEqual(Gui.PasswordMask(""), "—")


#MARK: report stuffs
class ReportTests(Unittest.TestCase):
    def testAuditReportsWeakAndReusedPasswordsWithoutLeakingThem(self):
        Findings = Gui.AuditVault(ExampleVault())
        Report = "\n".join(f"{Name}: {Finding}" for Name, Finding in Findings)

        self.assertIn("Bad Bank", Report)
        self.assertIn("reused password", Report)
        self.assertIn("Bad Bank, Worse Bank", Report)
        self.assertNotIn("Good-Fake-Password-123!", Report)

    def testAuditAcceptsAHealthyHiddenVault(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".healthy.p00p"
            Vault = Main.NewVault()
            Vault["entries"]["Example"] = {
                "username": "fake-user",
                "password": "Good-Fake-Password-123!",
                "notes": "",
                "updated_at": Main.CurrentTime(),
            }
            Main.SaveVault(FilePath, Vault)

            self.assertEqual(Gui.AuditVault(Vault, FilePath), [])

    def testAnatomyReportUsesRealEnvelopeValues(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".anatomy.p00p"
            Main.SaveVault(FilePath, ExampleVault())

            Report = Gui.FormatAnatomy(FilePath)

            self.assertIn("magic:         b'P00P\\x00'", Report)
            self.assertIn("version:       1", Report)
            self.assertIn("decoded:       3 entries, integrity check passed", Report)


if __name__ == "__main__":
    Unittest.main()
