#------------------------------------------------------------------#
# p00p submission report machine                                  #
# turns all the safe aggregate paperwork into one shareable thing  #
#------------------------------------------------------------------#

import json as Json
import os as Os
import tempfile as Tempfile
from datetime import datetime as DateTime, timezone as Timezone
from pathlib import Path


REPORT_PROTOCOL = "p00p-submission-report"


class ReportError(Exception):
    pass


def MarkdownCell(Value):
    return str(Value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


class SubmissionReport:
    def __init__(
        self,
        FilePath,
        ProjectVersion,
        FormatVersion,
        Header,
        DoctorPayload,
        StatisticsPayload,
        TheaterPayload,
        LabPayload,
        PooplineSummary,
        GeneratedAt=None,
    ):
        self.FilePath = Path(FilePath)
        self.ProjectVersion = str(ProjectVersion)
        self.FormatVersion = int(FormatVersion)
        self.Header = dict(Header)
        self.DoctorPayload = dict(DoctorPayload)
        self.StatisticsPayload = dict(StatisticsPayload)
        self.TheaterPayload = dict(TheaterPayload)
        self.LabPayload = dict(LabPayload)
        self.PooplineSummary = str(PooplineSummary)
        self.GeneratedAt = GeneratedAt or DateTime.now(Timezone.utc).isoformat(
            timespec="seconds"
        )

    def AnatomyDictionary(self):
        return {
            "magic": str(self.Header.get("magic", "P00P\\0")),
            "format_version": self.FormatVersion,
            "header_bytes": int(self.Header.get("header_size", 0)),
            "payload_bytes": int(self.Header.get("payload_size", 0)),
            "file_bytes": int(self.Header.get("file_size", 0)),
            "salt": str(self.Header.get("salt", "")),
            "checksum": str(self.Header.get("digest", "")),
            "poopline": self.PooplineSummary,
        }

    def AsDictionary(self):
        return {
            "protocol": REPORT_PROTOCOL,
            "generated_at": self.GeneratedAt,
            "project_version": self.ProjectVersion,
            "file": str(self.FilePath),
            "anatomy": self.AnatomyDictionary(),
            "doctor": self.DoctorPayload,
            "statistics": self.StatisticsPayload,
            "security_theater": self.TheaterPayload,
            "storage_lab": self.LabPayload,
            "warnings": [
                "this report intentionally contains no credential values",
                "the .p00p format is camouflage, not encryption",
                "the security theater score is a joke, not a security measurement",
                "the storage lab measures behavior, not security",
            ],
        }

    def AsJson(self):
        return Json.dumps(self.AsDictionary(), indent=2, sort_keys=True)

    def AsText(self):
        DoctorSummary = self.DoctorPayload.get("summary", {})
        EntrySummary = self.StatisticsPayload.get("entries", {})
        Theater = self.TheaterPayload
        Lab = self.LabPayload
        Anatomy = self.AnatomyDictionary()
        return "\n".join((
            "P00P SUBMISSION REPORT",
            f"generated:       {self.GeneratedAt}",
            f"project:         v{self.ProjectVersion}",
            f"bowl:            {self.FilePath}",
            "",
            "FORMAT GUTS",
            f"format:          .p00p v{self.FormatVersion}",
            f"file bytes:      {Anatomy['file_bytes']}",
            f"payload bytes:   {Anatomy['payload_bytes']}",
            f"salt:            {Anatomy['salt']}",
            f"checksum:        {Anatomy['checksum']}",
            f"poopline:        {Anatomy['poopline']}",
            "",
            "BOWL NUMBERS",
            f"entries:         {EntrySummary.get('total', 0)}",
            f"basic-ok:        {EntrySummary.get('basic_ok', 0)}",
            f"need attention:  {EntrySummary.get('need_attention', 0)}",
            f"reuse groups:    {EntrySummary.get('reused_groups', 0)}",
            "",
            "DOCTOR",
            f"passes:          {DoctorSummary.get('ok', 0)}",
            f"notes:           {DoctorSummary.get('note', 0)}",
            f"warnings:        {DoctorSummary.get('warning', 0)}",
            f"failures:        {DoctorSummary.get('error', 0)}",
            "",
            "SECURITY THEATER",
            f"applause:        {Theater.get('score', 0)}/{Theater.get('possible', 0)}",
            f"rating:          {Theater.get('rating', 'unknown')}",
            "",
            "WEIRD STORAGE LAB",
            f"result:          {'PASS' if Lab.get('passed') else 'ATTENTION'}",
            f"rounds:          {Lab.get('rounds', 0)}",
            f"unique blobs:    {Lab.get('randomization', {}).get('unique_envelopes', 0)}",
            f"unique salts:    {Lab.get('randomization', {}).get('unique_salts', 0)}",
            f"plaintext hits:  {Lab.get('plaintext_scan', {}).get('envelopes_with_a_probe', 0)}",
            f"corruption stop: {'YES' if Lab.get('corruption_rejected') else 'NO'}",
            "",
            "IMPORTANT: this report contains no credential values.",
            "the .p00p format is camouflage, not encryption.",
            "the theater score is a joke, not a security measurement.",
            "the storage lab demonstrates behavior, not security.",
        ))

    def AsMarkdown(self):
        Anatomy = self.AnatomyDictionary()
        DoctorSummary = self.DoctorPayload.get("summary", {})
        EntrySummary = self.StatisticsPayload.get("entries", {})
        Storage = self.StatisticsPayload.get("storage", {})
        Lengths = self.StatisticsPayload.get("password_length_buckets", {})
        Findings = self.DoctorPayload.get("findings", ())
        TheaterCues = self.TheaterPayload.get("cues", ())
        Lab = self.LabPayload

        Lines = [
            "# P00P vault report",
            "",
            f"> generated `{MarkdownCell(self.GeneratedAt)}` by P00P v{MarkdownCell(self.ProjectVersion)}",
            "",
            "This report intentionally contains **no entry names, usernames, passwords, or notes**.",
            "",
            "## Bowl summary",
            "",
            "| thing | count |",
            "| --- | ---: |",
            f"| entries | {EntrySummary.get('total', 0)} |",
            f"| basic checks look okay | {EntrySummary.get('basic_ok', 0)} |",
            f"| need basic attention | {EntrySummary.get('need_attention', 0)} |",
            f"| have usernames | {EntrySummary.get('with_username', 0)} |",
            f"| have notes | {EntrySummary.get('with_notes', 0)} |",
            f"| reused-password groups | {EntrySummary.get('reused_groups', 0)} |",
            "",
            "## Binary anatomy",
            "",
            "| thing | value |",
            "| --- | --- |",
            f"| format | `.p00p` v{self.FormatVersion} |",
            f"| file bytes | {Anatomy['file_bytes']} |",
            f"| header bytes | {Anatomy['header_bytes']} |",
            f"| payload bytes | {Anatomy['payload_bytes']} |",
            f"| salt | `{MarkdownCell(Anatomy['salt'])}` |",
            f"| checksum | `{MarkdownCell(Anatomy['checksum'])}` |",
            f"| decoded JSON bytes | {Storage.get('decoded_json_bytes', 0)} |",
            f"| compression ratio | {Storage.get('compression_ratio', 0)}x |",
            "",
            f"Poopline receipt: `{MarkdownCell(Anatomy['poopline'])}`",
            "",
            "## Password-length buckets",
            "",
            "Exact lengths stay hidden; only broad buckets appear here.",
            "",
            "| length | entries |",
            "| --- | ---: |",
        ]
        for Label, Count in Lengths.items():
            Lines.append(f"| {MarkdownCell(Label)} | {int(Count)} |")

        Lines.extend((
            "",
            "## Vault doctor",
            "",
            f"**{DoctorSummary.get('ok', 0)} pass, {DoctorSummary.get('note', 0)} note, "
            f"{DoctorSummary.get('warning', 0)} warning, {DoctorSummary.get('error', 0)} failure.**",
            "",
            "| result | check | detail |",
            "| --- | --- | --- |",
        ))
        for Finding in Findings:
            Level = str(Finding.get("level", "unknown")).upper()
            Lines.append(
                f"| {MarkdownCell(Level)} | {MarkdownCell(Finding.get('title', 'unknown'))} | "
                f"{MarkdownCell(Finding.get('detail', ''))} |"
            )

        Lines.extend((
            "",
            "## Security theater",
            "",
            f"**{self.TheaterPayload.get('score', 0)}/{self.TheaterPayload.get('possible', 0)} "
            f"applause points — {MarkdownCell(self.TheaterPayload.get('rating', 'unknown'))}.**",
            "",
            "| cue | points | explanation |",
            "| --- | ---: | --- |",
        ))
        for Cue in TheaterCues:
            Points = f"{Cue.get('points', 0)}/{Cue.get('possible', 0)}"
            Lines.append(
                f"| {MarkdownCell(Cue.get('name', 'unknown'))} | {Points} | "
                f"{MarkdownCell(Cue.get('explanation', ''))} |"
            )

        LabRandom = Lab.get("randomization", {})
        LabScan = Lab.get("plaintext_scan", {})
        LabEncode = Lab.get("encode_timing", {})
        LabDecode = Lab.get("decode_timing", {})
        Lines.extend((
            "",
            "## Weird storage lab",
            "",
            f"**{'PASS' if Lab.get('passed') else 'ATTENTION'} after {Lab.get('rounds', 0)} round trips.**",
            "",
            "| experiment | result |",
            "| --- | ---: |",
            f"| unique envelopes | {LabRandom.get('unique_envelopes', 0)} |",
            f"| unique salts | {LabRandom.get('unique_salts', 0)} |",
            f"| envelopes with plaintext probe | {LabScan.get('envelopes_with_a_probe', 0)} |",
            f"| corruption rejected | {'yes' if Lab.get('corruption_rejected') else 'no'} |",
            f"| median encode ms | {LabEncode.get('median_ms', 0)} |",
            f"| median decode ms | {LabDecode.get('median_ms', 0)} |",
        ))

        Lines.extend((
            "",
            "## Reality check",
            "",
            "- The `.p00p` format is camouflage, **not encryption**.",
            "- The theater score is a joke, **not a security measurement**.",
            "- The storage lab demonstrates behavior, **not security**.",
            "- Only fake credentials belong in this project.",
            "",
        ))
        return "\n".join(Lines)


def WriteReport(FilePath, Text, Force=False):
    FilePath = Path(FilePath)
    try:
        FilePath.parent.mkdir(parents=True, exist_ok=True)
    except OSError as Exc:
        raise ReportError(f"could not prepare report folder: {Exc}") from Exc
    if FilePath.exists() and not Force:
        raise ReportError(
            f"report already exists: {FilePath} (use --force to replace it)"
        )
    if FilePath.exists() and not FilePath.is_file():
        raise ReportError(f"report destination is not a regular file: {FilePath}")

    TemporaryPath = None
    try:
        with Tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{FilePath.name}.",
            suffix=".writing",
            dir=FilePath.parent,
            delete=False,
        ) as Handle:
            TemporaryPath = Path(Handle.name)
            Handle.write(str(Text))
            if not str(Text).endswith("\n"):
                Handle.write("\n")
            Handle.flush()
            Os.fsync(Handle.fileno())
        Os.chmod(TemporaryPath, 0o600)
        if Force:
            Os.replace(TemporaryPath, FilePath)
            TemporaryPath = None
        else:
            try:
                Os.link(TemporaryPath, FilePath)
            except FileExistsError as Exc:
                raise ReportError(
                    f"report already exists: {FilePath} (use --force to replace it)"
                ) from Exc
            TemporaryPath.unlink()
            TemporaryPath = None
    except ReportError:
        raise
    except OSError as Exc:
        raise ReportError(f"could not write report: {Exc}") from Exc
    finally:
        if TemporaryPath is not None:
            try:
                TemporaryPath.unlink(missing_ok=True)
            except OSError:
                pass
    return FilePath
