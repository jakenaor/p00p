#------------------------------------------------------------------#
# p00p vault doctor                                                #
# a suspiciously elaborate clinic for one tiny password bowl       #
#------------------------------------------------------------------#

import hashlib as Hashlib
import json as Json
import os as Os
from datetime import datetime as DateTime, timezone as Timezone
from pathlib import Path


LEVEL_OK = "ok"
LEVEL_NOTE = "note"
LEVEL_WARNING = "warning"
LEVEL_ERROR = "error"
LEVEL_ORDER = {
    LEVEL_OK: 0,
    LEVEL_NOTE: 1,
    LEVEL_WARNING: 2,
    LEVEL_ERROR: 3,
}


#MARK: clipboards for the tiny hospital
class DoctorFinding:
    Icons = {
        LEVEL_OK: "PASS",
        LEVEL_NOTE: "NOTE",
        LEVEL_WARNING: "WARN",
        LEVEL_ERROR: "FAIL",
    }

    def __init__(self, Code, Level, Title, Detail, Repairable=False):
        if Level not in LEVEL_ORDER:
            raise ValueError(f"unknown doctor level: {Level}")
        self.Code = str(Code)
        self.Level = Level
        self.Title = str(Title)
        self.Detail = str(Detail)
        self.Repairable = bool(Repairable)

    @property
    def Passed(self):
        return self.Level in {LEVEL_OK, LEVEL_NOTE}

    def AsLine(self):
        RepairText = " [repairable]" if self.Repairable else ""
        return (
            f"[{self.Icons[self.Level]}] {self.Code}: {self.Title}{RepairText}\n"
            f"       {self.Detail}"
        )

    def AsDictionary(self):
        return {
            "code": self.Code,
            "level": self.Level,
            "title": self.Title,
            "detail": self.Detail,
            "repairable": self.Repairable,
        }


class DoctorContext:
    def __init__(
        self,
        FilePath,
        Blob,
        Header,
        Vault,
        PasswordIssueFinder,
        ExpectedVersion,
        MaximumFileSize,
        Now=None,
    ):
        self.FilePath = Path(FilePath)
        self.Blob = bytes(Blob)
        self.Header = dict(Header)
        self.Vault = Vault
        self.PasswordIssueFinder = PasswordIssueFinder
        self.ExpectedVersion = int(ExpectedVersion)
        self.MaximumFileSize = int(MaximumFileSize)
        self.Now = Now or DateTime.now(Timezone.utc)


class DoctorCheck:
    Code = "doctor.unknown"
    Title = "an unnamed doctor wandered in"

    def Finding(self, Level, Detail, Repairable=False):
        return DoctorFinding(
            self.Code,
            Level,
            self.Title,
            Detail,
            Repairable=Repairable,
        )

    def Examine(self, Context):
        raise NotImplementedError


#MARK: filesystem ward
class HiddenFilenameCheck(DoctorCheck):
    Code = "file.hidden"
    Title = "dotfile invisibility costume"

    def Examine(self, Context):
        if Context.FilePath.name.startswith("."):
            return self.Finding(LEVEL_OK, "the filename starts with a dot")
        return self.Finding(
            LEVEL_WARNING,
            "the filename is visible in ordinary directory listings",
        )


class ExtensionCheck(DoctorCheck):
    Code = "file.extension"
    Title = "suspicious extension paperwork"

    def Examine(self, Context):
        Extension = Context.FilePath.suffix.casefold()
        if Extension in {".p00p", ".poop"}:
            return self.Finding(LEVEL_OK, f"the bowl uses {Extension}")
        return self.Finding(
            LEVEL_WARNING,
            "the bowl is missing its deeply professional .p00p or .poop extension",
        )


class OwnerOnlyPermissionCheck(DoctorCheck):
    Code = "file.permissions"
    Title = "owner-only bathroom lock"

    def Examine(self, Context):
        try:
            Mode = Context.FilePath.stat().st_mode & 0o777
        except OSError as Exc:
            return self.Finding(LEVEL_ERROR, f"permissions could not be read: {Exc}")
        if Mode & 0o077 == 0:
            return self.Finding(LEVEL_OK, f"permissions are {Mode:03o}")
        return self.Finding(
            LEVEL_WARNING,
            f"permissions are {Mode:03o}; group or other users can access the file",
            Repairable=True,
        )


class FileSizeCheck(DoctorCheck):
    Code = "file.size"
    Title = "bowl capacity measurement"

    def Examine(self, Context):
        Size = len(Context.Blob)
        Percent = (Size / Context.MaximumFileSize * 100) if Context.MaximumFileSize else 0
        if Percent >= 90:
            return self.Finding(
                LEVEL_WARNING,
                f"the vault is {Size} bytes ({Percent:.1f}% of the configured safety limit)",
            )
        return self.Finding(
            LEVEL_OK,
            f"the vault is {Size} bytes ({Percent:.3f}% of the safety limit)",
        )


#MARK: binary envelope ward
class FormatVersionCheck(DoctorCheck):
    Code = "format.version"
    Title = "time-traveler version check"

    def Examine(self, Context):
        Actual = Context.Header.get("version")
        if Actual == Context.ExpectedVersion:
            return self.Finding(LEVEL_OK, f"format version {Actual} is understood")
        return self.Finding(
            LEVEL_ERROR,
            f"format version {Actual!r} does not match {Context.ExpectedVersion}",
        )


class IntegrityCheck(DoctorCheck):
    Code = "format.integrity"
    Title = "checksum and decoder pulse"

    def Examine(self, Context):
        # constructing the context requires the normal decoder to finish first.
        # this check records that successful precondition in the final chart.
        Digest = Context.Header.get("digest", b"")
        if not Digest:
            return self.Finding(LEVEL_ERROR, "the decoded envelope has no digest")
        return self.Finding(
            LEVEL_OK,
            f"the {len(Digest)}-byte digest matched and the payload decoded",
        )


class PlaintextLeakCheck(DoctorCheck):
    Code = "format.plaintext"
    Title = "lazy-scraper string hunt"

    def Examine(self, Context):
        LeakCount = 0
        CheckedCount = 0
        for Name, Entry in Context.Vault.get("entries", {}).items():
            for Value in (
                Name,
                Entry.get("username", ""),
                Entry.get("password", ""),
                Entry.get("notes", ""),
            ):
                Encoded = Value.encode("utf-8")
                # very small strings match random bytes too easily to mean anything.
                if len(Encoded) < 8:
                    continue
                CheckedCount += 1
                if Encoded in Context.Blob:
                    LeakCount += 1
        if LeakCount:
            return self.Finding(
                LEVEL_ERROR,
                f"{LeakCount} of {CheckedCount} long stored strings appear in the raw file",
            )
        return self.Finding(
            LEVEL_OK,
            f"none of {CheckedCount} checked long strings appear directly in the raw file",
        )


class CompressionCheck(DoctorCheck):
    Code = "format.compression"
    Title = "trash-compactor pressure gauge"

    def Examine(self, Context):
        Raw = Json.dumps(
            Context.Vault,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        PayloadSize = max(1, int(Context.Header.get("payload_size", 0)))
        Ratio = len(Raw) / PayloadSize
        if Ratio > 250:
            return self.Finding(
                LEVEL_NOTE,
                f"decoded JSON is {Ratio:.1f}x the payload; repetitive data compressed extremely well",
            )
        return self.Finding(
            LEVEL_OK,
            f"decoded JSON is {len(Raw)} bytes and the payload is {PayloadSize} bytes ({Ratio:.2f}x)",
        )


#MARK: timestamp ward
def ParseTimestamp(Value):
    if not isinstance(Value, str) or not Value.strip():
        return None
    try:
        Parsed = DateTime.fromisoformat(Value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if Parsed.tzinfo is None:
        Parsed = Parsed.replace(tzinfo=Timezone.utc)
    return Parsed.astimezone(Timezone.utc)


class TimestampCheck(DoctorCheck):
    Code = "vault.timestamps"
    Title = "chronology goblin consultation"

    def Examine(self, Context):
        Created = ParseTimestamp(Context.Vault.get("created_at"))
        Updated = ParseTimestamp(Context.Vault.get("updated_at"))
        InvalidEntryTimes = 0
        FutureEntryTimes = 0
        FutureTolerance = 300

        for Entry in Context.Vault.get("entries", {}).values():
            Value = Entry.get("updated_at")
            if Value is None:
                continue
            Parsed = ParseTimestamp(Value)
            if Parsed is None:
                InvalidEntryTimes += 1
            elif (Parsed - Context.Now).total_seconds() > FutureTolerance:
                FutureEntryTimes += 1

        Problems = []
        if Created is None:
            Problems.append("vault created_at is invalid")
        if Updated is None:
            Problems.append("vault updated_at is invalid")
        if Created and Updated and Updated < Created:
            Problems.append("vault updated_at is older than created_at")
        if Created and (Created - Context.Now).total_seconds() > FutureTolerance:
            Problems.append("vault created_at is in the future")
        if Updated and (Updated - Context.Now).total_seconds() > FutureTolerance:
            Problems.append("vault updated_at is in the future")
        if InvalidEntryTimes:
            Problems.append(f"{InvalidEntryTimes} entry timestamp(s) are invalid")
        if FutureEntryTimes:
            Problems.append(f"{FutureEntryTimes} entry timestamp(s) are in the future")

        if Problems:
            return self.Finding(LEVEL_WARNING, "; ".join(Problems))
        Count = len(Context.Vault.get("entries", {}))
        return self.Finding(
            LEVEL_OK,
            f"vault timestamps and {Count} entry timestamp slot(s) look chronological",
        )


#MARK: credential ward that refuses to print credentials
class PasswordHygieneCheck(DoctorCheck):
    Code = "entries.passwords"
    Title = "password hygiene aggregate"

    def Examine(self, Context):
        Affected = 0
        IssueCount = 0
        for Entry in Context.Vault.get("entries", {}).values():
            Issues = Context.PasswordIssueFinder(Entry.get("password", ""))
            if Issues:
                Affected += 1
                IssueCount += len(Issues)
        if Affected:
            return self.Finding(
                LEVEL_WARNING,
                f"{Affected} entry/entries have {IssueCount} basic password finding(s)",
            )
        return self.Finding(LEVEL_OK, "no basic password hygiene findings")


class ReusedPasswordCheck(DoctorCheck):
    Code = "entries.reuse"
    Title = "duplicate secret fingerprint census"

    def Examine(self, Context):
        Fingerprints = {}
        for Entry in Context.Vault.get("entries", {}).values():
            Password = Entry.get("password", "")
            Fingerprint = Hashlib.sha256(Password.encode("utf-8")).digest()
            Fingerprints[Fingerprint] = Fingerprints.get(Fingerprint, 0) + 1
        Groups = [Count for Count in Fingerprints.values() if Count > 1]
        if Groups:
            Affected = sum(Groups)
            return self.Finding(
                LEVEL_WARNING,
                f"{Affected} entries belong to {len(Groups)} reused-password group(s)",
            )
        return self.Finding(LEVEL_OK, "no duplicate password fingerprints were found")


class UsernameCheck(DoctorCheck):
    Code = "entries.usernames"
    Title = "username attendance sheet"

    def Examine(self, Context):
        Entries = Context.Vault.get("entries", {})
        Missing = sum(not Entry.get("username", "").strip() for Entry in Entries.values())
        if Missing:
            return self.Finding(
                LEVEL_NOTE,
                f"{Missing} of {len(Entries)} entries have no username",
            )
        return self.Finding(LEVEL_OK, f"all {len(Entries)} entries have usernames")


#MARK: final chart and needlessly official diagnostic ward
class DoctorReport:
    def __init__(self, FilePath, Findings):
        self.FilePath = Path(FilePath)
        self.Findings = tuple(Findings)

    def Count(self, Level):
        return sum(Finding.Level == Level for Finding in self.Findings)

    @property
    def WorstLevel(self):
        return max(
            (Finding.Level for Finding in self.Findings),
            key=lambda Level: LEVEL_ORDER[Level],
            default=LEVEL_OK,
        )

    @property
    def Healthy(self):
        return self.Count(LEVEL_WARNING) == 0 and self.Count(LEVEL_ERROR) == 0

    def Summary(self):
        return (
            f"{self.Count(LEVEL_OK)} pass, {self.Count(LEVEL_NOTE)} note, "
            f"{self.Count(LEVEL_WARNING)} warning, {self.Count(LEVEL_ERROR)} failure"
        )

    def AsText(self):
        Lines = [
            "P00P VAULT DOCTOR",
            f"patient: {self.FilePath}",
            f"result:  {self.Summary()}",
            "",
        ]
        Lines.extend(Finding.AsLine() for Finding in self.Findings)
        Lines.extend((
            "",
            "diagnosis: camouflage is working as designed, which is still not encryption.",
            "prescription: use fake credentials here and a real password manager for real ones.",
        ))
        return "\n".join(Lines)

    def AsDictionary(self):
        return {
            "protocol": "p00p-doctor",
            "patient": str(self.FilePath),
            "healthy": self.Healthy,
            "worst_level": self.WorstLevel,
            "summary": {
                Level: self.Count(Level)
                for Level in (LEVEL_OK, LEVEL_NOTE, LEVEL_WARNING, LEVEL_ERROR)
            },
            "findings": [Finding.AsDictionary() for Finding in self.Findings],
            "security_notice": "camouflage is not encryption; only use fake credentials",
        }

    def AsJson(self):
        return Json.dumps(self.AsDictionary(), indent=2, sort_keys=True)


class DiagnosticWard:
    def __init__(self, Checks=None):
        self.Checks = tuple(Checks or (
            HiddenFilenameCheck(),
            ExtensionCheck(),
            OwnerOnlyPermissionCheck(),
            FileSizeCheck(),
            FormatVersionCheck(),
            IntegrityCheck(),
            PlaintextLeakCheck(),
            CompressionCheck(),
            TimestampCheck(),
            PasswordHygieneCheck(),
            ReusedPasswordCheck(),
            UsernameCheck(),
        ))

    def Admit(self, Context):
        Findings = []
        for Check in self.Checks:
            try:
                Findings.append(Check.Examine(Context))
            except Exception as Exc:
                # one weird optional check should not hide all other diagnostics.
                Findings.append(DoctorFinding(
                    Check.Code,
                    LEVEL_ERROR,
                    Check.Title,
                    f"the check itself fell over: {type(Exc).__name__}",
                ))
        return DoctorReport(Context.FilePath, Findings)


DEFAULT_WARD = DiagnosticWard()


def ExamineVault(Context):
    return DEFAULT_WARD.Admit(Context)


def RepairOwnerOnlyPermissions(FilePath):
    FilePath = Path(FilePath)
    Os.chmod(FilePath, 0o600)
    return FilePath.stat().st_mode & 0o777
