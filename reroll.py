#------------------------------------------------------------------#
# p00p camouflage reroller                                        #
# same fake secrets, completely different binary soup              #
#------------------------------------------------------------------#

import hashlib as Hashlib
import json as Json
import secrets as Secrets
from pathlib import Path


class RerollError(Exception):
    pass


def FreshSalt(OldSalt, Size, RandomBytes=None):
    RandomBytes = RandomBytes or Secrets.token_bytes
    for _Attempt in range(8):
        Candidate = RandomBytes(Size)
        if not isinstance(Candidate, bytes) or len(Candidate) != Size:
            raise RerollError(f"salt goblin returned something other than {Size} bytes")
        if Candidate != OldSalt:
            return Candidate
    raise RerollError("salt goblin somehow rolled the same salt eight times")


class RerollReceipt:
    def __init__(self, FilePath, BeforeBlob, AfterBlob, OldSalt, NewSalt, EntryCount):
        self.FilePath = Path(FilePath)
        self.BeforeBytes = len(BeforeBlob)
        self.AfterBytes = len(AfterBlob)
        self.BeforeHash = Hashlib.sha256(BeforeBlob).hexdigest()
        self.AfterHash = Hashlib.sha256(AfterBlob).hexdigest()
        self.OldSalt = bytes(OldSalt).hex()
        self.NewSalt = bytes(NewSalt).hex()
        self.EntryCount = int(EntryCount)

    @property
    def Changed(self):
        return self.BeforeHash != self.AfterHash and self.OldSalt != self.NewSalt

    def AsDictionary(self):
        return {
            "protocol": "p00p-reroll",
            "file": str(self.FilePath),
            "entries": self.EntryCount,
            "changed": self.Changed,
            "before": {
                "bytes": self.BeforeBytes,
                "sha256": self.BeforeHash,
                "salt": self.OldSalt,
            },
            "after": {
                "bytes": self.AfterBytes,
                "sha256": self.AfterHash,
                "salt": self.NewSalt,
            },
            "security_notice": "new camouflage is still not encryption",
        }

    def AsJson(self):
        return Json.dumps(self.AsDictionary(), indent=2, sort_keys=True)

    def AsText(self):
        return "\n".join((
            "P00P CAMOUFLAGE REROLLED",
            f"bowl:          {self.FilePath}",
            f"entries:       {self.EntryCount}",
            f"old salt:      {self.OldSalt}",
            f"new salt:      {self.NewSalt}",
            f"old sha256:    {self.BeforeHash}",
            f"new sha256:    {self.AfterHash}",
            f"size:          {self.BeforeBytes} -> {self.AfterBytes} bytes",
            "decoded data:  unchanged",
            "reality check: different soup is still not encryption",
        ))
