import unittest as Unittest
from pathlib import Path

import qt_gui as Gui


#MARK: future beep boop stuffs
class SoundHookTests(Unittest.TestCase):
    def testKnownCueReachesTheOneSoundHook(self):
        Backend = Gui.VaultBackend()
        Heard = []
        Backend.soundRequested.connect(Heard.append)

        Backend.requestSound(" UI_CLICK ")

        self.assertEqual(Heard, ["ui_click"])

    def testTypoCueDoesNotSummonRandomAudio(self):
        Backend = Gui.VaultBackend()
        Heard = []
        Backend.soundRequested.connect(Heard.append)

        Backend.requestSound("ui_clonk")

        self.assertEqual(Heard, [])

    def testEveryCueHasOneObviousNoOpLandingSpot(self):
        for Cue in Gui.SOUND_CUES:
            self.assertIsNone(Gui.HandleSoundCue(Cue))


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
