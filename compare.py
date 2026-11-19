#------------------------------------------------------------------#
# p00p vault comparison bureaucracy                               #
# discovers what changed without yelling passwords into stdout     #
#------------------------------------------------------------------#

import hashlib as Hashlib
import json as Json
from pathlib import Path


CONTENT_FIELDS = ("username", "password", "notes")
STATUS_ORDER = {
    "renamed": 0,
    "changed": 1,
    "added": 2,
    "removed": 3,
}


def CanonicalBytes(Value):
    return Json.dumps(
        Value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def Fingerprint(Value):
    return Hashlib.sha256(CanonicalBytes(Value)).hexdigest()


def EntryContent(Entry):
    return {Field: Entry.get(Field, "") for Field in CONTENT_FIELDS}


def EntryFingerprint(Entry):
    return Fingerprint(EntryContent(Entry))


#MARK: individual change tickets
class EntryDelta:
    def __init__(self, Status, Name=None, OldName=None, NewName=None, Fields=()):
        if Status not in STATUS_ORDER:
            raise ValueError(f"unsupported delta status: {Status}")
        self.Status = Status
        self.Name = Name
        self.OldName = OldName
        self.NewName = NewName
        self.Fields = tuple(Fields)

    def SortKey(self):
        DisplayName = self.Name or self.NewName or self.OldName or ""
        return STATUS_ORDER[self.Status], DisplayName.casefold(), DisplayName

    def SafeLabel(self, Anonymous=False):
        if Anonymous:
            return "hidden entry"
        if self.Status == "renamed":
            return f"{self.OldName!r} -> {self.NewName!r}"
        return repr(self.Name)

    def AsLine(self, Anonymous=False):
        Label = self.SafeLabel(Anonymous=Anonymous)
        if self.Status == "renamed":
            return f"~ renamed: {Label}"
        if self.Status == "changed":
            return f"~ changed {Label}: {', '.join(self.Fields)}"
        Mark = "+" if self.Status == "added" else "-"
        return f"{Mark} {self.Status}: {Label}"

    def AsDictionary(self, Anonymous=False):
        Payload = {
            "status": self.Status,
            "fields": list(self.Fields),
        }
        if not Anonymous:
            if self.Status == "renamed":
                Payload.update({"old_name": self.OldName, "new_name": self.NewName})
            else:
                Payload["name"] = self.Name
        return Payload


#MARK: the report nobody asked to have this many methods
class VaultDifference:
    def __init__(self, LeftPath, RightPath, Deltas, UnchangedNames):
        self.LeftPath = Path(LeftPath)
        self.RightPath = Path(RightPath)
        self.Deltas = tuple(sorted(Deltas, key=lambda Delta: Delta.SortKey()))
        self.UnchangedNames = tuple(sorted(UnchangedNames, key=str.casefold))

    def Count(self, Status):
        return sum(Delta.Status == Status for Delta in self.Deltas)

    @property
    def Identical(self):
        return not self.Deltas

    @property
    def ChangedEntryCount(self):
        return len(self.Deltas)

    def Summary(self):
        return (
            f"{self.Count('added')} added, {self.Count('removed')} removed, "
            f"{self.Count('changed')} changed, {self.Count('renamed')} renamed, "
            f"{len(self.UnchangedNames)} unchanged"
        )

    def AsText(self, Anonymous=False):
        Lines = [
            "P00P VAULT DIFFERENCE ENGINE",
            f"left:    {self.LeftPath}",
            f"right:   {self.RightPath}",
            f"result:  {self.Summary()}",
            "",
        ]
        if self.Identical:
            Lines.append("= decoded credential contents are identical")
        else:
            Lines.extend(Delta.AsLine(Anonymous=Anonymous) for Delta in self.Deltas)
        Lines.extend((
            "",
            "privacy note: changed password values are never printed.",
            "reality note: both input files are camouflage, not encryption.",
        ))
        return "\n".join(Lines)

    def AsDictionary(self, Anonymous=False):
        return {
            "protocol": "p00p-difference",
            "left": str(self.LeftPath),
            "right": str(self.RightPath),
            "anonymous": bool(Anonymous),
            "identical": self.Identical,
            "summary": {
                "added": self.Count("added"),
                "removed": self.Count("removed"),
                "changed": self.Count("changed"),
                "renamed": self.Count("renamed"),
                "unchanged": len(self.UnchangedNames),
            },
            "deltas": [
                Delta.AsDictionary(Anonymous=Anonymous)
                for Delta in self.Deltas
            ],
            "security_notice": "changed password values are never included",
        }

    def AsJson(self, Anonymous=False):
        return Json.dumps(
            self.AsDictionary(Anonymous=Anonymous),
            indent=2,
            sort_keys=True,
        )


#MARK: renamed-entry detective bureau
class RenameDetector:
    def __init__(self, LeftEntries, RightEntries, RemovedNames, AddedNames):
        self.LeftEntries = LeftEntries
        self.RightEntries = RightEntries
        self.RemovedNames = set(RemovedNames)
        self.AddedNames = set(AddedNames)

    def _buckets(self, Entries, Names):
        Buckets = {}
        for Name in Names:
            Digest = EntryFingerprint(Entries[Name])
            Buckets.setdefault(Digest, []).append(Name)
        for NamesInBucket in Buckets.values():
            NamesInBucket.sort(key=str.casefold)
        return Buckets

    def Detect(self):
        RemovedBuckets = self._buckets(self.LeftEntries, self.RemovedNames)
        AddedBuckets = self._buckets(self.RightEntries, self.AddedNames)
        Renames = []
        for Digest in sorted(set(RemovedBuckets) & set(AddedBuckets)):
            OldNames = RemovedBuckets[Digest]
            NewNames = AddedBuckets[Digest]
            for OldName, NewName in zip(OldNames, NewNames):
                Renames.append((OldName, NewName))
                self.RemovedNames.remove(OldName)
                self.AddedNames.remove(NewName)
        return Renames, self.RemovedNames, self.AddedNames


def ChangedFields(LeftEntry, RightEntry):
    return tuple(
        Field
        for Field in CONTENT_FIELDS
        if LeftEntry.get(Field, "") != RightEntry.get(Field, "")
    )


def CompareVaults(LeftVault, RightVault, LeftPath="left", RightPath="right"):
    LeftEntries = LeftVault.get("entries", {})
    RightEntries = RightVault.get("entries", {})
    LeftNames = set(LeftEntries)
    RightNames = set(RightEntries)
    SharedNames = LeftNames & RightNames
    RemovedNames = LeftNames - RightNames
    AddedNames = RightNames - LeftNames

    Renames, RemovedNames, AddedNames = RenameDetector(
        LeftEntries,
        RightEntries,
        RemovedNames,
        AddedNames,
    ).Detect()

    Deltas = [
        EntryDelta("renamed", OldName=OldName, NewName=NewName, Fields=("name",))
        for OldName, NewName in Renames
    ]
    Unchanged = []
    for Name in sorted(SharedNames, key=str.casefold):
        Fields = ChangedFields(LeftEntries[Name], RightEntries[Name])
        if Fields:
            Deltas.append(EntryDelta("changed", Name=Name, Fields=Fields))
        else:
            Unchanged.append(Name)
    Deltas.extend(EntryDelta("removed", Name=Name) for Name in RemovedNames)
    Deltas.extend(EntryDelta("added", Name=Name) for Name in AddedNames)
    return VaultDifference(LeftPath, RightPath, Deltas, Unchanged)
