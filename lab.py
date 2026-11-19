#------------------------------------------------------------------#
# p00p weird-storage laboratory                                    #
# repeatedly bowls the same data and writes down only safe numbers  #
#------------------------------------------------------------------#

import hashlib as Hashlib
import json as Json
import statistics as Statistics
import time as Time


DEFAULT_ROUNDS = 25
MIN_ROUNDS = 2
MAX_ROUNDS = 500


class LabError(Exception):
    pass


def _milliseconds(Seconds):
    return round(max(0.0, float(Seconds)) * 1000.0, 4)


def _timing_summary(Samples):
    return {
        "minimum_ms": _milliseconds(min(Samples)),
        "median_ms": _milliseconds(Statistics.median(Samples)),
        "mean_ms": _milliseconds(Statistics.fmean(Samples)),
        "maximum_ms": _milliseconds(max(Samples)),
    }


def _plaintext_probes(Vault):
    # tiny strings can occur in random soup by coincidence, which makes a pretty
    # useless test. four bytes is still strict while avoiding most fake alarms.
    Probes = set()
    for Name, Entry in Vault.get("entries", {}).items():
        for Value in (
            Name,
            Entry.get("username", ""),
            Entry.get("password", ""),
            Entry.get("notes", ""),
        ):
            Encoded = str(Value).encode("utf-8")
            if len(Encoded) >= 4:
                Probes.add(Encoded)
    return tuple(Probes)


class StorageLabReport:
    def __init__(
        self,
        Rounds,
        EntryCount,
        DecodedBytes,
        EnvelopeSizes,
        EncodeTimes,
        DecodeTimes,
        UniqueEnvelopes,
        UniqueSalts,
        PlaintextProbeCount,
        PlaintextEnvelopeHits,
        CorruptionRejected,
    ):
        self.Rounds = int(Rounds)
        self.EntryCount = int(EntryCount)
        self.DecodedBytes = int(DecodedBytes)
        self.EnvelopeSizes = tuple(int(Size) for Size in EnvelopeSizes)
        self.EncodeTimes = tuple(float(Value) for Value in EncodeTimes)
        self.DecodeTimes = tuple(float(Value) for Value in DecodeTimes)
        self.UniqueEnvelopes = int(UniqueEnvelopes)
        self.UniqueSalts = int(UniqueSalts)
        self.PlaintextProbeCount = int(PlaintextProbeCount)
        self.PlaintextEnvelopeHits = int(PlaintextEnvelopeHits)
        self.CorruptionRejected = bool(CorruptionRejected)

    @property
    def Passed(self):
        return (
            self.UniqueEnvelopes == self.Rounds
            and self.UniqueSalts == self.Rounds
            and self.PlaintextEnvelopeHits == 0
            and self.CorruptionRejected
        )

    def AsDictionary(self):
        MeanEnvelope = Statistics.fmean(self.EnvelopeSizes)
        Ratio = MeanEnvelope / max(1, self.DecodedBytes)
        return {
            "protocol": "p00p-storage-lab",
            "passed": self.Passed,
            "rounds": self.Rounds,
            "entries": self.EntryCount,
            "decoded_json_bytes": self.DecodedBytes,
            "envelope_bytes": {
                "minimum": min(self.EnvelopeSizes),
                "mean": round(MeanEnvelope, 2),
                "maximum": max(self.EnvelopeSizes),
                "mean_to_json_ratio": round(Ratio, 4),
            },
            "encode_timing": _timing_summary(self.EncodeTimes),
            "decode_timing": _timing_summary(self.DecodeTimes),
            "randomization": {
                "unique_envelopes": self.UniqueEnvelopes,
                "unique_salts": self.UniqueSalts,
            },
            "plaintext_scan": {
                "probe_count": self.PlaintextProbeCount,
                "envelopes_with_a_probe": self.PlaintextEnvelopeHits,
            },
            "corruption_rejected": self.CorruptionRejected,
            "security_notice": (
                "this measures format behavior; it does not prove encryption or security"
            ),
        }

    def AsJson(self):
        return Json.dumps(self.AsDictionary(), indent=2, sort_keys=True)

    def AsText(self):
        Data = self.AsDictionary()
        Encode = Data["encode_timing"]
        Decode = Data["decode_timing"]
        Sizes = Data["envelope_bytes"]
        Result = "PASS" if self.Passed else "ATTENTION"
        return "\n".join((
            "P00P WEIRD STORAGE LAB",
            f"result:              {Result}",
            f"round trips:         {self.Rounds}",
            f"entries:             {self.EntryCount}",
            f"decoded JSON:        {self.DecodedBytes} bytes",
            f"envelope bytes:      {Sizes['minimum']} / {Sizes['mean']} / {Sizes['maximum']} min/mean/max",
            f"mean/json ratio:     {Sizes['mean_to_json_ratio']}",
            f"encode milliseconds: {Encode['minimum_ms']} / {Encode['median_ms']} / {Encode['maximum_ms']} min/median/max",
            f"decode milliseconds: {Decode['minimum_ms']} / {Decode['median_ms']} / {Decode['maximum_ms']} min/median/max",
            f"unique envelopes:    {self.UniqueEnvelopes}/{self.Rounds}",
            f"unique salts:        {self.UniqueSalts}/{self.Rounds}",
            f"plaintext probes:    {self.PlaintextProbeCount} across {self.PlaintextEnvelopeHits} matching envelope(s)",
            f"corruption rejected: {'YES' if self.CorruptionRejected else 'NO'}",
            "notice: format behavior is not proof of encryption or security",
        ))

    def Summary(self):
        Result = "PASS" if self.Passed else "ATTENTION"
        return (
            f"{Result} // {self.Rounds} ROUNDS // "
            f"{self.UniqueEnvelopes} UNIQUE // "
            f"{self.PlaintextEnvelopeHits} PLAINTEXT HITS"
        )


def RunStorageLab(
    Vault,
    Rounds,
    EncodeFunction,
    DecodeFunction,
    HeaderFunction,
    Clock=Time.perf_counter,
):
    try:
        Rounds = int(Rounds)
    except (TypeError, ValueError) as Exc:
        raise LabError("lab rounds must be an integer") from Exc
    if not MIN_ROUNDS <= Rounds <= MAX_ROUNDS:
        raise LabError(f"lab rounds must be between {MIN_ROUNDS} and {MAX_ROUNDS}")
    if not isinstance(Vault, dict) or not isinstance(Vault.get("entries"), dict):
        raise LabError("lab received a malformed bowl")

    DecodedBytes = len(
        Json.dumps(Vault, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    Probes = _plaintext_probes(Vault)
    EnvelopeSizes = []
    EncodeTimes = []
    DecodeTimes = []
    EnvelopeHashes = set()
    Salts = set()
    PlaintextEnvelopeHits = 0
    FirstBlob = None
    FirstHeader = None

    for _Round in range(Rounds):
        Started = Clock()
        Blob = bytes(EncodeFunction(Vault))
        EncodeTimes.append(Clock() - Started)

        Started = Clock()
        Decoded = DecodeFunction(Blob)
        DecodeTimes.append(Clock() - Started)
        if Decoded != Vault:
            raise LabError("an encode/decode lab round changed the decoded bowl")

        Header = HeaderFunction(Blob)
        Salt = bytes(Header.get("salt", b""))
        if not Salt:
            raise LabError("a lab envelope came back without salt")
        EnvelopeSizes.append(len(Blob))
        EnvelopeHashes.add(Hashlib.sha256(Blob).digest())
        Salts.add(Salt)
        if any(Probe in Blob for Probe in Probes):
            PlaintextEnvelopeHits += 1
        if FirstBlob is None:
            FirstBlob = Blob
            FirstHeader = Header

    Mutation = bytearray(FirstBlob)
    PayloadStart = int(FirstHeader.get("header_size", 0))
    PayloadSize = int(FirstHeader.get("payload_size", 0))
    if PayloadSize <= 0 or not 0 <= PayloadStart < len(Mutation):
        raise LabError("lab could not locate a payload byte to corrupt")
    Mutation[PayloadStart + PayloadSize // 2] ^= 0x01
    try:
        DecodeFunction(bytes(Mutation))
    except Exception:  # decoder type is injected; any clean rejection counts here.
        CorruptionRejected = True
    else:
        CorruptionRejected = False

    return StorageLabReport(
        Rounds=Rounds,
        EntryCount=len(Vault["entries"]),
        DecodedBytes=DecodedBytes,
        EnvelopeSizes=EnvelopeSizes,
        EncodeTimes=EncodeTimes,
        DecodeTimes=DecodeTimes,
        UniqueEnvelopes=len(EnvelopeHashes),
        UniqueSalts=len(Salts),
        PlaintextProbeCount=len(Probes),
        PlaintextEnvelopeHits=PlaintextEnvelopeHits,
        CorruptionRejected=CorruptionRejected,
    )
