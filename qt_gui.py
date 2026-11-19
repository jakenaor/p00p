#------------------------------------------------------------------#
# qt quick shell for the p00p password thingy                      #
# the shader is real. the security claims are still extremely not #
#------------------------------------------------------------------#

import argparse as Argparse
import copy as Copy
import hashlib as Hashlib
import os as Os
import subprocess as Subprocess
import sys as Sys
from pathlib import Path

from PySide6.QtCore import (
    Property, QAbstractEventDispatcher, QEvent, QObject, QSettings, Qt, QTimer,
    QUrl, Signal, Slot,
)
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

import main as Main
import lifeboat as Lifeboat
import soundboard as Soundboard
import decoy as Decoy
import history as History
import merge as Merge
import reroll as Reroll
import report as Report
import seal as Seal
import lab as Lab
import ledger as Ledger


ROOT = Path(__file__).resolve().parent
QML_FILE = ROOT / "qml" / "Main.qml"
SHADER_SOURCE = ROOT / "qml" / "shaders" / "crt.frag"
SHADER_PACK = ROOT / "qml" / "shaders" / "crt.frag.qsb"
SOUND_CUES = Soundboard.CUE_NAMES
DEFAULT_VOLUME = 70
DEFAULT_SFX_ENABLED = True
DEFAULT_SHADER_ENABLED = True
DEFAULT_CLIPBOARD_SECONDS = 20
DEFAULT_REVEAL_SECONDS = 20
DEFAULT_IDLE_SECONDS = 300
MIN_TIMER_SECONDS = 5
MAX_TIMER_SECONDS = 120
MIN_IDLE_SECONDS = 30
MAX_IDLE_SECONDS = 3600
GUI_LAB_ROUNDS = 10


def HandleSoundCue(Cue, Volume):
    # the beep goblin makes a tiny wav on first use and QSoundEffect plays it async.
    # audio trouble is deliberately nonfatal; this function remains a signal sink.
    Soundboard.PlayCue(Cue, Volume)
    return None


def ClampVolume(Value):
    try:
        return max(0, min(100, int(Value)))
    except (TypeError, ValueError):
        return DEFAULT_VOLUME


def ClampTimer(Value, Default):
    try:
        return max(MIN_TIMER_SECONDS, min(MAX_TIMER_SECONDS, int(Value)))
    except (TypeError, ValueError):
        return Default


def ClampIdleTimer(Value):
    try:
        return max(MIN_IDLE_SECONDS, min(MAX_IDLE_SECONDS, int(Value)))
    except (TypeError, ValueError):
        return DEFAULT_IDLE_SECONDS


def SettingBool(Value, Default=True):
    if isinstance(Value, bool):
        return Value
    if Value is None:
        return bool(Default)
    return str(Value).strip().casefold() in {"1", "true", "yes", "on"}


def QtTimersAvailable():
    # unit tests often have no running event dispatcher. starting a real QTimer there
    # only prints spooky warnings and never creates a useful deadline anyway.
    return QAbstractEventDispatcher.instance() is not None


#MARK: shader stuffs
def CompileShaders():
    # frozen apps already brought their shader. compiling inside the bundle is silly.
    if getattr(Sys, "frozen", False):
        if not SHADER_PACK.is_file():
            raise RuntimeError("packaged app is missing the compiled CRT shader")
        return
    # only wake qsb when the readable shader is newer than its packed blob.
    if SHADER_PACK.is_file() and SHADER_PACK.stat().st_mtime >= SHADER_SOURCE.stat().st_mtime:
        return
    import PySide6
    Qsb = Path(PySide6.__file__).resolve().parent / "qsb"
    if not Qsb.is_file():
        raise RuntimeError("PySide6 installed without the qsb shader compiler")
    Result = Subprocess.run(
        (str(Qsb), "--qt6", "-o", str(SHADER_PACK), str(SHADER_SOURCE)),
        capture_output=True,
        text=True,
        check=False,
    )
    if Result.returncode != 0:
        raise RuntimeError(f"CRT shader compilation failed:\n{Result.stderr or Result.stdout}")


#MARK: password stuffs
def PasswordMask(Password):
    return "•" * 12 if Password else "—"


def PasswordHealth(Password):
    if not Password:
        return {"healthy": False, "issues": [], "text": "NO FAKE PASSWORD YET"}
    Issues = list(Main.PasswordIssues(Password))
    if Issues:
        Text = f"{len(Issues)} BASIC ISSUE(S): " + "; ".join(Issues)
    else:
        Text = "BASIC CHECKS: LOOKS SURPRISINGLY DECENT"
    return {"healthy": not Issues, "issues": Issues, "text": Text.upper()}


def EntryIssueCounts(Vault):
    Counts = {}
    Fingerprints = {}
    for Name, Entry in Vault.get("entries", {}).items():
        Password = Entry.get("password", "")
        Counts[Name] = len(Main.PasswordIssues(Password))
        if not Entry.get("username"):
            Counts[Name] += 1
        # fingerprints spot reuse without keeping another plaintext password list.
        Fingerprint = Hashlib.sha256(Password.encode("utf-8")).hexdigest()
        Fingerprints.setdefault(Fingerprint, []).append(Name)
    for Names in Fingerprints.values():
        if len(Names) > 1:
            for Name in Names:
                Counts[Name] += 1
    return Counts


#MARK: qml bridge thingy
class VaultBackend(QObject):
    vaultPathChanged = Signal()
    entriesChanged = Signal()
    selectionChanged = Signal()
    selectionMoved = Signal(int)
    statusChanged = Signal()
    settingsChanged = Signal()
    utilityChanged = Signal()
    historyChanged = Signal()
    privacyChanged = Signal()
    soundRequested = Signal(str, int)

    def __init__(self, StartPath=None, Settings=None):
        super().__init__()
        self.Settings = Settings or QSettings("Hack Club", "P00P")
        self.Vault = None
        self.FilePath = None
        self.SelectedName = ""
        self.Query = ""
        self.SortColumn = "name"
        self.SortDescending = False
        self.PasswordVisible = False
        self.PrivacyCurtain = False
        self.Status = "SYS // READY"
        self.DoctorSummary = "NO VAULT OPEN"
        self.StatsSummary = "NO VAULT OPEN"
        self.LastLifeboat = "NO LIFEBOAT LAUNCHED THIS SESSION"
        self.SealSummary = "NO SEAL CHECKED THIS SESSION"
        self.LabSummary = "NO STORAGE LAB RUN THIS SESSION"
        self.LedgerSummary = "NO BOWL LEDGER CHECKED THIS SESSION"
        self.History = History.HistoryBook()
        self.Volume = ClampVolume(self.Settings.value("audio/volume", DEFAULT_VOLUME))
        self.SfxEnabled = SettingBool(
            self.Settings.value("audio/enabled", DEFAULT_SFX_ENABLED),
            DEFAULT_SFX_ENABLED,
        )
        self.ShaderEnabled = SettingBool(
            self.Settings.value("display/shader", DEFAULT_SHADER_ENABLED),
            DEFAULT_SHADER_ENABLED,
        )
        self.ClipboardSeconds = ClampTimer(
            self.Settings.value("privacy/clipboard_seconds", DEFAULT_CLIPBOARD_SECONDS),
            DEFAULT_CLIPBOARD_SECONDS,
        )
        self.RevealSeconds = ClampTimer(
            self.Settings.value("privacy/reveal_seconds", DEFAULT_REVEAL_SECONDS),
            DEFAULT_REVEAL_SECONDS,
        )
        self.IdleSeconds = ClampIdleTimer(
            self.Settings.value("privacy/idle_seconds", DEFAULT_IDLE_SECONDS)
        )

        # owned timers can be restarted. random old callbacks should not win fights
        # against a newer copy or a newly revealed row.
        self.ClipboardText = ""
        self.ClipboardTimer = QTimer(self)
        self.ClipboardTimer.setSingleShot(True)
        self.ClipboardTimer.timeout.connect(self._clear_clipboard_if_unchanged)
        self.RevealTimer = QTimer(self)
        self.RevealTimer.setSingleShot(True)
        self.RevealTimer.timeout.connect(self._hide_password)
        self.IdleTimer = QTimer(self)
        self.IdleTimer.setSingleShot(True)
        self.IdleTimer.timeout.connect(self._idle_curtain_timeout)

        Candidate = Path(StartPath or Os.environ.get("P00P_FILE", Main.DEFAULT_VAULT))
        if Candidate.is_file():
            self._load(Candidate, Quiet=True)

    def _entry(self):
        if self.Vault is None or self.SelectedName not in self.Vault.get("entries", {}):
            return {}
        return self.Vault["entries"][self.SelectedName]

    def _issue_counts(self):
        return EntryIssueCounts(self.Vault or {"entries": {}})

    def _rows(self):
        if self.Vault is None:
            return []
        Query = self.Query.strip().casefold()
        Counts = self._issue_counts()
        Rows = []
        for Name, Entry in self.Vault.get("entries", {}).items():
            # same rule as the cli: search labels and notes, never the password itself.
            Searchable = (Name, Entry.get("username", ""), Entry.get("notes", ""))
            if Query and not any(Query in str(Value).casefold() for Value in Searchable):
                continue
            Rows.append({
                "name": Name,
                "username": Entry.get("username") or "—",
                "health": Counts.get(Name, 0),
                "healthText": "OK" if Counts.get(Name, 0) == 0 else f"{Counts[Name]} ISSUES",
                "updated": str(Entry.get("updated_at") or "UNKNOWN"),
            })

        Column = self.SortColumn if self.SortColumn in {"name", "username", "health", "updated"} else "name"
        def SortValue(Row):
            Value = Row[Column]
            # name is the tie breaker so rows do not teleport when values match.
            return (Value.casefold() if isinstance(Value, str) else Value, Row["name"].casefold())
        return sorted(Rows, key=SortValue, reverse=self.SortDescending)

    def _emit_everything(self):
        self.vaultPathChanged.emit()
        self.entriesChanged.emit()
        self.selectionChanged.emit()
        self.statusChanged.emit()
        self.utilityChanged.emit()
        self.historyChanged.emit()
        self.privacyChanged.emit()

    def _set_status(self, Text):
        self.Status = f"SYS // {Text.upper()}"
        self.statusChanged.emit()

    def _refresh_doctor_summary(self):
        if self.FilePath is None:
            self.DoctorSummary = "NO VAULT OPEN"
            self.utilityChanged.emit()
            return False
        try:
            Report = Main.VaultDoctorReport(self.FilePath)
        except (Main.P00PError, OSError) as Exc:
            self.DoctorSummary = f"DOCTOR FAILED // {type(Exc).__name__.upper()}"
            self.utilityChanged.emit()
            return False
        self.DoctorSummary = Report.Summary().upper()
        self.utilityChanged.emit()
        return True

    def _refresh_stats_summary(self):
        if self.FilePath is None:
            self.StatsSummary = "NO VAULT OPEN"
            self.utilityChanged.emit()
            return False
        try:
            Report = Main.BowlStatisticsReport(self.FilePath)
        except (Main.P00PError, OSError) as Exc:
            self.StatsSummary = f"STATS FAILED // {type(Exc).__name__.upper()}"
            self.utilityChanged.emit()
            return False
        self.StatsSummary = Report.Summary()
        self.utilityChanged.emit()
        return True

    @Slot(str)
    def requestSound(self, Cue):
        # unknown noises get ignored instead of turning one typo into a ghost sound.
        Cue = str(Cue).strip().lower()
        if Cue in SOUND_CUES and self.SfxEnabled and self.Volume > 0:
            self.soundRequested.emit(Cue, self.Volume)

    def _load(self, FilePath, Quiet=False, SoundCue="vault_open"):
        try:
            Vault = Main.LoadVault(FilePath)
        except (Main.P00PError, OSError) as Exc:
            if not Quiet:
                self.requestSound("error")
                QMessageBox.critical(None, "VAULT ERROR", str(Exc))
            return False
        # only replace the live ui state after the whole file survived decoding.
        self.Vault = Vault
        self.FilePath = Path(FilePath)
        self.PrivacyCurtain = False
        Names = sorted(Vault.get("entries", {}), key=str.casefold)
        self.SelectedName = Names[0] if Names else ""
        self._cover_password()
        self.History.Clear()
        self.SealSummary = "NOT CHECKED FOR THIS OPEN BOWL"
        self.LabSummary = "NOT RUN FOR THIS OPEN BOWL"
        self.LedgerSummary = "NOT CHECKED FOR THIS OPEN BOWL"
        self._refresh_doctor_summary()
        self._refresh_stats_summary()
        self.Status = f"SYS // OPENED {len(Names)} VAULT ENTR{'Y' if len(Names) == 1 else 'IES'}"
        self._emit_everything()
        self._restart_idle_timer()
        self.requestSound(SoundCue)
        return True

    def _save(self):
        if self.Vault is None or self.FilePath is None:
            return False
        try:
            Main.SaveVault(self.FilePath, self.Vault)
        except (Main.P00PError, OSError) as Exc:
            self.requestSound("error")
            QMessageBox.critical(None, "SAVE ERROR", str(Exc))
            return False
        self._refresh_doctor_summary()
        self._refresh_stats_summary()
        self.SealSummary = "VAULT CHANGED // EXISTING SEAL MAY BE STALE"
        self.LabSummary = "VAULT CHANGED // RUN LAB AGAIN"
        self.LedgerSummary = "VAULT CHANGED // LEDGER CHECKPOINT IS STALE"
        self.utilityChanged.emit()
        return True

    @Property(str, notify=vaultPathChanged)
    def vaultPath(self):
        return str(self.FilePath) if self.FilePath else "NO VAULT OPEN"

    @Property(list, notify=entriesChanged)
    def entries(self):
        return self._rows()

    @Property(str, notify=entriesChanged)
    def summaryText(self):
        if self.Vault is None:
            return "NO VAULT OPEN"
        Counts = self._issue_counts()
        return (
            f"{len(self._rows())} SHOWN  //  {len(Counts)} TOTAL  //  "
            f"{sum(Value > 0 for Value in Counts.values())} NEED ATTENTION"
        )

    @Property(str, notify=selectionChanged)
    def selectedName(self):
        return self.SelectedName or "—"

    @Property(str, notify=selectionChanged)
    def selectedUsername(self):
        return self._entry().get("username") or "—"

    @Property(str, notify=selectionChanged)
    def selectedPassword(self):
        Password = self._entry().get("password", "")
        return Password if self.PasswordVisible else PasswordMask(Password)

    @Property(str, notify=selectionChanged)
    def selectedUpdated(self):
        return str(self._entry().get("updated_at") or "—")

    @Property(str, notify=selectionChanged)
    def selectedNotes(self):
        return self._entry().get("notes") or "NO NOTES"

    @Property(str, notify=selectionChanged)
    def selectedHealth(self):
        if not self.SelectedName:
            return "—"
        Count = self._issue_counts().get(self.SelectedName, 0)
        return "OK" if Count == 0 else f"{Count} BASIC ISSUE(S)"

    @Property(bool, notify=selectionChanged)
    def passwordVisible(self):
        return self.PasswordVisible

    @Property(str, notify=statusChanged)
    def statusText(self):
        return self.Status

    @Property(str, notify=utilityChanged)
    def doctorSummary(self):
        return self.DoctorSummary

    @Property(str, notify=utilityChanged)
    def statsSummary(self):
        return self.StatsSummary

    @Property(str, notify=utilityChanged)
    def lastLifeboat(self):
        return self.LastLifeboat

    @Property(str, notify=utilityChanged)
    def sealSummary(self):
        return self.SealSummary

    @Property(str, notify=utilityChanged)
    def labSummary(self):
        return self.LabSummary

    @Property(str, notify=utilityChanged)
    def ledgerSummary(self):
        return self.LedgerSummary

    @Property(bool, notify=vaultPathChanged)
    def hasVault(self):
        return self.Vault is not None and self.FilePath is not None

    @Property(bool, notify=historyChanged)
    def canUndo(self):
        return self.History.CanUndo

    @Property(bool, notify=historyChanged)
    def canRedo(self):
        return self.History.CanRedo

    @Property(str, notify=historyChanged)
    def undoText(self):
        return self.History.UndoLabel

    @Property(str, notify=historyChanged)
    def redoText(self):
        return self.History.RedoLabel

    #MARK: settings stuffs
    @Property(int, notify=settingsChanged)
    def volume(self):
        return self.Volume

    @Property(bool, notify=settingsChanged)
    def sfxEnabled(self):
        return self.SfxEnabled

    @Property(bool, notify=settingsChanged)
    def shaderEnabled(self):
        return self.ShaderEnabled

    @Property(int, notify=settingsChanged)
    def clipboardSeconds(self):
        return self.ClipboardSeconds

    @Property(int, notify=settingsChanged)
    def revealSeconds(self):
        return self.RevealSeconds

    @Property(int, notify=settingsChanged)
    def idleSeconds(self):
        return self.IdleSeconds

    @Property(bool, notify=privacyChanged)
    def privacyCurtain(self):
        return self.PrivacyCurtain

    @Property(bool, notify=entriesChanged)
    def hasEntries(self):
        return bool(self.Vault and self.Vault.get("entries"))

    @Property(str, constant=True)
    def versionText(self):
        return Main.PROJECT_VERSION

    @Property(int, constant=True)
    def commonPasswordCount(self):
        return len(Main.COMMON_PASSWORDS)

    @Slot(int)
    def setVolume(self, Volume):
        Volume = ClampVolume(Volume)
        if Volume == self.Volume:
            return
        self.Volume = Volume
        self.Settings.setValue("audio/volume", Volume)
        self.Settings.sync()
        self.settingsChanged.emit()

    @Slot(bool)
    def setSfxEnabled(self, Enabled):
        Enabled = bool(Enabled)
        if Enabled == self.SfxEnabled:
            return
        self.SfxEnabled = Enabled
        self.Settings.setValue("audio/enabled", Enabled)
        self.Settings.sync()
        self.settingsChanged.emit()
        # turning it on gets one proof-of-life click. turning it off stays quiet.
        if Enabled:
            self.requestSound("ui_click")

    @Slot(bool)
    def setShaderEnabled(self, Enabled):
        Enabled = bool(Enabled)
        if Enabled == self.ShaderEnabled:
            return
        self.ShaderEnabled = Enabled
        self.Settings.setValue("display/shader", Enabled)
        self.Settings.sync()
        self.settingsChanged.emit()

    @Slot(int)
    def setClipboardSeconds(self, Seconds):
        Seconds = ClampTimer(Seconds, DEFAULT_CLIPBOARD_SECONDS)
        if Seconds == self.ClipboardSeconds:
            return
        self.ClipboardSeconds = Seconds
        self.Settings.setValue("privacy/clipboard_seconds", Seconds)
        self.Settings.sync()
        if self.ClipboardTimer.isActive():
            self.ClipboardTimer.start(Seconds * 1000)
        self.settingsChanged.emit()

    @Slot(int)
    def setRevealSeconds(self, Seconds):
        Seconds = ClampTimer(Seconds, DEFAULT_REVEAL_SECONDS)
        if Seconds == self.RevealSeconds:
            return
        self.RevealSeconds = Seconds
        self.Settings.setValue("privacy/reveal_seconds", Seconds)
        self.Settings.sync()
        if self.RevealTimer.isActive():
            self.RevealTimer.start(Seconds * 1000)
        self.settingsChanged.emit()

    @Slot(int)
    def setIdleSeconds(self, Seconds):
        Seconds = ClampIdleTimer(Seconds)
        if Seconds == self.IdleSeconds:
            return
        self.IdleSeconds = Seconds
        self.Settings.setValue("privacy/idle_seconds", Seconds)
        self.Settings.sync()
        self._restart_idle_timer()
        self.settingsChanged.emit()

    @Slot()
    def resetSettings(self):
        # reset app knobs, not the vault. password deletion lives behind its own giant button.
        self.Volume = DEFAULT_VOLUME
        self.SfxEnabled = DEFAULT_SFX_ENABLED
        self.ShaderEnabled = DEFAULT_SHADER_ENABLED
        self.ClipboardSeconds = DEFAULT_CLIPBOARD_SECONDS
        self.RevealSeconds = DEFAULT_REVEAL_SECONDS
        self.IdleSeconds = DEFAULT_IDLE_SECONDS
        self.Settings.setValue("audio/volume", self.Volume)
        self.Settings.setValue("audio/enabled", self.SfxEnabled)
        self.Settings.setValue("display/shader", self.ShaderEnabled)
        self.Settings.setValue("privacy/clipboard_seconds", self.ClipboardSeconds)
        self.Settings.setValue("privacy/reveal_seconds", self.RevealSeconds)
        self.Settings.setValue("privacy/idle_seconds", self.IdleSeconds)
        self.Settings.sync()
        self._restart_idle_timer()
        self.settingsChanged.emit()
        self.requestSound("ui_click")

    #MARK: diagnostic and lifeboat stuffs
    @Slot(result=bool)
    def runDoctor(self):
        if not self.hasVault:
            self._set_status("NO VAULT OPEN FOR DOCTOR")
            self.requestSound("error")
            return False
        Healthy = self._refresh_doctor_summary()
        if Healthy:
            self._set_status(f"DOCTOR // {self.DoctorSummary}")
            self.requestSound("doctor")
        else:
            self._set_status("VAULT DOCTOR COULD NOT FINISH")
            self.requestSound("error")
        return Healthy

    @Slot(result=bool)
    def runStorageLab(self):
        if not self.hasVault:
            self._set_status("NO VAULT OPEN FOR STORAGE LAB")
            self.requestSound("error")
            return False
        try:
            Result = Main.StorageLabForVault(self.FilePath, GUI_LAB_ROUNDS)
        except (Main.P00PError, Lab.LabError, OSError) as Exc:
            self.LabSummary = f"LAB FAILED // {type(Exc).__name__.upper()}"
            self.utilityChanged.emit()
            self.requestSound("error")
            QMessageBox.critical(None, "STORAGE LAB ERROR", str(Exc))
            return False
        self.LabSummary = Result.Summary()
        self.utilityChanged.emit()
        if Result.Passed:
            self._set_status("STORAGE LAB // ALL FORMAT BEHAVIOR CHECKS PASSED")
            self.requestSound("doctor")
        else:
            self._set_status("STORAGE LAB // SOMETHING NEEDS ATTENTION")
            self.requestSound("error")
        QMessageBox.information(None, "P00P WEIRD STORAGE LAB", Result.AsText())
        return Result.Passed

    @Slot(result=bool)
    def backupVault(self):
        if not self.hasVault:
            self._set_status("NO VAULT OPEN FOR LIFEBOAT")
            self.requestSound("error")
            return False
        try:
            Blob = Main.ReadVaultBlob(self.FilePath)
            Vault = Main.DecodeVault(Blob)
            Destination = Lifeboat.SuggestedSnapshotPath(self.FilePath)
            Receipt = Lifeboat.Launch(
                Source=self.FilePath,
                Destination=Destination,
                Blob=Blob,
                EntryCount=len(Vault["entries"]),
                Action="backup",
            )
        except (
            Main.P00PError,
            Lifeboat.LifeboatError,
            OSError,
        ) as Exc:
            self.requestSound("error")
            QMessageBox.critical(None, "LIFEBOAT ERROR", str(Exc))
            return False
        self.LastLifeboat = str(Receipt.Destination)
        self.utilityChanged.emit()
        self._set_status(f"LIFEBOAT LAUNCHED // {Receipt.Destination.name}")
        self.requestSound("backup")
        return True

    @Slot(result=bool)
    def newDecoyVault(self):
        Filename, _ = QFileDialog.getSaveFileName(
            None,
            "NEW FAKE DEMO BOWL",
            str(ROOT / ".p00p-demo.p00p"),
            "p00p vaults (*.p00p *.poop);;All files (*)",
        )
        if not Filename:
            return False
        FilePath = Path(Filename)
        if not FilePath.suffix:
            FilePath = FilePath.with_suffix(".p00p")
        if FilePath.exists():
            Answer = QMessageBox.warning(
                None,
                "REPLACE EXISTING BOWL?",
                f"{FilePath.name} already exists. replace it with 24 fake demo entries?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if Answer != QMessageBox.StandardButton.Yes:
                return False
        Vault = Main.NewVault()
        try:
            Decoy.PopulateVault(Vault, 24, Main.CurrentTime)
            Main.SaveVault(FilePath, Vault)
        except (Main.P00PError, Decoy.DecoyError, OSError) as Exc:
            self.requestSound("error")
            QMessageBox.critical(None, "DECOY FOUNDRY ERROR", str(Exc))
            return False
        Loaded = self._load(FilePath, SoundCue="vault_new")
        if Loaded:
            self._set_status("NEW 24-ENTRY DECOY BOWL READY")
        return Loaded

    @Slot(result=bool)
    def rerollCamouflage(self):
        if not self.hasVault:
            self._set_status("NO VAULT OPEN TO REROLL")
            self.requestSound("error")
            return False
        try:
            Receipt = Main.RerollVault(self.FilePath)
        except (
            Main.P00PError,
            Lifeboat.LifeboatError,
            Reroll.RerollError,
            OSError,
        ) as Exc:
            self.requestSound("error")
            QMessageBox.critical(None, "CAMOUFLAGE REROLL ERROR", str(Exc))
            return False
        self._refresh_doctor_summary()
        self._refresh_stats_summary()
        self.SealSummary = "CAMOUFLAGE REROLLED // EXISTING SEAL IS STALE"
        self.LabSummary = "CAMOUFLAGE CHANGED // RUN LAB AGAIN"
        self.LedgerSummary = "CAMOUFLAGE CHANGED // LEDGER CHECKPOINT IS STALE"
        self.utilityChanged.emit()
        self._set_status(f"CAMOUFLAGE REROLLED // {Receipt.AfterHash[:12]}")
        self.requestSound("generate")
        return True

    @Slot(result=bool)
    def stampLedgerCheckpoint(self):
        if not self.hasVault:
            self._set_status("NO VAULT OPEN FOR BOWL LEDGER")
            self.requestSound("error")
            return False
        try:
            Result = Main.RecordVaultLedger(self.FilePath, Action="checkpoint")
        except (
            Main.P00PError,
            Ledger.LedgerError,
            Lifeboat.LifeboatError,
            OSError,
        ) as Exc:
            self.LedgerSummary = f"LEDGER FAILED // {type(Exc).__name__.upper()}"
            self.utilityChanged.emit()
            self.requestSound("error")
            QMessageBox.critical(None, "BOWL LEDGER ERROR", str(Exc))
            return False
        self.LedgerSummary = Result.Summary()
        self.utilityChanged.emit()
        self._set_status(f"BOWL LEDGER CHECKPOINT #{len(Result.Records)} STAMPED")
        self.requestSound("backup")
        return True

    @Slot(result=bool)
    def verifyVaultLedger(self):
        if not self.hasVault:
            self._set_status("NO VAULT OPEN TO CHECK AGAINST LEDGER")
            self.requestSound("error")
            return False
        try:
            Result = Main.VerifyVaultLedger(self.FilePath)
        except (Main.P00PError, Ledger.LedgerError, OSError) as Exc:
            self.LedgerSummary = "LEDGER CHECK COULD NOT RUN"
            self.utilityChanged.emit()
            self.requestSound("error")
            QMessageBox.critical(None, "BOWL LEDGER VERIFY ERROR", str(Exc))
            return False
        self.LedgerSummary = Result.Summary()
        self.utilityChanged.emit()
        if Result.Passed:
            self._set_status("BOWL LEDGER // CURRENT BYTES MATCH LAST CHECKPOINT")
            self.requestSound("doctor")
        else:
            self._set_status("BOWL LEDGER // VAULT CHANGED SINCE LAST CHECKPOINT")
            self.requestSound("error")
            QMessageBox.warning(
                None,
                "BOWL LEDGER IS STALE",
                Result.AsText(),
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
            )
        return Result.Passed

    @Slot(result=bool)
    def exportSafeReport(self):
        if not self.hasVault:
            self._set_status("NO VAULT OPEN TO REPORT ON")
            self.requestSound("error")
            return False
        DefaultName = self.FilePath.with_name(f"{self.FilePath.stem}-report.md")
        Filename, _ = QFileDialog.getSaveFileName(
            None,
            "EXPORT SECRET-SAFE REPORT",
            str(DefaultName),
            "Markdown (*.md);;JSON (*.json);;Plain text (*.txt)",
        )
        if not Filename:
            return False
        FilePath = Path(Filename)
        Suffix = FilePath.suffix.casefold()
        Format = "json" if Suffix == ".json" else "text" if Suffix == ".txt" else "markdown"
        if not Suffix:
            FilePath = FilePath.with_suffix(".md")
        Force = False
        if FilePath.exists():
            Answer = QMessageBox.warning(
                None,
                "REPLACE EXISTING REPORT?",
                f"{FilePath.name} already exists. replace it with a fresh safe report?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if Answer != QMessageBox.StandardButton.Yes:
                return False
            Force = True
        try:
            Submission = Main.SubmissionReportForVault(self.FilePath)
            Text = Main.RenderSubmissionReport(Submission, Format)
            Report.WriteReport(FilePath, Text, Force=Force)
        except (Main.P00PError, Report.ReportError, OSError) as Exc:
            self.requestSound("error")
            QMessageBox.critical(None, "REPORT ERROR", str(Exc))
            return False
        self._set_status(f"SAFE REPORT EXPORTED // {FilePath.name}")
        self.requestSound("backup")
        return True

    @Slot(result=bool)
    def mergeAnotherVault(self):
        if not self.hasVault:
            self._set_status("NO VAULT OPEN ON THE LEFT SIDE TO MERGE")
            self.requestSound("error")
            return False
        RightFilename, _ = QFileDialog.getOpenFileName(
            None,
            "CHOOSE THE RIGHT-SIDE BOWL",
            str(self.FilePath.parent),
            "p00p vaults (*.p00p *.poop);;All files (*)",
        )
        if not RightFilename:
            return False
        Policy, Accepted = QInputDialog.getItem(
            None,
            "WHAT IF NAMES COLLIDE?",
            "CONFLICT POLICY",
            Merge.POLICIES,
            0,
            False,
        )
        if not Accepted:
            return False
        Suggested = self.FilePath.with_name(f"{self.FilePath.stem}-merged.p00p")
        OutputFilename, _ = QFileDialog.getSaveFileName(
            None,
            "SAVE THE THIRD BOWL",
            str(Suggested),
            "p00p vaults (*.p00p *.poop);;All files (*)",
        )
        if not OutputFilename:
            return False
        OutputPath = Path(OutputFilename)
        if not OutputPath.suffix:
            OutputPath = OutputPath.with_suffix(".p00p")
        Force = False
        if OutputPath.exists():
            Answer = QMessageBox.warning(
                None,
                "REPLACE EXISTING THIRD BOWL?",
                f"{OutputPath.name} already exists. replace it with the merged bowl?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if Answer != QMessageBox.StandardButton.Yes:
                return False
            Force = True
        try:
            Receipt = Main.MergeVaultFiles(
                LeftPath=self.FilePath,
                RightPath=Path(RightFilename),
                OutputPath=OutputPath,
                Policy=str(Policy),
                Force=Force,
            )
        except (
            Main.P00PError,
            Merge.MergeError,
            Lifeboat.LifeboatError,
            OSError,
        ) as Exc:
            self.requestSound("error")
            QMessageBox.critical(None, "BOWL MERGE ERROR", str(Exc))
            return False
        self._set_status(
            f"MERGED THIRD BOWL // {Receipt.FinalEntries} ENTRIES // {OutputPath.name}"
        )
        self.requestSound("backup")
        return True

    @Slot(result=bool)
    def stampVaultSeal(self):
        if not self.hasVault:
            self._set_status("NO VAULT OPEN TO STAMP")
            self.requestSound("error")
            return False
        SealPath = Seal.SuggestedSealPath(self.FilePath)
        Force = False
        if SealPath.exists():
            Answer = QMessageBox.warning(
                None,
                "RESTAMP THIS BOWL?",
                f"{SealPath.name} already exists. replace it with the current byte identity?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if Answer != QMessageBox.StandardButton.Yes:
                return False
            Force = True
        try:
            _Destination, Document = Main.CreateVaultSeal(
                self.FilePath,
                SealPath=SealPath,
                Force=Force,
            )
        except (
            Main.P00PError,
            Seal.SealError,
            Lifeboat.LifeboatError,
            OSError,
        ) as Exc:
            self.requestSound("error")
            QMessageBox.critical(None, "SEAL STAMP ERROR", str(Exc))
            return False
        self.SealSummary = (
            f"STAMPED // {Document['vault_sha256'][:12]}... // {SealPath.name}"
        )
        self.utilityChanged.emit()
        self._set_status("TOILET-WAX BYTE SEAL STAMPED")
        self.requestSound("backup")
        return True

    @Slot(result=bool)
    def verifyVaultSeal(self):
        if not self.hasVault:
            self._set_status("NO VAULT OPEN TO VERIFY")
            self.requestSound("error")
            return False
        SealPath = Seal.SuggestedSealPath(self.FilePath)
        try:
            Result = Main.VerifyVaultSeal(self.FilePath, SealPath)
        except (Main.P00PError, Seal.SealError, OSError) as Exc:
            self.SealSummary = "SEAL CHECK COULD NOT RUN"
            self.utilityChanged.emit()
            self.requestSound("error")
            QMessageBox.critical(None, "SEAL VERIFY ERROR", str(Exc))
            return False
        Failed = sum(not Check["passed"] for Check in Result.Checks)
        if Result.Passed:
            self.SealSummary = f"PASS // EXACT BYTE MATCH // {SealPath.name}"
            self._set_status("SEAL VERIFIED // EXACT BOWL MATCH")
            self.requestSound("doctor")
        else:
            self.SealSummary = f"FAIL // {Failed} SEAL CHECK(S) FAILED"
            self._set_status("SEAL BROKEN // CURRENT BOWL DOES NOT MATCH")
            self.requestSound("error")
            QMessageBox.warning(
                None,
                "SEAL BROKEN",
                Result.AsText(),
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
            )
        self.utilityChanged.emit()
        return Result.Passed

    #MARK: vault picker stuffs
    @Slot()
    def newVault(self):
        Filename, _ = QFileDialog.getSaveFileName(
            None, "NEW P00P VAULT", str(ROOT / Main.DEFAULT_VAULT),
            "p00p vaults (*.p00p *.poop);;All files (*)",
        )
        if not Filename:
            return
        FilePath = Path(Filename)
        # the save dialog can return a naked name, so give it the stupid extension.
        if not FilePath.suffix:
            FilePath = FilePath.with_suffix(".p00p")
        Vault = Main.NewVault()
        try:
            Main.SaveVault(FilePath, Vault)
        except (Main.P00PError, OSError) as Exc:
            self.requestSound("error")
            QMessageBox.critical(None, "NEW VAULT ERROR", str(Exc))
            return
        self._load(FilePath, SoundCue="vault_new")

    @Slot()
    def openVault(self):
        Filename, _ = QFileDialog.getOpenFileName(
            None, "OPEN P00P VAULT", str(ROOT),
            "p00p vaults (*.p00p *.poop);;All files (*)",
        )
        if Filename:
            self._load(Path(Filename))

    @Slot(str)
    def setQuery(self, Query):
        self.Query = Query
        self.entriesChanged.emit()

    @Slot(str)
    def setSort(self, Column):
        self.SortColumn = str(Column).lower()
        self.entriesChanged.emit()

    @Slot()
    def toggleSort(self):
        self.SortDescending = not self.SortDescending
        self.entriesChanged.emit()

    @Slot(str)
    def selectEntry(self, Name):
        if self.Vault is None or Name not in self.Vault.get("entries", {}):
            return
        self.SelectedName = Name
        # changing rows should immediately cover whatever password was revealed before.
        self._cover_password()
        self.selectionChanged.emit()

    @Slot(int)
    def selectRow(self, Index):
        Rows = self._rows()
        if not Rows:
            return
        Index = max(0, min(int(Index), len(Rows) - 1))
        self.SelectedName = Rows[Index]["name"]
        self._cover_password()
        self.selectionChanged.emit()
        self.selectionMoved.emit(Index)

    @Slot(int)
    def selectRelative(self, Offset):
        Rows = self._rows()
        if not Rows:
            return
        Names = [Row["name"] for Row in Rows]
        try:
            CurrentIndex = Names.index(self.SelectedName)
        except ValueError:
            CurrentIndex = -1 if int(Offset) >= 0 else 0
        # wrapping makes a long keyboard trip predictable instead of getting stuck.
        self.selectRow((CurrentIndex + int(Offset)) % len(Rows))

    @Slot(result="QVariantMap")
    def selectedEntry(self):
        Entry = self._entry()
        return {
            "name": self.SelectedName,
            "username": Entry.get("username", ""),
            "password": Entry.get("password", ""),
            "notes": Entry.get("notes", ""),
        }

    @Slot(str, result="QVariantMap")
    def passwordHealth(self, Password):
        return PasswordHealth(Password)

    @Slot(int, bool, result=str)
    def generatePassword(self, Length, Symbols):
        try:
            Password = Main.GeneratePassword(int(Length), Symbols=bool(Symbols))
            self.requestSound("generate")
            return Password
        except Main.P00PError as Exc:
            self.requestSound("error")
            QMessageBox.warning(None, "GENERATOR ERROR", str(Exc))
            return ""

    #MARK: undo timeline stuffs
    def _remember_change(self, Label, OldVault, OldSelection):
        self.History.Remember(Label, OldVault, OldSelection)
        self.historyChanged.emit()

    def _apply_history_move(self, Direction):
        if self.Vault is None:
            return False
        if Direction == "undo":
            Move = self.History.PlanUndo(self.Vault, self.SelectedName)
        else:
            Move = self.History.PlanRedo(self.Vault, self.SelectedName)
        if Move is None:
            self._set_status(f"NOTHING TO {Direction.upper()}")
            return False

        LiveVault = self.Vault
        LiveSelection = self.SelectedName
        self.Vault = Copy.deepcopy(Move.Target.Vault)
        CandidateSelection = Move.Target.SelectedName
        Names = sorted(self.Vault.get("entries", {}), key=str.casefold)
        self.SelectedName = (
            CandidateSelection
            if CandidateSelection in self.Vault.get("entries", {})
            else (Names[0] if Names else "")
        )
        if not self._save():
            # the history stacks do not move until the old/new bowl really reaches disk.
            self.Vault = LiveVault
            self.SelectedName = LiveSelection
            return False

        self.History.Commit(Move)
        self._cover_password()
        self._set_status(f"{Direction.upper()} // {Move.Target.Label}")
        self.requestSound("entry_save")
        self.entriesChanged.emit()
        self.selectionChanged.emit()
        self.historyChanged.emit()
        return True

    @Slot(result=bool)
    def undo(self):
        return self._apply_history_move("undo")

    @Slot(result=bool)
    def redo(self):
        return self._apply_history_move("redo")

    #MARK: entry stuffs
    @Slot(str, str, str, str, result=bool)
    def addEntry(self, Name, Username, Password, Notes):
        if self.Vault is None:
            QMessageBox.information(None, "NO VAULT", "OPEN OR CREATE A VAULT FIRST")
            return False
        try:
            CleanName = Main.NormalizeName(Name)
        except Main.P00PError as Exc:
            QMessageBox.warning(None, "ENTRY ERROR", str(Exc))
            return False
        if not Password:
            QMessageBox.warning(None, "ENTRY ERROR", "THE PASSWORD CANNOT BE EMPTY")
            return False
        if any(Existing.casefold() == CleanName.casefold() for Existing in self.Vault["entries"]):
            QMessageBox.warning(None, "ENTRY ERROR", "AN ENTRY WITH THAT NAME ALREADY EXISTS")
            return False
        # edit a copy first. a failed disk save should not mutate the visible vault.
        Working = Copy.deepcopy(self.Vault)
        Working["entries"][CleanName] = {
            "username": Username.strip(),
            "password": Password,
            "notes": Notes.strip(),
            "updated_at": Main.CurrentTime(),
        }
        Original = self.Vault
        OriginalSelection = self.SelectedName
        self.Vault = Working
        if not self._save():
            # put the old bowl back if the new one never reached disk.
            self.Vault = Original
            return False
        self._remember_change(f"ADD {CleanName}", Original, OriginalSelection)
        self.SelectedName = CleanName
        self._cover_password()
        self._set_status(f"ADDED {CleanName}")
        self.requestSound("entry_save")
        self.entriesChanged.emit()
        self.selectionChanged.emit()
        return True

    @Slot(str, str, str, str, str, result=bool)
    def editEntry(self, OriginalName, Name, Username, Password, Notes):
        if self.Vault is None or OriginalName not in self.Vault.get("entries", {}):
            return False
        try:
            CleanName = Main.NormalizeName(Name)
        except Main.P00PError as Exc:
            QMessageBox.warning(None, "ENTRY ERROR", str(Exc))
            return False
        if not Password:
            QMessageBox.warning(None, "ENTRY ERROR", "THE PASSWORD CANNOT BE EMPTY")
            return False
        Collision = any(
            Existing != OriginalName and Existing.casefold() == CleanName.casefold()
            for Existing in self.Vault["entries"]
        )
        if Collision:
            QMessageBox.warning(None, "ENTRY ERROR", "AN ENTRY WITH THAT NAME ALREADY EXISTS")
            return False
        # pop then insert also handles a real rename instead of cloning the entry.
        Working = Copy.deepcopy(self.Vault)
        Working["entries"].pop(OriginalName)
        Working["entries"][CleanName] = {
            "username": Username.strip(),
            "password": Password,
            "notes": Notes.strip(),
            "updated_at": Main.CurrentTime(),
        }
        Original = self.Vault
        OriginalSelection = self.SelectedName
        self.Vault = Working
        if not self._save():
            self.Vault = Original
            return False
        self._remember_change(f"EDIT {OriginalName}", Original, OriginalSelection)
        self.SelectedName = CleanName
        self._cover_password()
        self._set_status(f"UPDATED {CleanName}")
        self.requestSound("entry_save")
        self.entriesChanged.emit()
        self.selectionChanged.emit()
        return True

    @Slot()
    def removeEntry(self):
        if self.Vault is None or not self.SelectedName:
            return
        Answer = QMessageBox.question(
            None, "REMOVE ENTRY", f"REMOVE {self.SelectedName}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if Answer != QMessageBox.StandardButton.Yes:
            return
        RemovedName = self.SelectedName
        Working = Copy.deepcopy(self.Vault)
        Working["entries"].pop(RemovedName)
        Original = self.Vault
        OriginalSelection = self.SelectedName
        self.Vault = Working
        if not self._save():
            self.Vault = Original
            return
        self._remember_change(f"REMOVE {RemovedName}", Original, OriginalSelection)
        Names = sorted(self.Vault["entries"], key=str.casefold)
        # land on the first remaining row so the details panel never points at a ghost.
        self.SelectedName = Names[0] if Names else ""
        self._cover_password()
        self._set_status(f"REMOVED {RemovedName}")
        self.requestSound("entry_remove")
        self.entriesChanged.emit()
        self.selectionChanged.emit()

    @Slot(result=bool)
    def deleteAllEntries(self):
        if not self.Vault or not self.Vault.get("entries"):
            return False
        Count = len(self.Vault["entries"])
        Answer = QMessageBox.warning(
            None,
            "DELETE EVERY ENTRY",
            f"DELETE ALL {Count} ENTRIES FROM THIS VAULT?\n\n"
            "U CAN UNDO IT UNTIL THE APP CLOSES OR ANOTHER VAULT OPENS.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if Answer != QMessageBox.StandardButton.Yes:
            return False
        Working = Copy.deepcopy(self.Vault)
        Working["entries"].clear()
        Original = self.Vault
        OriginalSelection = self.SelectedName
        self.Vault = Working
        if not self._save():
            self.Vault = Original
            return False
        self._remember_change(
            f"DELETE ALL {Count} ENTRIES", Original, OriginalSelection
        )
        self.SelectedName = ""
        self._cover_password()
        self._set_status(f"DELETED ALL {Count} ENTRIES")
        self.requestSound("delete_all")
        self.entriesChanged.emit()
        self.selectionChanged.emit()
        return True

    #MARK: clipboard stuffs
    def _clear_clipboard_later(self, Text):
        self.ClipboardText = Text
        # start() resets this exact timer, including when the copied text is identical.
        self.ClipboardTimer.start(self.ClipboardSeconds * 1000)

    def _clear_clipboard_if_unchanged(self):
        Clipboard = QGuiApplication.clipboard()
        # do not erase something the user copied after p00p put its thingy in there.
        if self.ClipboardText and Clipboard.text() == self.ClipboardText:
            Clipboard.clear()
            self._set_status("CLIPBOARD CLEARED")
        self.ClipboardText = ""

    @Slot()
    def clearOwnedClipboard(self):
        # quitting should not strand a copied password forever, but never eat a newer copy.
        self.ClipboardTimer.stop()
        self._clear_clipboard_if_unchanged()

    @Slot()
    def copyUsername(self):
        Text = self._entry().get("username", "")
        if not Text:
            return
        QGuiApplication.clipboard().setText(Text)
        self._clear_clipboard_later(Text)
        self._set_status(f"USERNAME COPIED FOR {self.ClipboardSeconds} SECONDS")
        self.requestSound("copy")

    @Slot()
    def copyPassword(self):
        Text = self._entry().get("password", "")
        if not Text:
            return
        QGuiApplication.clipboard().setText(Text)
        self._clear_clipboard_later(Text)
        self._set_status(f"PASSWORD COPIED FOR {self.ClipboardSeconds} SECONDS")
        self.requestSound("copy")

    @Slot()
    def clearClipboard(self):
        self.ClipboardTimer.stop()
        self.ClipboardText = ""
        QGuiApplication.clipboard().clear()
        self._set_status("CLIPBOARD CLEARED")
        self.requestSound("hide")

    @Slot()
    def togglePassword(self):
        if not self._entry():
            return
        if self.PasswordVisible:
            self._cover_password(Emit=True)
            self._set_status("PASSWORD HIDDEN")
            self.requestSound("hide")
            return
        self.PasswordVisible = True
        self.selectionChanged.emit()
        self._set_status(f"PASSWORD REVEALED FOR {self.RevealSeconds} SECONDS")
        self.requestSound("reveal")
        # revealed means revealed briefly, not until the app gets forgotten.
        self.RevealTimer.start(self.RevealSeconds * 1000)

    def _cover_password(self, Emit=False):
        self.RevealTimer.stop()
        WasVisible = self.PasswordVisible
        self.PasswordVisible = False
        if Emit and WasVisible:
            self.selectionChanged.emit()
        return WasVisible

    def _hide_password(self):
        self._cover_password(Emit=True)

    def _restart_idle_timer(self):
        if self.hasVault and not self.PrivacyCurtain and QtTimersAvailable():
            self.IdleTimer.start(self.IdleSeconds * 1000)
        else:
            self.IdleTimer.stop()

    def _idle_curtain_timeout(self):
        self.dropPrivacyCurtain("IDLE TIMER")

    @Slot()
    def registerActivity(self):
        # mouse wiggles and keyboard taps only postpone the curtain. they never lift it.
        if not self.PrivacyCurtain:
            self._restart_idle_timer()

    @Slot(str, result=bool)
    def dropPrivacyCurtain(self, Reason="MANUAL"):
        if not self.hasVault or self.PrivacyCurtain:
            return False
        self.PrivacyCurtain = True
        self.IdleTimer.stop()
        self._cover_password(Emit=True)
        self.clearOwnedClipboard()
        self.privacyChanged.emit()
        self._set_status(f"PRIVACY CURTAIN DROPPED // {Reason}")
        self.requestSound("hide")
        return True

    @Slot(result=bool)
    def liftPrivacyCurtain(self):
        if not self.PrivacyCurtain:
            return False
        self.PrivacyCurtain = False
        self.privacyChanged.emit()
        self._restart_idle_timer()
        self._set_status("PRIVACY CURTAIN LIFTED // NOT AN AUTHENTICATION CHECK")
        self.requestSound("ui_click")
        return True

    @Slot()
    def coverForPrivacy(self):
        if self._cover_password(Emit=True):
            self._set_status("PASSWORD HIDDEN WHEN WINDOW LEFT")

    @Slot(bool)
    def setCustomCursorActive(self, Active):
        if hasattr(self, "CursorFilter"):
            self.CursorFilter.setActive(bool(Active))


#MARK: fake mouse stuffs
class CursorEventFilter(QObject):
    ACTIVITY_EVENTS = frozenset((
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonRelease,
        QEvent.Type.MouseMove,
        QEvent.Type.KeyPress,
        QEvent.Type.Wheel,
        QEvent.Type.TouchBegin,
        QEvent.Type.TouchUpdate,
    ))

    def __init__(self, Window, Backend=None):
        super().__init__(Window)
        self.Window = Window
        self.Backend = Backend
        self.OverrideActive = False

    def setActive(self, Active):
        if Active and bool(self.Window.property("cursorInside")):
            # blank the boring mac cursor. qml draws the chunky one over everything else.
            if not self.OverrideActive:
                QGuiApplication.setOverrideCursor(QCursor(Qt.CursorShape.BlankCursor))
                self.OverrideActive = True
            self.Window.setCursor(QCursor(Qt.CursorShape.BlankCursor))
        else:
            # always restore the mac cursor when leaving or cmd-tabbing away.
            self.Window.unsetCursor()
            if self.OverrideActive:
                QGuiApplication.restoreOverrideCursor()
                self.OverrideActive = False

    def _move_pointer(self, Event):
        Position = Event.position()
        self.Window.setProperty("cursorX", Position.x())
        self.Window.setProperty("cursorY", Position.y())
        self.Window.setProperty("cursorInside", True)

    def eventFilter(self, Watched, Event):
        EventType = Event.type()
        if self.Backend is not None and EventType in self.ACTIVITY_EVENTS:
            self.Backend.registerActivity()
        if EventType == QEvent.Type.MouseButtonPress:
            # first click opts into the tic-80-ish cursor for this window.
            self._move_pointer(Event)
            self.Window.setProperty("customCursorActive", True)
            self.Window.setProperty("cursorPressed", True)
        elif EventType == QEvent.Type.MouseButtonRelease:
            self._move_pointer(Event)
            self.Window.setProperty("cursorPressed", False)
        elif EventType == QEvent.Type.MouseMove:
            self._move_pointer(Event)
        elif EventType == QEvent.Type.Enter:
            self.Window.setProperty("cursorInside", True)
            self.setActive(bool(self.Window.property("customCursorActive")))
        elif EventType == QEvent.Type.Leave:
            self.Window.setProperty("cursorInside", False)
            self.Window.setProperty("cursorPressed", False)
            self.setActive(False)
        elif EventType == QEvent.Type.WindowDeactivate:
            self.setActive(False)
            # cmd-tab should cover a revealed password before another app gets the screen.
            if self.Backend is not None:
                self.Backend.coverForPrivacy()
        elif EventType == QEvent.Type.WindowActivate:
            self.setActive(bool(self.Window.property("customCursorActive")))
            if self.Backend is not None:
                self.Backend.registerActivity()
        return super().eventFilter(Watched, Event)


#MARK: start the app
def RunQtGui(StartPath=None):
    CompileShaders()
    if Sys.platform == "darwin":
        Os.environ.setdefault("QSG_RHI_BACKEND", "metal")
    QQuickStyle.setStyle("Basic")
    # qt does not need to chew on p00p's --vault argument after argparse ate it.
    App = QApplication.instance() or QApplication([Sys.argv[0]])
    App.setApplicationName("p00p weird storage")
    Engine = QQmlApplicationEngine()
    Backend = VaultBackend(StartPath=StartPath)
    # one hookup for every procedural retro beep in the audio goblin.
    Backend.soundRequested.connect(HandleSoundCue)
    App.aboutToQuit.connect(Backend.clearOwnedClipboard)
    # qml gets one boring backend object instead of importing python spaghetti.
    Engine.rootContext().setContextProperty("backend", Backend)
    Engine.load(QUrl.fromLocalFile(str(QML_FILE)))
    if not Engine.rootObjects():
        return 1
    RootWindow = Engine.rootObjects()[0]
    Backend.CursorFilter = CursorEventFilter(RootWindow, Backend)
    RootWindow.installEventFilter(Backend.CursorFilter)
    return App.exec()


def BuildQtParser():
    Parser = Argparse.ArgumentParser(
        prog="qt_gui.py",
        description="open the blocky shader version of the p00p password bowl",
    )
    Parser.add_argument(
        "--vault",
        type=Path,
        help="open this .p00p or .poop file on startup",
    )
    Parser.add_argument("--version", action="version", version=f"p00p {Main.PROJECT_VERSION}")
    return Parser


def RunQtApp(CommandArgs=None):
    Args = BuildQtParser().parse_args(CommandArgs)
    return RunQtGui(StartPath=Args.vault)


if __name__ == "__main__":
    raise SystemExit(RunQtApp())
