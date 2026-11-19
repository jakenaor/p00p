import tempfile as Tempfile
import unittest as Unittest
from pathlib import Path
from unittest import mock as Mock

import main as Main
import qt_gui as Gui


class MemorySettings:
    def __init__(self, Values=None):
        self.Values = dict(Values or {})

    def value(self, Name, Default=None):
        return self.Values.get(Name, Default)

    def setValue(self, Name, Value):
        self.Values[Name] = Value

    def sync(self):
        pass


#MARK: procedural beep boop stuffs
class SoundHookTests(Unittest.TestCase):
    def testKnownCueReachesTheOneSoundHook(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())
        Heard = []
        Backend.soundRequested.connect(lambda Cue, Volume: Heard.append((Cue, Volume)))

        Backend.requestSound(" UI_CLICK ")

        self.assertEqual(Heard, [("ui_click", Gui.DEFAULT_VOLUME)])

    def testTypoCueDoesNotSummonRandomAudio(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())
        Heard = []
        Backend.soundRequested.connect(lambda Cue, Volume: Heard.append((Cue, Volume)))

        Backend.requestSound("ui_clonk")

        self.assertEqual(Heard, [])

    def testEveryCueHasOneObviousNoOpLandingSpot(self):
        for Cue in Gui.SOUND_CUES:
            self.assertIsNone(Gui.HandleSoundCue(Cue, Gui.DEFAULT_VOLUME))


#MARK: settings stuffs
class SettingsTests(Unittest.TestCase):
    def testAudioAndShaderSettingsStick(self):
        Settings = MemorySettings()
        Backend = Gui.VaultBackend(Settings=Settings)

        Backend.setVolume(37)
        Backend.setSfxEnabled(False)
        Backend.setShaderEnabled(False)
        Backend.setClipboardSeconds(42)
        Backend.setRevealSeconds(31)
        Backend.setIdleSeconds(480)

        self.assertEqual(Backend.volume, 37)
        self.assertFalse(Backend.sfxEnabled)
        self.assertFalse(Backend.shaderEnabled)
        self.assertEqual(Backend.clipboardSeconds, 42)
        self.assertEqual(Backend.revealSeconds, 31)
        self.assertEqual(Backend.idleSeconds, 480)
        self.assertEqual(Settings.Values["audio/volume"], 37)
        self.assertFalse(Settings.Values["audio/enabled"])
        self.assertFalse(Settings.Values["display/shader"])
        self.assertEqual(Settings.Values["privacy/clipboard_seconds"], 42)
        self.assertEqual(Settings.Values["privacy/reveal_seconds"], 31)
        self.assertEqual(Settings.Values["privacy/idle_seconds"], 480)

        Reloaded = Gui.VaultBackend(Settings=Settings)
        self.assertEqual(Reloaded.volume, 37)
        self.assertFalse(Reloaded.sfxEnabled)
        self.assertFalse(Reloaded.shaderEnabled)
        self.assertEqual(Reloaded.clipboardSeconds, 42)
        self.assertEqual(Reloaded.revealSeconds, 31)
        self.assertEqual(Reloaded.idleSeconds, 480)

    def testSfxMasterSwitchSilencesEveryCue(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())
        Heard = []
        Backend.soundRequested.connect(lambda Cue, Volume: Heard.append((Cue, Volume)))

        Backend.setSfxEnabled(False)
        Backend.requestSound("copy")
        Backend.requestSound("error")

        self.assertEqual(Heard, [])

    def testVolumeCannotEscapeTheSlider(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())

        Backend.setVolume(9000)
        self.assertEqual(Backend.volume, 100)
        Backend.setVolume(-10)
        self.assertEqual(Backend.volume, 0)

    def testZeroMasterVolumeIsActuallySilent(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())
        Heard = []
        Backend.soundRequested.connect(lambda Cue, Volume: Heard.append((Cue, Volume)))

        Backend.setVolume(0)
        Backend.requestSound("ui_click")

        self.assertEqual(Heard, [])

    def testPrivacyTimersStayInsideUsefulBounds(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())

        Backend.setClipboardSeconds(0)
        Backend.setRevealSeconds(999)

        self.assertEqual(Backend.clipboardSeconds, Gui.MIN_TIMER_SECONDS)
        self.assertEqual(Backend.revealSeconds, Gui.MAX_TIMER_SECONDS)

    def testPrivacyTimersDriveTheRestartableTimers(self):
        Settings = MemorySettings({
            "privacy/clipboard_seconds": 17,
            "privacy/reveal_seconds": 29,
        })
        Backend = Gui.VaultBackend(Settings=Settings)
        Backend.Vault = Main.NewVault()
        Backend.Vault["entries"]["timer"] = {"password": "fake"}
        Backend.SelectedName = "timer"
        Backend.ClipboardTimer = Mock.Mock()
        Backend.RevealTimer = Mock.Mock()

        Backend._clear_clipboard_later("fake")
        Backend.togglePassword()

        Backend.ClipboardTimer.start.assert_called_once_with(17_000)
        Backend.RevealTimer.start.assert_called_once_with(29_000)

    def testCopyingAgainRestartsOneClipboardDeadline(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())
        Backend.ClipboardTimer = Mock.Mock()

        Backend._clear_clipboard_later("same fake thing")
        Backend._clear_clipboard_later("same fake thing")

        self.assertEqual(Backend.ClipboardTimer.start.call_count, 2)
        self.assertEqual(Backend.ClipboardText, "same fake thing")

    def testOldRevealTimerStopsWhenTheSelectedRowChanges(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())
        Backend.Vault = Main.NewVault()
        Backend.Vault["entries"].update({
            "first": {"password": "fake one"},
            "second": {"password": "fake two"},
        })
        Backend.SelectedName = "first"
        Backend.PasswordVisible = True
        Backend.RevealTimer = Mock.Mock()

        Backend.selectEntry("second")

        self.assertFalse(Backend.passwordVisible)
        Backend.RevealTimer.stop.assert_called_once_with()

    def testClipboardTimerLeavesNewerClipboardStuffAlone(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())
        Clipboard = Mock.Mock()
        Clipboard.text.return_value = "newer thing from somewhere else"
        Backend.ClipboardText = "old p00p thing"

        with Mock.patch.object(Gui.QGuiApplication, "clipboard", return_value=Clipboard):
            Backend._clear_clipboard_if_unchanged()

        Clipboard.clear.assert_not_called()
        self.assertEqual(Backend.ClipboardText, "")

    def testClipboardTimerClearsOnlyItsOwnStillCurrentText(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())
        Clipboard = Mock.Mock()
        Clipboard.text.return_value = "fake p00p thing"
        Backend.ClipboardText = "fake p00p thing"

        with Mock.patch.object(Gui.QGuiApplication, "clipboard", return_value=Clipboard):
            Backend._clear_clipboard_if_unchanged()

        Clipboard.clear.assert_called_once_with()
        self.assertEqual(Backend.ClipboardText, "")

    def testQuitCleanupClearsOnlyTheClipboardTextP00POwns(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())
        Backend.ClipboardTimer = Mock.Mock()
        Clipboard = Mock.Mock()
        Clipboard.text.return_value = "fake copied password"
        Backend.ClipboardText = "fake copied password"

        with Mock.patch.object(Gui.QGuiApplication, "clipboard", return_value=Clipboard):
            Backend.clearOwnedClipboard()

        Backend.ClipboardTimer.stop.assert_called_once_with()
        Clipboard.clear.assert_called_once_with()

    def testLeavingTheWindowImmediatelyCoversARevealedPassword(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())
        Backend.PasswordVisible = True
        Backend.RevealTimer = Mock.Mock()
        Changes = []
        Backend.selectionChanged.connect(lambda: Changes.append("covered"))

        Backend.coverForPrivacy()

        self.assertFalse(Backend.passwordVisible)
        Backend.RevealTimer.stop.assert_called_once_with()
        self.assertEqual(Changes, ["covered"])
        self.assertIn("WINDOW LEFT", Backend.statusText)

    def testResetOnlyResetsAppKnobs(self):
        Settings = MemorySettings({"audio/volume": 12, "display/shader": False})
        Backend = Gui.VaultBackend(Settings=Settings)

        Backend.resetSettings()

        self.assertEqual(Backend.volume, Gui.DEFAULT_VOLUME)
        self.assertEqual(Backend.sfxEnabled, Gui.DEFAULT_SFX_ENABLED)
        self.assertEqual(Backend.shaderEnabled, Gui.DEFAULT_SHADER_ENABLED)
        self.assertEqual(Backend.clipboardSeconds, Gui.DEFAULT_CLIPBOARD_SECONDS)
        self.assertEqual(Backend.revealSeconds, Gui.DEFAULT_REVEAL_SECONDS)
        self.assertEqual(Backend.idleSeconds, Gui.DEFAULT_IDLE_SECONDS)

    def testDeleteAllNeedsConfirmationThenSavesTheEmptyVault(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".delete-test.p00p"
            Vault = Main.NewVault()
            Vault["entries"]["fake bank"] = {
                "username": "fake-user",
                "password": "Fake-Password-123!",
                "notes": "delete me",
            }
            Main.SaveVault(FilePath, Vault)
            Backend = Gui.VaultBackend(StartPath=FilePath, Settings=MemorySettings())

            with Mock.patch.object(
                Gui.QMessageBox,
                "warning",
                return_value=Gui.QMessageBox.StandardButton.Yes,
            ):
                Deleted = Backend.deleteAllEntries()

            self.assertTrue(Deleted)
            self.assertFalse(Backend.hasEntries)
            self.assertEqual(Main.LoadVault(FilePath)["entries"], {})

    def testDeleteAllDoesNothingWhenConfirmationSaysNo(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())
        Backend.Vault = Main.NewVault()
        Backend.Vault["entries"]["keep me"] = {"password": "fake"}

        with Mock.patch.object(
            Gui.QMessageBox,
            "warning",
            return_value=Gui.QMessageBox.StandardButton.No,
        ):
            Deleted = Backend.deleteAllEntries()

        self.assertFalse(Deleted)
        self.assertIn("keep me", Backend.Vault["entries"])

    def testDeleteAllRollsBackWhenTheDiskRefusesTheSave(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())
        Backend.Vault = Main.NewVault()
        Backend.Vault["entries"]["survivor"] = {"password": "fake"}

        with Mock.patch.object(
            Gui.QMessageBox,
            "warning",
            return_value=Gui.QMessageBox.StandardButton.Yes,
        ), Mock.patch.object(Backend, "_save", return_value=False):
            Deleted = Backend.deleteAllEntries()

        self.assertFalse(Deleted)
        self.assertIn("survivor", Backend.Vault["entries"])


#MARK: fake privacy curtain stuffs
class PrivacyCurtainTests(Unittest.TestCase):
    def MakeOpenBackend(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())
        Backend.Vault = Main.NewVault()
        Backend.Vault["entries"]["fake"] = {"password": "Fake-Password-123!"}
        Backend.FilePath = Path(".fake-open-vault.p00p")
        Backend.IdleTimer = Mock.Mock()
        return Backend

    def testIdleSettingHasItsOwnUsefulBounds(self):
        self.assertEqual(Gui.ClampIdleTimer(1), Gui.MIN_IDLE_SECONDS)
        self.assertEqual(Gui.ClampIdleTimer(99999), Gui.MAX_IDLE_SECONDS)
        self.assertEqual(Gui.ClampIdleTimer("nope"), Gui.DEFAULT_IDLE_SECONDS)

    def testRealActivityRestartsOneIdleDeadline(self):
        Backend = self.MakeOpenBackend()
        Backend.IdleSeconds = 450

        with Mock.patch.object(Gui, "QtTimersAvailable", return_value=True):
            Backend.registerActivity()

        Backend.IdleTimer.start.assert_called_once_with(450_000)

    def testActivityCannotSecretlyLiftAnAlreadyDroppedCurtain(self):
        Backend = self.MakeOpenBackend()
        Backend.PrivacyCurtain = True

        Backend.registerActivity()

        Backend.IdleTimer.start.assert_not_called()
        self.assertTrue(Backend.privacyCurtain)

    def testDroppingCurtainCoversPasswordAndClearsOnlyOwnedClipboard(self):
        Backend = self.MakeOpenBackend()
        Backend.PasswordVisible = True
        Backend.RevealTimer = Mock.Mock()
        Backend.ClipboardTimer = Mock.Mock()
        Backend.ClipboardText = "fake copied thing"
        Clipboard = Mock.Mock()
        Clipboard.text.return_value = "fake copied thing"

        with Mock.patch.object(Gui.QGuiApplication, "clipboard", return_value=Clipboard):
            Dropped = Backend.dropPrivacyCurtain("TEST TIMER")

        self.assertTrue(Dropped)
        self.assertTrue(Backend.privacyCurtain)
        self.assertFalse(Backend.passwordVisible)
        Backend.RevealTimer.stop.assert_called_once_with()
        Backend.IdleTimer.stop.assert_called_once_with()
        Backend.ClipboardTimer.stop.assert_called_once_with()
        Clipboard.clear.assert_called_once_with()
        self.assertIn("TEST TIMER", Backend.statusText)

    def testLiftingCurtainRequiresExplicitCallAndRestartsClock(self):
        Backend = self.MakeOpenBackend()
        Backend.PrivacyCurtain = True

        with Mock.patch.object(Gui, "QtTimersAvailable", return_value=True):
            Lifted = Backend.liftPrivacyCurtain()

        self.assertTrue(Lifted)
        self.assertFalse(Backend.privacyCurtain)
        Backend.IdleTimer.start.assert_called_once_with(
            Gui.DEFAULT_IDLE_SECONDS * 1000
        )
        self.assertIn("NOT AN AUTHENTICATION", Backend.statusText)

    def testCursorFilterCountsKeyboardInputAsActivity(self):
        Window = Gui.QObject()
        Backend = Mock.Mock()
        Filter = Gui.CursorEventFilter(Window, Backend)
        Event = Gui.QEvent(Gui.QEvent.Type.KeyPress)

        Filter.eventFilter(Window, Event)

        Backend.registerActivity.assert_called_once_with()


#MARK: doctor and lifeboat stuffs
class UtilityTests(Unittest.TestCase):
    def MakeVault(self, Directory):
        FilePath = Path(Directory) / ".gui-utility.p00p"
        Vault = Main.NewVault()
        Vault["entries"]["fake orbital account"] = {
            "username": "fake-astronaut",
            "password": "Fake-Orbital-Password-246!",
            "notes": "demo only",
            "updated_at": Main.CurrentTime(),
        }
        Main.SaveVault(FilePath, Vault)
        return FilePath

    def testLoadingVaultPopulatesDoctorSummary(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = self.MakeVault(Directory)

            Backend = Gui.VaultBackend(StartPath=FilePath, Settings=MemorySettings())

            self.assertTrue(Backend.hasVault)
            self.assertIn("PASS", Backend.doctorSummary)
            self.assertNotIn("Fake-Orbital-Password-246!", Backend.doctorSummary)
            self.assertIn("1 ENTRIES", Backend.statsSummary)
            self.assertIn("1 BASIC-OK", Backend.statsSummary)
            self.assertNotIn("Fake-Orbital-Password-246!", Backend.statsSummary)

    def testRunDoctorRefreshesSummaryAndStatus(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = self.MakeVault(Directory)
            Backend = Gui.VaultBackend(StartPath=FilePath, Settings=MemorySettings())
            Backend.DoctorSummary = "STALE"

            Result = Backend.runDoctor()

            self.assertTrue(Result)
            self.assertNotEqual(Backend.doctorSummary, "STALE")
            self.assertIn("DOCTOR", Backend.statusText)

    def testGuiStorageLabRunsReadOnlyAndShowsSafeNumbers(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = self.MakeVault(Directory)
            Before = FilePath.read_bytes()
            Backend = Gui.VaultBackend(StartPath=FilePath, Settings=MemorySettings())

            with Mock.patch.object(Gui.QMessageBox, "information") as Information:
                Result = Backend.runStorageLab()

            self.assertTrue(Result)
            self.assertEqual(FilePath.read_bytes(), Before)
            self.assertIn("10 ROUNDS", Backend.labSummary)
            self.assertIn("STORAGE LAB", Backend.statusText)
            ShownText = Information.call_args.args[2]
            self.assertIn("P00P WEIRD STORAGE LAB", ShownText)
            self.assertNotIn("Fake-Orbital-Password-246!", ShownText)

    def testGuiStorageLabFailureIsNonfatalAndRemembered(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = self.MakeVault(Directory)
            Backend = Gui.VaultBackend(StartPath=FilePath, Settings=MemorySettings())

            with Mock.patch.object(
                Gui.Main,
                "StorageLabForVault",
                side_effect=Gui.Lab.LabError("centrifuge escaped"),
            ), Mock.patch.object(Gui.QMessageBox, "critical") as Critical:
                Result = Backend.runStorageLab()

            self.assertFalse(Result)
            self.assertIn("LAB FAILED", Backend.labSummary)
            Critical.assert_called_once()

    def testGuiCanStampAndVerifySecretSafeBowlLedger(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = self.MakeVault(Directory)
            Backend = Gui.VaultBackend(StartPath=FilePath, Settings=MemorySettings())

            Stamped = Backend.stampLedgerCheckpoint()
            Verified = Backend.verifyVaultLedger()

            LedgerPath = Gui.Ledger.SuggestedLedgerPath(FilePath)
            Paperwork = LedgerPath.read_text(encoding="utf-8")
            self.assertTrue(Stamped)
            self.assertTrue(Verified)
            self.assertIn("MATCH", Backend.ledgerSummary)
            self.assertIn("CURRENT BYTES MATCH", Backend.statusText)
            self.assertNotIn("fake-astronaut", Paperwork)
            self.assertNotIn("Fake-Orbital-Password-246!", Paperwork)

    def testGuiSaveMarksLedgerStaleThenVerifierNotices(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = self.MakeVault(Directory)
            Backend = Gui.VaultBackend(StartPath=FilePath, Settings=MemorySettings())
            self.assertTrue(Backend.stampLedgerCheckpoint())
            Backend.Vault["entries"]["fake orbital account"]["notes"] = "changed"

            Saved = Backend._save()
            with Mock.patch.object(Gui.QMessageBox, "warning") as Warning:
                Verified = Backend.verifyVaultLedger()

            self.assertTrue(Saved)
            self.assertFalse(Verified)
            self.assertIn("STALE", Backend.ledgerSummary)
            Warning.assert_called_once()

    def testGuiRefusesToOverwriteBrokenLedger(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = self.MakeVault(Directory)
            LedgerPath = Gui.Ledger.SuggestedLedgerPath(FilePath)
            LedgerPath.write_bytes(b"broken gui paperwork\n")
            Backend = Gui.VaultBackend(StartPath=FilePath, Settings=MemorySettings())

            with Mock.patch.object(Gui.QMessageBox, "critical") as Critical:
                Result = Backend.stampLedgerCheckpoint()

            self.assertFalse(Result)
            self.assertEqual(LedgerPath.read_bytes(), b"broken gui paperwork\n")
            self.assertIn("LEDGER FAILED", Backend.ledgerSummary)
            Critical.assert_called_once()

    def testOneClickLifeboatCopiesExactCurrentVault(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = self.MakeVault(Directory)
            Destination = Path(Directory) / ".gui-lifeboat.p00p"
            Backend = Gui.VaultBackend(StartPath=FilePath, Settings=MemorySettings())

            with Mock.patch.object(
                Gui.Lifeboat,
                "SuggestedSnapshotPath",
                return_value=Destination,
            ):
                Result = Backend.backupVault()

            self.assertTrue(Result)
            self.assertEqual(Destination.read_bytes(), FilePath.read_bytes())
            self.assertEqual(Backend.lastLifeboat, str(Destination))
            self.assertIn("LIFEBOAT LAUNCHED", Backend.statusText)

    def testUtilitiesRefuseToRunWithoutAnOpenVault(self):
        Backend = Gui.VaultBackend(
            StartPath=Path("definitely-not-an-open-vault.p00p"),
            Settings=MemorySettings(),
        )

        self.assertFalse(Backend.runDoctor())
        self.assertFalse(Backend.runStorageLab())
        self.assertFalse(Backend.backupVault())
        self.assertFalse(Backend.rerollCamouflage())
        self.assertFalse(Backend.exportSafeReport())
        self.assertFalse(Backend.mergeAnotherVault())
        self.assertFalse(Backend.stampVaultSeal())
        self.assertFalse(Backend.verifyVaultSeal())
        self.assertFalse(Backend.stampLedgerCheckpoint())
        self.assertFalse(Backend.verifyVaultLedger())
        self.assertIn("NO VAULT", Backend.statusText)

    def testLifeboatFailureDoesNotChangeLastSuccessfulPath(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = self.MakeVault(Directory)
            Backend = Gui.VaultBackend(StartPath=FilePath, Settings=MemorySettings())
            Backend.LastLifeboat = "PREVIOUS GOOD BOAT"

            with Mock.patch.object(
                Gui.Lifeboat,
                "SuggestedSnapshotPath",
                return_value=FilePath,
            ), Mock.patch.object(Gui.QMessageBox, "critical") as Critical:
                Result = Backend.backupVault()

            self.assertFalse(Result)
            self.assertEqual(Backend.lastLifeboat, "PREVIOUS GOOD BOAT")
            Critical.assert_called_once()

    def testGuiCanMakeAndOpenAWholeFakeDemoBowl(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".gui-demo.p00p"
            Backend = Gui.VaultBackend(
                StartPath=Path(Directory) / "nothing-open.p00p",
                Settings=MemorySettings(),
            )

            with Mock.patch.object(
                Gui.QFileDialog,
                "getSaveFileName",
                return_value=(str(FilePath), ""),
            ):
                Result = Backend.newDecoyVault()

            Vault = Main.LoadVault(FilePath)
            self.assertTrue(Result)
            self.assertEqual(len(Vault["entries"]), 24)
            self.assertTrue(all(
                Entry["password"].startswith("FAKE-")
                for Entry in Vault["entries"].values()
            ))
            self.assertEqual(Backend.vaultPath, str(FilePath))
            self.assertIn("DECOY BOWL READY", Backend.statusText)

    def testGuiDecoyDialogCanBeCancelledWithoutMakingAnything(self):
        Backend = Gui.VaultBackend(
            StartPath=Path("nothing-open-for-decoys.p00p"),
            Settings=MemorySettings(),
        )

        with Mock.patch.object(
            Gui.QFileDialog,
            "getSaveFileName",
            return_value=("", ""),
        ):
            Result = Backend.newDecoyVault()

        self.assertFalse(Result)
        self.assertFalse(Backend.hasVault)

    def testGuiDecoyFoundryDoesNotReplaceAFileAfterNo(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = Path(Directory) / ".keep-this.p00p"
            Main.SaveVault(FilePath, Main.NewVault())
            Before = FilePath.read_bytes()
            Backend = Gui.VaultBackend(
                StartPath=Path(Directory) / "nothing-open.p00p",
                Settings=MemorySettings(),
            )

            with Mock.patch.object(
                Gui.QFileDialog,
                "getSaveFileName",
                return_value=(str(FilePath), ""),
            ), Mock.patch.object(
                Gui.QMessageBox,
                "warning",
                return_value=Gui.QMessageBox.StandardButton.No,
            ):
                Result = Backend.newDecoyVault()

            self.assertFalse(Result)
            self.assertEqual(FilePath.read_bytes(), Before)

    def testGuiRerollChangesBytesWithoutChangingOpenData(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = self.MakeVault(Directory)
            Backend = Gui.VaultBackend(StartPath=FilePath, Settings=MemorySettings())
            BeforeBlob = FilePath.read_bytes()
            BeforeVault = Main.LoadVault(FilePath)

            Result = Backend.rerollCamouflage()

            self.assertTrue(Result)
            self.assertNotEqual(FilePath.read_bytes(), BeforeBlob)
            self.assertEqual(Main.LoadVault(FilePath), BeforeVault)
            self.assertEqual(Backend.Vault, BeforeVault)
            self.assertIn("CAMOUFLAGE REROLLED", Backend.statusText)

    def testGuiRerollFailureIsNonfatal(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = self.MakeVault(Directory)
            Backend = Gui.VaultBackend(StartPath=FilePath, Settings=MemorySettings())

            with Mock.patch.object(
                Gui.Main,
                "RerollVault",
                side_effect=Main.P00PError("salt dice exploded"),
            ), Mock.patch.object(Gui.QMessageBox, "critical") as Critical:
                Result = Backend.rerollCamouflage()

            self.assertFalse(Result)
            Critical.assert_called_once()

    def testGuiRerollMarksAnExistingByteSealStale(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath = self.MakeVault(Directory)
            Backend = Gui.VaultBackend(StartPath=FilePath, Settings=MemorySettings())
            self.assertTrue(Backend.stampVaultSeal())

            Rerolled = Backend.rerollCamouflage()

            self.assertTrue(Rerolled)
            self.assertIn("SEAL IS STALE", Backend.sealSummary)
            self.assertFalse(Main.VerifyVaultSeal(FilePath).Passed)

    def testGuiExportsMarkdownReportWithoutCredentials(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            ReportPath = Path(Directory) / "submission.md"
            Backend = Gui.VaultBackend(StartPath=VaultPath, Settings=MemorySettings())

            with Mock.patch.object(
                Gui.QFileDialog,
                "getSaveFileName",
                return_value=(str(ReportPath), ""),
            ):
                Result = Backend.exportSafeReport()

            Text = ReportPath.read_text(encoding="utf-8")
            self.assertTrue(Result)
            self.assertIn("# P00P vault report", Text)
            self.assertNotIn("Fake-Orbital-Password-246!", Text)
            self.assertIn("SAFE REPORT EXPORTED", Backend.statusText)

    def testGuiReportDoesNotReplaceAFileAfterNo(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            ReportPath = Path(Directory) / "keep.md"
            ReportPath.write_text("keep my words\n", encoding="utf-8")
            Backend = Gui.VaultBackend(StartPath=VaultPath, Settings=MemorySettings())

            with Mock.patch.object(
                Gui.QFileDialog,
                "getSaveFileName",
                return_value=(str(ReportPath), ""),
            ), Mock.patch.object(
                Gui.QMessageBox,
                "warning",
                return_value=Gui.QMessageBox.StandardButton.No,
            ):
                Result = Backend.exportSafeReport()

            self.assertFalse(Result)
            self.assertEqual(
                ReportPath.read_text(encoding="utf-8"),
                "keep my words\n",
            )

    def testGuiMergesAnotherBowlIntoASeparateThirdBowl(self):
        with Tempfile.TemporaryDirectory() as Directory:
            LeftPath = self.MakeVault(Directory)
            RightPath = Path(Directory) / ".right.p00p"
            OutputPath = Path(Directory) / ".third.p00p"
            RightVault = Main.NewVault()
            RightVault["entries"]["fake lunar account"] = {
                "username": "fake-moon-user",
                "password": "Fake-Moon-Password-135!",
                "notes": "demo only",
                "updated_at": Main.CurrentTime(),
            }
            Main.SaveVault(RightPath, RightVault)
            Backend = Gui.VaultBackend(StartPath=LeftPath, Settings=MemorySettings())

            with Mock.patch.object(
                Gui.QFileDialog,
                "getOpenFileName",
                return_value=(str(RightPath), ""),
            ), Mock.patch.object(
                Gui.QInputDialog,
                "getItem",
                return_value=("error", True),
            ), Mock.patch.object(
                Gui.QFileDialog,
                "getSaveFileName",
                return_value=(str(OutputPath), ""),
            ):
                Result = Backend.mergeAnotherVault()

            self.assertTrue(Result)
            self.assertEqual(
                set(Main.LoadVault(OutputPath)["entries"]),
                {"fake orbital account", "fake lunar account"},
            )
            self.assertEqual(Backend.vaultPath, str(LeftPath))
            self.assertIn("MERGED THIRD BOWL", Backend.statusText)

    def testGuiMergeConflictLeavesNoOutputAndShowsError(self):
        with Tempfile.TemporaryDirectory() as Directory:
            LeftPath = self.MakeVault(Directory)
            RightPath = Path(Directory) / ".conflict.p00p"
            OutputPath = Path(Directory) / ".not-created.p00p"
            RightVault = Main.NewVault()
            RightVault["entries"]["FAKE ORBITAL ACCOUNT"] = {
                "username": "different-fake-user",
                "password": "Fake-Different-Password-753!",
                "notes": "deliberate conflict",
                "updated_at": Main.CurrentTime(),
            }
            Main.SaveVault(RightPath, RightVault)
            Backend = Gui.VaultBackend(StartPath=LeftPath, Settings=MemorySettings())

            with Mock.patch.object(
                Gui.QFileDialog,
                "getOpenFileName",
                return_value=(str(RightPath), ""),
            ), Mock.patch.object(
                Gui.QInputDialog,
                "getItem",
                return_value=("error", True),
            ), Mock.patch.object(
                Gui.QFileDialog,
                "getSaveFileName",
                return_value=(str(OutputPath), ""),
            ), Mock.patch.object(Gui.QMessageBox, "critical") as Critical:
                Result = Backend.mergeAnotherVault()

            self.assertFalse(Result)
            self.assertFalse(OutputPath.exists())
            Critical.assert_called_once()

    def testGuiMergeCanBeCancelledAtPolicyPicker(self):
        with Tempfile.TemporaryDirectory() as Directory:
            LeftPath = self.MakeVault(Directory)
            RightPath = Path(Directory) / ".right.p00p"
            Main.SaveVault(RightPath, Main.NewVault())
            Backend = Gui.VaultBackend(StartPath=LeftPath, Settings=MemorySettings())

            with Mock.patch.object(
                Gui.QFileDialog,
                "getOpenFileName",
                return_value=(str(RightPath), ""),
            ), Mock.patch.object(
                Gui.QInputDialog,
                "getItem",
                return_value=("error", False),
            ), Mock.patch.object(Gui.QFileDialog, "getSaveFileName") as SaveDialog:
                Result = Backend.mergeAnotherVault()

            self.assertFalse(Result)
            SaveDialog.assert_not_called()

    def testGuiStampsAndVerifiesDefaultByteSeal(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            SealPath = Gui.Seal.SuggestedSealPath(VaultPath)
            Backend = Gui.VaultBackend(StartPath=VaultPath, Settings=MemorySettings())

            Stamped = Backend.stampVaultSeal()
            Verified = Backend.verifyVaultSeal()

            self.assertTrue(Stamped)
            self.assertTrue(Verified)
            self.assertTrue(SealPath.is_file())
            self.assertEqual(SealPath.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("Fake-Orbital-Password-246!", SealPath.read_text())
            self.assertIn("PASS", Backend.sealSummary)
            self.assertIn("EXACT BOWL MATCH", Backend.statusText)

    def testGuiMarksSealStaleAfterItSavesAChange(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            Backend = Gui.VaultBackend(StartPath=VaultPath, Settings=MemorySettings())
            self.assertTrue(Backend.stampVaultSeal())

            Backend.Vault["entries"]["fake orbital account"]["notes"] = "changed"
            Saved = Backend._save()

            self.assertTrue(Saved)
            self.assertIn("MAY BE STALE", Backend.sealSummary)

    def testGuiBrokenSealWarnsInsteadOfPretendingItPassed(self):
        with Tempfile.TemporaryDirectory() as Directory:
            VaultPath = self.MakeVault(Directory)
            Backend = Gui.VaultBackend(StartPath=VaultPath, Settings=MemorySettings())
            self.assertTrue(Backend.stampVaultSeal())
            Vault = Main.LoadVault(VaultPath)
            Vault["entries"]["fake orbital account"]["notes"] = "changed outside gui"
            Main.SaveVault(VaultPath, Vault)

            with Mock.patch.object(Gui.QMessageBox, "warning") as Warning:
                Verified = Backend.verifyVaultSeal()

            self.assertFalse(Verified)
            self.assertIn("FAIL", Backend.sealSummary)
            self.assertIn("SEAL BROKEN", Backend.statusText)
            Warning.assert_called_once()


#MARK: session undo goblin stuffs
class HistoryIntegrationTests(Unittest.TestCase):
    def MakeBackend(self, Directory):
        FilePath = Path(Directory) / ".history.p00p"
        Main.SaveVault(FilePath, Main.NewVault())
        return FilePath, Gui.VaultBackend(
            StartPath=FilePath,
            Settings=MemorySettings(),
        )

    def testAddCanUndoAndRedoAllTheWayThroughDisk(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath, Backend = self.MakeBackend(Directory)

            Added = Backend.addEntry(
                "fake moon", "astronaut", "Fake-Moon-Password-123!", "demo"
            )
            self.assertTrue(Added)
            self.assertTrue(Backend.canUndo)
            self.assertIn("fake moon", Main.LoadVault(FilePath)["entries"])

            self.assertTrue(Backend.undo())
            self.assertNotIn("fake moon", Main.LoadVault(FilePath)["entries"])
            self.assertTrue(Backend.canRedo)

            self.assertTrue(Backend.redo())
            self.assertIn("fake moon", Main.LoadVault(FilePath)["entries"])
            self.assertEqual(Backend.selectedName, "fake moon")

    def testRemoveThenUndoRestoresTheWholeEntry(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath, Backend = self.MakeBackend(Directory)
            Backend.addEntry(
                "fake bank", "fake-user", "Fake-Bank-Password-456!", "keep me"
            )
            Expected = Main.LoadVault(FilePath)["entries"]["fake bank"]
            Backend.History.Clear()

            with Mock.patch.object(
                Gui.QMessageBox,
                "question",
                return_value=Gui.QMessageBox.StandardButton.Yes,
            ):
                Backend.removeEntry()
            self.assertNotIn("fake bank", Main.LoadVault(FilePath)["entries"])

            self.assertTrue(Backend.undo())
            self.assertEqual(
                Main.LoadVault(FilePath)["entries"]["fake bank"],
                Expected,
            )

    def testDeleteAllIsActuallyUndoableDuringTheSession(self):
        with Tempfile.TemporaryDirectory() as Directory:
            FilePath, Backend = self.MakeBackend(Directory)
            Backend.addEntry("one", "u", "Fake-One-Password-123!", "")
            Backend.addEntry("two", "u", "Fake-Two-Password-456!", "")
            Backend.History.Clear()

            with Mock.patch.object(
                Gui.QMessageBox,
                "warning",
                return_value=Gui.QMessageBox.StandardButton.Yes,
            ):
                self.assertTrue(Backend.deleteAllEntries())
            self.assertEqual(Main.LoadVault(FilePath)["entries"], {})

            self.assertTrue(Backend.undo())
            self.assertEqual(
                set(Main.LoadVault(FilePath)["entries"]),
                {"one", "two"},
            )

    def testFailedUndoDoesNotLieOrMoveTheTimeline(self):
        with Tempfile.TemporaryDirectory() as Directory:
            _, Backend = self.MakeBackend(Directory)
            Backend.addEntry("stay", "u", "Fake-Stay-Password-789!", "")
            self.assertTrue(Backend.canUndo)

            with Mock.patch.object(Backend, "_save", return_value=False):
                Result = Backend.undo()

            self.assertFalse(Result)
            self.assertIn("stay", Backend.Vault["entries"])
            self.assertTrue(Backend.canUndo)
            self.assertFalse(Backend.canRedo)

    def testOpeningAnotherVaultFlushesTheOldBowlsTimeline(self):
        with Tempfile.TemporaryDirectory() as Directory:
            _, Backend = self.MakeBackend(Directory)
            Backend.addEntry("old", "u", "Fake-Old-Password-159!", "")
            self.assertTrue(Backend.canUndo)
            OtherPath = Path(Directory) / ".other.p00p"
            Main.SaveVault(OtherPath, Main.NewVault())

            self.assertTrue(Backend._load(OtherPath, Quiet=True))

            self.assertFalse(Backend.canUndo)
            self.assertFalse(Backend.canRedo)
            self.assertEqual(Backend.vaultPath, str(OtherPath))


#MARK: keyboard row stuffs
class SelectionTests(Unittest.TestCase):
    def MakeBackend(self):
        Backend = Gui.VaultBackend(Settings=MemorySettings())
        Backend.Vault = Main.NewVault()
        Backend.Vault["entries"].update({
            "alpha": {"username": "z-user", "password": "fake-a", "notes": ""},
            "beta": {"username": "a-user", "password": "fake-b", "notes": "moon"},
            "gamma": {"username": "m-user", "password": "fake-c", "notes": ""},
        })
        Backend.SelectedName = "alpha"
        return Backend

    def testRelativeSelectionWrapsInVisibleSortOrder(self):
        Backend = self.MakeBackend()
        Moved = []
        Backend.selectionMoved.connect(Moved.append)

        Backend.selectRelative(-1)

        self.assertEqual(Backend.selectedName, "gamma")
        self.assertEqual(Moved, [2])

    def testRelativeSelectionUsesFilteredRowsNotHiddenRows(self):
        Backend = self.MakeBackend()
        Backend.Query = "moon"

        Backend.selectRelative(1)

        self.assertEqual(Backend.selectedName, "beta")

    def testRowSelectionUsesTheCurrentUsernameSort(self):
        Backend = self.MakeBackend()
        Backend.SortColumn = "username"

        Backend.selectRow(0)
        self.assertEqual(Backend.selectedName, "beta")
        Backend.selectRow(99)
        self.assertEqual(Backend.selectedName, "alpha")

    def testKeyboardSelectionCoversAVisiblePassword(self):
        Backend = self.MakeBackend()
        Backend.PasswordVisible = True
        Backend.RevealTimer = Mock.Mock()

        Backend.selectRelative(1)

        self.assertFalse(Backend.passwordVisible)
        Backend.RevealTimer.stop.assert_called_once_with()


#MARK: qt command stuffs
class QtCommandTests(Unittest.TestCase):
    def testVaultArgumentPointsAtTheRequestedBowl(self):
        Args = Gui.BuildQtParser().parse_args(("--vault", ".space.poop"))

        self.assertEqual(Args.vault, Path(".space.poop"))

    def testVaultArgumentCanBeLeftOut(self):
        Args = Gui.BuildQtParser().parse_args(())

        self.assertIsNone(Args.vault)


if __name__ == "__main__":
    Unittest.main()
