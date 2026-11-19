import tempfile as Tempfile
import unittest as Unittest
from types import SimpleNamespace
from unittest import mock as Mock
from pathlib import Path

import ctk_gui as ModernGui
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


#MARK: entry dialog helper stuffs
class DialogHelperTests(Unittest.TestCase):
    def testBlankPasswordHasAQuietStartingMessage(self):
        Summary = Gui.PasswordHealthSummary("")

        self.assertFalse(Summary["healthy"])
        self.assertEqual(Summary["issues"], ())
        self.assertEqual(Summary["text"], "no fake password yet")

    def testWeakPasswordSummaryListsIssuesWithoutRepeatingPassword(self):
        Summary = Gui.PasswordHealthSummary("hunter2")

        self.assertFalse(Summary["healthy"])
        self.assertGreater(len(Summary["issues"]), 1)
        self.assertNotIn("hunter2", Summary["text"].casefold())

    def testHealthyPasswordGetsTheGoodMessage(self):
        Summary = Gui.PasswordHealthSummary("Good-Fake-Password-123!")

        self.assertTrue(Summary["healthy"])
        self.assertEqual(Summary["issues"], ())
        self.assertIn("looks surprisingly decent", Summary["text"])

    def testGeneratorLengthAcceptsStringsAndRejectsNonsense(self):
        self.assertEqual(Gui.GeneratorLength("24"), 24)
        with self.assertRaisesRegex(Main.P00PError, "whole number"):
            Gui.GeneratorLength("twenty four")
        with self.assertRaisesRegex(Main.P00PError, "12-256"):
            Gui.GeneratorLength("999")


#MARK: easter egg stuffs
class EasterEggTests(Unittest.TestCase):
    def testSequenceLatchOnlyOpensAfterTheWholePattern(self):
        Latch = Gui.SequenceLatch(("Up", "Down", "b", "a"))

        Results = [Latch.Feed(Key) for Key in ("Up", "Down", "b", "a")]

        self.assertEqual(Results, [False, False, False, True])

    def testSequenceLatchResetsAndCanBeUsedAgain(self):
        Latch = Gui.SequenceLatch(("a", "b", "a"))

        self.assertFalse(Latch.Feed("a"))
        self.assertFalse(Latch.Feed("wrong"))
        self.assertFalse(Latch.Feed("a"))
        self.assertFalse(Latch.Feed("b"))
        self.assertTrue(Latch.Feed("a"))
        self.assertFalse(Latch.Feed("a"))

    def testMascotOpensGoldenPoopAfterExactlyFiveClicks(self):
        Window = SimpleNamespace(MascotClicks=0, SetStatus=Mock.Mock())

        with Mock.patch.object(ModernGui, "ModernSecretWindow") as SecretWindow:
            for _ in range(4):
                ModernGui.ModernP00PWindow.OnMascotClick(Window)
            SecretWindow.assert_not_called()

            ModernGui.ModernP00PWindow.OnMascotClick(Window)

        SecretWindow.assert_called_once()
        self.assertEqual(SecretWindow.call_args.args[1], "Golden poop discovered")
        self.assertEqual(Window.MascotClicks, 0)
        Window.SetStatus.assert_called_once_with("Easter egg found: golden poop")

    def testKonamiSequenceOpensSewerMode(self):
        Latch = Mock.Mock()
        Latch.Feed.return_value = True
        Window = SimpleNamespace(SecretSequence=Latch, SetStatus=Mock.Mock())
        Event = SimpleNamespace(keysym="a")

        with Mock.patch.object(ModernGui, "ModernSecretWindow") as SecretWindow:
            ModernGui.ModernP00PWindow.OnSecretKey(Window, Event)

        Latch.Feed.assert_called_once_with("a")
        SecretWindow.assert_called_once()
        self.assertEqual(SecretWindow.call_args.args[1], "Sewer mode unlocked")
        Window.SetStatus.assert_called_once_with("Secret sewer mode unlocked")


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
