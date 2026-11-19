#------------------------------------------------------------------#
# p00p scatter crate                                               #
# three weird fragments, any two rebuild the exact original bowl   #
#------------------------------------------------------------------#

import hashlib as Hashlib
import json as Json
import os as Os
import secrets as Secrets
import struct as Struct
import tempfile as Tempfile
from pathlib import Path


FRAGMENT_MAGIC = b"P00PSHRD"
FRAGMENT_VERSION = 1
THRESHOLD = 2
FRAGMENT_COUNT = 3
SET_ID_BYTES = 16
MAX_FRAGMENT_PAYLOAD = 16 * 1024 * 1024
HEADER = Struct.Struct(">8sBBBB16sQ32s32s")


class ScatterError(Exception):
    pass


#MARK: tiny finite-field math dungeon
def _slow_gf_multiply(Left, Right):
    """Multiply two bytes in GF(2^8), using the same polynomial as AES."""
    Left = int(Left)
    Right = int(Right)
    if not 0 <= Left <= 255 or not 0 <= Right <= 255:
        raise ScatterError("GF(256) values must fit in one byte")
    Answer = 0
    for _Bit in range(8):
        if Right & 1:
            Answer ^= Left
        Carry = Left & 0x80
        Left = (Left << 1) & 0xff
        if Carry:
            Left ^= 0x1b
        Right >>= 1
    return Answer


def _gf_power(Value, Exponent):
    Answer = 1
    while Exponent:
        if Exponent & 1:
            Answer = _slow_gf_multiply(Answer, Value)
        Value = _slow_gf_multiply(Value, Value)
        Exponent >>= 1
    return Answer


def _gf_inverse(Value):
    Value = int(Value)
    if Value == 0:
        raise ScatterError("zero has no GF(256) inverse")
    return _gf_power(Value, 254)


_MULTIPLICATION_TABLES = {}


def MultiplicationTable(Factor):
    Factor = int(Factor)
    if not 0 <= Factor <= 255:
        raise ScatterError("GF(256) factor must fit in one byte")
    if Factor not in _MULTIPLICATION_TABLES:
        _MULTIPLICATION_TABLES[Factor] = bytes(
            _slow_gf_multiply(Value, Factor) for Value in range(256)
        )
    return _MULTIPLICATION_TABLES[Factor]


def _recovery_factor(LeftX, RightX):
    # y = secret + slope*x. rearrange two points to get the intercept at x=0.
    Denominator = LeftX ^ RightX
    return _slow_gf_multiply(LeftX, _gf_inverse(Denominator))


# warmed once so splitting/rebuilding does table lookups instead of millions of
# dramatic little polynomial divisions.
for _WarmFactor in (1, 2, 3):
    MultiplicationTable(_WarmFactor)


#MARK: strict fragment envelope
class Fragment:
    def __init__(self, Index, SetId, OriginalSize, OriginalDigest, Payload):
        self.Index = int(Index)
        self.SetId = bytes(SetId)
        self.OriginalSize = int(OriginalSize)
        self.OriginalDigest = bytes(OriginalDigest)
        self.Payload = bytes(Payload)

    @property
    def PayloadDigest(self):
        return Hashlib.sha256(self.Payload).digest()

    def Encode(self):
        ValidateFragment(self)
        Header = HEADER.pack(
            FRAGMENT_MAGIC,
            FRAGMENT_VERSION,
            self.Index,
            THRESHOLD,
            FRAGMENT_COUNT,
            self.SetId,
            self.OriginalSize,
            self.OriginalDigest,
            self.PayloadDigest,
        )
        return Header + self.Payload


def ValidateFragment(FragmentThing):
    if not isinstance(FragmentThing, Fragment):
        raise ScatterError("fragment must be a Fragment object")
    if FragmentThing.Index not in (1, 2, 3):
        raise ScatterError(f"fragment index must be 1, 2, or 3 (got {FragmentThing.Index})")
    if len(FragmentThing.SetId) != SET_ID_BYTES:
        raise ScatterError("fragment set id has the wrong size")
    if not 1 <= FragmentThing.OriginalSize <= MAX_FRAGMENT_PAYLOAD:
        raise ScatterError("fragment original size is outside the safe limit")
    if len(FragmentThing.OriginalDigest) != 32:
        raise ScatterError("fragment original SHA-256 has the wrong size")
    if len(FragmentThing.Payload) != FragmentThing.OriginalSize:
        raise ScatterError("fragment payload length does not match its header")
    return FragmentThing


def DecodeFragment(Blob):
    Blob = bytes(Blob)
    if len(Blob) > HEADER.size + MAX_FRAGMENT_PAYLOAD:
        raise ScatterError(f"fragment is too large ({len(Blob)} bytes)")
    if len(Blob) < HEADER.size:
        raise ScatterError("fragment is too short to have a header")
    try:
        (
            Magic,
            Version,
            Index,
            Needed,
            Count,
            SetId,
            OriginalSize,
            OriginalDigest,
            PayloadDigest,
        ) = HEADER.unpack(Blob[:HEADER.size])
    except Struct.error as Exc:
        raise ScatterError("fragment header could not be unpacked") from Exc
    if Magic != FRAGMENT_MAGIC:
        raise ScatterError("wrong fragment magic")
    if Version != FRAGMENT_VERSION:
        raise ScatterError(f"unsupported fragment version: {Version}")
    if Needed != THRESHOLD or Count != FRAGMENT_COUNT:
        raise ScatterError("fragment has an unsupported recovery scheme")
    Payload = Blob[HEADER.size:]
    FragmentThing = Fragment(Index, SetId, OriginalSize, OriginalDigest, Payload)
    ValidateFragment(FragmentThing)
    if not Secrets.compare_digest(FragmentThing.PayloadDigest, PayloadDigest):
        raise ScatterError(f"fragment {Index} payload SHA-256 does not match")
    return FragmentThing


def ReadFragment(FragmentPath):
    FragmentPath = Path(FragmentPath)
    if not FragmentPath.exists():
        raise ScatterError(f"fragment not found: {FragmentPath}")
    if not FragmentPath.is_file():
        raise ScatterError(f"fragment is not a regular file: {FragmentPath}")
    try:
        if FragmentPath.stat().st_size > HEADER.size + MAX_FRAGMENT_PAYLOAD:
            raise ScatterError(f"fragment is suspiciously huge: {FragmentPath}")
        Blob = FragmentPath.read_bytes()
    except ScatterError:
        raise
    except OSError as Exc:
        raise ScatterError(f"could not read fragment {FragmentPath}: {Exc}") from Exc
    return DecodeFragment(Blob)


#MARK: bowl scattering and reassembly
def SplitBlob(Blob, RandomBytes=Secrets.token_bytes, SetId=None):
    Blob = bytes(Blob)
    if not 1 <= len(Blob) <= MAX_FRAGMENT_PAYLOAD:
        raise ScatterError("bowl bytes are outside the fragment size limit")
    SetId = RandomBytes(SET_ID_BYTES) if SetId is None else bytes(SetId)
    if len(SetId) != SET_ID_BYTES:
        raise ScatterError(f"set id must be exactly {SET_ID_BYTES} bytes")
    Slopes = bytes(RandomBytes(len(Blob)))
    if len(Slopes) != len(Blob):
        raise ScatterError("random source returned the wrong number of bytes")
    OriginalDigest = Hashlib.sha256(Blob).digest()
    Fragments = []
    for Index in (1, 2, 3):
        TimesX = MultiplicationTable(Index)
        Payload = bytes(
            SecretByte ^ TimesX[SlopeByte]
            for SecretByte, SlopeByte in zip(Blob, Slopes)
        )
        Fragments.append(Fragment(
            Index=Index,
            SetId=SetId,
            OriginalSize=len(Blob),
            OriginalDigest=OriginalDigest,
            Payload=Payload,
        ))
    return tuple(Fragments)


def _compatible_pair(Left, Right):
    ValidateFragment(Left)
    ValidateFragment(Right)
    if Left.Index == Right.Index:
        raise ScatterError(f"two copies of fragment {Left.Index} are still only one point")
    if Left.SetId != Right.SetId:
        raise ScatterError("fragments came from different scatter sets")
    if Left.OriginalSize != Right.OriginalSize:
        raise ScatterError("fragments disagree about the original bowl size")
    if not Secrets.compare_digest(Left.OriginalDigest, Right.OriginalDigest):
        raise ScatterError("fragments disagree about the original bowl SHA-256")
    return True


def RebuildBlob(Left, Right):
    _compatible_pair(Left, Right)
    Factor = _recovery_factor(Left.Index, Right.Index)
    TimesFactor = MultiplicationTable(Factor)
    Rebuilt = bytes(
        LeftByte ^ TimesFactor[LeftByte ^ RightByte]
        for LeftByte, RightByte in zip(Left.Payload, Right.Payload)
    )
    if len(Rebuilt) != Left.OriginalSize:
        raise ScatterError("rebuilt bowl has the wrong length")
    ActualDigest = Hashlib.sha256(Rebuilt).digest()
    if not Secrets.compare_digest(ActualDigest, Left.OriginalDigest):
        raise ScatterError("rebuilt bowl SHA-256 does not match the fragment promise")
    return Rebuilt

# RepairFragment receives two compatible Fragment objects and one missing integer index.
# It returns the exact absent Fragment or raises ScatterError before producing a duplicate.
# Probe is a temporary Fragment with requested index and matched metadata/length invariants.
# Pair-checking Probe against both inputs rejects present or out-of-range indices early.
# Factor is one GF(256) byte: (left index XOR missing) divided by (left XOR right).
# Prior compatibility/absence checks make its denominator nonzero and value byte-sized.
# TimesFactor is an immutable 256-byte lookup table for multiplication by Factor.
# It may be safely reused from the module cache because callers cannot mutate bytes.
# LeftByte and RightByte are aligned integers from the two validated byte payloads.
# Each stays in 0..255, and equal payload lengths keep zip from truncating either side.
# RepairedPayload is immutable bytes with exactly the shared original payload length.
# Each byte is LeftByte XOR TimesFactor[LeftByte XOR RightByte] in GF(256).
# Repaired is a validated Fragment at Probe.Index with matching set metadata and payload.
# RebuildBlob(Left, Repaired) must satisfy the original digest before it is returned.
def RepairFragment(Left, Right, MissingIndex): _compatible_pair(Left, Right); Probe = Fragment(MissingIndex, Left.SetId, Left.OriginalSize, Left.OriginalDigest, Left.Payload); _compatible_pair(Left, Probe); _compatible_pair(Right, Probe); Factor = _slow_gf_multiply(Left.Index ^ Probe.Index, _gf_inverse(Left.Index ^ Right.Index)); TimesFactor = MultiplicationTable(Factor); RepairedPayload = bytes(LeftByte ^ TimesFactor[LeftByte ^ RightByte] for LeftByte, RightByte in zip(Left.Payload, Right.Payload)); Repaired = Fragment(Probe.Index, Left.SetId, Left.OriginalSize, Left.OriginalDigest, RepairedPayload); RebuildBlob(Left, Repaired); return Repaired


def SuggestedFragmentPaths(VaultPath, Prefix=None):
    VaultPath = Path(VaultPath)
    if Prefix is None:
        Prefix = VaultPath.with_name(f"{VaultPath.name}.fragment")
    Prefix = Path(Prefix)
    return tuple(
        Path(f"{Prefix}.{Index}-of-{FRAGMENT_COUNT}.p00pshard")
        for Index in (1, 2, 3)
    )


#MARK: three-file transaction crate
def _paths_are_distinct(Paths):
    Seen = set()
    for Candidate in Paths:
        try:
            Key = str(Path(Candidate).resolve())
        except OSError:
            Key = str(Path(Candidate).absolute())
        if Key in Seen:
            return False
        Seen.add(Key)
    return True


def WriteFragmentSet(Paths, EncodedFragments):
    Paths = tuple(Path(PathThing) for PathThing in Paths)
    Blobs = tuple(bytes(Blob) for Blob in EncodedFragments)
    if len(Paths) != FRAGMENT_COUNT or len(Blobs) != FRAGMENT_COUNT:
        raise ScatterError("a scatter crate needs exactly three paths and three fragments")
    if not _paths_are_distinct(Paths):
        raise ScatterError("fragment output paths must be different")
    for Destination in Paths:
        if Destination.exists() or Destination.is_symlink():
            raise ScatterError(f"fragment already exists: {Destination}")

    Temporaries = []
    Installed = []
    try:
        # prepare all three before publishing any of them.
        for Destination, Blob in zip(Paths, Blobs):
            Destination.parent.mkdir(parents=True, exist_ok=True)
            Handle = Tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{Destination.name}.",
                suffix=".scattering",
                dir=Destination.parent,
                delete=False,
            )
            Temporary = Path(Handle.name)
            Temporaries.append(Temporary)
            try:
                Handle.write(Blob)
                Handle.flush()
                Os.fsync(Handle.fileno())
            finally:
                Handle.close()
            Os.chmod(Temporary, 0o600)

        # hard links give us create-if-absent. a race cannot silently overwrite a file.
        for Temporary, Destination in zip(Temporaries, Paths):
            try:
                Os.link(Temporary, Destination)
            except FileExistsError as Exc:
                raise ScatterError(f"fragment appeared while scattering: {Destination}") from Exc
            Installed.append(Destination)
            Os.chmod(Destination, 0o600)
    except (OSError, ScatterError) as Exc:
        for Destination in reversed(Installed):
            try:
                Destination.unlink(missing_ok=True)
            except OSError:
                pass
        if isinstance(Exc, ScatterError):
            raise
        raise ScatterError(f"could not publish fragment crate: {Exc}") from Exc
    finally:
        for Temporary in Temporaries:
            try:
                Temporary.unlink(missing_ok=True)
            except OSError:
                pass
    return Paths


class ScatterReceipt:
    def __init__(self, VaultPath, FragmentPaths, Fragments):
        self.VaultPath = Path(VaultPath)
        self.FragmentPaths = tuple(Path(Item) for Item in FragmentPaths)
        self.Fragments = tuple(Fragments)

    def AsDictionary(self):
        First = self.Fragments[0]
        return {
            "protocol": "p00p-scatter-receipt",
            "vault": str(self.VaultPath),
            "fragments": [str(PathThing) for PathThing in self.FragmentPaths],
            "needed": THRESHOLD,
            "created": FRAGMENT_COUNT,
            "vault_bytes": First.OriginalSize,
            "vault_sha256": First.OriginalDigest.hex(),
            "set_id": First.SetId.hex(),
            "security_notice": (
                "one fragment is incomplete; any two recover the bowl; this code is experimental"
            ),
        }

    def AsJson(self):
        return Json.dumps(self.AsDictionary(), indent=2, sort_keys=True)

    def AsText(self):
        Data = self.AsDictionary()
        Lines = [
            "P00P SCATTER CRATE",
            f"vault:       {self.VaultPath}",
            f"set id:      {Data['set_id']}",
            f"bowl bytes:  {Data['vault_bytes']}",
            f"bowl sha256: {Data['vault_sha256']}",
            "recovery:    ANY 2 OF 3 FRAGMENTS",
        ]
        Lines.extend(f"fragment:    {PathThing}" for PathThing in self.FragmentPaths)
        Lines.append("warning: experimental storage, not an audited password-manager backup")
        return "\n".join(Lines)


class GatherReceipt:
    def __init__(self, FragmentPaths, OutputPath, Blob, SetId):
        self.FragmentPaths = tuple(Path(Item) for Item in FragmentPaths)
        self.OutputPath = Path(OutputPath)
        self.Blob = bytes(Blob)
        self.SetId = bytes(SetId)

    def AsDictionary(self):
        return {
            "protocol": "p00p-gather-receipt",
            "fragments": [str(Item) for Item in self.FragmentPaths],
            "output": str(self.OutputPath),
            "bytes": len(self.Blob),
            "sha256": Hashlib.sha256(self.Blob).hexdigest(),
            "set_id": self.SetId.hex(),
            "security_notice": "the reconstructed output is the original reversible p00p bowl",
        }

    def AsJson(self):
        return Json.dumps(self.AsDictionary(), indent=2, sort_keys=True)

    def AsText(self):
        Data = self.AsDictionary()
        return "\n".join((
            "P00P FRAGMENTS GATHERED",
            f"left:    {self.FragmentPaths[0]}",
            f"right:   {self.FragmentPaths[1]}",
            f"output:  {self.OutputPath}",
            f"bytes:   {Data['bytes']}",
            f"sha256:  {Data['sha256']}",
            "warning: restored bowl is still camouflage, not encryption",
        ))


def ScatterToFiles(VaultPath, Blob, Prefix=None, RandomBytes=Secrets.token_bytes):
    Fragments = SplitBlob(Blob, RandomBytes=RandomBytes)
    Paths = SuggestedFragmentPaths(VaultPath, Prefix)
    WriteFragmentSet(Paths, (FragmentThing.Encode() for FragmentThing in Fragments))
    return ScatterReceipt(VaultPath, Paths, Fragments)


def GatherFromFiles(LeftPath, RightPath):
    LeftPath = Path(LeftPath)
    RightPath = Path(RightPath)
    Left = ReadFragment(LeftPath)
    Right = ReadFragment(RightPath)
    Blob = RebuildBlob(Left, Right)
    return Blob, Left.SetId
