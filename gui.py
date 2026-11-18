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

import main as Main


#MARK: colors and stuffs
WINDOW_BG = "#eaded4"
PANEL_BG = "#fffaf5"
PANEL_LIGHT = "#ead9ca"
TEXT = "#2a1b14"
MUTED = "#705e54"
BROWN = "#8a5638"
BROWN_HOVER = "#a86c48"
CREAM = "#59321f"
RED = "#d96b5f"
GREEN = "#76bd82"
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
    ))


#MARK: the main window thingy
class P00PWindow(Tk.Tk):
    def __init__(self, StartPath=None):
        super().__init__()
        self.title("p00p password bowl")
        self.geometry("1000x680")
        self.minsize(820, 560)
        self.configure(bg=WINDOW_BG)

        self.Vault = None
        self.FilePath = None
        self.SelectedName = None
        self.PasswordVisible = False
        self.SearchText = Tk.StringVar()
        self.PathText = Tk.StringVar(value="no bowl open")
        self.StatusText = Tk.StringVar(value="make or open a .p00p bowl to start")

        self.BuildStyles()
        self.BuildMenu()
        self.BuildHeader()
        self.BuildVaultBar()
        self.BuildContent()
        self.BuildStatusBar()
        self.BindKeys()

        DefaultPath = StartPath or Os.environ.get("P00P_FILE", Main.DEFAULT_VAULT)
        if DefaultPath and Path(DefaultPath).is_file():
            self.LoadPath(Path(DefaultPath), Quiet=True)
        else:
            self.UpdateControls()

    #MARK: visual stuffs
    def BuildStyles(self):
        Style = Ttk.Style(self)
        # old macOS python ships Tk 8.5. forcing the clam theme makes its
        # widgets render completely blank in dark mode, so keep aqua here.
        Style.configure("P00P.TFrame", background=PANEL_BG)
        Style.configure("P00P.TLabel", background=PANEL_BG, foreground=TEXT,
                        font=(FONT, 13))
        Style.configure("Muted.TLabel", background=PANEL_BG, foreground=MUTED,
                        font=(FONT, 11))
        Style.configure("Title.TLabel", background=WINDOW_BG, foreground=CREAM,
                        font=(FONT, 30, "bold"))
        Style.configure("Warning.TLabel", background="#f5d4ce", foreground="#8a2f27",
                        font=(FONT, 11, "bold"), padding=(12, 8))
        Style.configure("P00P.TButton", background=BROWN, foreground=TEXT,
                        font=(FONT, 11, "bold"), padding=(12, 7), borderwidth=0)
        Style.map("P00P.TButton", background=[("active", BROWN_HOVER), ("disabled", "#3d3531")],
                  foreground=[("disabled", "#7e746e")])
        Style.configure("Quiet.TButton", background=PANEL_LIGHT, foreground=TEXT,
                        font=(FONT, 11), padding=(10, 7), borderwidth=0)
        Style.map("Quiet.TButton", background=[("active", "#dec8b6"), ("disabled", "#eee6df")],
                  foreground=[("disabled", "#9a8d85")])
        Style.configure("Danger.TButton", background="#703c37", foreground=TEXT,
                        font=(FONT, 11), padding=(10, 7), borderwidth=0)
        Style.map("Danger.TButton", background=[("active", "#925049")])
        Style.configure("P00P.Treeview", background=PANEL_BG, fieldbackground=PANEL_BG,
                        foreground=TEXT, rowheight=34, borderwidth=0, font=(FONT, 11))
        Style.configure("P00P.Treeview.Heading", background=PANEL_LIGHT, foreground=CREAM,
                        font=(FONT, 11, "bold"), relief="flat")
        Style.map("P00P.Treeview", background=[("selected", BROWN)],
                  foreground=[("selected", "#ffffff")])

    def BuildMenu(self):
        MenuBar = Tk.Menu(self)
        FileMenu = Tk.Menu(MenuBar, tearoff=False)
        FileMenu.add_command(label="new bowl", command=self.NewVault, accelerator="Cmd+N")
        FileMenu.add_command(label="open bowl...", command=self.OpenVault, accelerator="Cmd+O")
        FileMenu.add_separator()
        FileMenu.add_command(label="quit", command=self.destroy, accelerator="Cmd+Q")
        MenuBar.add_cascade(label="file", menu=FileMenu)

        ToolsMenu = Tk.Menu(MenuBar, tearoff=False)
        ToolsMenu.add_command(label="add fake login", command=self.AddEntry, accelerator="Cmd+Shift+N")
        ToolsMenu.add_command(label="audit bowl", command=self.ShowAudit)
        ToolsMenu.add_command(label="file anatomy", command=self.ShowAnatomy)
        MenuBar.add_cascade(label="tools", menu=ToolsMenu)

        HelpMenu = Tk.Menu(MenuBar, tearoff=False)
        HelpMenu.add_command(label="important security reality check", command=self.ShowAbout)
        MenuBar.add_cascade(label="help", menu=HelpMenu)
        self.configure(menu=MenuBar)

    def BuildHeader(self):
        Header = Ttk.Frame(self, style="P00P.TFrame", padding=(24, 18))
        Header.pack(fill="x", padx=18, pady=(18, 8))
        Header.columnconfigure(0, weight=1)
        Ttk.Label(Header, text="p00p", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        Ttk.Label(Header, text="persistent 0-leak 0bject protocol",
                  style="Muted.TLabel").grid(row=1, column=0, sticky="w")
        Ttk.Label(Header, text="NOT REAL ENCRYPTION — ONLY USE FAKE PASSWORDS",
                  style="Warning.TLabel").grid(row=0, column=1, rowspan=2, sticky="e")

    def BuildVaultBar(self):
        Bar = Ttk.Frame(self, style="P00P.TFrame", padding=(16, 12))
        Bar.pack(fill="x", padx=18, pady=8)
        Bar.columnconfigure(0, weight=1)
        Ttk.Label(Bar, textvariable=self.PathText, style="P00P.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 12))
        Ttk.Button(Bar, text="new bowl", style="Quiet.TButton", command=self.NewVault).grid(
            row=0, column=1, padx=4)
        Ttk.Button(Bar, text="open bowl", style="P00P.TButton", command=self.OpenVault).grid(
            row=0, column=2, padx=(4, 0))

    def BuildContent(self):
        Content = Ttk.Frame(self, style="P00P.TFrame")
        Content.pack(fill="both", expand=True, padx=18, pady=8)
        Content.columnconfigure(0, weight=3)
        Content.columnconfigure(1, weight=2)
        Content.rowconfigure(0, weight=1)
        self.BuildEntryList(Content)
        self.BuildDetails(Content)

    def BuildEntryList(self, Parent):
        Left = Ttk.Frame(Parent, style="P00P.TFrame", padding=14)
        Left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        Left.columnconfigure(0, weight=1)
        Left.rowconfigure(2, weight=1)

        Heading = Ttk.Frame(Left, style="P00P.TFrame")
        Heading.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        Heading.columnconfigure(0, weight=1)
        Ttk.Label(Heading, text="fake logins", style="P00P.TLabel").grid(row=0, column=0, sticky="w")
        self.AddButton = Ttk.Button(Heading, text="+ add", style="P00P.TButton",
                                   command=self.AddEntry)
        self.AddButton.grid(row=0, column=1, sticky="e")

        Search = Ttk.Entry(Left, textvariable=self.SearchText, font=(FONT, 12))
        Search.grid(row=1, column=0, sticky="ew", pady=(0, 10), ipady=5)
        Search.insert(0, "")
        self.SearchEntry = Search
        self.SearchText.trace_add("write", lambda *_: self.RefreshList())

        TreeFrame = Ttk.Frame(Left, style="P00P.TFrame")
        TreeFrame.grid(row=2, column=0, sticky="nsew")
        TreeFrame.columnconfigure(0, weight=1)
        TreeFrame.rowconfigure(0, weight=1)
        self.EntryTree = Ttk.Treeview(TreeFrame, columns=("username", "updated"),
                                      show="tree headings", style="P00P.Treeview")
        self.EntryTree.heading("#0", text="name")
        self.EntryTree.heading("username", text="username")
        self.EntryTree.heading("updated", text="updated")
        self.EntryTree.column("#0", width=190, minwidth=120)
        self.EntryTree.column("username", width=150, minwidth=100)
        self.EntryTree.column("updated", width=105, minwidth=90, anchor="center")
        Scroll = Ttk.Scrollbar(TreeFrame, orient="vertical", command=self.EntryTree.yview)
        self.EntryTree.configure(yscrollcommand=Scroll.set)
        self.EntryTree.grid(row=0, column=0, sticky="nsew")
        Scroll.grid(row=0, column=1, sticky="ns")
        self.EntryTree.bind("<<TreeviewSelect>>", self.OnSelection)
        self.EntryTree.bind("<Double-1>", lambda _Event: self.EditEntry())

    def BuildDetails(self, Parent):
        Right = Ttk.Frame(Parent, style="P00P.TFrame", padding=18)
        Right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        Right.columnconfigure(0, weight=1)
        Ttk.Label(Right, text="selected poop", style="P00P.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 18))

        self.NameValue = self.DetailRow(Right, 1, "name")
        self.UsernameValue = self.DetailRow(Right, 2, "username")
        self.PasswordValue = self.DetailRow(Right, 3, "password")
        self.UpdatedValue = self.DetailRow(Right, 4, "updated")

        Ttk.Label(Right, text="notes", style="Muted.TLabel").grid(
            row=5, column=0, sticky="w", pady=(16, 4))
        self.NotesText = Tk.Text(Right, height=6, wrap="word", bg=PANEL_LIGHT, fg=TEXT,
                                 insertbackground=TEXT, relief="flat", font=(FONT, 11),
                                 padx=10, pady=8, state="disabled")
        self.NotesText.grid(row=6, column=0, sticky="nsew")
        Right.rowconfigure(6, weight=1)

        Buttons = Ttk.Frame(Right, style="P00P.TFrame")
        Buttons.grid(row=7, column=0, sticky="ew", pady=(16, 0))
        Buttons.columnconfigure((0, 1), weight=1)
        self.RevealButton = Ttk.Button(Buttons, text="reveal", style="Quiet.TButton",
                                      command=self.TogglePassword)
        self.RevealButton.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=4)
        self.CopyButton = Ttk.Button(Buttons, text="copy", style="Quiet.TButton",
                                    command=self.CopyPassword)
        self.CopyButton.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=4)
        self.EditButton = Ttk.Button(Buttons, text="edit", style="P00P.TButton",
                                    command=self.EditEntry)
        self.EditButton.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=4)
        self.RemoveButton = Ttk.Button(Buttons, text="remove", style="Danger.TButton",
                                      command=self.RemoveEntry)
        self.RemoveButton.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=4)

    def DetailRow(self, Parent, Row, Label):
        Box = Ttk.Frame(Parent, style="P00P.TFrame")
        Box.grid(row=Row, column=0, sticky="ew", pady=5)
        Box.columnconfigure(1, weight=1)
        Ttk.Label(Box, text=Label, style="Muted.TLabel", width=10).grid(row=0, column=0, sticky="w")
        Value = Ttk.Label(Box, text="—", style="P00P.TLabel", anchor="w")
        Value.grid(row=0, column=1, sticky="ew")
        return Value

    def BuildStatusBar(self):
        Bar = Ttk.Frame(self, style="P00P.TFrame", padding=(14, 8))
        Bar.pack(fill="x", padx=18, pady=(8, 18))
        Ttk.Label(Bar, textvariable=self.StatusText, style="Muted.TLabel").pack(side="left")
        Ttk.Button(Bar, text="audit", style="Quiet.TButton", command=self.ShowAudit).pack(
            side="right", padx=(6, 0))
        Ttk.Button(Bar, text="file guts", style="Quiet.TButton", command=self.ShowAnatomy).pack(
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
        self.EntryTree.bind("<Return>", lambda _Event: self.EditEntry())
        self.EntryTree.bind("<Delete>", lambda _Event: self.RemoveEntry())

    #MARK: opening and saving bowls
    def NewVault(self):
        Filename = FileDialog.asksaveasfilename(
            parent=self,
            title="where should the new password bowl go?",
            defaultextension=".p00p",
            initialfile=".passwords.p00p",
            filetypes=(("p00p bowls", "*.p00p *.poop"), ("all files", "*")),
        )
        if not Filename:
            return
        FilePath = Path(Filename)
        try:
            Vault = Main.NewVault()
            Main.SaveVault(FilePath, Vault)
        except Main.P00PError as Exc:
            self.ShowError("couldnt make the bowl", Exc)
            return
        self.Vault = Vault
        self.FilePath = FilePath
        self.PathText.set(str(FilePath))
        self.SelectedName = None
        self.SearchText.set("")
        self.RefreshList()
        self.SetStatus("new empty bowl made. try not to put a real password in it")

    def OpenVault(self):
        Filename = FileDialog.askopenfilename(
            parent=self,
            title="pick a suspicious password bowl",
            filetypes=(("p00p bowls", "*.p00p *.poop"), ("all files", "*")),
        )
        if Filename:
            self.LoadPath(Path(Filename))

    def LoadPath(self, FilePath, Quiet=False):
        try:
            Vault = Main.LoadVault(Path(FilePath))
        except Main.P00PError as Exc:
            if not Quiet:
                self.ShowError("that bowl is broken or fake", Exc)
            return False
        self.Vault = Vault
        self.FilePath = Path(FilePath)
        self.PathText.set(str(self.FilePath))
        self.SelectedName = None
        self.PasswordVisible = False
        self.RefreshList()
        self.SetStatus(f"opened {len(Vault['entries'])} fake login(s)")
        return True

    def SaveCandidate(self, Candidate, Status):
        try:
            Main.SaveVault(self.FilePath, Candidate)
        except Main.P00PError as Exc:
            self.ShowError("the bowl refused to save", Exc)
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
            self.ShowDetails(None)
            self.UpdateControls()
            return

        Names = FilterEntryNames(self.Vault, self.SearchText.get())
        for Name in Names:
            Entry = self.Vault["entries"][Name]
            Updated = str(Entry.get("updated_at", "unknown"))[:10]
            self.EntryTree.insert("", "end", iid=Name, text=Name,
                                  values=(Entry.get("username") or "—", Updated))
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

    def OnSelection(self, _Event=None):
        Selection = self.EntryTree.selection()
        self.SelectedName = Selection[0] if Selection else None
        self.PasswordVisible = False
        self.ShowDetails(self.SelectedName)
        self.UpdateControls()

    def ShowDetails(self, Name):
        if not Name or self.Vault is None or Name not in self.Vault["entries"]:
            Values = ("—", "—", "—", "—")
            Notes = "pick a fake login from the list"
        else:
            Entry = self.Vault["entries"][Name]
            Password = Entry.get("password", "")
            VisiblePassword = Password if self.PasswordVisible else "•" * max(8, min(len(Password), 24))
            Values = (Name, Entry.get("username") or "—", VisiblePassword,
                      Entry.get("updated_at") or "unknown")
            Notes = Entry.get("notes") or "no notes"
        for Widget, Value in zip(
            (self.NameValue, self.UsernameValue, self.PasswordValue, self.UpdatedValue), Values
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
        for Button in (self.RevealButton, self.CopyButton, self.EditButton, self.RemoveButton):
            Button.configure(state="normal" if HasSelection else "disabled")

    #MARK: changing the password stuffs
    def AddEntry(self):
        if self.Vault is None:
            MessageBox.showinfo("no bowl yet", "make or open a .p00p bowl first", parent=self)
            return
        EntryDialog(self, Title="add fake login", OnSave=self.SaveNewEntry)

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
        EntryDialog(self, Title="edit fake login", OnSave=self.SaveEditedEntry,
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
            "flush this entry?", f"remove {Name!r} from the bowl?\n\nthis cannot be undone.",
            parent=self, icon="warning",
        )
        if not Confirmed:
            return
        Candidate = Copy.deepcopy(self.Vault)
        del Candidate["entries"][Name]
        self.SelectedName = None
        self.SaveCandidate(Candidate, f"removed {Name!r}")

    #MARK: password buttons
    def TogglePassword(self):
        if not self.SelectedName:
            return
        self.PasswordVisible = not self.PasswordVisible
        self.ShowDetails(self.SelectedName)

    def CopyPassword(self):
        if not self.SelectedName or self.Vault is None:
            return
        Password = self.Vault["entries"][self.SelectedName].get("password", "")
        self.clipboard_clear()
        self.clipboard_append(Password)
        self.update_idletasks()
        self.SetStatus("password copied. clipboard clears in 20 seconds")
        self.after(20_000, lambda: self.ClearClipboardIfSame(Password))

    def ClearClipboardIfSame(self, Password):
        try:
            if self.clipboard_get() == Password:
                self.clipboard_clear()
                self.SetStatus("clipboard cleared")
        except Tk.TclError:
            pass

    #MARK: report windows
    def ShowAudit(self):
        if self.Vault is None:
            MessageBox.showinfo("no bowl yet", "open a bowl before auditing it", parent=self)
            return
        Findings = AuditVault(self.Vault, self.FilePath)
        if Findings:
            Lines = [f"{len(Findings)} thing(s) look kinda bad:\n"]
            Lines.extend(f"• {Name}: {Finding}" for Name, Finding in Findings)
        else:
            Lines = ["no basic hygiene problems found :D"]
        Lines.extend(("", "this only checks basic patterns.",
                      "the entire p00p format is still not real encryption."))
        TextWindow(self, "bowl audit", "\n".join(Lines))

    def ShowAnatomy(self):
        if self.FilePath is None:
            MessageBox.showinfo("no bowl yet", "open a bowl before dissecting it", parent=self)
            return
        try:
            Report = FormatAnatomy(self.FilePath)
        except Main.P00PError as Exc:
            self.ShowError("couldnt inspect the bowl", Exc)
            return
        TextWindow(self, "file guts", Report, Monospace=True)

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
        self.geometry("500x540")
        self.minsize(440, 500)
        self.configure(bg=WINDOW_BG)
        self.transient(Parent)
        self.grab_set()

        self.NameText = Tk.StringVar(value=Name)
        self.UsernameText = Tk.StringVar(value=self.Entry.get("username", ""))
        self.PasswordText = Tk.StringVar(value=self.Entry.get("password", ""))
        self.ShowPassword = Tk.BooleanVar(value=False)

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

        Ttk.Label(Body, text="notes", style="Muted.TLabel").grid(
            row=8, column=0, sticky="w", pady=(12, 3))
        self.Notes = Tk.Text(Body, height=6, wrap="word", bg=PANEL_LIGHT, fg=TEXT,
                             insertbackground=TEXT, relief="flat", font=(FONT, 11),
                             padx=10, pady=8)
        self.Notes.grid(row=9, column=0, sticky="nsew")
        self.Notes.insert("1.0", self.Entry.get("notes", ""))
        Body.rowconfigure(9, weight=1)

        Buttons = Ttk.Frame(Body, style="P00P.TFrame")
        Buttons.grid(row=10, column=0, sticky="ew", pady=(18, 0))
        Buttons.columnconfigure((0, 1), weight=1)
        Ttk.Button(Buttons, text="cancel", style="Quiet.TButton", command=self.destroy).grid(
            row=0, column=0, sticky="ew", padx=(0, 5))
        Ttk.Button(Buttons, text="save fake login", style="P00P.TButton", command=self.Save).grid(
            row=0, column=1, sticky="ew", padx=(5, 0))

        self.bind("<Escape>", lambda _Event: self.destroy())
        self.bind("<Command-Return>", lambda _Event: self.Save())
        self.bind("<Control-Return>", lambda _Event: self.Save())
        self.NameEntry.focus_set()

    def Field(self, Parent, Row, Label, Variable):
        Ttk.Label(Parent, text=Label, style="Muted.TLabel").grid(row=Row, column=0, sticky="w")
        Entry = Ttk.Entry(Parent, textvariable=Variable, font=(FONT, 12))
        Entry.grid(row=Row + 1, column=0, sticky="ew", pady=(3, 12), ipady=5)
        return Entry

    def Generate(self):
        self.PasswordText.set(Main.GeneratePassword())
        self.ShowPassword.set(True)
        self.UpdatePasswordVisibility()

    def UpdatePasswordVisibility(self):
        self.PasswordEntry.configure(show="" if self.ShowPassword.get() else "•")

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
        Data = {
            "name": Name,
            "username": self.UsernameText.get().strip(),
            "password": Password,
            "notes": self.Notes.get("1.0", "end-1c").strip(),
        }
        if self.OnSave(Data):
            self.destroy()


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
    App = P00PWindow(StartPath=StartPath)
    App.mainloop()


if __name__ == "__main__":
    RunGui()
