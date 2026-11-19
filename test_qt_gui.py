import unittest as Unittest

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


if __name__ == "__main__":
    Unittest.main()
