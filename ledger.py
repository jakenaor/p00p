#------------------------------------------------------------------#
# p00p bowl ledger                                                 #
# hash-chained paperwork that remembers no actual credential stuff  #
#------------------------------------------------------------------#

import hashlib as Hashlib
import json as Json
import re as Re
from pathlib import Path


LEDGER_PROTOCOL = "p00p-bowl-ledger"
LEDGER_VERSION = 1
MAX_LEDGER_BYTES = 2 * 1024 * 1024
MAX_EVENTS = 10_000
ZERO_HASH = "0" * 64
HASH_PATTERN = Re.compile(r"^[0-9a-f]{64}$")
EVENT_ACTIONS = (
    "checkpoint",
    "before-demo",
    "after-demo",
    "backup-confirmed",
    "submission",
)
RECORD_FIELDS = frozenset((
    "protocol",
    "version",
    "sequence",
    "action",
    "recorded_at",
    "vault_name",
    "vault_bytes",
    "entry_count",
    "vault_sha256",
    "previous_hash",
    "record_hash",
))


class LedgerError(Exception):
    pass


def SuggestedLedgerPath(VaultPath):
    VaultPath = Path(VaultPath)
    return VaultPath.with_name(f"{VaultPath.name}.ledger.jsonl")


def VaultHash(Blob):
    return Hashlib.sha256(bytes(Blob)).hexdigest()


def _canonical_body(Record):
    Body = {Key: Value for Key, Value in Record.items() if Key != "record_hash"}
    return Json.dumps(Body, separators=(",", ":"), sort_keys=True).encode("utf-8")


def RecordHash(Record):
    return Hashlib.sha256(_canonical_body(Record)).hexdigest()


def _require_plain_integer(Record, Field, Minimum=0):
    Value = Record.get(Field)
    if isinstance(Value, bool) or not isinstance(Value, int) or Value < Minimum:
        raise LedgerError(f"ledger field {Field!r} must be an integer >= {Minimum}")
    return Value


def ValidateRecord(Record, ExpectedSequence, ExpectedPreviousHash, VaultName=None):
    if not isinstance(Record, dict):
        raise LedgerError(f"ledger record {ExpectedSequence} is not an object")
    Unknown = set(Record) - RECORD_FIELDS
    Missing = RECORD_FIELDS - set(Record)
    if Missing:
        raise LedgerError(
            f"ledger record {ExpectedSequence} is missing: {', '.join(sorted(Missing))}"
        )
    if Unknown:
        raise LedgerError(
            f"ledger record {ExpectedSequence} has unknown fields: {', '.join(sorted(Unknown))}"
        )
    if Record.get("protocol") != LEDGER_PROTOCOL:
        raise LedgerError(f"ledger record {ExpectedSequence} has the wrong protocol")
    if Record.get("version") != LEDGER_VERSION:
        raise LedgerError(
            f"unsupported ledger version in record {ExpectedSequence}: {Record.get('version')!r}"
        )
    Sequence = _require_plain_integer(Record, "sequence", 1)
    if Sequence != ExpectedSequence:
        raise LedgerError(
            f"ledger sequence jumped: expected {ExpectedSequence}, found {Sequence}"
        )
    Action = Record.get("action")
    if Action not in EVENT_ACTIONS:
        raise LedgerError(f"ledger record {Sequence} has unknown action: {Action!r}")
    RecordedAt = Record.get("recorded_at")
    if not isinstance(RecordedAt, str) or not RecordedAt.strip():
        raise LedgerError(f"ledger record {Sequence} has no timestamp")
    Name = Record.get("vault_name")
    if not isinstance(Name, str) or not Name or Path(Name).name != Name:
        raise LedgerError(f"ledger record {Sequence} has an invalid vault filename")
    if VaultName is not None and Name != VaultName:
        raise LedgerError(
            f"ledger record {Sequence} switched vault names from {VaultName!r} to {Name!r}"
        )
    _require_plain_integer(Record, "vault_bytes")
    _require_plain_integer(Record, "entry_count")
    for Field in ("vault_sha256", "previous_hash", "record_hash"):
        Value = Record.get(Field)
        if not isinstance(Value, str) or HASH_PATTERN.fullmatch(Value) is None:
            raise LedgerError(f"ledger record {Sequence} has malformed {Field}")
    if Record["previous_hash"] != ExpectedPreviousHash:
        raise LedgerError(f"ledger chain broke before record {Sequence}")
    ExpectedHash = RecordHash(Record)
    if Record["record_hash"] != ExpectedHash:
        raise LedgerError(f"ledger record {Sequence} hash does not match its contents")
    return Name


def ValidateLedger(Records):
    if not isinstance(Records, (list, tuple)):
        raise LedgerError("ledger must be a sequence of records")
    if not Records:
        raise LedgerError("ledger has no records")
    if len(Records) > MAX_EVENTS:
        raise LedgerError(f"ledger has too many records ({len(Records)} > {MAX_EVENTS})")
    PreviousHash = ZERO_HASH
    VaultName = None
    for Sequence, Record in enumerate(Records, start=1):
        VaultName = ValidateRecord(
            Record,
            ExpectedSequence=Sequence,
            ExpectedPreviousHash=PreviousHash,
            VaultName=VaultName,
        )
        PreviousHash = Record["record_hash"]
    return Records


def NewRecord(VaultPath, Blob, EntryCount, Action, RecordedAt, Previous=None):
    if Action not in EVENT_ACTIONS:
        raise LedgerError(f"unknown ledger action: {Action!r}")
    if not isinstance(RecordedAt, str) or not RecordedAt.strip():
        raise LedgerError("ledger timestamp is missing")
    if isinstance(EntryCount, bool):
        raise LedgerError("ledger entry count must be a plain integer")
    try:
        EntryCount = int(EntryCount)
    except (TypeError, ValueError, OverflowError) as Exc:
        raise LedgerError("ledger entry count must be a plain integer") from Exc
    if EntryCount < 0:
        raise LedgerError("ledger entry count cannot be negative")
    if Previous is None:
        Sequence = 1
        PreviousHash = ZERO_HASH
    else:
        Sequence = int(Previous["sequence"]) + 1
        PreviousHash = str(Previous["record_hash"])
    Blob = bytes(Blob)
    Record = {
        "protocol": LEDGER_PROTOCOL,
        "version": LEDGER_VERSION,
        "sequence": Sequence,
        "action": Action,
        "recorded_at": RecordedAt,
        "vault_name": Path(VaultPath).name,
        "vault_bytes": len(Blob),
        "entry_count": EntryCount,
        "vault_sha256": VaultHash(Blob),
        "previous_hash": PreviousHash,
    }
    Record["record_hash"] = RecordHash(Record)
    ValidateRecord(
        Record,
        ExpectedSequence=Sequence,
        ExpectedPreviousHash=PreviousHash,
        VaultName=None if Previous is None else Previous["vault_name"],
    )
    return Record


def AppendRecord(Records, VaultPath, Blob, EntryCount, Action, RecordedAt):
    Working = [dict(Record) for Record in Records]
    if Working:
        ValidateLedger(Working)
        if len(Working) >= MAX_EVENTS:
            raise LedgerError(f"ledger already reached its {MAX_EVENTS}-record limit")
    Record = NewRecord(
        VaultPath=VaultPath,
        Blob=Blob,
        EntryCount=EntryCount,
        Action=Action,
        RecordedAt=RecordedAt,
        Previous=Working[-1] if Working else None,
    )
    Working.append(Record)
    ValidateLedger(Working)
    return Working, Record


def EncodeLedger(Records):
    ValidateLedger(Records)
    Blob = b"".join(
        Json.dumps(Record, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n"
        for Record in Records
    )
    if len(Blob) > MAX_LEDGER_BYTES:
        raise LedgerError(f"encoded ledger is too large ({len(Blob)} bytes)")
    return Blob


def DecodeLedger(Blob):
    Blob = bytes(Blob)
    if len(Blob) > MAX_LEDGER_BYTES:
        raise LedgerError(f"ledger is too large ({len(Blob)} bytes)")
    try:
        Text = Blob.decode("utf-8")
    except UnicodeDecodeError as Exc:
        raise LedgerError("ledger is not UTF-8") from Exc
    Lines = Text.splitlines()
    if not Lines:
        raise LedgerError("ledger has no records")
    if len(Lines) > MAX_EVENTS:
        raise LedgerError(f"ledger has too many records ({len(Lines)} > {MAX_EVENTS})")
    Records = []
    for LineNumber, Line in enumerate(Lines, start=1):
        if not Line.strip():
            raise LedgerError(f"ledger line {LineNumber} is blank")
        try:
            Records.append(Json.loads(Line))
        except Json.JSONDecodeError as Exc:
            raise LedgerError(f"ledger line {LineNumber} is not valid JSON") from Exc
    ValidateLedger(Records)
    return Records


def ReadLedger(LedgerPath):
    LedgerPath = Path(LedgerPath)
    if not LedgerPath.exists():
        raise LedgerError(f"ledger not found: {LedgerPath}")
    if not LedgerPath.is_file():
        raise LedgerError(f"ledger is not a regular file: {LedgerPath}")
    try:
        if LedgerPath.stat().st_size > MAX_LEDGER_BYTES:
            raise LedgerError(f"ledger is suspiciously huge: {LedgerPath}")
        Blob = LedgerPath.read_bytes()
    except LedgerError:
        raise
    except OSError as Exc:
        raise LedgerError(f"could not read ledger {LedgerPath}: {Exc}") from Exc
    return DecodeLedger(Blob)


class LedgerVerification:
    def __init__(self, LedgerPath, VaultPath, Records, Blob, EntryCount):
        ValidateLedger(Records)
        self.LedgerPath = Path(LedgerPath)
        self.VaultPath = Path(VaultPath)
        self.Records = tuple(dict(Record) for Record in Records)
        self.Blob = bytes(Blob)
        self.EntryCount = int(EntryCount)
        self.Last = self.Records[-1]
        self.Checks = (
            ("vault filename", self.Last["vault_name"] == self.VaultPath.name),
            ("vault byte size", self.Last["vault_bytes"] == len(self.Blob)),
            ("vault SHA-256", self.Last["vault_sha256"] == VaultHash(self.Blob)),
            ("decoded entry count", self.Last["entry_count"] == self.EntryCount),
        )

    @property
    def Passed(self):
        return all(Passed for _Name, Passed in self.Checks)

    def AsDictionary(self):
        return {
            "protocol": "p00p-ledger-verification",
            "passed": self.Passed,
            "ledger": str(self.LedgerPath),
            "vault": str(self.VaultPath),
            "record_count": len(self.Records),
            "last_record": {
                "sequence": self.Last["sequence"],
                "action": self.Last["action"],
                "recorded_at": self.Last["recorded_at"],
                "record_hash": self.Last["record_hash"],
            },
            "checks": [
                {"name": Name, "passed": Passed}
                for Name, Passed in self.Checks
            ],
            "security_notice": (
                "the hash chain catches accidents; without a secret key it is not tamperproof"
            ),
        }

    def AsJson(self):
        return Json.dumps(self.AsDictionary(), indent=2, sort_keys=True)

    def AsText(self):
        Lines = [
            "P00P BOWL LEDGER",
            f"ledger:       {self.LedgerPath}",
            f"vault:        {self.VaultPath}",
            f"records:      {len(self.Records)}",
            f"last action:  {self.Last['action']}",
            f"last time:    {self.Last['recorded_at']}",
            f"record hash:  {self.Last['record_hash']}",
        ]
        for Name, Passed in self.Checks:
            Lines.append(f"[{'PASS' if Passed else 'FAIL'}] {Name}")
        Lines.extend((
            f"result:       {'CURRENT BOWL MATCHES' if self.Passed else 'BOWL CHANGED SINCE LAST RECORD'}",
            "notice: hash chaining catches accidents, not an attacker who can rewrite the ledger",
        ))
        return "\n".join(Lines)

    def Summary(self):
        Match = "MATCH" if self.Passed else "STALE"
        return f"{Match} // {len(self.Records)} RECORD(S) // LAST {self.Last['action'].upper()}"


def VerifyLedger(Records, LedgerPath, VaultPath, Blob, EntryCount):
    return LedgerVerification(
        LedgerPath=LedgerPath,
        VaultPath=VaultPath,
        Records=Records,
        Blob=Blob,
        EntryCount=EntryCount,
    )
