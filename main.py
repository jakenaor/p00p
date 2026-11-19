#------------------------------------------------------------------#
# persistent 0-leak 0bject protocol                               #
# the password manager that is actually safe probably              #
# app by jakenaor                                                  #
#                                                                  #
# no more stolen passwords after you download fartnite :D          #
# hackers cant see dot files. this is definitely how security works#
#------------------------------------------------------------------#

# anti-hacker stuffs

import argparse as Argparse
import getpass as Getpass
import hashlib as Hashlib
import os as Os
import secrets as Secrets
import string as String
import struct as Struct
import subprocess as Subprocess
import sys as Sys
import tempfile as Tempfile
from datetime import datetime as DateTime, timezone as Timezone
from pathlib import Path

import poopline as Poopline
import theater as Theater


MAGIC = b"P00P\x00"
VERSION = 1
SALT_SIZE = 16
DIGEST_SIZE = 16
DEFAULT_VAULT = ".passwords.p00p"
CAMOUFLAGE_KEY = b"persistent-zero-leak-object-protocol-but-not-really"
PROJECT_VERSION = "0.2.0"
DEFAULT_PASSWORD_LENGTH = 24
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256
PASSWORD_SYMBOLS = "!@#$%^&*()-_=+[]{}:,.?"
COMMON_PASSWORDS = {
    "12345678",
    "letmein",
    "password",
    "password1",
    "qwerty",
    "qwerty123",
}


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
    # looks random enough to grep. it is still not encryption dum dum.
    return Poopline.CamouflageBytes(Data, Salt, CAMOUFLAGE_KEY)


def EncodeVault(Vault, Salt=None):
    ValidateVault(Vault)
    Salt = Salt or Secrets.token_bytes(SALT_SIZE)
    Payload = Poopline.EncodePayload(Vault, Salt, CAMOUFLAGE_KEY)
    Header = MAGIC + bytes([VERSION]) + Salt + Struct.pack(">I", len(Payload))
    Digest = Hashlib.sha256(Header + Payload).digest()[:DIGEST_SIZE]
    return Header + Payload + Digest


def DecodeVault(Blob):
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
    if not Secrets.compare_digest(Digest, ExpectedDigest):
        raise P00PError("the vault is corrupted (integrity check failed)")

    try:
        Vault = Poopline.DecodePayload(Payload, Salt, CAMOUFLAGE_KEY)
    except Poopline.PooplineError as Exc:
        raise P00PError(f"the vault payload could not be decoded ({Exc.StageName} failed)") from Exc

    ValidateVault(Vault)
    return Vault


def PayloadRitualSummary(Vault, Salt):
    Receipts = Poopline.InspectPayloadRitual(Vault, Salt, CAMOUFLAGE_KEY)
    return " -> ".join(
        f"{Receipt['stage']} {Receipt['before_size']}B>{Receipt['after_size']}B"
        for Receipt in Receipts
    )


#MARK: checking the poops
def ValidateVault(Vault):
    if not isinstance(Vault, dict) or Vault.get("protocol") != "p00p":
        raise P00PError("the vault has an invalid structure")
    Entries = Vault.get("entries")
    if not isinstance(Entries, dict):
        raise P00PError("the vault has an invalid entries table")
    for Name, Entry in Entries.items():
        if not isinstance(Name, str) or not Name.strip() or not isinstance(Entry, dict):
            raise P00PError("the vault contains a malformed entry")
        for Field in ("username", "password", "notes"):
            if not isinstance(Entry.get(Field, ""), str):
                raise P00PError(f"entry {Name!r} has an invalid {Field}")


#MARK: file guts
def ParseHeader(Blob):
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
        return FilePath.read_bytes()
    except OSError as Exc:
        raise P00PError(f"could not read {FilePath}: {Exc}") from Exc


def LoadVault(FilePath):
    return DecodeVault(ReadVaultBlob(FilePath))


def SaveVault(FilePath, Vault):
    FilePath.parent.mkdir(parents=True, exist_ok=True)
    Vault["updated_at"] = CurrentTime()
    Encoded = EncodeVault(Vault)
    TemporaryName = None
    try:
        with Tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{FilePath.name}.", dir=FilePath.parent, delete=False
        ) as Temporary:
            TemporaryName = Temporary.name
            Temporary.write(Encoded)
            Temporary.flush()
            Os.fsync(Temporary.fileno())
        Os.chmod(TemporaryName, 0o600)
        Os.replace(TemporaryName, FilePath)
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
    return Cleaned


def FindEntry(Entries, RequestedName):
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
    Characters = [Secrets.choice(Group) for Group in Groups]
    Alphabet = "".join(Groups)
    Characters.extend(Secrets.choice(Alphabet) for _ in range(Length - len(Characters)))
    Secrets.SystemRandom().shuffle(Characters)
    return "".join(Characters)


def PasswordIssues(Password):
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
    Existing = next((Item for Item in Entries if Item.casefold() == Name.casefold()), None)
    if Existing and not Args.replace:
        raise P00PError(f"entry already exists: {Existing} (use --replace to update it)")

    GeneratedPassword = Args.generate is not None
    if GeneratedPassword:
        Password = GeneratePassword(Args.generate, Symbols=not Args.no_symbols)
    else:
        Password = Args.password
    if Password is None:
        Password = Getpass.getpass("password (hidden while typing): ")
    if not Password:
        raise P00PError("password cannot be empty")

    if Existing and Existing != Name:
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
    Candidates = []
    CustomPython = Os.environ.get("P00P_GUI_PYTHON")
    if CustomPython:
        Candidates.append(Path(CustomPython).expanduser())
    Candidates.append(Path(__file__).resolve().parent / ".venv" / "bin" / "python")

    for Prefix in (Path("/opt/homebrew"), Path("/usr/local")):
        Candidates.append(Prefix / "bin" / "python3")
        for Version in ("3.15", "3.14", "3.13", "3.12", "3.11", "3.10", "3.9"):
            Candidates.append(Prefix / "bin" / f"python{Version}")
            Candidates.append(Prefix / "opt" / f"python@{Version}" / "libexec" / "bin" / "python3")

    FrameworkRoot = Path("/Library/Frameworks/Python.framework/Versions")
    Candidates.append(FrameworkRoot / "Current" / "bin" / "python3")
    for Version in ("3.15", "3.14", "3.13", "3.12", "3.11", "3.10", "3.9"):
        Candidates.append(FrameworkRoot / Version / "bin" / "python3")

    Seen = set()
    for Candidate in Candidates:
        Candidate = Path(Candidate)
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


def CustomTkinterAvailable():
    try:
        import customtkinter
        return bool(customtkinter)
    except ImportError:
        return False


def ProbeGuiRuntime(PythonPath):
    try:
        Result = Subprocess.run(
            (str(PythonPath), "-c",
             "import tkinter as Tk, customtkinter; print(Tk.TkVersion)"),
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, Subprocess.TimeoutExpired):
        return False
    return Result.returncode == 0 and ParseTkVersion(Result.stdout.strip()) >= (8, 6)


def FindCompatibleGuiPython():
    CurrentPython = Path(Sys.executable).absolute()
    for Candidate in GuiPythonCandidates():
        try:
            if not Candidate.is_file() or Candidate.absolute() == CurrentPython:
                continue
        except OSError:
            continue
        if ProbeGuiRuntime(Candidate):
            return Candidate.absolute()
    return None


def GuiRuntimeError(Version):
    VersionText = ".".join(str(Part) for Part in Version) if Version != (0, 0) else "missing"
    return P00PError(
        f"this python has Tk {VersionText}, but the GUI needs Tk 8.6+ and CustomTkinter. "
        "run 'python3.12 -m venv .venv' and '.venv/bin/pip install -r requirements.txt', "
        "then launch it again"
    )


def CommandGui(Args):
    TkVersion = CurrentTkVersion()
    if TkVersion < (8, 6) or not CustomTkinterAvailable():
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
        Args.handler(Args)
    except (P00PError, KeyboardInterrupt, EOFError) as Exc:
        Message = str(Exc) or "cancelled"
        print(f"p00p: {Message}", file=Sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(RunApp())
