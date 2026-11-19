
#------------------------------------------------------------------#
# persistent 0-leak 0bject protocol                                #
# the password manager that is actually safe probably              #
# app by jakenaor                                                  #
#                                                                  #
# no more stolen passwords after you download fartnite :D          #
# hackers cant see dot files. this is definitely how security works#
#------------------------------------------------------------------#

# anti-hacker stuffs

import argparse as Argparse
import copy as Copy
import getpass as Getpass
import hashlib as Hashlib
import json as Json
import os as Os
import secrets as Secrets
import string as String
import struct as Struct
import subprocess as Subprocess
import sys as Sys
import tempfile as Tempfile
import zlib as Zlib
from datetime import datetime as DateTime, timezone as Timezone
from pathlib import Path

import poopline as Poopline
import theater as Theater
import doctor as Doctor
import lifeboat as Lifeboat
import compare as Compare
import decoy as Decoy
import reroll as Reroll
import bowlstats as BowlStats
import report as Report
import merge as Merge
import seal as Seal
import lab as Lab
import ledger as Ledger
# Scatter is a module namespace; its split/rebuild boundary accepts immutable bytes.
# Its file helpers return validated fragment/receipt objects or raise ScatterError.
import scatter as Scatter

# add common passwords. if the file falls out of the package the rest of the
# app should still open, it just loses one giant wall of bad-password knowledge.
COMMON_PASSWORDS_PATH = Path(__file__).with_name("10k-common-passwords.txt")

MAGIC = b"P00P\x00"
VERSION = 1
# header = magic + version + salt + payload size. checksum gets glued on the end.
SALT_SIZE = 16
DIGEST_SIZE = 16
DEFAULT_VAULT = ".passwords.p00p"
CAMOUFLAGE_KEY = b"persistent-zero-leak-object-protocol-but-not-really"
PROJECT_VERSION = "0.2.0"
DEFAULT_PASSWORD_LENGTH = 24
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256
PASSWORD_SYMBOLS = "!@#$%^&*()-_=+[]{}:,.?"
# a password bowl should not secretly be a 12gb zip bomb wearing a funny hat.
MAX_VAULT_FILE_SIZE = 16 * 1024 * 1024
MAX_VAULT_DECODED_SIZE = 32 * 1024 * 1024
MAX_ENTRY_COUNT = 100_000
MAX_ENTRY_NAME_LENGTH = 256
MAX_USERNAME_LENGTH = 4_096
MAX_STORED_PASSWORD_LENGTH = 16_384
MAX_NOTES_LENGTH = 1_048_576
SUBMISSION_LAB_ROUNDS = 10


def LoadCommonPasswords(FilePath=COMMON_PASSWORDS_PATH):
    try:
        PasswordSoup = Path(FilePath).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        # missing optional data should not brick the entire password bowl.
        return frozenset()
    return frozenset(
        Password.strip().casefold()
        for Password in PasswordSoup.splitlines()
        if Password.strip()
    )


COMMON_PASSWORDS = LoadCommonPasswords()


class P00PError(Exception):
    pass


#MARK: time stuffs
def CurrentTime():
    return DateTime.now(Timezone.utc).isoformat(timespec="seconds")


#MARK: making the bowl
def NewVault():
    Timestamp = CurrentTime()
    return {
        "protocol": "p00p",
        "created_at": Timestamp,
        "updated_at": Timestamp,
        "entries": {},
    }


#MARK: hiding the poops
def Camouflage(Data, Salt):
    # looks random enough to grep.
    Stream = Hashlib.shake_256(CAMOUFLAGE_KEY + Salt).digest(len(Data))
    return bytes(Left ^ Right for Left, Right in zip(Data, Stream))


def EncodeVault(Vault, Salt=None):
    # reject cursed shapes before they become a cursed file forever.
    ValidateVault(Vault)
    Salt = Secrets.token_bytes(SALT_SIZE) if Salt is None else Salt
    if not isinstance(Salt, bytes) or len(Salt) != SALT_SIZE:
        raise P00PError(f"vault salt must be exactly {SALT_SIZE} bytes")
    # sorted compact json makes the same vault predictable before the random salt touches it.
    Raw = Json.dumps(Vault, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(Raw) > MAX_VAULT_DECODED_SIZE:
        raise P00PError("the vault contents are too huge to save")
    Payload = Camouflage(Zlib.compress(Raw, level=9), Salt)
    Header = MAGIC + bytes([VERSION]) + Salt + Struct.pack(">I", len(Payload))
    # this catches damage and tampering. it does not magically make this encryption.
    Digest = Hashlib.sha256(Header + Payload).digest()[:DIGEST_SIZE]
    return Header + Payload + Digest


def DecodeVault(Blob):
    # check every boundary before slicing so half a file cannot pretend to be a vault.
    if len(Blob) > MAX_VAULT_FILE_SIZE:
        raise P00PError("the vault file is suspiciously huge")
    MinimumSize = len(MAGIC) + 1 + SALT_SIZE + 4 + DIGEST_SIZE
    if len(Blob) < MinimumSize or not Blob.startswith(MAGIC):
        raise P00PError("that is not a valid .p00p file")

    Cursor = len(MAGIC)
    FileVersion = Blob[Cursor]
    Cursor += 1
    if FileVersion != VERSION:
        raise P00PError(f"unsupported .p00p version: {FileVersion}")

    Salt = Blob[Cursor : Cursor + SALT_SIZE]
    Cursor += SALT_SIZE
    PayloadSize = Struct.unpack(">I", Blob[Cursor : Cursor + 4])[0]
    Cursor += 4
    ExpectedSize = Cursor + PayloadSize + DIGEST_SIZE
    if len(Blob) != ExpectedSize:
        raise P00PError("the vault is truncated or has trailing data")

    Payload = Blob[Cursor : Cursor + PayloadSize]
    Digest = Blob[-DIGEST_SIZE:]
    ExpectedDigest = Hashlib.sha256(Blob[:-DIGEST_SIZE]).digest()[:DIGEST_SIZE]
    # compare_digest avoids leaking the first wrong checksum byte through timing.
    if not Secrets.compare_digest(Digest, ExpectedDigest):
        raise P00PError("the vault is corrupted (integrity check failed)")

    try:
        Compressed = Camouflage(Payload, Salt)
        Decoder = Zlib.decompressobj()
        Raw = Decoder.decompress(Compressed, MAX_VAULT_DECODED_SIZE + 1)
        # unconsumed input after hitting the cap means more output was waiting to explode.
        if len(Raw) > MAX_VAULT_DECODED_SIZE or Decoder.unconsumed_tail:
            raise P00PError("the vault payload expands past the safety limit")
        Raw += Decoder.flush()
        if len(Raw) > MAX_VAULT_DECODED_SIZE:
            raise P00PError("the vault payload expands past the safety limit")
        if not Decoder.eof or Decoder.unused_data:
            raise P00PError("the vault payload has invalid compressed data")
        Vault = Json.loads(Raw.decode("utf-8"))
    except P00PError:
        raise
    except (Zlib.error, UnicodeDecodeError, Json.JSONDecodeError) as Exc:
        raise P00PError("the vault payload could not be decoded") from Exc

    ValidateVault(Vault)
    return Vault


def PayloadRitualSummary(Vault, Salt):
    # reenact the save and only report sizes. no password soup leaves the bowl.
    Receipts = Poopline.InspectPayloadRitual(Vault, Salt, CAMOUFLAGE_KEY)
    return " -> ".join(
        f"{Receipt['stage']} {Receipt['before_size']}B>{Receipt['after_size']}B"
        for Receipt in Receipts
    )


#MARK: checking the poops
def ValidateVault(Vault):
    # decoded json is still untrusted input until all the important shapes are checked.
    if not isinstance(Vault, dict) or Vault.get("protocol") != "p00p":
        raise P00PError("the vault has an invalid structure")
    Entries = Vault.get("entries")
    if not isinstance(Entries, dict):
        raise P00PError("the vault has an invalid entries table")
    if len(Entries) > MAX_ENTRY_COUNT:
        raise P00PError("the vault contains too many entries")
    for Field in ("created_at", "updated_at"):
        if Field in Vault and not isinstance(Vault[Field], str):
            raise P00PError(f"the vault has an invalid {Field}")
    for Name, Entry in Entries.items():
        if not isinstance(Name, str) or not Name.strip() or not isinstance(Entry, dict):
            raise P00PError("the vault contains a malformed entry")
        if len(Name) > MAX_ENTRY_NAME_LENGTH:
            raise P00PError(f"entry name is longer than {MAX_ENTRY_NAME_LENGTH} characters")
        Limits = {
            "username": MAX_USERNAME_LENGTH,
            "password": MAX_STORED_PASSWORD_LENGTH,
            "notes": MAX_NOTES_LENGTH,
        }
        for Field, Limit in Limits.items():
            Value = Entry.get(Field, "")
            if not isinstance(Value, str):
                raise P00PError(f"entry {Name!r} has an invalid {Field}")
            if len(Value) > Limit:
                raise P00PError(f"entry {Name!r} has an oversized {Field}")
        if "updated_at" in Entry and not isinstance(Entry["updated_at"], str):
            raise P00PError(f"entry {Name!r} has an invalid updated_at")


#MARK: file guts
def ParseHeader(Blob):
    # anatomy only needs the envelope, so do not decode passwords just to count bytes.
    MinimumSize = len(MAGIC) + 1 + SALT_SIZE + 4 + DIGEST_SIZE
    if len(Blob) < MinimumSize or not Blob.startswith(MAGIC):
        raise P00PError("that is not a valid .p00p file")
    Cursor = len(MAGIC)
    FileVersion = Blob[Cursor]
    Cursor += 1
    Salt = Blob[Cursor : Cursor + SALT_SIZE]
    Cursor += SALT_SIZE
    PayloadSize = Struct.unpack(">I", Blob[Cursor : Cursor + 4])[0]
    Cursor += 4
    if len(Blob) != Cursor + PayloadSize + DIGEST_SIZE:
        raise P00PError("the vault is truncated or has trailing data")
    return {
        "version": FileVersion,
        "salt": Salt,
        "header_size": Cursor,
        "payload_size": PayloadSize,
        "digest": Blob[-DIGEST_SIZE:],
        "file_size": len(Blob),
    }


def ReadVaultBlob(FilePath):
    if not FilePath.exists():
        raise P00PError(f"vault not found: {FilePath} (run 'init' first)")
    if not FilePath.is_file():
        raise P00PError(f"vault is not a regular file: {FilePath}")
    try:
        if FilePath.stat().st_size > MAX_VAULT_FILE_SIZE:
            raise P00PError(f"vault is suspiciously huge: {FilePath}")
        Blob = FilePath.read_bytes()
        # check again because another process can replace or grow it between stat and read.
        if len(Blob) > MAX_VAULT_FILE_SIZE:
            raise P00PError(f"vault is suspiciously huge: {FilePath}")
        return Blob
    except P00PError:
        raise
    except OSError as Exc:
        raise P00PError(f"could not read {FilePath}: {Exc}") from Exc


def LoadVault(FilePath):
    return DecodeVault(ReadVaultBlob(FilePath))


def SaveVault(FilePath, Vault):
    FilePath.parent.mkdir(parents=True, exist_ok=True)
    # encode a copy first. a disk tantrum should not lie about when the live bowl saved.
    Working = Copy.deepcopy(Vault)
    SavedAt = CurrentTime()
    Working["updated_at"] = SavedAt
    Encoded = EncodeVault(Working)
    if len(Encoded) > MAX_VAULT_FILE_SIZE:
        raise P00PError("the vault is too huge to save")
    TemporaryName = None
    try:
        # write beside the real vault, fsync it, then swap it in all at once.
        with Tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{FilePath.name}.", dir=FilePath.parent, delete=False
        ) as Temporary:
            TemporaryName = Temporary.name
            Temporary.write(Encoded)
            Temporary.flush()
            Os.fsync(Temporary.fileno())
        Os.chmod(TemporaryName, 0o600)
        # replace is atomic on the same filesystem, unlike writing over the live file.
        Os.replace(TemporaryName, FilePath)
        Vault["updated_at"] = SavedAt
    except OSError as Exc:
        if TemporaryName:
            try:
                Os.unlink(TemporaryName)
            except OSError:
                pass
        raise P00PError(f"could not save {FilePath}: {Exc}") from Exc


def NormalizeName(Name):
    Cleaned = Name.strip()
    if not Cleaned:
        raise P00PError("entry names cannot be empty")
    if len(Cleaned) > MAX_ENTRY_NAME_LENGTH:
        raise P00PError(f"entry names cannot exceed {MAX_ENTRY_NAME_LENGTH} characters")
    return Cleaned


def FindEntry(Entries, RequestedName):
    # names keep their spelling but commands should not care about capitalization.
    Requested = RequestedName.casefold()
    Matches = [Name for Name in Entries if Name.casefold() == Requested]
    if not Matches:
        raise P00PError(f"entry not found: {RequestedName}")
    return Matches[0]


def GeneratePassword(Length=DEFAULT_PASSWORD_LENGTH, Symbols=True):
    if not MIN_PASSWORD_LENGTH <= Length <= MAX_PASSWORD_LENGTH:
        raise P00PError(
            f"password length must be between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH}"
        )
    Groups = [String.ascii_lowercase, String.ascii_uppercase, String.digits]
    if Symbols:
        Groups.append(PASSWORD_SYMBOLS)
    # pick one from every group first so randomness cannot accidentally skip a whole type.
    Characters = [Secrets.choice(Group) for Group in Groups]
    Alphabet = "".join(Groups)
    Characters.extend(Secrets.choice(Alphabet) for _ in range(Length - len(Characters)))
    # shuffle those guaranteed characters so they do not always sit at the front.
    Secrets.SystemRandom().shuffle(Characters)
    return "".join(Characters)


def PasswordIssues(Password):
    # tiny hygiene checks for the demo. this is not zxcvbn wearing a poop hat.
    Issues = []
    if len(Password) < MIN_PASSWORD_LENGTH:
        Issues.append(f"shorter than {MIN_PASSWORD_LENGTH} characters")
    if Password.casefold() in COMMON_PASSWORDS:
        Issues.append("appears in the tiny common-password list")
    if Password and len(set(Password)) < 4:
        Issues.append("uses very few unique characters")
    if not any(Character.islower() for Character in Password):
        Issues.append("has no lowercase letter")
    if not any(Character.isupper() for Character in Password):
        Issues.append("has no uppercase letter")
    if not any(Character.isdigit() for Character in Password):
        Issues.append("has no digit")
    if not any(not Character.isalnum() for Character in Password):
        Issues.append("has no symbol")
    return Issues


#MARK: command stuffs
def CommandInit(Args):
    if Args.vault.exists() and not Args.force:
        raise P00PError(f"vault already exists: {Args.vault} (use --force to replace it)")
    SaveVault(Args.vault, NewVault())
    print(f"made a suspiciously secure vault at {Args.vault}")
    print("warning: .p00p camouflage is not encryption; use fake passwords for demos")


#MARK: password stuffs
def CommandAdd(Args):
    if Args.no_symbols and Args.generate is None:
        raise P00PError("--no-symbols requires --generate")
    Vault = LoadVault(Args.vault)
    Entries = Vault["entries"]
    Name = NormalizeName(Args.name)
    # case-only duplicates are still duplicates on purpose.
    Existing = next((Item for Item in Entries if Item.casefold() == Name.casefold()), None)
    if Existing and not Args.replace:
        raise P00PError(f"entry already exists: {Existing} (use --replace to update it)")

    GeneratedPassword = Args.generate is not None
    if GeneratedPassword:
        Password = GeneratePassword(Args.generate, Symbols=not Args.no_symbols)
    else:
        Password = Args.password
    if Password is None:
        # getpass keeps the terminal from echoing the password into scrollback.
        Password = Getpass.getpass("password (hidden while typing): ")
    if not Password:
        raise P00PError("password cannot be empty")

    if Existing and Existing != Name:
        # replacing Example with example should rename it, not leave both behind.
        del Entries[Existing]
    Entries[Name] = {
        "username": Args.username or "",
        "password": Password,
        "notes": Args.notes or "",
        "updated_at": CurrentTime(),
    }
    SaveVault(Args.vault, Vault)
    Verb = "updated" if Existing else "added"
    print(f"{Verb} {Name!r} in {Args.vault}")
    if GeneratedPassword:
        print(f"generated password: {Password}")
        print("save it now; this is the only automatic reveal")


#MARK: looking at the stuffs
def CommandList(Args):
    Entries = LoadVault(Args.vault)["entries"]
    if not Entries:
        print("the vault is empty (a pristine bowl)")
        return
    for Name in sorted(Entries, key=str.casefold):
        Username = Entries[Name].get("username") or "-"
        print(f"{Name}\t{Username}")


def CommandGet(Args):
    Entries = LoadVault(Args.vault)["entries"]
    Name = FindEntry(Entries, Args.name)
    Entry = Entries[Name]
    Password = Entry.get("password", "")
    # a fixed-ish mask does not advertise the exact password length by default.
    VisiblePassword = Password if Args.show else ("*" * max(8, min(len(Password), 24)))
    print(f"name:     {Name}")
    print(f"username: {Entry.get('username') or '-'}")
    print(f"password: {VisiblePassword}")
    if Entry.get("notes"):
        print(f"notes:    {Entry['notes']}")
    if not Args.show:
        print("(pass --show to reveal the password)")


def CommandSearch(Args):
    Query = Args.query.strip().casefold()
    if not Query:
        raise P00PError("search query cannot be empty")
    Entries = LoadVault(Args.vault)["entries"]
    Matches = []
    for Name, Entry in Entries.items():
        # never search password contents. matching a secret would be a very weird leak.
        Searchable = (Name, Entry.get("username", ""), Entry.get("notes", ""))
        if any(Query in Value.casefold() for Value in Searchable):
            Matches.append(Name)
    if not Matches:
        print(f"no entries matched {Args.query!r}")
        return
    for Name in sorted(Matches, key=str.casefold):
        Username = Entries[Name].get("username") or "-"
        print(f"{Name}\t{Username}")


def CommandRename(Args):
    Vault = LoadVault(Args.vault)
    Entries = Vault["entries"]
    OldName = FindEntry(Entries, Args.old_name)
    NewName = NormalizeName(Args.new_name)
    Conflict = next(
        # the old row is allowed to change capitalization without colliding with itself.
        (Name for Name in Entries if Name.casefold() == NewName.casefold() and Name != OldName),
        None,
    )
    if Conflict:
        raise P00PError(f"entry already exists: {Conflict}")
    Entry = Entries.pop(OldName)
    Entry["updated_at"] = CurrentTime()
    Entries[NewName] = Entry
    SaveVault(Args.vault, Vault)
    print(f"renamed {OldName!r} to {NewName!r}")


def CommandRemove(Args):
    Vault = LoadVault(Args.vault)
    Entries = Vault["entries"]
    Name = FindEntry(Entries, Args.name)
    if not Args.yes:
        Answer = input(f"remove {Name!r}? [y/N] ").strip().casefold()
        if Answer not in {"y", "yes"}:
            print("cancelled")
            return
    del Entries[Name]
    SaveVault(Args.vault, Vault)
    print(f"removed {Name!r}")


def CommandInfo(Args):
    Vault = LoadVault(Args.vault)
    print(f"file:       {Args.vault}")
    print(f"format:     .p00p v{VERSION} (camouflaged, NOT encrypted)")
    print(f"entries:    {len(Vault['entries'])}")
    print(f"created:    {Vault.get('created_at', 'unknown')}")
    print(f"updated:    {Vault.get('updated_at', 'unknown')}")
    print(f"bad ideas: {len(COMMON_PASSWORDS)} common passwords loaded")
    try:
        Mode = Args.vault.stat().st_mode & 0o777
        print(f"permissions: {Mode:03o}")
    except OSError:
        pass


def CommandGenerate(Args):
    print(GeneratePassword(Args.length, Symbols=not Args.no_symbols))


#MARK: audit stuffs
def CommandAudit(Args):
    Vault = LoadVault(Args.vault)
    Entries = Vault["entries"]
    Findings = 0
    Fingerprints = {}

    print(f"auditing {len(Entries)} entries in {Args.vault}")
    for Name in sorted(Entries, key=str.casefold):
        Entry = Entries[Name]
        Password = Entry.get("password", "")
        Issues = PasswordIssues(Password)
        if not Entry.get("username"):
            Issues.append("has no username")
        if Issues:
            Findings += len(Issues)
            print(f"- {Name}: {'; '.join(Issues)}")
        # hashes only group reused values in memory. the report never prints the secret.
        Fingerprint = Hashlib.sha256(Password.encode("utf-8")).hexdigest()
        Fingerprints.setdefault(Fingerprint, []).append(Name)

    ReusedGroups = [Names for Names in Fingerprints.values() if len(Names) > 1]
    for Names in ReusedGroups:
        Findings += 1
        print(f"- reused password: {', '.join(sorted(Names, key=str.casefold))}")

    FilenameChecks = []
    if not Args.vault.name.startswith("."):
        FilenameChecks.append("vault filename is not hidden")
    if Args.vault.suffix.casefold() not in {".p00p", ".poop"}:
        FilenameChecks.append("vault does not use a suspiciously incorrect extension")
    try:
        Mode = Args.vault.stat().st_mode & 0o777
        if Mode & 0o077:
            FilenameChecks.append(f"vault permissions are {Mode:03o}, not owner-only")
    except OSError:
        FilenameChecks.append("vault permissions could not be checked")
    for Finding in FilenameChecks:
        Findings += 1
        print(f"- file: {Finding}")

    if Findings:
        print(f"result: {Findings} finding(s); the bowl needs attention")
    else:
        print("result: no basic hygiene findings")
    print("reality check: camouflage still is not encryption")


#MARK: doctor stuffs
def VaultDoctorReport(FilePath):
    FilePath = Path(FilePath)
    Blob = ReadVaultBlob(FilePath)
    Header = ParseHeader(Blob)
    Vault = DecodeVault(Blob)
    Context = Doctor.DoctorContext(
        FilePath=FilePath,
        Blob=Blob,
        Header=Header,
        Vault=Vault,
        PasswordIssueFinder=PasswordIssues,
        ExpectedVersion=VERSION,
        MaximumFileSize=MAX_VAULT_FILE_SIZE,
    )
    return Doctor.ExamineVault(Context)


def CommandDoctor(Args):
    if Args.fix_permissions:
        try:
            Mode = Doctor.RepairOwnerOnlyPermissions(Args.vault)
        except OSError as Exc:
            raise P00PError(f"could not repair vault permissions: {Exc}") from Exc
        if not Args.json:
            print(f"permission repair: set {Args.vault} to {Mode:03o}")
    Report = VaultDoctorReport(Args.vault)
    print(Report.AsJson() if Args.json else Report.AsText())


#MARK: lifeboat stuffs
def CommandBackup(Args):
    Source = Path(Args.vault)
    Blob = ReadVaultBlob(Source)
    Vault = DecodeVault(Blob)
    Destination = (
        Path(Args.destination)
        if Args.destination is not None
        else Lifeboat.SuggestedSnapshotPath(Source)
    )
    Receipt = Lifeboat.Launch(
        Source=Source,
        Destination=Destination,
        Blob=Blob,
        EntryCount=len(Vault["entries"]),
        Force=Args.force,
        Action="backup",
    )
    print(Receipt.AsJson() if Args.json else Receipt.AsText())


def CommandRestore(Args):
    Source = Path(Args.source)
    Blob = ReadVaultBlob(Source)
    Vault = DecodeVault(Blob)
    Receipt = Lifeboat.Launch(
        Source=Source,
        Destination=Args.vault,
        Blob=Blob,
        EntryCount=len(Vault["entries"]),
        Force=Args.force,
        Action="restore",
    )
    print(Receipt.AsJson() if Args.json else Receipt.AsText())


#MARK: difference engine stuffs
def CommandDiff(Args):
    LeftPath = Path(Args.vault)
    RightPath = Path(Args.other)
    LeftVault = LoadVault(LeftPath)
    RightVault = LoadVault(RightPath)
    Difference = Compare.CompareVaults(
        LeftVault,
        RightVault,
        LeftPath=LeftPath,
        RightPath=RightPath,
    )
    if Args.json:
        print(Difference.AsJson(Anonymous=Args.anonymous))
    else:
        print(Difference.AsText(Anonymous=Args.anonymous))


#MARK: fake fake password stuffs
def CommandDecoy(Args):
    FilePath = Path(Args.vault)
    if FilePath.exists() and not Args.force:
        raise P00PError(
            f"vault already exists: {FilePath} (use --force to replace it with decoys)"
        )
    Vault = NewVault()
    Recipe = Decoy.DecoyRecipe(Count=Args.count, Seed=Args.seed)
    Decoy.DecoyFactory(Recipe, CurrentTime).FillVault(Vault)
    SaveVault(FilePath, Vault)
    Receipt = Decoy.DecoyReceipt(FilePath, Recipe.Count, Recipe.Deterministic)
    print(Receipt.AsJson() if Args.json else Receipt.AsText())


#MARK: new binary soup same old fake secrets
def RerollVault(FilePath):
    FilePath = Path(FilePath)
    BeforeBlob = ReadVaultBlob(FilePath)
    Header = ParseHeader(BeforeBlob)
    Vault = DecodeVault(BeforeBlob)
    NewSalt = Reroll.FreshSalt(Header["salt"], SALT_SIZE)
    AfterBlob = EncodeVault(Vault, Salt=NewSalt)
    if len(AfterBlob) > MAX_VAULT_FILE_SIZE:
        raise P00PError("rerolled vault somehow crossed the file safety limit")
    # AtomicDock writes beside the live bowl, fsyncs, chmods, then swaps it in.
    Lifeboat.AtomicDock(FilePath, Force=True).Install(AfterBlob)
    return Reroll.RerollReceipt(
        FilePath=FilePath,
        BeforeBlob=BeforeBlob,
        AfterBlob=AfterBlob,
        OldSalt=Header["salt"],
        NewSalt=NewSalt,
        EntryCount=len(Vault["entries"]),
    )


def CommandReroll(Args):
    Receipt = RerollVault(Args.vault)
    print(Receipt.AsJson() if Args.json else Receipt.AsText())


#MARK: bowl counting stuffs
def BowlStatisticsReport(FilePath):
    FilePath = Path(FilePath)
    Blob = ReadVaultBlob(FilePath)
    Header = ParseHeader(Blob)
    Vault = DecodeVault(Blob)
    return BowlStats.BowlStatistics(
        FilePath=FilePath,
        Vault=Vault,
        Blob=Blob,
        Header=Header,
        PasswordIssueFinder=PasswordIssues,
    )


def CommandStats(Args):
    Report = BowlStatisticsReport(Args.vault)
    print(Report.AsJson() if Args.json else Report.AsText())


#MARK: repeatable weird storage science fair stuffs
def StorageLabForVault(FilePath, Rounds=Lab.DEFAULT_ROUNDS):
    Vault = LoadVault(Path(FilePath))
    return Lab.RunStorageLab(
        Vault=Vault,
        Rounds=Rounds,
        EncodeFunction=EncodeVault,
        DecodeFunction=DecodeVault,
        HeaderFunction=ParseHeader,
    )


def CommandLab(Args):
    Result = StorageLabForVault(Args.vault, Args.rounds)
    print(Result.AsJson() if Args.json else Result.AsText())
    return 0 if Result.Passed else 2


#MARK: one giant safe paperwork pile
def SubmissionReportForVault(FilePath):
    FilePath = Path(FilePath)
    Blob = ReadVaultBlob(FilePath)
    Header = ParseHeader(Blob)
    Vault = DecodeVault(Blob)
    DoctorReport = VaultDoctorReport(FilePath)
    StatisticsReport = BowlStatisticsReport(FilePath)
    TheaterReport = SecurityTheaterReport(FilePath)
    LabReport = StorageLabForVault(FilePath, SUBMISSION_LAB_ROUNDS)
    SafeHeader = {
        "magic": "P00P\\0",
        "header_size": Header["header_size"],
        "payload_size": Header["payload_size"],
        "file_size": Header["file_size"],
        "salt": Header["salt"].hex(),
        "digest": Header["digest"].hex(),
    }
    return Report.SubmissionReport(
        FilePath=FilePath,
        ProjectVersion=PROJECT_VERSION,
        FormatVersion=VERSION,
        Header=SafeHeader,
        DoctorPayload=DoctorReport.AsDictionary(),
        StatisticsPayload=StatisticsReport.AsDictionary(),
        TheaterPayload=TheaterReport.AsDictionary(),
        LabPayload=LabReport.AsDictionary(),
        PooplineSummary=PayloadRitualSummary(Vault, Header["salt"]),
    )


def RenderSubmissionReport(Submission, Format):
    if Format == "json":
        return Submission.AsJson()
    if Format == "text":
        return Submission.AsText()
    return Submission.AsMarkdown()


def CommandReport(Args):
    Submission = SubmissionReportForVault(Args.vault)
    Text = RenderSubmissionReport(Submission, Args.format)
    if Args.output is None:
        print(Text)
        return
    Destination = Report.WriteReport(Args.output, Text, Force=Args.force)
    print(f"wrote secret-safe {Args.format} report to {Destination}")


#MARK: pouring two bowls into a third bowl
def MergeVaultFiles(LeftPath, RightPath, OutputPath, Policy, Force=False):
    LeftPath = Path(LeftPath)
    RightPath = Path(RightPath)
    OutputPath = Path(OutputPath)
    if Lifeboat.PathsPointToSamePlace(OutputPath, LeftPath):
        raise Merge.MergeError("merge output cannot replace the left input vault")
    if Lifeboat.PathsPointToSamePlace(OutputPath, RightPath):
        raise Merge.MergeError("merge output cannot replace the right input vault")
    LeftVault = LoadVault(LeftPath)
    RightVault = LoadVault(RightPath)
    Plan, MergedVault = Merge.MergeVaults(
        LeftVault,
        RightVault,
        Policy,
        CurrentTime,
    )
    ValidateVault(MergedVault)
    Encoded = EncodeVault(MergedVault)
    Lifeboat.AtomicDock(OutputPath, Force=Force).Install(Encoded)
    return Plan.Receipt(LeftPath, RightPath, OutputPath)


def CommandMerge(Args):
    Receipt = MergeVaultFiles(
        LeftPath=Args.vault,
        RightPath=Args.right,
        OutputPath=Args.output,
        Policy=Args.conflict,
        Force=Args.force,
    )
    print(Receipt.AsJson() if Args.json else Receipt.AsText())


#MARK: toilet-wax byte identity seal stuffs
def CreateVaultSeal(VaultPath, SealPath=None, Force=False):
    VaultPath = Path(VaultPath)
    SealPath = Seal.SuggestedSealPath(VaultPath) if SealPath is None else Path(SealPath)
    if Lifeboat.PathsPointToSamePlace(VaultPath, SealPath):
        raise Seal.SealError("seal output cannot replace the vault it describes")
    Blob = ReadVaultBlob(VaultPath)
    Vault = DecodeVault(Blob)
    Document = Seal.BuildSeal(
        VaultPath=VaultPath,
        Blob=Blob,
        EntryCount=len(Vault["entries"]),
        SealedAt=CurrentTime(),
    )
    Lifeboat.AtomicDock(SealPath, Force=Force).Install(Seal.EncodeSeal(Document))
    return SealPath, Document


def VerifyVaultSeal(VaultPath, SealPath=None):
    VaultPath = Path(VaultPath)
    SealPath = Seal.SuggestedSealPath(VaultPath) if SealPath is None else Path(SealPath)
    Blob = ReadVaultBlob(VaultPath)
    Vault = DecodeVault(Blob)
    Document = Seal.ReadSeal(SealPath)
    return Seal.VerifySeal(
        Document,
        SealPath=SealPath,
        VaultPath=VaultPath,
        Blob=Blob,
        EntryCount=len(Vault["entries"]),
    )


def CommandSeal(Args):
    SealPath, Document = CreateVaultSeal(
        VaultPath=Args.vault,
        SealPath=Args.output,
        Force=Args.force,
    )
    if Args.json:
        Receipt = {"seal_path": str(SealPath), **Document}
        print(Json.dumps(Receipt, indent=2, sort_keys=True))
        return
    print("P00P TOILET-WAX SEAL STAMPED")
    print(f"vault:   {Args.vault}")
    print(f"seal:    {SealPath}")
    print(f"bytes:   {Document['vault_bytes']}")
    print(f"entries: {Document['entry_count']}")
    print(f"sha256:  {Document['vault_sha256']}")
    print("notice: byte identity is not encryption or authentication")


def CommandVerifySeal(Args):
    Result = VerifyVaultSeal(Args.vault, Args.seal_path)
    print(Result.AsJson() if Args.json else Result.AsText())
    return 0 if Result.Passed else 2


#MARK: absurd hash-chained bowl paperwork
def RecordVaultLedger(VaultPath, LedgerPath=None, Action="checkpoint"):
    VaultPath = Path(VaultPath)
    LedgerPath = (
        Ledger.SuggestedLedgerPath(VaultPath)
        if LedgerPath is None else Path(LedgerPath)
    )
    if Lifeboat.PathsPointToSamePlace(VaultPath, LedgerPath):
        raise Ledger.LedgerError("ledger cannot replace the vault it describes")
    Blob = ReadVaultBlob(VaultPath)
    Vault = DecodeVault(Blob)
    Records = Ledger.ReadLedger(LedgerPath) if LedgerPath.exists() else []
    Records, _Record = Ledger.AppendRecord(
        Records=Records,
        VaultPath=VaultPath,
        Blob=Blob,
        EntryCount=len(Vault["entries"]),
        Action=Action,
        RecordedAt=CurrentTime(),
    )
    Encoded = Ledger.EncodeLedger(Records)
    Lifeboat.AtomicDock(LedgerPath, Force=LedgerPath.exists()).Install(Encoded)
    return Ledger.VerifyLedger(
        Records,
        LedgerPath=LedgerPath,
        VaultPath=VaultPath,
        Blob=Blob,
        EntryCount=len(Vault["entries"]),
    )


def VerifyVaultLedger(VaultPath, LedgerPath=None):
    VaultPath = Path(VaultPath)
    LedgerPath = (
        Ledger.SuggestedLedgerPath(VaultPath)
        if LedgerPath is None else Path(LedgerPath)
    )
    Blob = ReadVaultBlob(VaultPath)
    Vault = DecodeVault(Blob)
    Records = Ledger.ReadLedger(LedgerPath)
    return Ledger.VerifyLedger(
        Records,
        LedgerPath=LedgerPath,
        VaultPath=VaultPath,
        Blob=Blob,
        EntryCount=len(Vault["entries"]),
    )


def CommandLedger(Args):
    if Args.record is None:
        Result = VerifyVaultLedger(Args.vault, Args.ledger_path)
    else:
        Result = RecordVaultLedger(
            Args.vault,
            LedgerPath=Args.ledger_path,
            Action=Args.record,
        )
    print(Result.AsJson() if Args.json else Result.AsText())
    return 0 if Result.Passed else 2

# CommandScatter receives a Namespace with path-like vault/output_prefix and bool json.
# It validates one bowl, publishes exactly three new fragments, and returns None.
# Blob is immutable bytes containing the exact on-disk p00p envelope, not decoded JSON.
# It is size-bounded by ReadVaultBlob and must pass DecodeVault before publication.
# Receipt is a ScatterReceipt created only after all three fragments publish successfully.
# It renders paths/counts/digests only and never receives decoded credential fields.
def CommandScatter(Args): Blob = ReadVaultBlob(Args.vault); DecodeVault(Blob); Receipt = Scatter.ScatterToFiles(Args.vault, Blob, Prefix=Args.output_prefix); print(Receipt.AsJson() if Args.json else Receipt.AsText())

# CommandGather receives Path left/right/output plus bool force/json Namespace fields.
# It validates/rebuilds/decodes before atomic output, prints a receipt, and returns None.
# Blob is immutable reconstructed bytes whose fragment metadata and SHA-256 already match.
# It must additionally pass DecodeVault before any output file can be installed.
# SetId is exactly 16 immutable matched-header bytes and is an identifier, never a key.
# It is receipt correlation metadata only and grants no overwrite or trust authority.
# Receipt is a GatherReceipt constructed only after AtomicDock installs the valid bowl.
# It renders paths/size/digest/set id only and never receives decoded credentials.
def CommandGather(Args): Blob, SetId = Scatter.GatherFromFiles(Args.left, Args.right); Lifeboat.Launch(Source=Args.left if Lifeboat.PathsPointToSamePlace(Args.output, Args.left) else Args.right, Destination=Args.output, Blob=Blob, EntryCount=len(DecodeVault(Blob)["entries"]), Force=Args.force, Action="restore"); Receipt = Scatter.GatherReceipt((Args.left, Args.right), Args.output, Blob, SetId); print(Receipt.AsJson() if Args.json else Receipt.AsText())

# CommandRepair receives Path left/right/output, integer index, and bool force fields.
# It atomically installs one validated fragment and never replaces either source path.
def CommandRepair(Args): Lifeboat.Launch(Source=Args.left if Lifeboat.PathsPointToSamePlace(Args.output, Args.left) else Args.right, Destination=Args.output, Blob=Scatter.RepairFragment(Scatter.ReadFragment(Args.left), Scatter.ReadFragment(Args.right), Args.index).Encode(), EntryCount=0, Force=Args.force, Action="repair-fragment"); print(Args.output)


#MARK: security theater stuffs
def SecurityTheaterReport(FilePath):
    Blob = ReadVaultBlob(Path(FilePath))
    Header = ParseHeader(Blob)
    Vault = DecodeVault(Blob)
    Receipts = Poopline.InspectPayloadRitual(Vault, Header["salt"], CAMOUFLAGE_KEY)
    return Theater.ScoreSecurityTheater(Vault, FilePath, Blob, Header, Receipts)


def CommandTheater(Args):
    print(SecurityTheaterReport(Args.vault).AsText())


#MARK: file guts
def CommandAnatomy(Args):
    # show the binary sandwich without dumping the decoded entry values.
    Blob = ReadVaultBlob(Args.vault)
    Header = ParseHeader(Blob)
    Vault = DecodeVault(Blob)
    print(f"file:         {Args.vault}")
    print(f"magic:        {MAGIC!r}")
    print(f"version:      {Header['version']}")
    print(f"salt:         {Header['salt'].hex()}")
    print(f"header bytes: {Header['header_size']}")
    print(f"payload bytes:{Header['payload_size']:>5}")
    print(f"checksum:     {Header['digest'].hex()}")
    print(f"total bytes:  {Header['file_size']}")
    print(f"decoded:      {len(Vault['entries'])} entries, integrity check passed")
    print(f"poopline:     {PayloadRitualSummary(Vault, Header['salt'])}")


#MARK: graphical stuffs
def ParseTkVersion(Value):
    try:
        Parts = str(Value).split(".")
        return tuple(int(Part) for Part in Parts[:2])
    except (TypeError, ValueError):
        return (0, 0)


def CurrentTkVersion():
    try:
        import tkinter as Tk
        return ParseTkVersion(Tk.TkVersion)
    except ImportError:
        return (0, 0)


def GuiPythonCandidates():
    Project = Path(__file__).resolve().parent
    Candidates = [Project / ".venv" / "bin" / "python"]
    CustomPython = Os.environ.get("P00P_GUI_PYTHON")
    if CustomPython:
        Candidates.append(Path(CustomPython).expanduser())

    # python.org works fine too. homebrew is an option, not a requirement.
    for Version in ("3.15", "3.14", "3.13", "3.12", "3.11", "3.10", "3.9"):
        Candidates.append(Path(f"/Library/Frameworks/Python.framework/Versions/{Version}/bin/python3"))
    for Prefix in (Path("/opt/homebrew"), Path("/usr/local")):
        Candidates.append(Prefix / "bin" / "python3")
        for Version in ("3.15", "3.14", "3.13", "3.12", "3.11", "3.10", "3.9"):
            Candidates.append(Prefix / "bin" / f"python{Version}")
            Candidates.append(Prefix / "opt" / f"python@{Version}" / "libexec" / "bin" / "python3")

    Seen = set()
    for Candidate in Candidates:
        if Candidate not in Seen:
            Seen.add(Candidate)
            yield Candidate


def ProbeTkVersion(PythonPath):
    try:
        Result = Subprocess.run(
            (str(PythonPath), "-c", "import tkinter as Tk; print(Tk.TkVersion)"),
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, Subprocess.TimeoutExpired):
        return (0, 0)
    if Result.returncode != 0:
        return (0, 0)
    return ParseTkVersion(Result.stdout.strip())


def FindCompatibleGuiPython():
    CurrentPython = Path(Sys.executable).resolve()
    for Candidate in GuiPythonCandidates():
        try:
            if not Candidate.is_file() or Candidate.resolve() == CurrentPython:
                continue
        except OSError:
            continue
        if ProbeTkVersion(Candidate) >= (8, 6):
            return Candidate.resolve()
    return None


def GuiRuntimeError(Version):
    VersionText = ".".join(str(Part) for Part in Version) if Version != (0, 0) else "missing"
    return P00PError(
        f"this python has Tk {VersionText}, but the GUI needs Tk 8.6+. "
        "make the project .venv and install requirements.txt with a current Python.org python. "
        "u can also set P00P_GUI_PYTHON to a compatible python path"
    )


def CommandGui(Args):
    TkVersion = CurrentTkVersion()
    if Sys.platform == "darwin" and TkVersion < (8, 6):
        BetterPython = FindCompatibleGuiPython()
        if BetterPython is None:
            raise GuiRuntimeError(TkVersion)
        MainPath = Path(__file__).resolve()
        Os.execv(
            str(BetterPython),
            (str(BetterPython), str(MainPath), "gui", "--vault", str(Args.vault)),
        )
        return
    from gui import RunGui
    RunGui(StartPath=Args.vault)


#MARK: argument stuffs
def AddVaultArgument(Parser):
    Parser.add_argument(
        "--vault",
        type=Path,
        default=Path(Os.environ.get("P00P_FILE", DEFAULT_VAULT)),
        help=f"vault path (default: {DEFAULT_VAULT}, or $P00P_FILE)",
    )


def BuildParser():
    Parser = Argparse.ArgumentParser(
        prog="p00p",
        description="hide fake passwords in a very serious custom file format",
        epilog="This is a Hack Club demo, not a secure password manager.",
    )
    Parser.add_argument("--version", action="version", version=f"p00p {PROJECT_VERSION}")
    Subparsers = Parser.add_subparsers(dest="command", required=True)

    InitParser = Subparsers.add_parser("init", help="create an empty vault")
    AddVaultArgument(InitParser)
    InitParser.add_argument("--force", action="store_true", help="replace an existing vault")
    InitParser.set_defaults(handler=CommandInit)

    AddParser = Subparsers.add_parser("add", help="add an entry")
    AddVaultArgument(AddParser)
    AddParser.add_argument("name", help="entry name, such as example.com")
    AddParser.add_argument("-u", "--username", help="username or email")
    PasswordGroup = AddParser.add_mutually_exclusive_group()
    PasswordGroup.add_argument(
        "-p", "--password", help="password (prompted securely if omitted)"
    )
    PasswordGroup.add_argument(
        "-g",
        "--generate",
        nargs="?",
        const=DEFAULT_PASSWORD_LENGTH,
        type=int,
        metavar="LENGTH",
        help=f"generate a password (default length: {DEFAULT_PASSWORD_LENGTH})",
    )
    AddParser.add_argument("-n", "--notes", help="optional notes")
    AddParser.add_argument(
        "--no-symbols", action="store_true", help="omit symbols from a generated password"
    )
    AddParser.add_argument("--replace", action="store_true", help="replace a matching entry")
    AddParser.set_defaults(handler=CommandAdd)

    ListParser = Subparsers.add_parser("list", help="list entry names")
    AddVaultArgument(ListParser)
    ListParser.set_defaults(handler=CommandList)

    GetParser = Subparsers.add_parser("get", help="show one entry")
    AddVaultArgument(GetParser)
    GetParser.add_argument("name", help="entry name (case-insensitive)")
    GetParser.add_argument("--show", action="store_true", help="reveal the stored password")
    GetParser.set_defaults(handler=CommandGet)

    SearchParser = Subparsers.add_parser(
        "search", help="search names, usernames, and notes"
    )
    AddVaultArgument(SearchParser)
    SearchParser.add_argument("query", help="case-insensitive search text")
    SearchParser.set_defaults(handler=CommandSearch)

    RenameParser = Subparsers.add_parser("rename", help="rename an entry")
    AddVaultArgument(RenameParser)
    RenameParser.add_argument("old_name", help="current entry name")
    RenameParser.add_argument("new_name", help="new entry name")
    RenameParser.set_defaults(handler=CommandRename)

    RemoveParser = Subparsers.add_parser("remove", aliases=["rm"], help="remove an entry")
    AddVaultArgument(RemoveParser)
    RemoveParser.add_argument("name", help="entry name (case-insensitive)")
    RemoveParser.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    RemoveParser.set_defaults(handler=CommandRemove)

    InfoParser = Subparsers.add_parser("info", help="inspect vault metadata")
    AddVaultArgument(InfoParser)
    InfoParser.set_defaults(handler=CommandInfo)

    GenerateParser = Subparsers.add_parser(
        "generate", aliases=["gen"], help="generate a random password"
    )
    GenerateParser.add_argument(
        "-l",
        "--length",
        type=int,
        default=DEFAULT_PASSWORD_LENGTH,
        help=f"password length (default: {DEFAULT_PASSWORD_LENGTH})",
    )
    GenerateParser.add_argument(
        "--no-symbols", action="store_true", help="generate only letters and digits"
    )
    GenerateParser.set_defaults(handler=CommandGenerate)

    AuditParser = Subparsers.add_parser(
        "audit", help="check password and file hygiene without revealing secrets"
    )
    AddVaultArgument(AuditParser)
    AuditParser.set_defaults(handler=CommandAudit)

    DoctorParser = Subparsers.add_parser(
        "doctor", help="run over-engineered diagnostics without revealing secrets"
    )
    AddVaultArgument(DoctorParser)
    DoctorParser.add_argument(
        "--json", action="store_true", help="print a machine-readable diagnostic report"
    )
    DoctorParser.add_argument(
        "--fix-permissions",
        action="store_true",
        help="set the vault file to owner-read/write (600) before checking it",
    )
    DoctorParser.set_defaults(handler=CommandDoctor)

    BackupParser = Subparsers.add_parser(
        "backup", aliases=["lifeboat"], help="make an atomic byte-for-byte vault snapshot"
    )
    AddVaultArgument(BackupParser)
    BackupParser.add_argument(
        "destination",
        nargs="?",
        type=Path,
        help="snapshot path (default: hidden timestamped .p00p beside the vault)",
    )
    BackupParser.add_argument(
        "--force", action="store_true", help="replace an existing destination"
    )
    BackupParser.add_argument(
        "--json", action="store_true", help="print a machine-readable lifeboat receipt"
    )
    BackupParser.set_defaults(handler=CommandBackup)

    RestoreParser = Subparsers.add_parser(
        "restore", help="atomically restore a validated lifeboat snapshot"
    )
    AddVaultArgument(RestoreParser)
    RestoreParser.add_argument("source", type=Path, help="snapshot to restore")
    RestoreParser.add_argument(
        "--force", action="store_true", help="replace an existing destination vault"
    )
    RestoreParser.add_argument(
        "--json", action="store_true", help="print a machine-readable lifeboat receipt"
    )
    RestoreParser.set_defaults(handler=CommandRestore)

    DiffParser = Subparsers.add_parser(
        "diff", aliases=["compare"], help="compare two decoded vaults without printing secrets"
    )
    AddVaultArgument(DiffParser)
    DiffParser.add_argument("other", type=Path, help="other vault to compare against")
    DiffParser.add_argument(
        "--anonymous", action="store_true", help="hide entry names as well as credential values"
    )
    DiffParser.add_argument(
        "--json", action="store_true", help="print a machine-readable difference report"
    )
    DiffParser.set_defaults(handler=CommandDiff)

    DecoyParser = Subparsers.add_parser(
        "decoy", aliases=["demo"], help="make a bowl full of unmistakably fake demo logins"
    )
    AddVaultArgument(DecoyParser)
    DecoyParser.add_argument(
        "-c", "--count", type=int, default=12,
        help="number of fake entries (default: 12, maximum: 500)",
    )
    DecoyParser.add_argument(
        "--seed", help="optional repeatable seed for screenshots and demos"
    )
    DecoyParser.add_argument(
        "--force", action="store_true", help="replace an existing vault with decoys"
    )
    DecoyParser.add_argument(
        "--json", action="store_true", help="print a machine-readable foundry receipt"
    )
    DecoyParser.set_defaults(handler=CommandDecoy)

    RerollParser = Subparsers.add_parser(
        "reroll", aliases=["repack"],
        help="rewrap unchanged data with fresh random camouflage",
    )
    AddVaultArgument(RerollParser)
    RerollParser.add_argument(
        "--json", action="store_true", help="print a machine-readable reroll receipt"
    )
    RerollParser.set_defaults(handler=CommandReroll)

    StatsParser = Subparsers.add_parser(
        "stats", aliases=["count"],
        help="show aggregate bowl statistics without printing credentials",
    )
    AddVaultArgument(StatsParser)
    StatsParser.add_argument(
        "--json", action="store_true", help="print machine-readable bowl statistics"
    )
    StatsParser.set_defaults(handler=CommandStats)

    LabParser = Subparsers.add_parser(
        "lab", aliases=["bench"],
        help="benchmark and poke the weird format without printing credentials",
    )
    AddVaultArgument(LabParser)
    LabParser.add_argument(
        "-r", "--rounds", type=int, default=Lab.DEFAULT_ROUNDS,
        help=f"encode/decode rounds (default: {Lab.DEFAULT_ROUNDS}, max: {Lab.MAX_ROUNDS})",
    )
    LabParser.add_argument(
        "--json", action="store_true", help="print machine-readable lab results"
    )
    LabParser.set_defaults(handler=CommandLab)

    ReportParser = Subparsers.add_parser(
        "report", help="combine anatomy, doctor, stats, theater, and lab into one safe report"
    )
    AddVaultArgument(ReportParser)
    ReportParser.add_argument(
        "-f", "--format", choices=("text", "markdown", "json"), default="markdown",
        help="report format (default: markdown)",
    )
    ReportParser.add_argument(
        "-o", "--output", type=Path, help="write atomically instead of printing"
    )
    ReportParser.add_argument(
        "--force", action="store_true", help="replace an existing output report"
    )
    ReportParser.set_defaults(handler=CommandReport)

    MergeParser = Subparsers.add_parser(
        "merge", aliases=["combine"],
        help="combine two vaults into a separate output bowl",
    )
    AddVaultArgument(MergeParser)
    MergeParser.add_argument("right", type=Path, help="second input vault")
    MergeParser.add_argument(
        "-o", "--output", type=Path, required=True, help="new merged vault path"
    )
    MergeParser.add_argument(
        "--conflict", choices=Merge.POLICIES, default=Merge.POLICY_ERROR,
        help="name-conflict policy (default: error)",
    )
    MergeParser.add_argument(
        "--force", action="store_true", help="replace an existing output vault"
    )
    MergeParser.add_argument(
        "--json", action="store_true", help="print a machine-readable merge receipt"
    )
    MergeParser.set_defaults(handler=CommandMerge)

    SealParser = Subparsers.add_parser(
        "seal", aliases=["stamp"],
        help="write a secret-safe SHA-256 sidecar for this exact vault",
    )
    AddVaultArgument(SealParser)
    SealParser.add_argument(
        "-o", "--output", type=Path,
        help="seal path (default: <vault>.seal.json)",
    )
    SealParser.add_argument(
        "--force", action="store_true", help="replace an existing seal"
    )
    SealParser.add_argument(
        "--json", action="store_true", help="print the seal receipt as JSON"
    )
    SealParser.set_defaults(handler=CommandSeal)

    VerifySealParser = Subparsers.add_parser(
        "verify-seal", aliases=["check-seal"],
        help="check whether a vault still exactly matches its byte seal",
    )
    AddVaultArgument(VerifySealParser)
    VerifySealParser.add_argument(
        "seal_path", nargs="?", type=Path,
        help="seal path (default: <vault>.seal.json)",
    )
    VerifySealParser.add_argument(
        "--json", action="store_true", help="print machine-readable verification"
    )
    VerifySealParser.set_defaults(handler=CommandVerifySeal)

    LedgerParser = Subparsers.add_parser(
        "ledger", aliases=["logbook"],
        help="verify or append secret-safe hash-chained bowl paperwork",
    )
    AddVaultArgument(LedgerParser)
    LedgerParser.add_argument(
        "--record", choices=Ledger.EVENT_ACTIONS,
        help="append one controlled action before verifying the current bowl",
    )
    LedgerParser.add_argument(
        "--ledger-path", type=Path,
        help="ledger path (default: <vault>.ledger.jsonl)",
    )
    LedgerParser.add_argument(
        "--json", action="store_true", help="print machine-readable ledger verification"
    )
    LedgerParser.set_defaults(handler=CommandLedger)

    # ScatterParser is an argparse parser owned only by the scatter/shard command branch.
    # It yields Path vault/output_prefix, bool json, and callable CommandScatter fields.
    ScatterParser = Subparsers.add_parser("scatter", aliases=["shard"], help="split one bowl into three fragments; any two can recover it")
    AddVaultArgument(ScatterParser)
    ScatterParser.add_argument("-o", "--output-prefix", type=Path, help="fragment name prefix (default: <vault>.fragment)")
    ScatterParser.add_argument("--json", action="store_true", help="print a machine-readable scatter receipt")
    ScatterParser.set_defaults(handler=CommandScatter)

    # GatherParser is an argparse parser owned only by the gather/unshard branch.
    # It yields Path left/right/output, bool force/json, and callable handler fields.
    GatherParser = Subparsers.add_parser("gather", aliases=["unshard"], help="rebuild a bowl from any two matching fragments")
    GatherParser.add_argument("left", type=Path, help="first fragment path (any index)")
    GatherParser.add_argument("right", type=Path, help="second fragment path (different index)")
    GatherParser.add_argument("-o", "--output", type=Path, required=True, help="new recovered vault path")
    GatherParser.add_argument("--force", action="store_true", help="replace an existing output vault")
    GatherParser.add_argument("--json", action="store_true", help="print a machine-readable gather receipt")
    GatherParser.set_defaults(handler=CommandGather)

    # RepairParser is an argparse parser owned only by the repair-fragment branch.
    # It yields Path left/right/output, int index, bool force, and CommandRepair fields.
    RepairParser = Subparsers.add_parser("repair-fragment", aliases=["repair-shard"], help="recreate one missing fragment from the other two")
    RepairParser.add_argument("left", type=Path, help="first surviving fragment path (any index)")
    RepairParser.add_argument("right", type=Path, help="second surviving fragment path (different index)")
    RepairParser.add_argument("--index", type=int, choices=(1, 2, 3), required=True, help="missing fragment index to recreate")
    RepairParser.add_argument("-o", "--output", type=Path, required=True, help="new repaired fragment path")
    RepairParser.add_argument("--force", action="store_true", help="replace an existing non-source output fragment")
    RepairParser.set_defaults(handler=CommandRepair)

    TheaterParser = Subparsers.add_parser(
        "theater", help="calculate a completely fake security theater score"
    )
    AddVaultArgument(TheaterParser)
    TheaterParser.set_defaults(handler=CommandTheater)

    AnatomyParser = Subparsers.add_parser(
        "anatomy", help="explain the vault's binary envelope"
    )
    AddVaultArgument(AnatomyParser)
    AnatomyParser.set_defaults(handler=CommandAnatomy)

    GuiParser = Subparsers.add_parser("gui", help="open the tkinter password bowl")
    AddVaultArgument(GuiParser)
    GuiParser.set_defaults(handler=CommandGui)
    return Parser


#MARK: start the app
def RunApp(CommandArgs=None):
    Parser = BuildParser()
    Args = Parser.parse_args(CommandArgs)
    try:
        Result = Args.handler(Args)
    except (
        P00PError,
        Lifeboat.LifeboatError,
        Decoy.DecoyError,
        Reroll.RerollError,
        Report.ReportError,
        Merge.MergeError,
        Seal.SealError,
        Lab.LabError,
        Ledger.LedgerError,
        Scatter.ScatterError,
        KeyboardInterrupt,
        EOFError,
    ) as Exc:
        Message = str(Exc) or "cancelled"
        print(f"p00p: {Message}", file=Sys.stderr)
        return 1
    return 0 if Result is None else int(Result)


if __name__ == "__main__":
    raise SystemExit(RunApp())

