#------------------------------------------------------------------#
# p00p lifeboat                                                    #
# byte-for-byte snapshots with far too much nautical paperwork     #
#------------------------------------------------------------------#

import hashlib as Hashlib
import json as Json
import os as Os
import tempfile as Tempfile
from datetime import datetime as DateTime, timezone as Timezone
from pathlib import Path


class LifeboatError(Exception):
    pass


def PathsPointToSamePlace(Left, Right):
    Left = Path(Left).expanduser()
    Right = Path(Right).expanduser()
    try:
        return Left.resolve() == Right.resolve()
    except OSError:
        return Left.absolute() == Right.absolute()


def SnapshotStem(Source):
    Name = Path(Source).name
    for Extension in (".p00p", ".poop"):
        if Name.casefold() == Extension:
            Name = ""
            break
        if Name.casefold().endswith(Extension):
            Name = Name[:-len(Extension)]
            break
    if Name.startswith("."):
        Name = Name[1:]
    Cleaned = "".join(
        Character if Character.isalnum() or Character in {"-", "_"} else "-"
        for Character in Name
    ).strip("-_")
    return Cleaned or "vault"


def SuggestedSnapshotPath(Source, Now=None):
    Source = Path(Source)
    Now = Now or DateTime.now(Timezone.utc)
    Stamp = Now.astimezone(Timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    Base = f".{SnapshotStem(Source)}.lifeboat-{Stamp}"
    Candidate = Source.with_name(f"{Base}.p00p")
    Counter = 2
    while Candidate.exists():
        Candidate = Source.with_name(f"{Base}-{Counter}.p00p")
        Counter += 1
    return Candidate


#MARK: receipt from the extremely official dockmaster
class LifeboatReceipt:
    def __init__(self, Action, Source, Destination, Blob, EntryCount):
        self.Action = str(Action)
        self.Source = Path(Source)
        self.Destination = Path(Destination)
        self.ByteCount = len(Blob)
        self.EntryCount = int(EntryCount)
        self.Digest = Hashlib.sha256(Blob).hexdigest()

    def AsDictionary(self):
        return {
            "protocol": "p00p-lifeboat",
            "action": self.Action,
            "source": str(self.Source),
            "destination": str(self.Destination),
            "bytes": self.ByteCount,
            "entries": self.EntryCount,
            "sha256": self.Digest,
            "security_notice": "this is a copy, not encryption",
        }

    def AsJson(self):
        return Json.dumps(self.AsDictionary(), indent=2, sort_keys=True)

    def AsText(self):
        Verb = "launched" if self.Action == "backup" else "docked"
        return "\n".join((
            f"P00P LIFEBOAT {Verb.upper()}",
            f"source:      {self.Source}",
            f"destination: {self.Destination}",
            f"entries:     {self.EntryCount}",
            f"bytes:       {self.ByteCount}",
            f"sha256:      {self.Digest}",
            "warning: this snapshot preserves camouflage, not secrecy",
        ))


#MARK: atomic dock machinery
class AtomicDock:
    def __init__(self, Destination, Force=False):
        self.Destination = Path(Destination)
        self.Force = bool(Force)
        self.TemporaryPath = None

    def _prepare_directory(self):
        try:
            self.Destination.parent.mkdir(parents=True, exist_ok=True)
        except OSError as Exc:
            raise LifeboatError(
                f"could not prepare {self.Destination.parent}: {Exc}"
            ) from Exc
        if self.Destination.exists() and not self.Force:
            raise LifeboatError(
                f"destination already exists: {self.Destination} (use --force to replace it)"
            )
        if self.Destination.exists() and not self.Destination.is_file():
            raise LifeboatError(f"destination is not a regular file: {self.Destination}")

    def _write_temporary(self, Blob):
        Handle = None
        try:
            Handle = Tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{self.Destination.name}.",
                suffix=".rowing",
                dir=self.Destination.parent,
                delete=False,
            )
            self.TemporaryPath = Path(Handle.name)
            Handle.write(Blob)
            Handle.flush()
            Os.fsync(Handle.fileno())
            Handle.close()
            Handle = None
            Os.chmod(self.TemporaryPath, 0o600)
        except OSError as Exc:
            if Handle is not None:
                Handle.close()
            self._clean_temporary()
            raise LifeboatError(f"could not write snapshot: {Exc}") from Exc

    def _install_without_overwrite(self):
        # a hard link is an atomic create-if-absent operation on the same filesystem.
        # the temp file lives beside the destination specifically so this can work.
        try:
            Os.link(self.TemporaryPath, self.Destination)
            self.TemporaryPath.unlink()
            self.TemporaryPath = None
        except FileExistsError as Exc:
            raise LifeboatError(
                f"destination already exists: {self.Destination} (use --force to replace it)"
            ) from Exc
        except OSError as Exc:
            raise LifeboatError(f"could not dock snapshot: {Exc}") from Exc

    def _install_with_overwrite(self):
        try:
            Os.replace(self.TemporaryPath, self.Destination)
            self.TemporaryPath = None
        except OSError as Exc:
            raise LifeboatError(f"could not replace {self.Destination}: {Exc}") from Exc

    def _clean_temporary(self):
        if self.TemporaryPath is None:
            return
        try:
            self.TemporaryPath.unlink(missing_ok=True)
        except OSError:
            pass
        self.TemporaryPath = None

    def Install(self, Blob):
        self._prepare_directory()
        self._write_temporary(Blob)
        try:
            if self.Force:
                self._install_with_overwrite()
            else:
                self._install_without_overwrite()
            Os.chmod(self.Destination, 0o600)
        except Exception:
            self._clean_temporary()
            raise
        return self.Destination


def Launch(Source, Destination, Blob, EntryCount, Force=False, Action="backup"):
    Source = Path(Source)
    Destination = Path(Destination)
    if PathsPointToSamePlace(Source, Destination):
        raise LifeboatError("source and destination point to the same vault")
    AtomicDock(Destination, Force=Force).Install(Blob)
    return LifeboatReceipt(Action, Source, Destination, Blob, EntryCount)
