#------------------------------------------------------------------#
# p00p security theater applause calculator                        #
# measures vibes. absolutely does not measure security             #
#------------------------------------------------------------------#

import hashlib as Hashlib
from pathlib import Path


#MARK: paperwork for every extremely serious check
class CueResult:
    def __init__(self, Name, Passed, Points, Explanation):
        self.Name = Name
        self.Passed = bool(Passed)
        self.Points = Points if self.Passed else 0
        self.Possible = Points
        self.Explanation = Explanation

    def AsLine(self):
        Mark = "✓" if self.Passed else "✗"
        return f"{Mark} {self.Name}: {self.Points}/{self.Possible} — {self.Explanation}"


class TheaterContext:
    def __init__(self, Vault, FilePath, Blob, Header, RitualReceipts):
        self.Vault = Vault
        self.FilePath = Path(FilePath)
        self.Blob = Blob
        self.Header = Header
        self.RitualReceipts = tuple(RitualReceipts)


class TheaterCue:
    Name = "unnamed dramatic pause"
    Points = 0

    def Result(self, Context):
        Passed, Explanation = self.Inspect(Context)
        return CueResult(self.Name, Passed, self.Points, Explanation)


#MARK: individual acts in the show
class HiddenFilenameCue(TheaterCue):
    Name = "dotfile invisibility cloak"
    Points = 15

    def Inspect(self, Context):
        Passed = Context.FilePath.name.startswith(".")
        Explanation = "filename starts with a dot" if Passed else "filename is visible to normal humans"
        return Passed, Explanation


class SuspiciousExtensionCue(TheaterCue):
    Name = "wrong-extension mustache"
    Points = 10

    def Inspect(self, Context):
        Passed = Context.FilePath.suffix.casefold() in {".p00p", ".poop"}
        Explanation = "uses a deeply professional poop extension" if Passed else "extension lacks poop energy"
        return Passed, Explanation


class OwnerOnlyCue(TheaterCue):
    Name = "owner-only bathroom lock"
    Points = 20

    def Inspect(self, Context):
        try:
            Mode = Context.FilePath.stat().st_mode & 0o777
        except OSError:
            return False, "permissions could not be inspected"
        Passed = Mode & 0o077 == 0
        Explanation = f"permissions are {Mode:03o}"
        return Passed, Explanation


class PlaintextDisappearingCue(TheaterCue):
    Name = "plaintext disappearing act"
    Points = 20

    def Inspect(self, Context):
        Tokens = []
        for Name, Entry in Context.Vault.get("entries", {}).items():
            Tokens.extend((Name, Entry.get("username", ""), Entry.get("password", ""),
                           Entry.get("notes", "")))
        LongTokens = [Token.encode("utf-8") for Token in Tokens if len(Token.encode("utf-8")) >= 8]
        Leaks = sum(Token in Context.Blob for Token in LongTokens)
        Passed = Leaks == 0
        Explanation = "no long entry strings appear directly" if Passed else f"{Leaks} long string(s) appear directly"
        return Passed, Explanation


class SaltShakerCue(TheaterCue):
    Name = "ceremonial salt shaker"
    Points = 10

    def Inspect(self, Context):
        Salt = Context.Header.get("salt", b"")
        Passed = len(Salt) == 16 and Salt != bytes(16)
        Explanation = "16 nonzero-ish salt bytes are present" if Passed else "salt looks missing or suspiciously zero"
        return Passed, Explanation


class ChecksumCurtainCallCue(TheaterCue):
    Name = "checksum curtain call"
    Points = 15

    def Inspect(self, Context):
        Digest = Context.Header.get("digest", b"")
        Expected = Hashlib.sha256(Context.Blob[:-len(Digest)]).digest()[:len(Digest)] if Digest else b""
        Passed = bool(Digest) and Digest == Expected
        Explanation = "the audience detected no accidental corruption" if Passed else "the checksum forgot its lines"
        return Passed, Explanation


class PooplinePaperworkCue(TheaterCue):
    Name = "three-goblin paperwork chain"
    Points = 10
    ExpectedStages = ("json goblin", "trash compactor", "toilet curtain")

    def Inspect(self, Context):
        ActualStages = tuple(Receipt.get("stage") for Receipt in Context.RitualReceipts)
        Passed = ActualStages == self.ExpectedStages
        Explanation = "all three goblins signed their receipts" if Passed else "the goblin paperwork is incomplete"
        return Passed, Explanation


#MARK: applause meter management hierarchy
class ApplauseMeter:
    Ratings = (
        (25, "transparent toilet"),
        (50, "cardboard firewall"),
        (75, "premium camouflage vibes"),
        (100, "military-grade-looking nonsense"),
        (101, "maximum security theater"),
    )

    def __init__(self, Results):
        self.Results = tuple(Results)
        self.Score = sum(Result.Points for Result in self.Results)
        self.Possible = sum(Result.Possible for Result in self.Results)

    def Rating(self):
        for Ceiling, Label in self.Ratings:
            if self.Score < Ceiling:
                return Label
        return self.Ratings[-1][1]

    def AsText(self):
        Lines = [
            f"SECURITY THEATER: {self.Score}/{self.Possible} applause points",
            f"rating: {self.Rating()}",
            "",
        ]
        Lines.extend(Result.AsLine() for Result in self.Results)
        Lines.extend((
            "",
            "IMPORTANT: this is a joke score, not a security score.",
            "camouflage still is not encryption. only use fake passwords.",
        ))
        return "\n".join(Lines)


class CueBook:
    def __init__(self, Cues=None):
        self.Cues = tuple(Cues or (
            HiddenFilenameCue(),
            SuspiciousExtensionCue(),
            OwnerOnlyCue(),
            PlaintextDisappearingCue(),
            SaltShakerCue(),
            ChecksumCurtainCallCue(),
            PooplinePaperworkCue(),
        ))

    def StartShow(self, Context):
        return ApplauseMeter(Cue.Result(Context) for Cue in self.Cues)


DEFAULT_CUE_BOOK = CueBook()


def ScoreSecurityTheater(Vault, FilePath, Blob, Header, RitualReceipts):
    Context = TheaterContext(Vault, FilePath, Blob, Header, RitualReceipts)
    return DEFAULT_CUE_BOOK.StartShow(Context)
