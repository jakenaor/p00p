#------------------------------------------------------------------#
# p00p toilet-wax byte seal                                        #
# proves a bowl is byte-for-byte the same bowl, not that it is safe #
#------------------------------------------------------------------#

import hashlib as Hashlib
import json as Json
import re as Re
from pathlib import Path


SEAL_PROTOCOL = "p00p-bowl-seal"
SEAL_VERSION = 1
MAX_SEAL_BYTES = 64 * 1024
SHA256_PATTERN = Re.compile(r"^[0-9a-f]{64}$")


class SealError(Exception):
    pass


def SuggestedSealPath(VaultPath):
    VaultPath = Path(VaultPath)
    return VaultPath.with_name(f"{VaultPath.name}.seal.json")


def BowlHash(Blob):
    return Hashlib.sha256(bytes(Blob)).hexdigest()


def BuildSeal(VaultPath, Blob, EntryCount, SealedAt):
    Blob = bytes(Blob)
    EntryCount = int(EntryCount)
    if EntryCount < 0:
        raise SealError("entry count cannot be negative")
    if not isinstance(SealedAt, str) or not SealedAt.strip():
        raise SealError("seal timestamp is missing")
    return {
        "protocol": SEAL_PROTOCOL,
        "version": SEAL_VERSION,
        "vault_name": Path(VaultPath).name,
        "vault_bytes": len(Blob),
        "vault_sha256": BowlHash(Blob),
        "entry_count": EntryCount,
        "sealed_at": SealedAt,
        "security_notice": (
            "byte identity only; this seal is not encryption or authentication"
        ),
    }


def EncodeSeal(Seal):
    ValidateSeal(Seal)
    return (Json.dumps(Seal, indent=2, sort_keys=True) + "\n").encode("utf-8")


def DecodeSeal(Blob):
    Blob = bytes(Blob)
    if len(Blob) > MAX_SEAL_BYTES:
        raise SealError(f"seal is too large ({len(Blob)} bytes)")
    try:
        Seal = Json.loads(Blob.decode("utf-8"))
    except (UnicodeDecodeError, Json.JSONDecodeError) as Exc:
        raise SealError("seal is not valid UTF-8 JSON") from Exc
    ValidateSeal(Seal)
    return Seal


def ReadSeal(SealPath):
    SealPath = Path(SealPath)
    if not SealPath.exists():
        raise SealError(f"seal not found: {SealPath}")
    if not SealPath.is_file():
        raise SealError(f"seal is not a regular file: {SealPath}")
    try:
        if SealPath.stat().st_size > MAX_SEAL_BYTES:
            raise SealError(f"seal is suspiciously huge: {SealPath}")
        Blob = SealPath.read_bytes()
    except SealError:
        raise
    except OSError as Exc:
        raise SealError(f"could not read seal {SealPath}: {Exc}") from Exc
    return DecodeSeal(Blob)


def ValidateSeal(Seal):
    if not isinstance(Seal, dict):
        raise SealError("seal root must be a JSON object")
    if Seal.get("protocol") != SEAL_PROTOCOL:
        raise SealError("wrong seal protocol")
    if Seal.get("version") != SEAL_VERSION:
        raise SealError(f"unsupported seal version: {Seal.get('version')!r}")
    if not isinstance(Seal.get("vault_name"), str) or not Seal["vault_name"]:
        raise SealError("seal has no vault filename")
    if Path(Seal["vault_name"]).name != Seal["vault_name"]:
        raise SealError("seal filename must not contain a path")
    for Field in ("vault_bytes", "entry_count"):
        Value = Seal.get(Field)
        if isinstance(Value, bool) or not isinstance(Value, int) or Value < 0:
            raise SealError(f"seal field {Field!r} must be a non-negative integer")
    Digest = Seal.get("vault_sha256")
    if not isinstance(Digest, str) or SHA256_PATTERN.fullmatch(Digest) is None:
        raise SealError("seal SHA-256 is malformed")
    if not isinstance(Seal.get("sealed_at"), str) or not Seal["sealed_at"].strip():
        raise SealError("seal timestamp is missing")
    return Seal


class SealVerification:
    def __init__(self, SealPath, VaultPath, Checks):
        self.SealPath = Path(SealPath)
        self.VaultPath = Path(VaultPath)
        self.Checks = tuple(Checks)

    @property
    def Passed(self):
        return all(Check["passed"] for Check in self.Checks)

    def AsDictionary(self):
        return {
            "protocol": "p00p-seal-verification",
            "passed": self.Passed,
            "seal": str(self.SealPath),
            "vault": str(self.VaultPath),
            "checks": [dict(Check) for Check in self.Checks],
            "security_notice": (
                "a passing seal proves byte identity, not password security"
            ),
        }

    def AsJson(self):
        return Json.dumps(self.AsDictionary(), indent=2, sort_keys=True)

    def AsText(self):
        Lines = [
            "P00P TOILET-WAX SEAL VERIFICATION",
            f"vault: {self.VaultPath}",
            f"seal:  {self.SealPath}",
        ]
        for Check in self.Checks:
            Mark = "PASS" if Check["passed"] else "FAIL"
            Lines.append(f"[{Mark}] {Check['name']}: {Check['detail']}")
        Lines.extend((
            f"result: {'EXACT BOWL MATCH' if self.Passed else 'SEAL BROKEN'}",
            "notice: byte identity is not encryption or authentication",
        ))
        return "\n".join(Lines)


def VerifySeal(Seal, SealPath, VaultPath, Blob, EntryCount=None):
    ValidateSeal(Seal)
    VaultPath = Path(VaultPath)
    Blob = bytes(Blob)
    ActualHash = BowlHash(Blob)
    Checks = [
        {
            "name": "vault filename",
            "passed": Seal["vault_name"] == VaultPath.name,
            "detail": (
                "name matches"
                if Seal["vault_name"] == VaultPath.name
                else "name differs from sealed bowl"
            ),
        },
        {
            "name": "file size",
            "passed": Seal["vault_bytes"] == len(Blob),
            "detail": f"sealed {Seal['vault_bytes']} bytes; found {len(Blob)} bytes",
        },
        {
            "name": "SHA-256",
            "passed": Seal["vault_sha256"] == ActualHash,
            "detail": (
                f"sealed {Seal['vault_sha256'][:12]}...; found {ActualHash[:12]}..."
            ),
        },
    ]
    if EntryCount is not None:
        EntryCount = int(EntryCount)
        Checks.append({
            "name": "entry count",
            "passed": Seal["entry_count"] == EntryCount,
            "detail": f"sealed {Seal['entry_count']}; decoded {EntryCount}",
        })
    return SealVerification(SealPath, VaultPath, Checks)
