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


#MARK: future beep boop stuffs
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

        self.assertEqual(Backend.volume, 37)
        self.assertFalse(Backend.sfxEnabled)
        self.assertFalse(Backend.shaderEnabled)
        self.assertEqual(Backend.clipboardSeconds, 42)
        self.assertEqual(Backend.revealSeconds, 31)
        self.assertEqual(Settings.Values["audio/volume"], 37)
        self.assertFalse(Settings.Values["audio/enabled"])
        self.assertFalse(Settings.Values["display/shader"])
        self.assertEqual(Settings.Values["privacy/clipboard_seconds"], 42)
        self.assertEqual(Settings.Values["privacy/reveal_seconds"], 31)

        Reloaded = Gui.VaultBackend(Settings=Settings)
        self.assertEqual(Reloaded.volume, 37)
        self.assertFalse(Reloaded.sfxEnabled)
        self.assertFalse(Reloaded.shaderEnabled)
        self.assertEqual(Reloaded.clipboardSeconds, 42)
        self.assertEqual(Reloaded.revealSeconds, 31)

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

    def testPrivacyTimersDriveTheActualSingleShots(self):
        Settings = MemorySettings({
            "privacy/clipboard_seconds": 17,
            "privacy/reveal_seconds": 29,
        })
        Backend = Gui.VaultBackend(Settings=Settings)
        Backend.Vault = Main.NewVault()
        Backend.Vault["entries"]["timer"] = {"password": "fake"}
        Backend.SelectedName = "timer"

        with Mock.patch.object(Gui.QTimer, "singleShot") as SingleShot:
            Backend._clear_clipboard_later("fake")
            Backend.togglePassword()

        self.assertEqual(SingleShot.call_args_list[0].args[0], 17_000)
        self.assertEqual(SingleShot.call_args_list[1].args[0], 29_000)

    def testResetOnlyResetsAppKnobs(self):
        Settings = MemorySettings({"audio/volume": 12, "display/shader": False})
        Backend = Gui.VaultBackend(Settings=Settings)

        Backend.resetSettings()

        self.assertEqual(Backend.volume, Gui.DEFAULT_VOLUME)
        self.assertEqual(Backend.sfxEnabled, Gui.DEFAULT_SFX_ENABLED)
        self.assertEqual(Backend.shaderEnabled, Gui.DEFAULT_SHADER_ENABLED)
        self.assertEqual(Backend.clipboardSeconds, Gui.DEFAULT_CLIPBOARD_SECONDS)
        self.assertEqual(Backend.revealSeconds, Gui.DEFAULT_REVEAL_SECONDS)

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
