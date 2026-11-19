#------------------------------------------------------------------#
# p00p graphical password bowl                                    #
# tkinter because electron does not need to eat every app :D       #
#------------------------------------------------------------------#

import copy as Copy
import hashlib as Hashlib
import os as Os
import tkinter as Tk
from pathlib import Path
from tkinter import filedialog as FileDialog
from tkinter import messagebox as MessageBox
from tkinter import ttk as Ttk
#
import main as Main


#MARK: colors and stuffs
WINDOW_BG = "#0e0c0b"
PANEL_BG = "#171310"
PANEL_LIGHT = "#211b17"
PANEL_BORDER = "#342a24"
TEXT = "#f6eee8"
MUTED = "#a8998f"
BROWN = "#d07b42"
BROWN_HOVER = "#e38b50"
CREAM = "#fff5ed"
RED = "#ff7777"
GREEN = "#6bd18d"
FONT = "Avenir Next"
MONO_FONT = "SF Mono"


#MARK: helper stuffs
def FilterEntryNames(Vault, Query=""):
    Query = str(Query or "").strip().casefold()
    Names = []
    for Name, Entry in Vault.get("entries", {}).items():
        Searchable = (Name, Entry.get("username", ""), Entry.get("notes", ""))
        if not Query or any(Query in str(Value).casefold() for Value in Searchable):
            Names.append(Name)
    return sorted(Names, key=str.casefold)


def EntryIssueCounts(Vault):
    Counts = {}
    Fingerprints = {}
    for Name, Entry in Vault.get("entries", {}).items():
        Password = Entry.get("password", "")
        Counts[Name] = len(Main.PasswordIssues(Password))
        if not Entry.get("username"):
            Counts[Name] += 1
        Fingerprint = Hashlib.sha256(Password.encode("utf-8")).hexdigest()
        Fingerprints.setdefault(Fingerprint, []).append(Name)

    for Names in Fingerprints.values():
        if len(Names) > 1:
            for Name in Names:
                Counts[Name] += 1
    return Counts


def EntryRows(Vault, Query="", SortColumn="name", Descending=False):
    Counts = EntryIssueCounts(Vault)
    Rows = []
    for Name in FilterEntryNames(Vault, Query):
        Entry = Vault["entries"][Name]
        Rows.append({
            "name": Name,
            "username": Entry.get("username") or "—",
            "health": Counts.get(Name, 0),
            "updated": str(Entry.get("updated_at") or "unknown"),
        })

    if SortColumn not in {"name", "username", "health", "updated"}:
        SortColumn = "name"

    def SortValue(Row):
        Value = Row[SortColumn]
        if isinstance(Value, str):
            Value = Value.casefold()
        return (Value, Row["name"].casefold())

    return sorted(Rows, key=SortValue, reverse=Descending)


def VaultSummary(Vault, Query=""):
    Counts = EntryIssueCounts(Vault)
    Total = len(Vault.get("entries", {}))
    Shown = len(FilterEntryNames(Vault, Query))
    NeedsWork = sum(Count > 0 for Count in Counts.values())
    return {
        "total": Total,
        "shown": Shown,
        "needs_work": NeedsWork,
        "issues": sum(Counts.values()),
    }


def PasswordMask(Password):
    return "•" * 12 if Password else "—"


def PasswordHealthSummary(Password):
    if not Password:
        return {
            "healthy": False,
            "issues": (),
            "text": "no fake password yet",
        }
    Issues = tuple(Main.PasswordIssues(Password))
    if not Issues:
        Text = "basic checks: looks surprisingly decent"
    else:
        Text = f"{len(Issues)} basic issue(s): " + "; ".join(Issues)
    return {
        "healthy": not Issues,
        "issues": Issues,
        "text": Text,
    }


def GeneratorLength(Value):
    try:
        Length = int(Value)
    except (TypeError, ValueError) as Exc:
        raise Main.P00PError("generator length must be a whole number") from Exc
    if not Main.MIN_PASSWORD_LENGTH <= Length <= Main.MAX_PASSWORD_LENGTH:
        raise Main.P00PError(
            f"generator length must be {Main.MIN_PASSWORD_LENGTH}-{Main.MAX_PASSWORD_LENGTH}"
        )
    return Length


class SequenceLatch:
    def __init__(self, Pattern):
        self.Pattern = tuple(Pattern)
        self.Position = 0

    def Feed(self, Key):
        if not self.Pattern:
            return False
        Expected = self.Pattern[self.Position]
        if Key == Expected:
            self.Position += 1
        elif Key == self.Pattern[0]:
            self.Position = 1
        else:
            self.Position = 0
        if self.Position == len(self.Pattern):
            self.Position = 0
            return True
        return False


def AuditVault(Vault, FilePath=None):
    Findings = []
    Fingerprints = {}
    Entries = Vault.get("entries", {})

    for Name in sorted(Entries, key=str.casefold):
        Entry = Entries[Name]
        Password = Entry.get("password", "")
        Issues = Main.PasswordIssues(Password)
        if not Entry.get("username"):
            Issues.append("has no username")
        for Issue in Issues:
            Findings.append((Name, Issue))
        Fingerprint = Hashlib.sha256(Password.encode("utf-8")).hexdigest()
        Fingerprints.setdefault(Fingerprint, []).append(Name)

    for Names in Fingerprints.values():
        if len(Names) > 1:
            Findings.append(("reused password", ", ".join(sorted(Names, key=str.casefold))))

    if FilePath is not None:
        FilePath = Path(FilePath)
        if not FilePath.name.startswith("."):
            Findings.append(("file", "the vault filename is not hidden"))
        if FilePath.suffix.casefold() not in {".p00p", ".poop"}:
            Findings.append(("file", "the vault has the wrong suspicious extension"))
        try:
            Mode = FilePath.stat().st_mode & 0o777
            if Mode & 0o077:
                Findings.append(("file", f"permissions are {Mode:03o}, not owner-only"))
        except OSError:
            Findings.append(("file", "permissions could not be checked"))
    return Findings


def FormatAnatomy(FilePath):
    Blob = Main.ReadVaultBlob(Path(FilePath))
    Header = Main.ParseHeader(Blob)
    Vault = Main.DecodeVault(Blob)
    return "\n".join((
        f"file:          {FilePath}",
        f"magic:         {Main.MAGIC!r}",
        f"version:       {Header['version']}",
        f"salt:          {Header['salt'].hex()}",
        f"header bytes:  {Header['header_size']}",
        f"payload bytes: {Header['payload_size']}",
        f"checksum:      {Header['digest'].hex()}",
        f"total bytes:   {Header['file_size']}",
        f"decoded:       {len(Vault['entries'])} entries, integrity check passed",
        f"poopline:      {Main.PayloadRitualSummary(Vault, Header['salt'])}",
    ))


#MARK: the main window thingy
class P00PWindow(Tk.Tk):
    def __init__(self, StartPath=None):
        super().__init__()
        self.title("p00p weird storage")
        self.geometry("1080x680")
        self.minsize(900, 600)
        self.configure(bg=WINDOW_BG)

        self.Vault = None
        self.FilePath = None
        self.SelectedName = None
        self.PasswordVisible = False
        self.RevealAfterId = None
        self.SortColumn = "name"
        self.SortDescending = False
        self.MascotClicks = 0
        self.SecretSequence = SequenceLatch(
            ("Up", "Up", "Down", "Down", "Left", "Right", "Left", "Right", "b", "a")
        )
        self.SearchText = Tk.StringVar()
        self.PathText = Tk.StringVar(value="no vault open")
        self.StatusText = Tk.StringVar(value="Create or open a .p00p vault to begin")
        self.ListSummaryText = Tk.StringVar(value="no vault open")

        self.BuildStyles()
        self.BuildMenu()
        self.BuildHeader()
        self.BuildVaultBar()
        self.BuildContent()
        self.BuildStatusBar()
        self.BindKeys()
        self.after_idle(self.CenterWindow)

        DefaultPath = StartPath or Os.environ.get("P00P_FILE", Main.DEFAULT_VAULT)
        if DefaultPath and Path(DefaultPath).is_file():
            self.LoadPath(Path(DefaultPath), Quiet=True)
        else:
            self.UpdateControls()

    def CenterWindow(self):
        self.update_idletasks()
        Width = 1080
        Height = 680
        ScreenWidth = self.winfo_screenwidth()
        ScreenHeight = self.winfo_screenheight()
        X = max(20, (ScreenWidth - Width) // 2)
        Y = max(20, (ScreenHeight - Height) // 2)
        self.geometry(f"{Width}x{Height}+{X}+{Y}")

    #MARK: visual stuffs
    def BuildStyles(self):
        Style = Ttk.Style(self)
        # the launcher rejects apples broken Tk 8.5 now, so clam is safe and
        # actually honors the colors instead of inventing charcoal rectangles.
        Style.theme_use("clam")
        Style.configure("Window.TFrame", background=WINDOW_BG)
        Style.configure("P00P.TFrame", background=PANEL_BG)
        Style.configure("Card.TFrame", background=PANEL_BG, borderwidth=0,
                        relief="flat")
        Style.configure("P00P.TLabel", background=PANEL_BG, foreground=TEXT,
                        font=(FONT, 12))
        Style.configure("Muted.TLabel", background=PANEL_BG, foreground=MUTED,
                        font=(FONT, 11))
        Style.configure("Title.TLabel", background=PANEL_BG, foreground=CREAM,
                        font=(FONT, 32, "bold"))
        Style.configure("Section.TLabel", background=PANEL_BG, foreground=TEXT,
                        font=(FONT, 15, "bold"))
        Style.configure("Eyebrow.TLabel", background=PANEL_BG, foreground=BROWN,
                        font=(FONT, 10, "bold"))
        Style.configure("PoopMark.TLabel", background=PANEL_BG,
                        font=("Apple Color Emoji", 44))
        Style.configure("DetailKey.TLabel", background=PANEL_BG, foreground=MUTED,
                        font=(FONT, 10, "bold"))
        Style.configure("DetailValue.TLabel", background=PANEL_BG, foreground=TEXT,
                        font=(FONT, 12))
        Style.configure("Warning.TLabel", background="#2b211b", foreground="#ffb47e",
                        font=(FONT, 10, "bold"), padding=(12, 8))
        Style.configure("Good.TLabel", background="#17251c", foreground=GREEN,
                        font=(FONT, 11, "bold"), padding=(12, 8))
        Style.configure("P00P.TButton", background=BROWN, foreground="#ffffff",
                        font=(FONT, 11, "bold"), padding=(14, 9), borderwidth=0,
                        relief="flat")
        Style.map("P00P.TButton", background=[("active", BROWN_HOVER),
                                               ("pressed", "#b96532"),
                                               ("disabled", "#332a25")],
                  foreground=[("disabled", "#71645d")])
        Style.configure("Quiet.TButton", background=PANEL_LIGHT, foreground=TEXT,
                        font=(FONT, 11, "bold"), padding=(12, 8), borderwidth=0,
                        relief="flat")
        Style.map("Quiet.TButton", background=[("active", "#302721"),
                                                ("pressed", "#3a2f28"),
                                                ("disabled", "#1a1613")],
                  foreground=[("disabled", "#6e625b")])
        Style.configure("Danger.TButton", background="#2b1818", foreground=RED,
                        font=(FONT, 11, "bold"), padding=(12, 8), borderwidth=0,
                        relief="flat")
        Style.map("Danger.TButton", background=[("active", "#3b2020"),
                                                 ("pressed", "#4a2626")])
        Style.configure("Search.TEntry", fieldbackground=PANEL_LIGHT, foreground=TEXT,
                        bordercolor=PANEL_BORDER, lightcolor=PANEL_BORDER,
                        darkcolor=PANEL_BORDER, padding=8)
        Style.configure("P00P.Treeview", background=PANEL_BG, fieldbackground=PANEL_BG,
                        foreground=TEXT, rowheight=38, borderwidth=0, font=(FONT, 11))
        Style.configure("P00P.Treeview.Heading", background=PANEL_LIGHT, foreground=TEXT,
                        font=(FONT, 10, "bold"), relief="flat", padding=(8, 9))
        Style.map("P00P.Treeview.Heading", background=[("active", "#302721")])
        Style.map("P00P.Treeview", background=[("selected", BROWN)],
                  foreground=[("selected", "#ffffff")])

    def BuildMenu(self):
        MenuBar = Tk.Menu(self)
        FileMenu = Tk.Menu(MenuBar, tearoff=False)
        FileMenu.add_command(label="new vault", command=self.NewVault, accelerator="Cmd+N")
        FileMenu.add_command(label="open vault...", command=self.OpenVault, accelerator="Cmd+O")
        FileMenu.add_separator()
        FileMenu.add_command(label="quit", command=self.destroy, accelerator="Cmd+Q")
        MenuBar.add_cascade(label="file", menu=FileMenu)

        ToolsMenu = Tk.Menu(MenuBar, tearoff=False)
        ToolsMenu.add_command(label="add entry", command=self.AddEntry, accelerator="Cmd+Shift+N")
        ToolsMenu.add_command(label="audit vault", command=self.ShowAudit)
        ToolsMenu.add_command(label="security theater score", command=self.ShowTheater)
        ToolsMenu.add_command(label="file anatomy", command=self.ShowAnatomy)
        MenuBar.add_cascade(label="tools", menu=ToolsMenu)

        HelpMenu = Tk.Menu(MenuBar, tearoff=False)
        HelpMenu.add_command(label="important security reality check", command=self.ShowAbout)
        MenuBar.add_cascade(label="help", menu=HelpMenu)
        self.configure(menu=MenuBar)

    def BuildHeader(self):
        Header = Ttk.Frame(self, style="Card.TFrame", padding=(20, 10))
        Header.pack(fill="x", padx=16, pady=(14, 4))
        Header.columnconfigure(1, weight=1)
        self.BuildPoopMark(Header).grid(row=0, column=0, rowspan=3, sticky="w", padx=(0, 18))

        Brand = Ttk.Frame(Header, style="P00P.TFrame")
        Brand.grid(row=0, column=1, rowspan=3, sticky="w")
        Ttk.Label(Brand, text="LOCAL WEIRD STORAGE", style="Eyebrow.TLabel").grid(
            row=0, column=0, sticky="w")
        Ttk.Label(Brand, text="p00p vault", style="Title.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 1))
        Ttk.Label(Brand, text="custom binary vault  •  demo credentials only",
                  style="Muted.TLabel").grid(row=2, column=0, sticky="w")
        Ttk.Label(Header, text="DEMO  •  NOT ENCRYPTED",
                  style="Warning.TLabel").grid(row=0, column=2, rowspan=3, sticky="e")

    def BuildPoopMark(self, Parent):
        Mark = Ttk.Label(Parent, text="💩", style="PoopMark.TLabel", cursor="pointinghand")
        Mark.bind("<Button-1>", self.OnMascotClick)
        return Mark

    def BuildVaultBar(self):
        Bar = Ttk.Frame(self, style="Card.TFrame", padding=(14, 8))
        Bar.pack(fill="x", padx=16, pady=4)
        Bar.columnconfigure(0, weight=1)
        PathArea = Ttk.Frame(Bar, style="P00P.TFrame")
        PathArea.grid(row=0, column=0, sticky="w", padx=(0, 12))
        Ttk.Label(PathArea, text="ACTIVE VAULT", style="Eyebrow.TLabel").grid(
            row=0, column=0, sticky="w")
        Ttk.Label(PathArea, textvariable=self.PathText, style="P00P.TLabel").grid(
            row=1, column=0, sticky="w")
        Ttk.Button(Bar, text="new vault", style="Quiet.TButton", command=self.NewVault).grid(
            row=0, column=1, padx=4)
        Ttk.Button(Bar, text="open vault", style="P00P.TButton", command=self.OpenVault).grid(
            row=0, column=2, padx=(4, 0))

    def BuildContent(self):
        Content = Ttk.Frame(self, style="Window.TFrame")
        Content.pack(fill="both", expand=True, padx=16, pady=4)
        Content.columnconfigure(0, weight=3)
        Content.columnconfigure(1, weight=2)
        Content.rowconfigure(0, weight=1)
        self.BuildEntryList(Content)
        self.BuildDetails(Content)

    def BuildEntryList(self, Parent):
        Left = Ttk.Frame(Parent, style="Card.TFrame", padding=18)
        Left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        Left.columnconfigure(0, weight=1)
        Left.rowconfigure(4, weight=1)

        Heading = Ttk.Frame(Left, style="P00P.TFrame")
        Heading.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        Heading.columnconfigure(0, weight=1)
        Ttk.Label(Heading, text="entries", style="Section.TLabel").grid(
            row=0, column=0, sticky="w")
        self.AddButton = Ttk.Button(Heading, text="+ add entry", style="P00P.TButton",
                                   command=self.AddEntry)
        self.AddButton.grid(row=0, column=1, sticky="e")

        Ttk.Label(Left, text="Search names, usernames, and notes", style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 5))
        Search = Ttk.Entry(Left, textvariable=self.SearchText, font=(FONT, 12),
                           style="Search.TEntry")
        Search.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        Search.insert(0, "")
        self.SearchEntry = Search
        self.SearchText.trace_add("write", lambda *_: self.RefreshList())

        Ttk.Label(Left, textvariable=self.ListSummaryText, style="Muted.TLabel").grid(
            row=3, column=0, sticky="w", pady=(0, 8))

        TreeFrame = Ttk.Frame(Left, style="P00P.TFrame")
        TreeFrame.grid(row=4, column=0, sticky="nsew")
        TreeFrame.columnconfigure(0, weight=1)
        TreeFrame.rowconfigure(0, weight=1)
        self.EntryTree = Ttk.Treeview(TreeFrame, columns=("username", "health", "updated"),
                                      show="tree headings", style="P00P.Treeview", height=5)
        self.EntryTree.heading("#0", text="name", command=lambda: self.ChangeSort("name"))
        self.EntryTree.heading("username", text="username",
                               command=lambda: self.ChangeSort("username"))
        self.EntryTree.heading("health", text="health", command=lambda: self.ChangeSort("health"))
        self.EntryTree.heading("updated", text="updated", command=lambda: self.ChangeSort("updated"))
        self.EntryTree.column("#0", width=155, minwidth=110)
        self.EntryTree.column("username", width=120, minwidth=90)
        self.EntryTree.column("health", width=76, minwidth=68, anchor="center")
        self.EntryTree.column("updated", width=90, minwidth=82, anchor="center")
        Scroll = Ttk.Scrollbar(TreeFrame, orient="vertical", command=self.EntryTree.yview)
        self.EntryTree.configure(yscrollcommand=Scroll.set)
        self.EntryTree.grid(row=0, column=0, sticky="nsew")
        Scroll.grid(row=0, column=1, sticky="ns")
        self.EntryTree.bind("<<TreeviewSelect>>", self.OnSelection)
        self.EntryTree.bind("<Double-1>", lambda _Event: self.EditEntry())

    def BuildDetails(self, Parent):
        Right = Ttk.Frame(Parent, style="Card.TFrame", padding=18)
        Right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        Right.columnconfigure(0, weight=1)
        Ttk.Label(Right, text="entry details", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 16))

        self.NameValue = self.DetailRow(Right, 1, "name")
        self.UsernameValue = self.DetailRow(Right, 2, "username")
        self.PasswordValue = self.DetailRow(Right, 3, "password")
        self.UpdatedValue = self.DetailRow(Right, 4, "updated")
        self.HealthValue = self.DetailRow(Right, 5, "health")

        Ttk.Label(Right, text="notes", style="Muted.TLabel").grid(
            row=6, column=0, sticky="w", pady=(16, 4))
        self.NotesText = Tk.Text(Right, width=1, height=3, wrap="word", bg=PANEL_LIGHT, fg=TEXT,
                                 insertbackground=TEXT, relief="flat", font=(FONT, 11),
                                 padx=12, pady=10, state="disabled",
                                 highlightthickness=1, highlightbackground=PANEL_BORDER)
        self.NotesText.grid(row=7, column=0, sticky="nsew")
        Right.rowconfigure(7, weight=1)

        Buttons = Ttk.Frame(Right, style="P00P.TFrame")
        Buttons.grid(row=8, column=0, sticky="ew", pady=(16, 0))
        Buttons.columnconfigure((0, 1, 2), weight=1)
        self.RevealButton = Ttk.Button(Buttons, text="reveal", style="Quiet.TButton",
                                      command=self.TogglePassword)
        self.RevealButton.grid(row=0, column=0, sticky="ew", padx=(0, 3), pady=4)
        self.CopyButton = Ttk.Button(Buttons, text="copy password", style="Quiet.TButton",
                                    command=self.CopyPassword)
        self.CopyButton.grid(row=0, column=1, sticky="ew", padx=3, pady=4)
        self.CopyUsernameButton = Ttk.Button(Buttons, text="copy username", style="Quiet.TButton",
                                            command=self.CopyUsername)
        self.CopyUsernameButton.grid(row=0, column=2, sticky="ew", padx=(3, 0), pady=4)
        self.EditButton = Ttk.Button(Buttons, text="edit", style="P00P.TButton",
                                    command=self.EditEntry)
        self.EditButton.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 3), pady=4)
        self.RemoveButton = Ttk.Button(Buttons, text="remove", style="Danger.TButton",
                                      command=self.RemoveEntry)
        self.RemoveButton.grid(row=1, column=2, sticky="ew", padx=(3, 0), pady=4)

    def DetailRow(self, Parent, Row, Label):
        Box = Ttk.Frame(Parent, style="P00P.TFrame")
        Box.grid(row=Row, column=0, sticky="ew", pady=2)
        Box.columnconfigure(1, weight=1)
        Ttk.Label(Box, text=Label.upper(), style="DetailKey.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 14))
        Value = Ttk.Label(Box, text="—", style="DetailValue.TLabel", anchor="w")
        Value.grid(row=0, column=1, sticky="ew")
        return Value

    def BuildStatusBar(self):
        Bar = Ttk.Frame(self, style="Card.TFrame", padding=(12, 6))
        Bar.pack(side="bottom", fill="x", padx=16, pady=(4, 14))
        Ttk.Label(Bar, textvariable=self.StatusText, style="Muted.TLabel").pack(side="left")
        Ttk.Button(Bar, text="audit", style="Quiet.TButton", command=self.ShowAudit).pack(
            side="right", padx=(6, 0))
        Ttk.Button(Bar, text="security theater", style="Quiet.TButton", command=self.ShowTheater).pack(
            side="right", padx=(6, 0))
        Ttk.Button(Bar, text="file anatomy", style="Quiet.TButton", command=self.ShowAnatomy).pack(
            side="right")

    def BindKeys(self):
        for Shortcut in ("<Command-n>", "<Control-n>"):
            self.bind_all(Shortcut, lambda _Event: self.NewVault())
        for Shortcut in ("<Command-o>", "<Control-o>"):
            self.bind_all(Shortcut, lambda _Event: self.OpenVault())
        for Shortcut in ("<Command-Shift-N>", "<Control-Shift-N>"):
            self.bind_all(Shortcut, lambda _Event: self.AddEntry())
        for Shortcut in ("<Command-f>", "<Control-f>"):
            self.bind_all(Shortcut, lambda _Event: self.SearchEntry.focus_set())
        self.bind_all("<KeyPress>", self.OnSecretKey, add="+")
        self.EntryTree.bind("<Return>", lambda _Event: self.EditEntry())
        self.EntryTree.bind("<Delete>", lambda _Event: self.RemoveEntry())

    #MARK: secret sewer stuffs
    def OnSecretKey(self, Event):
        if self.SecretSequence.Feed(Event.keysym):
            SecretWindow(
                self,
                "Sewer mode unlocked",
                "🚽",
                "The ancient directional ritual worked.\n\n"
                "You now have administrator access to absolutely nothing.",
            )
            self.SetStatus("Secret sewer mode unlocked")

    def OnMascotClick(self, _Event=None):
        self.MascotClicks += 1
        if self.MascotClicks < 5:
            return
        self.MascotClicks = 0
        SecretWindow(
            self,
            "Golden poop discovered",
            "🏆",
            "You clicked the mascot five times. This achievement has no value, "
            "cannot be exported, and adds zero security.",
        )
        self.SetStatus("Easter egg found: golden poop")

    #MARK: opening and saving bowls
    def NewVault(self):
        Filename = FileDialog.asksaveasfilename(
            parent=self,
            title="Save the new .p00p vault",
            defaultextension=".p00p",
            initialfile=".passwords.p00p",
            filetypes=(("p00p vaults", "*.p00p *.poop"), ("all files", "*")),
        )
        if not Filename:
            return
        FilePath = Path(Filename)
        try:
            Vault = Main.NewVault()
            Main.SaveVault(FilePath, Vault)
        except Main.P00PError as Exc:
            self.ShowError("Could not create the vault", Exc)
            return
        self.Vault = Vault
        self.FilePath = FilePath
        self.CancelRevealTimer()
        self.PasswordVisible = False
        self.PathText.set(str(FilePath))
        self.SelectedName = None
        self.SearchText.set("")
        self.RefreshList()
        self.SetStatus("New empty vault created — demo credentials only")

    def OpenVault(self):
        Filename = FileDialog.askopenfilename(
            parent=self,
            title="Open a .p00p vault",
            filetypes=(("p00p vaults", "*.p00p *.poop"), ("all files", "*")),
        )
        if Filename:
            self.LoadPath(Path(Filename))

    def LoadPath(self, FilePath, Quiet=False):
        try:
            Vault = Main.LoadVault(Path(FilePath))
        except Main.P00PError as Exc:
            if not Quiet:
                self.ShowError("Could not open that vault", Exc)
            return False
        self.Vault = Vault
        self.FilePath = Path(FilePath)
        self.CancelRevealTimer()
        self.PathText.set(str(self.FilePath))
        self.SelectedName = None
        self.PasswordVisible = False
        self.RefreshList()
        self.SetStatus(f"Opened {len(Vault['entries'])} vault entr{'y' if len(Vault['entries']) == 1 else 'ies'}")
        return True

    def SaveCandidate(self, Candidate, Status):
        try:
            Main.SaveVault(self.FilePath, Candidate)
        except Main.P00PError as Exc:
            self.ShowError("Could not save the vault", Exc)
            return False
        self.Vault = Candidate
        self.RefreshList()
        self.SetStatus(Status)
        return True

    #MARK: list and selection stuffs
    def RefreshList(self):
        if not hasattr(self, "EntryTree"):
            return
        Selected = self.SelectedName
        for Item in self.EntryTree.get_children():
            self.EntryTree.delete(Item)
        if self.Vault is None:
            self.ListSummaryText.set("no vault open")
            self.ShowDetails(None)
            self.UpdateControls()
            return

        Query = self.SearchText.get()
        Rows = EntryRows(self.Vault, Query, self.SortColumn, self.SortDescending)
        Names = [Row["name"] for Row in Rows]
        for Row in Rows:
            Health = "ok" if Row["health"] == 0 else f"{Row['health']} issue(s)"
            self.EntryTree.insert("", "end", iid=Row["name"], text=Row["name"],
                                  values=(Row["username"], Health, Row["updated"][:10]))

        Summary = VaultSummary(self.Vault, Query)
        self.ListSummaryText.set(
            f"{Summary['shown']} shown  •  {Summary['total']} total  •  "
            f"{Summary['needs_work']} need attention"
        )
        self.UpdateSortHeadings()
        if Selected in Names:
            self.EntryTree.selection_set(Selected)
            self.EntryTree.focus(Selected)
            self.EntryTree.see(Selected)
        elif Names:
            self.EntryTree.selection_set(Names[0])
            self.EntryTree.focus(Names[0])
            self.OnSelection()
        else:
            self.SelectedName = None
            self.ShowDetails(None)
        self.UpdateControls()

    def ChangeSort(self, Column):
        if self.SortColumn == Column:
            self.SortDescending = not self.SortDescending
        else:
            self.SortColumn = Column
            self.SortDescending = Column == "updated"
        self.RefreshList()

    def UpdateSortHeadings(self):
        Labels = {
            "name": ("#0", "name"),
            "username": ("username", "username"),
            "health": ("health", "health"),
            "updated": ("updated", "updated"),
        }
        Arrow = " ▼" if self.SortDescending else " ▲"
        for Column, (TreeColumn, Label) in Labels.items():
            Suffix = Arrow if Column == self.SortColumn else ""
            self.EntryTree.heading(TreeColumn, text=Label + Suffix)

    def OnSelection(self, _Event=None):
        self.CancelRevealTimer()
        Selection = self.EntryTree.selection()
        self.SelectedName = Selection[0] if Selection else None
        self.PasswordVisible = False
        self.ShowDetails(self.SelectedName)
        self.UpdateControls()

    def ShowDetails(self, Name):
        if not Name or self.Vault is None or Name not in self.Vault["entries"]:
            Values = ("—", "—", "—", "—", "—")
            Notes = "Select an entry to inspect its details"
        else:
            Entry = self.Vault["entries"][Name]
            Password = Entry.get("password", "")
            VisiblePassword = Password if self.PasswordVisible else PasswordMask(Password)
            IssueCount = EntryIssueCounts(self.Vault).get(Name, 0)
            Health = "looks ok" if IssueCount == 0 else f"{IssueCount} basic issue(s)"
            Values = (Name, Entry.get("username") or "—", VisiblePassword,
                      Entry.get("updated_at") or "unknown", Health)
            Notes = Entry.get("notes") or "no notes"
        for Widget, Value in zip(
            (self.NameValue, self.UsernameValue, self.PasswordValue, self.UpdatedValue,
             self.HealthValue), Values
        ):
            Widget.configure(text=Value)
        self.NotesText.configure(state="normal")
        self.NotesText.delete("1.0", "end")
        self.NotesText.insert("1.0", Notes)
        self.NotesText.configure(state="disabled")
        self.RevealButton.configure(text="hide" if self.PasswordVisible else "reveal")

    def UpdateControls(self):
        HasVault = self.Vault is not None
        HasSelection = HasVault and self.SelectedName in self.Vault["entries"]
        self.AddButton.configure(state="normal" if HasVault else "disabled")
        for Button in (self.RevealButton, self.CopyButton, self.CopyUsernameButton,
                       self.EditButton, self.RemoveButton):
            Button.configure(state="normal" if HasSelection else "disabled")

    #MARK: changing the password stuffs
    def AddEntry(self):
        if self.Vault is None:
            MessageBox.showinfo("No vault open", "Create or open a .p00p vault first", parent=self)
            return
        EntryDialog(self, Title="Add vault entry", OnSave=self.SaveNewEntry)

    def SaveNewEntry(self, Data):
        Name = Data.pop("name")
        Existing = next(
            (Other for Other in self.Vault["entries"] if Other.casefold() == Name.casefold()), None
        )
        if Existing:
            MessageBox.showerror("already in the bowl", f"{Existing!r} already exists", parent=self)
            return False
        Candidate = Copy.deepcopy(self.Vault)
        Data["updated_at"] = Main.CurrentTime()
        Candidate["entries"][Name] = Data
        if self.SaveCandidate(Candidate, f"added {Name!r}"):
            self.SelectedName = Name
            self.RefreshList()
            return True
        return False

    def EditEntry(self):
        if not self.SelectedName or self.Vault is None:
            return
        Entry = Copy.deepcopy(self.Vault["entries"][self.SelectedName])
        EntryDialog(self, Title="Edit vault entry", OnSave=self.SaveEditedEntry,
                    Name=self.SelectedName, Entry=Entry)

    def SaveEditedEntry(self, Data):
        OldName = self.SelectedName
        NewName = Data.pop("name")
        Conflict = next((Name for Name in self.Vault["entries"]
                         if Name.casefold() == NewName.casefold() and Name != OldName), None)
        if Conflict:
            MessageBox.showerror("already in the bowl", f"{Conflict!r} already exists", parent=self)
            return False
        Candidate = Copy.deepcopy(self.Vault)
        Candidate["entries"].pop(OldName)
        Data["updated_at"] = Main.CurrentTime()
        Candidate["entries"][NewName] = Data
        if self.SaveCandidate(Candidate, f"updated {NewName!r}"):
            self.CancelRevealTimer()
            self.SelectedName = NewName
            self.PasswordVisible = False
            self.RefreshList()
            return True
        return False

    def RemoveEntry(self):
        if not self.SelectedName or self.Vault is None:
            return
        Name = self.SelectedName
        Confirmed = MessageBox.askyesno(
            "Remove this entry?", f"Remove {Name!r} from the vault?\n\nThis cannot be undone.",
            parent=self, icon="warning",
        )
        if not Confirmed:
            return
        self.CancelRevealTimer()
        Candidate = Copy.deepcopy(self.Vault)
        del Candidate["entries"][Name]
        self.SelectedName = None
        self.SaveCandidate(Candidate, f"removed {Name!r}")

    #MARK: password buttons
    def TogglePassword(self):
        if not self.SelectedName:
            return
        self.CancelRevealTimer()
        self.PasswordVisible = not self.PasswordVisible
        self.ShowDetails(self.SelectedName)
        if self.PasswordVisible:
            self.RevealAfterId = self.after(20_000, self.HidePassword)
            self.SetStatus("password revealed for 20 seconds")

    def HidePassword(self):
        self.RevealAfterId = None
        if self.PasswordVisible:
            self.PasswordVisible = False
            self.ShowDetails(self.SelectedName)
            self.SetStatus("password hidden again")

    def CancelRevealTimer(self):
        if self.RevealAfterId is not None:
            self.after_cancel(self.RevealAfterId)
            self.RevealAfterId = None

    def CopyPassword(self):
        if not self.SelectedName or self.Vault is None:
            return
        Password = self.Vault["entries"][self.SelectedName].get("password", "")
        self.CopyToClipboard(Password, "password")

    def CopyUsername(self):
        if not self.SelectedName or self.Vault is None:
            return
        Username = self.Vault["entries"][self.SelectedName].get("username", "")
        if not Username:
            self.SetStatus("this entry does not have a username")
            return
        self.CopyToClipboard(Username, "username")

    def CopyToClipboard(self, Value, Label):
        self.clipboard_clear()
        self.clipboard_append(Value)
        self.update_idletasks()
        self.SetStatus(f"{Label} copied. clipboard clears in 20 seconds")
        self.after(20_000, lambda: self.ClearClipboardIfSame(Value))

    def ClearClipboardIfSame(self, Value):
        try:
            if self.clipboard_get() == Value:
                self.clipboard_clear()
                self.SetStatus("clipboard cleared")
        except Tk.TclError:
            pass

    #MARK: report windows
    def ShowAudit(self):
        if self.Vault is None:
            MessageBox.showinfo("No vault open", "Open a vault before auditing it", parent=self)
            return
        Findings = AuditVault(self.Vault, self.FilePath)
        if Findings:
            Lines = [f"{len(Findings)} thing(s) look kinda bad:\n"]
            Lines.extend(f"• {Name}: {Finding}" for Name, Finding in Findings)
        else:
            Lines = ["no basic hygiene problems found :D"]
        Lines.extend(("", "this only checks basic patterns.",
                      "the entire p00p format is still not real encryption."))
        TextWindow(self, "Vault audit", "\n".join(Lines))

    def ShowTheater(self):
        if self.FilePath is None:
            MessageBox.showinfo("No vault open", "Open a vault before measuring its vibes", parent=self)
            return
        try:
            Report = Main.SecurityTheaterReport(self.FilePath).AsText()
        except Main.P00PError as Exc:
            self.ShowError("the applause meter broke", Exc)
            return
        TextWindow(self, "security theater applause meter", Report, Monospace=True)

    def ShowAnatomy(self):
        if self.FilePath is None:
            MessageBox.showinfo("No vault open", "Open a vault before inspecting it", parent=self)
            return
        try:
            Report = FormatAnatomy(self.FilePath)
        except Main.P00PError as Exc:
            self.ShowError("Could not inspect the vault", Exc)
            return
        TextWindow(self, "File anatomy", Report, Monospace=True)

    def ShowAbout(self):
        MessageBox.showwarning(
            "security reality check",
            "p00p is a Weird Storage demo, not a real password manager.\n\n"
            "hidden files + wrong extensions + reversible camouflage do not stop hackers. "
            "only store fake credentials in here.",
            parent=self,
        )

    def ShowError(self, Title, Error):
        MessageBox.showerror(Title, str(Error), parent=self)

    def SetStatus(self, Message):
        self.StatusText.set(Message)


#MARK: add/edit window thingy
class EntryDialog(Tk.Toplevel):
    def __init__(self, Parent, Title, OnSave, Name="", Entry=None):
        super().__init__(Parent)
        self.Parent = Parent
        self.OnSave = OnSave
        self.Entry = Entry or {}
        self.title(Title)
        self.geometry("560x690")
        self.minsize(500, 620)
        self.configure(bg=WINDOW_BG)
        self.transient(Parent)
        self.grab_set()

        self.NameText = Tk.StringVar(value=Name)
        self.UsernameText = Tk.StringVar(value=self.Entry.get("username", ""))
        self.PasswordText = Tk.StringVar(value=self.Entry.get("password", ""))
        self.ShowPassword = Tk.BooleanVar(value=False)
        self.PasswordLength = Tk.StringVar(value=str(Main.DEFAULT_PASSWORD_LENGTH))
        self.UseSymbols = Tk.BooleanVar(value=True)
        self.HealthText = Tk.StringVar(value="no fake password yet")

        Body = Ttk.Frame(self, style="P00P.TFrame", padding=22)
        Body.pack(fill="both", expand=True, padx=16, pady=16)
        Body.columnconfigure(0, weight=1)
        Ttk.Label(Body, text=Title, style="Title.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 18))
        self.NameEntry = self.Field(Body, 1, "name", self.NameText)
        self.Field(Body, 3, "username", self.UsernameText)

        Ttk.Label(Body, text="password", style="Muted.TLabel").grid(row=5, column=0, sticky="w")
        PasswordRow = Ttk.Frame(Body, style="P00P.TFrame")
        PasswordRow.grid(row=6, column=0, sticky="ew", pady=(3, 5))
        PasswordRow.columnconfigure(0, weight=1)
        self.PasswordEntry = Ttk.Entry(PasswordRow, textvariable=self.PasswordText,
                                       show="•", font=(FONT, 12))
        self.PasswordEntry.grid(row=0, column=0, sticky="ew", ipady=5)
        Ttk.Button(PasswordRow, text="generate", style="Quiet.TButton",
                   command=self.Generate).grid(row=0, column=1, padx=(8, 0))
        Ttk.Checkbutton(Body, text="show password", variable=self.ShowPassword,
                        command=self.UpdatePasswordVisibility).grid(row=7, column=0, sticky="w")

        GeneratorOptions = Ttk.Frame(Body, style="P00P.TFrame")
        GeneratorOptions.grid(row=8, column=0, sticky="ew", pady=(8, 5))
        Ttk.Label(GeneratorOptions, text="generated length", style="Muted.TLabel").pack(side="left")
        Ttk.Spinbox(
            GeneratorOptions,
            from_=Main.MIN_PASSWORD_LENGTH,
            to=Main.MAX_PASSWORD_LENGTH,
            textvariable=self.PasswordLength,
            width=6,
            font=(FONT, 11),
        ).pack(side="left", padx=(8, 14))
        Ttk.Checkbutton(GeneratorOptions, text="include symbols",
                        variable=self.UseSymbols).pack(side="left")

        self.HealthLabel = Ttk.Label(
            Body, textvariable=self.HealthText, style="Warning.TLabel", wraplength=460
        )
        self.HealthLabel.grid(row=9, column=0, sticky="ew", pady=(5, 8))

        Ttk.Label(Body, text="notes", style="Muted.TLabel").grid(
            row=10, column=0, sticky="w", pady=(8, 3))
        self.Notes = Tk.Text(Body, height=6, wrap="word", bg=PANEL_LIGHT, fg=TEXT,
                             insertbackground=TEXT, relief="flat", font=(FONT, 11),
                             padx=10, pady=8)
        self.Notes.grid(row=11, column=0, sticky="nsew")
        self.Notes.insert("1.0", self.Entry.get("notes", ""))
        Body.rowconfigure(11, weight=1)

        Buttons = Ttk.Frame(Body, style="P00P.TFrame")
        Buttons.grid(row=12, column=0, sticky="ew", pady=(18, 0))
        Buttons.columnconfigure((0, 1), weight=1)
        Ttk.Button(Buttons, text="cancel", style="Quiet.TButton", command=self.destroy).grid(
            row=0, column=0, sticky="ew", padx=(0, 5))
        Ttk.Button(Buttons, text="save entry", style="P00P.TButton", command=self.Save).grid(
            row=0, column=1, sticky="ew", padx=(5, 0))

        self.bind("<Escape>", lambda _Event: self.destroy())
        self.bind("<Command-Return>", lambda _Event: self.Save())
        self.bind("<Control-Return>", lambda _Event: self.Save())
        self.PasswordText.trace_add("write", lambda *_: self.UpdatePasswordHealth())
        self.UpdatePasswordHealth()
        self.NameEntry.focus_set()

    def Field(self, Parent, Row, Label, Variable):
        Ttk.Label(Parent, text=Label, style="Muted.TLabel").grid(row=Row, column=0, sticky="w")
        Entry = Ttk.Entry(Parent, textvariable=Variable, font=(FONT, 12))
        Entry.grid(row=Row + 1, column=0, sticky="ew", pady=(3, 12), ipady=5)
        return Entry

    def Generate(self):
        try:
            Length = GeneratorLength(self.PasswordLength.get())
            Password = Main.GeneratePassword(Length, Symbols=self.UseSymbols.get())
        except Main.P00PError as Exc:
            MessageBox.showerror("generator got confused", str(Exc), parent=self)
            return
        self.PasswordText.set(Password)
        self.ShowPassword.set(True)
        self.UpdatePasswordVisibility()

    def UpdatePasswordVisibility(self):
        self.PasswordEntry.configure(show="" if self.ShowPassword.get() else "•")

    def UpdatePasswordHealth(self):
        Summary = PasswordHealthSummary(self.PasswordText.get())
        self.HealthText.set(Summary["text"])
        self.HealthLabel.configure(style="Good.TLabel" if Summary["healthy"] else "Warning.TLabel")

    def Save(self):
        Name = self.NameText.get().strip()
        Password = self.PasswordText.get()
        if not Name:
            MessageBox.showerror("missing name", "give the fake login a name", parent=self)
            self.NameEntry.focus_set()
            return
        if not Password:
            MessageBox.showerror("missing password", "the password cannot be empty", parent=self)
            self.PasswordEntry.focus_set()
            return
        Summary = PasswordHealthSummary(Password)
        if Summary["issues"]:
            Confirmed = MessageBox.askyesno(
                "save a weak fake password?",
                f"the basic checker found {len(Summary['issues'])} issue(s):\n\n"
                + "\n".join(f"• {Issue}" for Issue in Summary["issues"])
                + "\n\nsave it anyway?",
                parent=self,
                icon="warning",
            )
            if not Confirmed:
                self.PasswordEntry.focus_set()
                return
        Data = {
            "name": Name,
            "username": self.UsernameText.get().strip(),
            "password": Password,
            "notes": self.Notes.get("1.0", "end-1c").strip(),
        }
        if self.OnSave(Data):
            self.destroy()


#MARK: hidden achievement window thingy
class SecretWindow(Tk.Toplevel):
    def __init__(self, Parent, Title, Emoji, Message):
        super().__init__(Parent)
        self.Parent = Parent
        self.title(Title)
        self.geometry("480x320")
        self.resizable(False, False)
        self.configure(bg=WINDOW_BG)
        self.transient(Parent)

        Frame = Ttk.Frame(self, style="Card.TFrame", padding=28)
        Frame.pack(fill="both", expand=True, padx=14, pady=14)
        Frame.columnconfigure(0, weight=1)
        Ttk.Label(Frame, text=Emoji, style="PoopMark.TLabel").grid(
            row=0, column=0, pady=(4, 12))
        Ttk.Label(Frame, text=Title, style="Section.TLabel").grid(
            row=1, column=0, pady=(0, 10))
        Ttk.Label(Frame, text=Message, style="Muted.TLabel", wraplength=390,
                  justify="center").grid(row=2, column=0, sticky="ew")
        Ttk.Button(Frame, text="return to the vault", style="P00P.TButton",
                   command=self.destroy).grid(row=3, column=0, pady=(22, 0))

        self.bind("<Escape>", lambda _Event: self.destroy())
        self.after_idle(self.CenterOverParent)

    def CenterOverParent(self):
        self.update_idletasks()
        Width = 480
        Height = 320
        X = self.Parent.winfo_rootx() + max(0, (self.Parent.winfo_width() - Width) // 2)
        Y = self.Parent.winfo_rooty() + max(0, (self.Parent.winfo_height() - Height) // 2)
        self.geometry(f"{Width}x{Height}+{X}+{Y}")


#MARK: report window thingy
class TextWindow(Tk.Toplevel):
    def __init__(self, Parent, Title, Content, Monospace=False):
        super().__init__(Parent)
        self.title(Title)
        self.geometry("620x440")
        self.minsize(480, 320)
        self.configure(bg=WINDOW_BG)
        self.transient(Parent)

        Frame = Ttk.Frame(self, style="P00P.TFrame", padding=18)
        Frame.pack(fill="both", expand=True, padx=14, pady=14)
        Frame.columnconfigure(0, weight=1)
        Frame.rowconfigure(1, weight=1)
        Ttk.Label(Frame, text=Title, style="Title.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 12))
        FontName = MONO_FONT if Monospace else FONT
        Text = Tk.Text(Frame, wrap="word", bg=PANEL_LIGHT, fg=TEXT, insertbackground=TEXT,
                       relief="flat", font=(FontName, 12), padx=14, pady=12)
        Text.grid(row=1, column=0, sticky="nsew")
        Text.insert("1.0", Content)
        Text.configure(state="disabled")
        Ttk.Button(Frame, text="done", style="P00P.TButton", command=self.destroy).grid(
            row=2, column=0, sticky="e", pady=(12, 0))
        self.bind("<Escape>", lambda _Event: self.destroy())


def RunGui(StartPath=None):
    from ctk_gui import RunModernGui
    RunModernGui(StartPath=StartPath)


if __name__ == "__main__":
    RunGui()
