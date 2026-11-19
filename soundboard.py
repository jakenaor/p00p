#------------------------------------------------------------------#
# p00p procedural beep goblin                                     #
# tiny retro wavs made at runtime so the repo needs zero sound files#
#------------------------------------------------------------------#

import hashlib as Hashlib
import math as Math
import os as Os
import struct as Struct
import tempfile as Tempfile
import wave as Wave
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtMultimedia import QSoundEffect


SAMPLE_RATE = 22_050
SAMPLE_WIDTH = 2
CHANNELS = 1
SYNTH_VERSION = 1
MAX_AMPLITUDE = 32_767
DEFAULT_ATTACK_MS = 3
DEFAULT_RELEASE_MS = 8


def Clamp(Value, Minimum, Maximum):
    return max(Minimum, min(Maximum, Value))


#MARK: sheet music for extremely small musicians
class ToneStep:
    SupportedWaveforms = frozenset({"square", "triangle", "sine", "noise", "silence"})

    def __init__(
        self,
        Frequency,
        DurationMs,
        Waveform="square",
        Amplitude=0.55,
        EndFrequency=None,
        AttackMs=DEFAULT_ATTACK_MS,
        ReleaseMs=DEFAULT_RELEASE_MS,
    ):
        Waveform = str(Waveform).casefold()
        if Waveform not in self.SupportedWaveforms:
            raise ValueError(f"unsupported waveform: {Waveform}")
        if float(DurationMs) <= 0:
            raise ValueError("tone duration must be positive")
        if Waveform != "silence" and float(Frequency) <= 0:
            raise ValueError("audible tone frequency must be positive")
        self.Frequency = float(Frequency)
        self.EndFrequency = float(EndFrequency if EndFrequency is not None else Frequency)
        self.DurationMs = float(DurationMs)
        self.Waveform = Waveform
        self.Amplitude = Clamp(float(Amplitude), 0.0, 1.0)
        self.AttackMs = max(0.0, float(AttackMs))
        self.ReleaseMs = max(0.0, float(ReleaseMs))

    @property
    def SampleCount(self):
        return max(1, round(SAMPLE_RATE * self.DurationMs / 1000))


class CueScore:
    def __init__(self, Name, Steps, Gain=1.0):
        self.Name = str(Name)
        self.Steps = tuple(Steps)
        self.Gain = Clamp(float(Gain), 0.0, 1.0)
        if not self.Name:
            raise ValueError("cue score needs a name")
        if not self.Steps:
            raise ValueError("cue score needs at least one tone")

    @property
    def DurationMs(self):
        return sum(Step.DurationMs for Step in self.Steps)

    @property
    def SampleCount(self):
        return sum(Step.SampleCount for Step in self.Steps)


def Tone(Frequency, DurationMs, **Options):
    return ToneStep(Frequency, DurationMs, **Options)


def Slide(Start, End, DurationMs, **Options):
    return ToneStep(Start, DurationMs, EndFrequency=End, **Options)


def Rest(DurationMs):
    return ToneStep(1, DurationMs, Waveform="silence", Amplitude=0)


CUE_SCORES = {
    "ui_click": CueScore("ui_click", (
        Tone(820, 34, Amplitude=0.38, ReleaseMs=5),
    ), Gain=0.55),
    "dialog_open": CueScore("dialog_open", (
        Slide(420, 720, 58, Waveform="triangle", Amplitude=0.48),
        Tone(910, 45, Waveform="square", Amplitude=0.35),
    ), Gain=0.62),
    "dialog_close": CueScore("dialog_close", (
        Slide(760, 340, 85, Waveform="triangle", Amplitude=0.42),
    ), Gain=0.58),
    "vault_open": CueScore("vault_open", (
        Tone(330, 55, Waveform="triangle"),
        Tone(495, 55, Waveform="triangle"),
        Tone(660, 90, Waveform="square", Amplitude=0.42),
    ), Gain=0.66),
    "vault_new": CueScore("vault_new", (
        Tone(392, 50, Waveform="triangle"),
        Tone(523.25, 50, Waveform="triangle"),
        Tone(659.25, 50, Waveform="triangle"),
        Tone(783.99, 105, Waveform="square", Amplitude=0.42),
    ), Gain=0.68),
    "vault_close": CueScore("vault_close", (
        Tone(523.25, 55, Waveform="triangle"),
        Tone(392, 85, Waveform="triangle"),
        Slide(260, 150, 90, Waveform="square", Amplitude=0.28),
    ), Gain=0.58),
    "doctor": CueScore("doctor", (
        Tone(440, 45, Waveform="square", Amplitude=0.32),
        Rest(28),
        Tone(440, 45, Waveform="square", Amplitude=0.32),
        Rest(28),
        Tone(880, 95, Waveform="triangle", Amplitude=0.5),
    ), Gain=0.64),
    "backup": CueScore("backup", (
        Slide(260, 520, 85, Waveform="triangle", Amplitude=0.5),
        Tone(659.25, 65, Waveform="square", Amplitude=0.36),
        Tone(987.77, 105, Waveform="triangle", Amplitude=0.48),
    ), Gain=0.66),
    "entry_save": CueScore("entry_save", (
        Tone(523.25, 48, Waveform="triangle"),
        Tone(783.99, 85, Waveform="square", Amplitude=0.38),
    ), Gain=0.61),
    "entry_remove": CueScore("entry_remove", (
        Tone(310, 55, Waveform="square", Amplitude=0.38),
        Slide(260, 110, 105, Waveform="triangle", Amplitude=0.52),
    ), Gain=0.62),
    "delete_all": CueScore("delete_all", (
        Tone(160, 85, Waveform="square", Amplitude=0.58),
        Tone(120, 110, Waveform="square", Amplitude=0.58),
        Tone(80, 160, Waveform="noise", Amplitude=0.46, ReleaseMs=35),
    ), Gain=0.72),
    "generate": CueScore("generate", (
        Slide(330, 990, 115, Waveform="triangle", Amplitude=0.48),
        Tone(1320, 45, Waveform="square", Amplitude=0.3),
    ), Gain=0.58),
    "copy": CueScore("copy", (
        Tone(1046.5, 35, Waveform="triangle", Amplitude=0.42),
        Rest(16),
        Tone(1318.5, 42, Waveform="triangle", Amplitude=0.42),
    ), Gain=0.54),
    "reveal": CueScore("reveal", (
        Slide(240, 720, 120, Waveform="sine", Amplitude=0.46),
    ), Gain=0.58),
    "hide": CueScore("hide", (
        Slide(720, 210, 105, Waveform="sine", Amplitude=0.4),
    ), Gain=0.54),
    # reserved for a future nope/permission-denied action; generic failures keep "error".
    "denied": CueScore("denied", (
        Tone(240, 48, Waveform="square", Amplitude=0.5, ReleaseMs=7),
        Rest(18),
        Slide(190, 105, 105, Waveform="square", Amplitude=0.56, ReleaseMs=24),
    ), Gain=0.68),
    "error": CueScore("error", (
        Tone(180, 80, Waveform="square", Amplitude=0.58),
        Rest(32),
        Tone(145, 125, Waveform="square", Amplitude=0.58),
    ), Gain=0.72),
    "easter_egg": CueScore("easter_egg", (
        Tone(261.63, 55, Waveform="square", Amplitude=0.4),
        Tone(329.63, 55, Waveform="square", Amplitude=0.4),
        Tone(392, 55, Waveform="square", Amplitude=0.4),
        Tone(523.25, 55, Waveform="square", Amplitude=0.4),
        Tone(659.25, 55, Waveform="square", Amplitude=0.4),
        Tone(783.99, 145, Waveform="triangle", Amplitude=0.56),
    ), Gain=0.7),
}
CUE_NAMES = frozenset(CUE_SCORES)


#MARK: tiny deterministic synthesizer
class NoiseGoblin:
    def __init__(self, Seed):
        Digest = Hashlib.sha256(str(Seed).encode("utf-8")).digest()
        self.State = int.from_bytes(Digest[:4], "big") or 0xA5A5A5A5

    def Next(self):
        # xorshift32 makes repeatable fake static without importing random state.
        self.State ^= (self.State << 13) & 0xFFFFFFFF
        self.State ^= self.State >> 17
        self.State ^= (self.State << 5) & 0xFFFFFFFF
        self.State &= 0xFFFFFFFF
        return (self.State / 0xFFFFFFFF) * 2.0 - 1.0


def Envelope(SampleIndex, SampleCount, AttackSamples, ReleaseSamples):
    Attack = 1.0
    if AttackSamples > 0 and SampleIndex < AttackSamples:
        Attack = SampleIndex / AttackSamples
    Remaining = SampleCount - SampleIndex - 1
    Release = 1.0
    if ReleaseSamples > 0 and Remaining < ReleaseSamples:
        Release = Remaining / ReleaseSamples
    return Clamp(min(Attack, Release), 0.0, 1.0)


def WaveValue(Waveform, Phase, Noise):
    Wrapped = Phase % 1.0
    if Waveform == "square":
        return 1.0 if Wrapped < 0.5 else -1.0
    if Waveform == "triangle":
        return 1.0 - 4.0 * abs(Wrapped - 0.5)
    if Waveform == "sine":
        return Math.sin(Wrapped * Math.tau)
    if Waveform == "noise":
        return Noise.Next()
    return 0.0


def RenderScoreSamples(Score):
    if not isinstance(Score, CueScore):
        raise TypeError("RenderScoreSamples expects a CueScore")
    Noise = NoiseGoblin(Score.Name)
    Samples = []
    Phase = 0.0
    for Step in Score.Steps:
        Count = Step.SampleCount
        AttackSamples = round(SAMPLE_RATE * Step.AttackMs / 1000)
        ReleaseSamples = round(SAMPLE_RATE * Step.ReleaseMs / 1000)
        for Index in range(Count):
            Progress = Index / max(1, Count - 1)
            Frequency = Step.Frequency + (Step.EndFrequency - Step.Frequency) * Progress
            Phase += Frequency / SAMPLE_RATE
            Value = WaveValue(Step.Waveform, Phase, Noise)
            Value *= Envelope(Index, Count, AttackSamples, ReleaseSamples)
            Value *= Step.Amplitude
            Samples.append(round(Clamp(Value, -1.0, 1.0) * MAX_AMPLITUDE))
    return tuple(Samples)


def RenderWaveBytes(Score):
    Samples = RenderScoreSamples(Score)
    Output = Tempfile.SpooledTemporaryFile(max_size=2 * 1024 * 1024)
    with Wave.open(Output, "wb") as Writer:
        Writer.setnchannels(CHANNELS)
        Writer.setsampwidth(SAMPLE_WIDTH)
        Writer.setframerate(SAMPLE_RATE)
        Writer.writeframes(Struct.pack(f"<{len(Samples)}h", *Samples))
    Output.seek(0)
    Data = Output.read()
    Output.close()
    return Data


#MARK: nonblocking qt playback and wav cache
class RetroSoundBoard:
    def __init__(self, Parent=None, EffectFactory=None, CacheDirectory=None):
        self.Parent = Parent
        self.EffectFactory = EffectFactory or QSoundEffect
        self.Effects = {}
        self.OwnsCache = CacheDirectory is None
        self.CacheOwner = Tempfile.TemporaryDirectory(prefix="p00p-beeps-") if self.OwnsCache else None
        self.CacheDirectory = Path(
            self.CacheOwner.name if self.CacheOwner is not None else CacheDirectory
        )
        self.CacheDirectory.mkdir(parents=True, exist_ok=True)
        self.Closed = False

    def _path_for(self, Cue):
        return self.CacheDirectory / f"p00p-synth-v{SYNTH_VERSION}-{Cue}.wav"

    def _ensure_wave(self, Cue):
        FilePath = self._path_for(Cue)
        if FilePath.is_file() and FilePath.stat().st_size > 44:
            return FilePath
        Data = RenderWaveBytes(CUE_SCORES[Cue])
        Temporary = FilePath.with_suffix(".wav.making")
        try:
            Temporary.write_bytes(Data)
            Os.replace(Temporary, FilePath)
        finally:
            try:
                Temporary.unlink(missing_ok=True)
            except OSError:
                pass
        return FilePath

    def _new_effect(self):
        try:
            return self.EffectFactory(self.Parent)
        except TypeError:
            return self.EffectFactory()

    def _effect_for(self, Cue):
        Effect = self.Effects.get(Cue)
        if Effect is not None:
            return Effect
        Effect = self._new_effect()
        Effect.setSource(QUrl.fromLocalFile(str(self._ensure_wave(Cue))))
        self.Effects[Cue] = Effect
        return Effect

    def Play(self, Cue, Volume):
        Cue = str(Cue).strip().casefold()
        if self.Closed or Cue not in CUE_SCORES:
            return False
        NormalizedVolume = Clamp(float(Volume), 0.0, 100.0) / 100.0
        if NormalizedVolume <= 0:
            return False
        Effect = self._effect_for(Cue)
        Effect.setVolume(NormalizedVolume * CUE_SCORES[Cue].Gain)
        # stopping first makes a repeated click restart immediately instead of being dropped.
        if hasattr(Effect, "stop"):
            Effect.stop()
        Effect.play()
        return True

    def Close(self):
        if self.Closed:
            return
        self.Closed = True
        for Effect in self.Effects.values():
            try:
                Effect.stop()
            except (AttributeError, RuntimeError):
                pass
        self.Effects.clear()
        if self.CacheOwner is not None:
            self.CacheOwner.cleanup()
            self.CacheOwner = None


_GLOBAL_BOARD = None


def GetSoundBoard():
    global _GLOBAL_BOARD
    Application = QCoreApplication.instance()
    if Application is None:
        return None
    if _GLOBAL_BOARD is None or _GLOBAL_BOARD.Closed:
        _GLOBAL_BOARD = RetroSoundBoard(Parent=Application)
        Application.aboutToQuit.connect(_GLOBAL_BOARD.Close)
    return _GLOBAL_BOARD


def PlayCue(Cue, Volume):
    Board = GetSoundBoard()
    if Board is None:
        return False
    try:
        return Board.Play(Cue, Volume)
    except (OSError, RuntimeError, ValueError):
        # audio failure must never take the password bowl down with it.
        return False
