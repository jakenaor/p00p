#------------------------------------------------------------------#
# p00p bowl statistics desk                                       #
# counts the fake secrets without printing the fake secrets        #
#------------------------------------------------------------------#

import hashlib as Hashlib
import json as Json
from collections import Counter
from pathlib import Path


LENGTH_BUCKETS = (
    ("EMPTY", 0, 0),
    ("1-7", 1, 7),
    ("8-11", 8, 11),
    ("12-19", 12, 19),
    ("20-31", 20, 31),
    ("32+", 32, None),
)


def LengthBucket(Length):
    for Label, Minimum, Maximum in LENGTH_BUCKETS:
        if Length >= Minimum and (Maximum is None or Length <= Maximum):
            return Label
    return "EMPTY"


def TinyBar(Value, Maximum, Width=18):
    if Maximum <= 0:
        Filled = 0
    else:
        Filled = round((Value / Maximum) * Width)
    Filled = max(0, min(Width, Filled))
    return "#" * Filled + "." * (Width - Filled)


class BowlStatistics:
    def __init__(self, FilePath, Vault, Blob, Header, PasswordIssueFinder):
        self.FilePath = Path(FilePath)
        self.Vault = Vault
        self.Blob = bytes(Blob)
        self.Header = dict(Header)
        self.PasswordIssueFinder = PasswordIssueFinder
        self.Entries = Vault.get("entries", {})
        self.EntryCount = len(self.Entries)
        self.WithUsernames = 0
        self.WithNotes = 0
        self.HealthyEntries = 0
        self.EntriesNeedingAttention = 0
        self.ReusedGroups = 0
        self.ReusedEntries = 0
        self.LengthCounts = Counter()
        self.IssueCounts = Counter()
        self._count_everything()

        Raw = Json.dumps(
            Vault,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        self.RawJsonBytes = len(Raw)
        self.PayloadBytes = int(Header.get("payload_size", 0))
        self.FileBytes = len(Blob)

    def _count_everything(self):
        Fingerprints = Counter()
        for Entry in self.Entries.values():
            Username = Entry.get("username", "")
            Password = Entry.get("password", "")
            Notes = Entry.get("notes", "")
            if Username.strip():
                self.WithUsernames += 1
            if Notes.strip():
                self.WithNotes += 1
            Issues = tuple(self.PasswordIssueFinder(Password))
            if Issues:
                self.EntriesNeedingAttention += 1
                self.IssueCounts.update(Issues)
            else:
                self.HealthyEntries += 1
            self.LengthCounts[LengthBucket(len(Password))] += 1
            Fingerprint = Hashlib.sha256(Password.encode("utf-8")).digest()
            Fingerprints[Fingerprint] += 1

        Reused = [Count for Count in Fingerprints.values() if Count > 1]
        self.ReusedGroups = len(Reused)
        self.ReusedEntries = sum(Reused)

    @property
    def CompressionRatio(self):
        return self.RawJsonBytes / max(1, self.PayloadBytes)

    @property
    def BytesPerEntry(self):
        return self.FileBytes / max(1, self.EntryCount)

    def Summary(self):
        return (
            f"{self.EntryCount} ENTRIES // {self.HealthyEntries} BASIC-OK // "
            f"{self.EntriesNeedingAttention} NEED ATTENTION // "
            f"{self.ReusedGroups} REUSE GROUPS"
        )

    def AsDictionary(self):
        return {
            "protocol": "p00p-bowl-statistics",
            "file": str(self.FilePath),
            "entries": {
                "total": self.EntryCount,
                "with_username": self.WithUsernames,
                "with_notes": self.WithNotes,
                "basic_ok": self.HealthyEntries,
                "need_attention": self.EntriesNeedingAttention,
                "reused_groups": self.ReusedGroups,
                "reused_entries": self.ReusedEntries,
            },
            "password_length_buckets": {
                Label: self.LengthCounts[Label]
                for Label, _Minimum, _Maximum in LENGTH_BUCKETS
            },
            "basic_issue_counts": dict(sorted(self.IssueCounts.items())),
            "storage": {
                "file_bytes": self.FileBytes,
                "payload_bytes": self.PayloadBytes,
                "decoded_json_bytes": self.RawJsonBytes,
                "compression_ratio": round(self.CompressionRatio, 3),
                "bytes_per_entry": round(self.BytesPerEntry, 2),
            },
            "security_notice": "aggregate statistics are not a security audit",
        }

    def AsJson(self):
        return Json.dumps(self.AsDictionary(), indent=2, sort_keys=True)

    def AsText(self):
        Lines = [
            "P00P BOWL STATISTICS",
            f"bowl:       {self.FilePath}",
            f"entries:    {self.EntryCount}",
            f"basic-ok:   {self.HealthyEntries}",
            f"attention:  {self.EntriesNeedingAttention}",
            f"usernames:  {self.WithUsernames}/{self.EntryCount}",
            f"notes:      {self.WithNotes}/{self.EntryCount}",
            f"reuse:      {self.ReusedGroups} group(s), {self.ReusedEntries} entries",
            "",
            "PASSWORD LENGTH BUCKETS (VALUES STAY HIDDEN)",
        ]
        HighestBucket = max(self.LengthCounts.values(), default=0)
        for Label, _Minimum, _Maximum in LENGTH_BUCKETS:
            Count = self.LengthCounts[Label]
            Lines.append(f"{Label:>7}  [{TinyBar(Count, HighestBucket)}] {Count}")

        Lines.extend(("", "BASIC ISSUE COUNTS"))
        if self.IssueCounts:
            for Issue, Count in sorted(
                self.IssueCounts.items(),
                key=lambda Item: (-Item[1], Item[0]),
            ):
                Lines.append(f"- {Issue}: {Count}")
        else:
            Lines.append("- none")

        Lines.extend((
            "",
            "STORAGE GUTS",
            f"file bytes:         {self.FileBytes}",
            f"payload bytes:      {self.PayloadBytes}",
            f"decoded JSON bytes: {self.RawJsonBytes}",
            f"compression ratio:  {self.CompressionRatio:.2f}x",
            f"bytes per entry:    {self.BytesPerEntry:.2f}",
            "",
            "reality check: aggregate statistics are not a security audit.",
        ))
        return "\n".join(Lines)
