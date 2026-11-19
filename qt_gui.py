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

from PySide6.QtCore import Property, QEvent, QObject, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

import main as Main


ROOT = Path(__file__).resolve().parent
QML_FILE = ROOT / "qml" / "Main.qml"
SHADER_SOURCE = ROOT / "qml" / "shaders" / "crt.frag"
SHADER_PACK = ROOT / "qml" / "shaders" / "crt.frag.qsb"
SOUND_CUES = frozenset({
    "ui_click",
    "dialog_open",
    "dialog_close",
    "vault_open",
    "vault_new",
    "entry_save",
    "entry_remove",
    "generate",
    "copy",
    "reveal",
    "hide",
    "error",
    "easter_egg",
})


def HandleSoundCue(Cue):
    # YOUR SOUND STUFF GOES HERE!! map Cue to a wav and play it without blocking qt.
    # all the ui actions already send their little names here so u only wire it once.
    return None


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
    statusChanged = Signal()
    soundRequested = Signal(str)

    def __init__(self, StartPath=None):
        super().__init__()
        self.Vault = None
        self.FilePath = None
        self.SelectedName = ""
        self.Query = ""
        self.SortColumn = "name"
        self.SortDescending = False
        self.PasswordVisible = False
        self.Status = "SYS // READY"

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

    def _set_status(self, Text):
        self.Status = f"SYS // {Text.upper()}"
        self.statusChanged.emit()

    @Slot(str)
    def requestSound(self, Cue):
        # unknown noises get ignored instead of turning one typo into a ghost sound.
        Cue = str(Cue).strip().lower()
        if Cue in SOUND_CUES:
            self.soundRequested.emit(Cue)

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
        Names = sorted(Vault.get("entries", {}), key=str.casefold)
        self.SelectedName = Names[0] if Names else ""
        self.PasswordVisible = False
        self.Status = f"SYS // OPENED {len(Names)} VAULT ENTR{'Y' if len(Names) == 1 else 'IES'}"
        self._emit_everything()
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
        self.PasswordVisible = False
        self.selectionChanged.emit()

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
        self.Vault = Working
        if not self._save():
            # put the old bowl back if the new one never reached disk.
            self.Vault = Original
            return False
        self.SelectedName = CleanName
        self.PasswordVisible = False
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
        self.Vault = Working
        if not self._save():
            self.Vault = Original
            return False
        self.SelectedName = CleanName
        self.PasswordVisible = False
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
        self.Vault = Working
        if not self._save():
            self.Vault = Original
            return
        Names = sorted(self.Vault["entries"], key=str.casefold)
        # land on the first remaining row so the details panel never points at a ghost.
        self.SelectedName = Names[0] if Names else ""
        self.PasswordVisible = False
        self._set_status(f"REMOVED {RemovedName}")
        self.requestSound("entry_remove")
        self.entriesChanged.emit()
        self.selectionChanged.emit()

    #MARK: clipboard stuffs
    def _clear_clipboard_later(self, Text):
        def Clear():
            Clipboard = QGuiApplication.clipboard()
            # do not erase something the user copied after the password.
            if Clipboard.text() == Text:
                Clipboard.clear()
                self._set_status("CLIPBOARD CLEARED")
        QTimer.singleShot(20_000, Clear)

    @Slot()
    def copyUsername(self):
        Text = self._entry().get("username", "")
        if not Text:
            return
        QGuiApplication.clipboard().setText(Text)
        self._clear_clipboard_later(Text)
        self._set_status("USERNAME COPIED FOR 20 SECONDS")
        self.requestSound("copy")

    @Slot()
    def copyPassword(self):
        Text = self._entry().get("password", "")
        if not Text:
            return
        QGuiApplication.clipboard().setText(Text)
        self._clear_clipboard_later(Text)
        self._set_status("PASSWORD COPIED FOR 20 SECONDS")
        self.requestSound("copy")

    @Slot()
    def togglePassword(self):
        if not self._entry():
            return
        self.PasswordVisible = not self.PasswordVisible
        self.requestSound("reveal" if self.PasswordVisible else "hide")
        self.selectionChanged.emit()
        if self.PasswordVisible:
            # revealed means revealed for 20 seconds, not until the app gets forgotten.
            QTimer.singleShot(20_000, self._hide_password)

    def _hide_password(self):
        if self.PasswordVisible:
            self.PasswordVisible = False
            self.selectionChanged.emit()

    @Slot(bool)
    def setCustomCursorActive(self, Active):
        if hasattr(self, "CursorFilter"):
            self.CursorFilter.setActive(bool(Active))


#MARK: fake mouse stuffs
class CursorEventFilter(QObject):
    def __init__(self, Window):
        super().__init__(Window)
        self.Window = Window
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
        elif EventType == QEvent.Type.WindowActivate:
            self.setActive(bool(self.Window.property("customCursorActive")))
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
    # one hookup for every sound. replace HandleSoundCue when ur audio goblin is ready.
    Backend.soundRequested.connect(HandleSoundCue)
    # qml gets one boring backend object instead of importing python spaghetti.
    Engine.rootContext().setContextProperty("backend", Backend)
    Engine.load(QUrl.fromLocalFile(str(QML_FILE)))
    if not Engine.rootObjects():
        return 1
    RootWindow = Engine.rootObjects()[0]
    Backend.CursorFilter = CursorEventFilter(RootWindow)
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
