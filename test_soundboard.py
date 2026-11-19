import io as Io
import tempfile as Tempfile
import unittest as Unittest
import wave as Wave
from pathlib import Path
from unittest import mock as Mock

import soundboard as Soundboard


class FakeEffect:
    def __init__(self, Parent=None):
        self.Parent = Parent
        self.Source = None
        self.Volume = None
        self.PlayCount = 0
        self.StopCount = 0

    def setSource(self, Source):
        self.Source = Source

    def setVolume(self, Volume):
        self.Volume = Volume

    def play(self):
        self.PlayCount += 1

    def stop(self):
        self.StopCount += 1


#MARK: waveform goblin stuffs
class SynthesizerTests(Unittest.TestCase):
    def testEveryDeclaredCueRendersAsReadableMonoPcmWave(self):
        for Name, Score in Soundboard.CUE_SCORES.items():
            with self.subTest(cue=Name):
                Data = Soundboard.RenderWaveBytes(Score)
                self.assertTrue(Data.startswith(b"RIFF"))
                self.assertEqual(Data[8:12], b"WAVE")
                with Wave.open(Io.BytesIO(Data), "rb") as Reader:
                    self.assertEqual(Reader.getnchannels(), Soundboard.CHANNELS)
                    self.assertEqual(Reader.getsampwidth(), Soundboard.SAMPLE_WIDTH)
                    self.assertEqual(Reader.getframerate(), Soundboard.SAMPLE_RATE)
                    self.assertEqual(Reader.getnframes(), Score.SampleCount)

    def testRenderedSamplesStayInsideSignedSixteenBitRange(self):
        for Score in Soundboard.CUE_SCORES.values():
            Samples = Soundboard.RenderScoreSamples(Score)
            self.assertGreater(len(Samples), 0)
            self.assertGreaterEqual(min(Samples), -Soundboard.MAX_AMPLITUDE)
            self.assertLessEqual(max(Samples), Soundboard.MAX_AMPLITUDE)

    def testAttackAndReleaseBringToneBackToZero(self):
        Score = Soundboard.CueScore("enveloped", (
            Soundboard.Tone(440, 100, AttackMs=10, ReleaseMs=10),
        ))

        Samples = Soundboard.RenderScoreSamples(Score)

        self.assertEqual(Samples[0], 0)
        self.assertEqual(Samples[-1], 0)
        self.assertTrue(any(Sample != 0 for Sample in Samples[100:-100]))

    def testNoiseAndEveryOtherWaveformAreDeterministic(self):
        for Name, Score in Soundboard.CUE_SCORES.items():
            with self.subTest(cue=Name):
                self.assertEqual(
                    Soundboard.RenderScoreSamples(Score),
                    Soundboard.RenderScoreSamples(Score),
                )

    def testPitchSlideChangesTheProducedSignal(self):
        Flat = Soundboard.CueScore("flat", (Soundboard.Tone(220, 100),))
        Sliding = Soundboard.CueScore("slide", (Soundboard.Slide(220, 880, 100),))

        self.assertNotEqual(
            Soundboard.RenderScoreSamples(Flat),
            Soundboard.RenderScoreSamples(Sliding),
        )

    def testInvalidSheetMusicIsRejectedEarly(self):
        with self.assertRaisesRegex(ValueError, "waveform"):
            Soundboard.Tone(440, 20, Waveform="kazoo")
        with self.assertRaisesRegex(ValueError, "duration"):
            Soundboard.Tone(440, 0)
        with self.assertRaisesRegex(ValueError, "frequency"):
            Soundboard.Tone(0, 20)
        with self.assertRaisesRegex(ValueError, "at least one"):
            Soundboard.CueScore("empty", ())

    def testCueRegistryAndQtRegistryCannotDriftApart(self):
        import qt_gui as Gui

        self.assertEqual(Gui.SOUND_CUES, frozenset(Soundboard.CUE_SCORES))


#MARK: nonblocking board stuffs
class SoundBoardTests(Unittest.TestCase):
    def testKnownCueBuildsOneEffectAndRestartsItOnEveryPlay(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Board = Soundboard.RetroSoundBoard(
                EffectFactory=FakeEffect,
                CacheDirectory=Directory,
            )

            self.assertTrue(Board.Play("ui_click", 50))
            self.assertTrue(Board.Play(" UI_CLICK ", 75))

            self.assertEqual(len(Board.Effects), 1)
            Effect = Board.Effects["ui_click"]
            self.assertEqual(Effect.PlayCount, 2)
            self.assertEqual(Effect.StopCount, 2)
            self.assertAlmostEqual(
                Effect.Volume,
                0.75 * Soundboard.CUE_SCORES["ui_click"].Gain,
            )
            self.assertTrue(Path(Effect.Source.toLocalFile()).is_file())

    def testWaveCacheRendersEachCueOnlyOnce(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Board = Soundboard.RetroSoundBoard(
                EffectFactory=FakeEffect,
                CacheDirectory=Directory,
            )
            with Mock.patch.object(
                Soundboard,
                "RenderWaveBytes",
                wraps=Soundboard.RenderWaveBytes,
            ) as Render:
                First = Board._ensure_wave("copy")
                Second = Board._ensure_wave("copy")

            self.assertEqual(First, Second)
            Render.assert_called_once_with(Soundboard.CUE_SCORES["copy"])

    def testUnknownSilentOrClosedPlaybackIsIgnored(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Board = Soundboard.RetroSoundBoard(
                EffectFactory=FakeEffect,
                CacheDirectory=Directory,
            )

            self.assertFalse(Board.Play("invented_noise", 50))
            self.assertFalse(Board.Play("copy", 0))
            Board.Close()
            self.assertFalse(Board.Play("copy", 50))
            self.assertEqual(Board.Effects, {})

    def testOwnedTemporaryCacheDisappearsOnClose(self):
        Board = Soundboard.RetroSoundBoard(EffectFactory=FakeEffect)
        CacheDirectory = Board.CacheDirectory
        Board.Play("error", 100)

        self.assertTrue(CacheDirectory.is_dir())
        Board.Close()

        self.assertFalse(CacheDirectory.exists())

    def testMasterVolumeIsClampedBeforeCueGain(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Board = Soundboard.RetroSoundBoard(
                EffectFactory=FakeEffect,
                CacheDirectory=Directory,
            )

            Board.Play("backup", 9000)

            self.assertEqual(
                Board.Effects["backup"].Volume,
                Soundboard.CUE_SCORES["backup"].Gain,
            )

    def testGlobalHelperIsQuietWhenNoQtApplicationExists(self):
        with Mock.patch.object(Soundboard.QCoreApplication, "instance", return_value=None):
            self.assertIsNone(Soundboard.GetSoundBoard())
            self.assertFalse(Soundboard.PlayCue("ui_click", 50))


if __name__ == "__main__":
    Unittest.main()
