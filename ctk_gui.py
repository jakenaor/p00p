#------------------------------------------------------------------#
# modern customtkinter shell for the p00p password thingy          #
# the storage is weird. the interface does not have to be          #
#------------------------------------------------------------------#

import copy as Copy
import os as Os
import tkinter as Tk
from pathlib import Path
from tkinter import filedialog as FileDialog
from tkinter import messagebox as MessageBox

import customtkinter as Ctk

import main as Main
from gui import AuditVault, EntryRows, FormatAnatomy, GeneratorLength
from gui import PasswordHealthSummary, PasswordMask, SequenceLatch, VaultSummary


#MARK: the not-ugly colors
BG = "#0b0e13"
SIDEBAR = "#0f1319"
SURFACE = "#151a22"
SURFACE_HIGH = "#1b222c"
SURFACE_HOVER = "#232c38"
BORDER = "#293341"
TEXT = "#f4f7fb"
MUTED = "#8f9baa"
ACCENT = "#f08a4b"
ACCENT_HOVER = "#ff9c61"
GREEN = "#55d491"
RED = "#ff6f7d"
WARNING = "#ffb27d"
FONT = "Avenir Next"
MONO_FONT = "SF Mono"


Ctk.set_appearance_mode("dark")


class ModernP00PWindow(Ctk.CTk):
    def __init__(self, StartPath=None):
        super().__init__(fg_color=BG)
        self.title("p00p weird storage")
        self.geometry("1120x700")
        self.minsize(960, 620)

        self.Vault = None
        self.FilePath = None
        self.SelectedName = None
        self.PasswordVisible = False
        self.RevealAfterId = None
        self.SortColumn = "name"
        self.SortDescending = False
        self.EntryRowsByName = {}
        self.MascotClicks = 0
        self.SecretSequence = SequenceLatch(
            ("Up", "Up", "Down", "Down", "Left", "Right", "Left", "Right", "b", "a")
        )

        self.SearchText = Tk.StringVar()
        self.PathText = Tk.StringVar(value="No vault open")
        self.StatusText = Tk.StringVar(value="Create or open a .p00p vault to begin")
        self.ListSummaryText = Tk.StringVar(value="No vault open")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.BuildMenu()
        self.BuildSidebar()
        self.BuildWorkspace()
        self.BindKeys()
        self.after_idle(self.CenterWindow)

        DefaultPath = StartPath or Os.environ.get("P00P_FILE", Main.DEFAULT_VAULT)
        if DefaultPath and Path(DefaultPath).is_file():
            self.LoadPath(Path(DefaultPath), Quiet=True)
        else:
            self.UpdateControls()

    #MARK: window + navigation stuffs
    def CenterWindow(self):
        self.update_idletasks()
        Width = min(1120, self.winfo_screenwidth() - 40)
        Height = min(700, self.winfo_screenheight() - 70)
        X = max(20, (self.winfo_screenwidth() - Width) // 2)
        Y = max(20, (self.winfo_screenheight() - Height) // 2)
        self.geometry(f"{Width}x{Height}+{X}+{Y}")

    def BuildMenu(self):
        MenuBar = Tk.Menu(self)
        FileMenu = Tk.Menu(MenuBar, tearoff=False)
        FileMenu.add_command(label="New vault", command=self.NewVault, accelerator="Cmd+N")
        FileMenu.add_command(label="Open vault…", command=self.OpenVault, accelerator="Cmd+O")
        FileMenu.add_separator()
        FileMenu.add_command(label="Quit", command=self.destroy, accelerator="Cmd+Q")
        MenuBar.add_cascade(label="File", menu=FileMenu)

        ToolsMenu = Tk.Menu(MenuBar, tearoff=False)
        ToolsMenu.add_command(label="Add entry", command=self.AddEntry, accelerator="Cmd+Shift+N")
        ToolsMenu.add_command(label="Audit vault", command=self.ShowAudit)
        ToolsMenu.add_command(label="Security theater", command=self.ShowTheater)
        ToolsMenu.add_command(label="File anatomy", command=self.ShowAnatomy)
        MenuBar.add_cascade(label="Tools", menu=ToolsMenu)

        HelpMenu = Tk.Menu(MenuBar, tearoff=False)
        HelpMenu.add_command(label="Security reality check", command=self.ShowAbout)
        MenuBar.add_cascade(label="Help", menu=HelpMenu)
        self.configure(menu=MenuBar)

    def BuildSidebar(self):
        Sidebar = Ctk.CTkFrame(self, width=218, corner_radius=0, fg_color=SIDEBAR)
        Sidebar.grid(row=0, column=0, sticky="nsew")
        Sidebar.grid_propagate(False)
        Sidebar.grid_columnconfigure(0, weight=1)
        Sidebar.grid_rowconfigure(8, weight=1)

        self.Mascot = Ctk.CTkLabel(
            Sidebar, text="💩", font=Ctk.CTkFont(family="Apple Color Emoji", size=42),
            cursor="pointinghand",
        )
        self.Mascot.grid(row=0, column=0, sticky="w", padx=24, pady=(28, 2))
        self.Mascot.bind("<Button-1>", self.OnMascotClick)
        Ctk.CTkLabel(
            Sidebar, text="p00p", text_color=TEXT,
            font=Ctk.CTkFont(family=FONT, size=28, weight="bold"),
        ).grid(row=1, column=0, sticky="w", padx=24)
        Ctk.CTkLabel(
            Sidebar, text="WEIRD STORAGE", text_color=ACCENT,
            font=Ctk.CTkFont(family=FONT, size=10, weight="bold"),
        ).grid(row=2, column=0, sticky="w", padx=25, pady=(0, 28))

        self.SidebarButton(Sidebar, 3, "Vault", self.FocusSearch, Active=True)
        self.SidebarButton(Sidebar, 4, "Audit", self.ShowAudit)
        self.SidebarButton(Sidebar, 5, "Security theater", self.ShowTheater)
        self.SidebarButton(Sidebar, 6, "File anatomy", self.ShowAnatomy)

        WarningCard = Ctk.CTkFrame(Sidebar, fg_color=SURFACE, corner_radius=12)
        WarningCard.grid(row=9, column=0, sticky="ew", padx=16, pady=18)
        Ctk.CTkLabel(
            WarningCard, text="DEMO ONLY", text_color=WARNING,
            font=Ctk.CTkFont(family=FONT, size=10, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(12, 2))
        Ctk.CTkLabel(
            WarningCard, text="Camouflage is not\nencryption.", text_color=MUTED,
            justify="left", font=Ctk.CTkFont(family=FONT, size=11),
        ).pack(anchor="w", padx=14, pady=(0, 12))

    def SidebarButton(self, Parent, Row, TextValue, Command, Active=False):
        Button = Ctk.CTkButton(
            Parent,
            text=TextValue,
            command=Command,
            height=42,
            corner_radius=9,
            anchor="w",
            fg_color=SURFACE_HIGH if Active else "transparent",
            hover_color=SURFACE_HOVER,
            text_color=TEXT if Active else MUTED,
            font=Ctk.CTkFont(family=FONT, size=13, weight="bold" if Active else "normal"),
        )
        Button.grid(row=Row, column=0, sticky="ew", padx=14, pady=3)
        return Button

    def BuildWorkspace(self):
        Workspace = Ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        Workspace.grid(row=0, column=1, sticky="nsew")
        Workspace.grid_columnconfigure(0, weight=1)
        Workspace.grid_rowconfigure(1, weight=1)
        self.BuildToolbar(Workspace)

        Content = Ctk.CTkFrame(Workspace, fg_color="transparent", corner_radius=0)
        Content.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 12))
        Content.grid_columnconfigure(0, weight=5)
        Content.grid_columnconfigure(1, weight=4)
        Content.grid_rowconfigure(0, weight=1)
        self.BuildEntryPane(Content)
        self.BuildDetailPane(Content)
        self.BuildStatus(Workspace)

    def BuildToolbar(self, Parent):
        Toolbar = Ctk.CTkFrame(Parent, fg_color="transparent", corner_radius=0)
        Toolbar.grid(row=0, column=0, sticky="ew", padx=22, pady=(20, 14))
        Toolbar.grid_columnconfigure(0, weight=1)
        PathBox = Ctk.CTkFrame(Toolbar, fg_color="transparent")
        PathBox.grid(row=0, column=0, sticky="w")
        Ctk.CTkLabel(
            PathBox, text="ACTIVE VAULT", text_color=ACCENT,
            font=Ctk.CTkFont(family=FONT, size=10, weight="bold"),
        ).pack(anchor="w")
        Ctk.CTkLabel(
            PathBox, textvariable=self.PathText, text_color=TEXT,
            font=Ctk.CTkFont(family=FONT, size=15, weight="bold"),
        ).pack(anchor="w")
        Ctk.CTkButton(
            Toolbar, text="New vault", command=self.NewVault, width=108, height=38,
            fg_color=SURFACE_HIGH, hover_color=SURFACE_HOVER, text_color=TEXT,
            corner_radius=10, font=Ctk.CTkFont(family=FONT, size=12, weight="bold"),
        ).grid(row=0, column=1, padx=(8, 4))
        Ctk.CTkButton(
            Toolbar, text="Open vault", command=self.OpenVault, width=112, height=38,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#1a0f09",
            corner_radius=10, font=Ctk.CTkFont(family=FONT, size=12, weight="bold"),
        ).grid(row=0, column=2, padx=(4, 0))

    #MARK: entry list stuffs
    def BuildEntryPane(self, Parent):
        Pane = Ctk.CTkFrame(Parent, fg_color=SURFACE, corner_radius=16,
                           border_width=1, border_color=BORDER)
        Pane.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        Pane.grid_columnconfigure(0, weight=1)
        Pane.grid_rowconfigure(5, weight=1)

        Header = Ctk.CTkFrame(Pane, fg_color="transparent")
        Header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 12))
        Header.grid_columnconfigure(0, weight=1)
        Ctk.CTkLabel(
            Header, text="Entries", text_color=TEXT,
            font=Ctk.CTkFont(family=FONT, size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        self.AddButton = Ctk.CTkButton(
            Header, text="+  Add entry", command=self.AddEntry, width=112, height=36,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#1a0f09",
            corner_radius=10, font=Ctk.CTkFont(family=FONT, size=12, weight="bold"),
        )
        self.AddButton.grid(row=0, column=1, sticky="e")

        self.SearchEntry = Ctk.CTkEntry(
            Pane, textvariable=self.SearchText, placeholder_text="Search entries…",
            height=40, corner_radius=10, fg_color=SURFACE_HIGH, border_color=BORDER,
            text_color=TEXT, placeholder_text_color=MUTED,
            font=Ctk.CTkFont(family=FONT, size=12),
        )
        self.SearchEntry.grid(row=1, column=0, sticky="ew", padx=18)
        self.SearchText.trace_add("write", lambda *_: self.RefreshList())

        SortBar = Ctk.CTkFrame(Pane, fg_color="transparent")
        SortBar.grid(row=2, column=0, sticky="ew", padx=18, pady=(10, 4))
        SortBar.grid_columnconfigure(1, weight=1)
        Ctk.CTkLabel(
            SortBar, text="Sort", text_color=MUTED,
            font=Ctk.CTkFont(family=FONT, size=11),
        ).grid(row=0, column=0, padx=(0, 8))
        self.SortMenu = Ctk.CTkOptionMenu(
            SortBar, values=["name", "username", "health", "updated"],
            command=self.ChangeSort, width=120, height=30, corner_radius=8,
            fg_color=SURFACE_HIGH, button_color=SURFACE_HOVER,
            button_hover_color=BORDER, dropdown_fg_color=SURFACE_HIGH,
            dropdown_hover_color=SURFACE_HOVER, text_color=TEXT,
            font=Ctk.CTkFont(family=FONT, size=11),
        )
        self.SortMenu.grid(row=0, column=1, sticky="w")
        self.SortDirectionButton = Ctk.CTkButton(
            SortBar, text="↑", command=self.ToggleSortDirection, width=34, height=30,
            corner_radius=8, fg_color=SURFACE_HIGH, hover_color=SURFACE_HOVER,
            text_color=TEXT, font=Ctk.CTkFont(family=FONT, size=14, weight="bold"),
        )
        self.SortDirectionButton.grid(row=0, column=2, sticky="e")

        Ctk.CTkLabel(
            Pane, textvariable=self.ListSummaryText, text_color=MUTED,
            font=Ctk.CTkFont(family=FONT, size=10),
        ).grid(row=3, column=0, sticky="w", padx=18, pady=(4, 8))

        ColumnHeader = Ctk.CTkFrame(Pane, fg_color="transparent")
        ColumnHeader.grid(row=4, column=0, sticky="ew", padx=18)
        for Column, (Label, Weight) in enumerate((("NAME", 4), ("USER", 3), ("HEALTH", 2))):
            ColumnHeader.grid_columnconfigure(Column, weight=Weight)
            Ctk.CTkLabel(
                ColumnHeader, text=Label, text_color=MUTED, anchor="w",
                font=Ctk.CTkFont(family=FONT, size=9, weight="bold"),
            ).grid(row=0, column=Column, sticky="ew", padx=(10 if Column == 0 else 4, 4))

        self.EntryList = Ctk.CTkScrollableFrame(
            Pane, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=MUTED,
        )
        self.EntryList.grid(row=5, column=0, sticky="nsew", padx=10, pady=(3, 12))
        self.EntryList.grid_columnconfigure(0, weight=1)

    def CreateEntryRow(self, Row, RowNumber):
        Name = Row["name"]
        Selected = Name == self.SelectedName
        Frame = Ctk.CTkFrame(
            self.EntryList,
            height=52,
            fg_color=ACCENT if Selected else SURFACE_HIGH,
            corner_radius=10,
            border_width=1,
            border_color=ACCENT if Selected else BORDER,
            cursor="pointinghand",
        )
        Frame.grid(row=RowNumber, column=0, sticky="ew", padx=2, pady=3)
        Frame.grid_propagate(False)
        Frame.grid_columnconfigure(0, weight=4)
        Frame.grid_columnconfigure(1, weight=3)
        Frame.grid_columnconfigure(2, weight=2)
        Color = "#1a0f09" if Selected else TEXT
        Health = "OK" if Row["health"] == 0 else f"{Row['health']} issues"
        Values = (Name, Row["username"], Health)
        for Column, Value in enumerate(Values):
            Label = Ctk.CTkLabel(
                Frame, text=Value, text_color=Color, anchor="w",
                font=Ctk.CTkFont(family=FONT, size=11,
                                 weight="bold" if Column == 0 or Selected else "normal"),
                cursor="pointinghand",
            )
            Label.grid(row=0, column=Column, sticky="ew", padx=(12 if Column == 0 else 6, 4))
            Label.bind("<Button-1>", lambda _Event, Item=Name: self.SelectEntry(Item))
            Label.bind("<Double-Button-1>", lambda _Event, Item=Name: self.OpenEntry(Item))
        Frame.bind("<Button-1>", lambda _Event, Item=Name: self.SelectEntry(Item))
        Frame.bind("<Double-Button-1>", lambda _Event, Item=Name: self.OpenEntry(Item))
        self.EntryRowsByName[Name] = Frame

    #MARK: detail pane stuffs
    def BuildDetailPane(self, Parent):
        Pane = Ctk.CTkFrame(Parent, fg_color=SURFACE, corner_radius=16,
                           border_width=1, border_color=BORDER)
        Pane.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        Pane.grid_columnconfigure(0, weight=1)
        Pane.grid_rowconfigure(8, weight=1)

        Ctk.CTkLabel(
            Pane, text="Entry details", text_color=TEXT,
            font=Ctk.CTkFont(family=FONT, size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 14))
        self.NameValue = self.DetailRow(Pane, 1, "NAME")
        self.UsernameValue = self.DetailRow(Pane, 2, "USERNAME")
        self.PasswordValue = self.DetailRow(Pane, 3, "PASSWORD")
        self.UpdatedValue = self.DetailRow(Pane, 4, "UPDATED")
        self.HealthValue = self.DetailRow(Pane, 5, "HEALTH")

        Ctk.CTkLabel(
            Pane, text="NOTES", text_color=MUTED,
            font=Ctk.CTkFont(family=FONT, size=9, weight="bold"),
        ).grid(row=6, column=0, sticky="w", padx=20, pady=(12, 5))
        self.NotesText = Ctk.CTkTextbox(
            Pane, height=92, corner_radius=10, fg_color=SURFACE_HIGH,
            border_width=1, border_color=BORDER, text_color=TEXT,
            font=Ctk.CTkFont(family=FONT, size=11), wrap="word",
        )
        self.NotesText.grid(row=7, column=0, sticky="nsew", padx=20)
        self.NotesText.configure(state="disabled")

        Buttons = Ctk.CTkFrame(Pane, fg_color="transparent")
        Buttons.grid(row=9, column=0, sticky="ew", padx=20, pady=(14, 20))
        Buttons.grid_columnconfigure((0, 1, 2), weight=1)
        self.RevealButton = self.ActionButton(Buttons, "Reveal", self.TogglePassword, 0, 0)
        self.CopyButton = self.ActionButton(Buttons, "Copy password", self.CopyPassword, 0, 1)
        self.CopyUsernameButton = self.ActionButton(
            Buttons, "Copy username", self.CopyUsername, 0, 2
        )
        self.EditButton = Ctk.CTkButton(
            Buttons, text="Edit entry", command=self.EditEntry, height=38,
            corner_radius=10, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#1a0f09", font=Ctk.CTkFont(family=FONT, size=11, weight="bold"),
        )
        self.EditButton.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 4), pady=(8, 0))
        self.RemoveButton = Ctk.CTkButton(
            Buttons, text="Remove", command=self.RemoveEntry, height=38,
            corner_radius=10, fg_color="#2a171c", hover_color="#3b2027",
            text_color=RED, font=Ctk.CTkFont(family=FONT, size=11, weight="bold"),
        )
        self.RemoveButton.grid(row=1, column=2, sticky="ew", padx=(4, 0), pady=(8, 0))

    def DetailRow(self, Parent, Row, Key):
        Frame = Ctk.CTkFrame(Parent, fg_color="transparent")
        Frame.grid(row=Row, column=0, sticky="ew", padx=20, pady=3)
        Frame.grid_columnconfigure(1, weight=1)
        Ctk.CTkLabel(
            Frame, text=Key, text_color=MUTED, width=78, anchor="w",
            font=Ctk.CTkFont(family=FONT, size=9, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        Value = Ctk.CTkLabel(
            Frame, text="—", text_color=TEXT, anchor="w",
            font=Ctk.CTkFont(family=FONT, size=11),
        )
        Value.grid(row=0, column=1, sticky="ew")
        return Value

    def ActionButton(self, Parent, TextValue, Command, Row, Column):
        Button = Ctk.CTkButton(
            Parent, text=TextValue, command=Command, height=36, corner_radius=9,
            fg_color=SURFACE_HIGH, hover_color=SURFACE_HOVER, text_color=TEXT,
            font=Ctk.CTkFont(family=FONT, size=10, weight="bold"),
        )
        Button.grid(row=Row, column=Column, sticky="ew", padx=(0 if Column == 0 else 4,
                                                                0 if Column == 2 else 4))
        return Button

    def BuildStatus(self, Parent):
        Bar = Ctk.CTkFrame(Parent, fg_color="transparent", height=24)
        Bar.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 12))
        Bar.grid_columnconfigure(0, weight=1)
        Ctk.CTkLabel(
            Bar, textvariable=self.StatusText, text_color=MUTED,
            font=Ctk.CTkFont(family=FONT, size=10),
        ).grid(row=0, column=0, sticky="w")

    def BindKeys(self):
        for Shortcut in ("<Command-n>", "<Control-n>"):
            self.bind_all(Shortcut, lambda _Event: self.NewVault())
        for Shortcut in ("<Command-o>", "<Control-o>"):
            self.bind_all(Shortcut, lambda _Event: self.OpenVault())
        for Shortcut in ("<Command-Shift-N>", "<Control-Shift-N>"):
            self.bind_all(Shortcut, lambda _Event: self.AddEntry())
        for Shortcut in ("<Command-f>", "<Control-f>"):
            self.bind_all(Shortcut, lambda _Event: self.FocusSearch())
        self.bind_all("<KeyPress>", self.OnSecretKey, add="+")

    def FocusSearch(self):
        self.SearchEntry.focus_set()

    #MARK: opening and saving stuffs
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
        self.CancelRevealTimer()
        self.Vault = Vault
        self.FilePath = FilePath
        self.SelectedName = None
        self.PasswordVisible = False
        self.PathText.set(str(FilePath))
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
        self.CancelRevealTimer()
        self.Vault = Vault
        self.FilePath = Path(FilePath)
        self.PathText.set(str(self.FilePath))
        self.SelectedName = None
        self.PasswordVisible = False
        self.RefreshList()
        Count = len(Vault["entries"])
        self.SetStatus(f"Opened {Count} vault entr{'y' if Count == 1 else 'ies'}")
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

    #MARK: rows and selection stuffs
    def RefreshList(self):
        if not hasattr(self, "EntryList"):
            return
        for Child in self.EntryList.winfo_children():
            Child.destroy()
        self.EntryRowsByName = {}
        if self.Vault is None:
            self.ListSummaryText.set("No vault open")
            self.SelectedName = None
            self.ShowDetails(None)
            self.UpdateControls()
            return

        Query = self.SearchText.get()
        Rows = EntryRows(self.Vault, Query, self.SortColumn, self.SortDescending)
        Names = [Row["name"] for Row in Rows]
        if self.SelectedName not in Names:
            self.SelectedName = Names[0] if Names else None
            self.PasswordVisible = False
        for RowNumber, Row in enumerate(Rows):
            self.CreateEntryRow(Row, RowNumber)

        Summary = VaultSummary(self.Vault, Query)
        self.ListSummaryText.set(
            f"{Summary['shown']} shown  •  {Summary['total']} total  •  "
            f"{Summary['needs_work']} need attention"
        )
        self.ShowDetails(self.SelectedName)
        self.UpdateControls()

    def SelectEntry(self, Name):
        if Name == self.SelectedName:
            return
        self.CancelRevealTimer()
        self.SelectedName = Name
        self.PasswordVisible = False
        self.RefreshList()

    def OpenEntry(self, Name):
        self.SelectEntry(Name)
        self.EditEntry()

    def ChangeSort(self, Column):
        self.SortColumn = Column
        self.RefreshList()

    def ToggleSortDirection(self):
        self.SortDescending = not self.SortDescending
        self.SortDirectionButton.configure(text="↓" if self.SortDescending else "↑")
        self.RefreshList()

    def ShowDetails(self, Name):
        if not Name or self.Vault is None or Name not in self.Vault["entries"]:
            Values = ("—", "—", "—", "—", "—")
            Notes = "Select an entry to inspect its details"
        else:
            Entry = self.Vault["entries"][Name]
            Password = Entry.get("password", "")
            VisiblePassword = Password if self.PasswordVisible else PasswordMask(Password)
            Issues = len(Main.PasswordIssues(Password)) + (0 if Entry.get("username") else 1)
            Health = "Looks okay" if Issues == 0 else f"{Issues} basic issue(s)"
            Values = (Name, Entry.get("username") or "—", VisiblePassword,
                      Entry.get("updated_at") or "unknown", Health)
            Notes = Entry.get("notes") or "No notes"
        for Widget, Value in zip(
            (self.NameValue, self.UsernameValue, self.PasswordValue,
             self.UpdatedValue, self.HealthValue), Values
        ):
            Widget.configure(text=Value)
        self.NotesText.configure(state="normal")
        self.NotesText.delete("1.0", "end")
        self.NotesText.insert("1.0", Notes)
        self.NotesText.configure(state="disabled")
        self.RevealButton.configure(text="Hide" if self.PasswordVisible else "Reveal")

    def UpdateControls(self):
        HasVault = self.Vault is not None
        HasSelection = HasVault and self.SelectedName in self.Vault["entries"]
        self.AddButton.configure(state="normal" if HasVault else "disabled")
        for Button in (self.RevealButton, self.CopyButton, self.CopyUsernameButton,
                       self.EditButton, self.RemoveButton):
            Button.configure(state="normal" if HasSelection else "disabled")

    #MARK: changing entry stuffs
    def AddEntry(self):
        if self.Vault is None:
            MessageBox.showinfo("No vault open", "Create or open a .p00p vault first", parent=self)
            return
        ModernEntryDialog(self, "Add vault entry", self.SaveNewEntry)

    def SaveNewEntry(self, Data):
        Name = Data.pop("name")
        Existing = next(
            (Other for Other in self.Vault["entries"] if Other.casefold() == Name.casefold()), None
        )
        if Existing:
            MessageBox.showerror("Entry already exists", f"{Existing!r} already exists", parent=self)
            return False
        Candidate = Copy.deepcopy(self.Vault)
        Data["updated_at"] = Main.CurrentTime()
        Candidate["entries"][Name] = Data
        if self.SaveCandidate(Candidate, f"Added {Name!r}"):
            self.SelectedName = Name
            self.RefreshList()
            return True
        return False

    def EditEntry(self):
        if not self.SelectedName or self.Vault is None:
            return
        Entry = Copy.deepcopy(self.Vault["entries"][self.SelectedName])
        ModernEntryDialog(self, "Edit vault entry", self.SaveEditedEntry,
                          Name=self.SelectedName, Entry=Entry)

    def SaveEditedEntry(self, Data):
        OldName = self.SelectedName
        NewName = Data.pop("name")
        Conflict = next((Name for Name in self.Vault["entries"]
                         if Name.casefold() == NewName.casefold() and Name != OldName), None)
        if Conflict:
            MessageBox.showerror("Entry already exists", f"{Conflict!r} already exists", parent=self)
            return False
        Candidate = Copy.deepcopy(self.Vault)
        Candidate["entries"].pop(OldName)
        Data["updated_at"] = Main.CurrentTime()
        Candidate["entries"][NewName] = Data
        if self.SaveCandidate(Candidate, f"Updated {NewName!r}"):
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
        if not MessageBox.askyesno(
            "Remove this entry?", f"Remove {Name!r} from the vault?\n\nThis cannot be undone.",
            parent=self, icon="warning",
        ):
            return
        self.CancelRevealTimer()
        Candidate = Copy.deepcopy(self.Vault)
        del Candidate["entries"][Name]
        self.SelectedName = None
        self.SaveCandidate(Candidate, f"Removed {Name!r}")

    #MARK: password actions
    def TogglePassword(self):
        if not self.SelectedName:
            return
        self.CancelRevealTimer()
        self.PasswordVisible = not self.PasswordVisible
        self.ShowDetails(self.SelectedName)
        if self.PasswordVisible:
            self.RevealAfterId = self.after(20_000, self.HidePassword)
            self.SetStatus("Password revealed for 20 seconds")

    def HidePassword(self):
        self.RevealAfterId = None
        if self.PasswordVisible:
            self.PasswordVisible = False
            self.ShowDetails(self.SelectedName)
            self.SetStatus("Password hidden again")

    def CancelRevealTimer(self):
        if self.RevealAfterId is not None:
            self.after_cancel(self.RevealAfterId)
            self.RevealAfterId = None

    def CopyPassword(self):
        if self.SelectedName and self.Vault is not None:
            self.CopyToClipboard(
                self.Vault["entries"][self.SelectedName].get("password", ""), "Password"
            )

    def CopyUsername(self):
        if not self.SelectedName or self.Vault is None:
            return
        Username = self.Vault["entries"][self.SelectedName].get("username", "")
        if not Username:
            self.SetStatus("This entry does not have a username")
            return
        self.CopyToClipboard(Username, "Username")

    def CopyToClipboard(self, Value, Label):
        self.clipboard_clear()
        self.clipboard_append(Value)
        self.update_idletasks()
        self.SetStatus(f"{Label} copied — clipboard clears in 20 seconds")
        self.after(20_000, lambda: self.ClearClipboardIfSame(Value))

    def ClearClipboardIfSame(self, Value):
        try:
            if self.clipboard_get() == Value:
                self.clipboard_clear()
                self.SetStatus("Clipboard cleared")
        except Tk.TclError:
            pass

    #MARK: reports and secrets
    def ShowAudit(self):
        if self.Vault is None:
            MessageBox.showinfo("No vault open", "Open a vault before auditing it", parent=self)
            return
        Findings = AuditVault(self.Vault, self.FilePath)
        if Findings:
            Lines = [f"{len(Findings)} thing(s) need attention:\n"]
            Lines.extend(f"• {Name}: {Finding}" for Name, Finding in Findings)
        else:
            Lines = ["No basic hygiene problems found."]
        Lines.extend(("", "This only checks basic patterns.",
                      "The p00p format is still not real encryption."))
        ModernTextWindow(self, "Vault audit", "\n".join(Lines))

    def ShowTheater(self):
        if self.FilePath is None:
            MessageBox.showinfo("No vault open", "Open a vault before scoring it", parent=self)
            return
        try:
            Report = Main.SecurityTheaterReport(self.FilePath).AsText()
        except Main.P00PError as Exc:
            self.ShowError("The applause meter broke", Exc)
            return
        ModernTextWindow(self, "Security theater", Report, Monospace=True)

    def ShowAnatomy(self):
        if self.FilePath is None:
            MessageBox.showinfo("No vault open", "Open a vault before inspecting it", parent=self)
            return
        try:
            Report = FormatAnatomy(self.FilePath)
        except Main.P00PError as Exc:
            self.ShowError("Could not inspect the vault", Exc)
            return
        ModernTextWindow(self, "File anatomy", Report, Monospace=True)

    def ShowAbout(self):
        MessageBox.showwarning(
            "Security reality check",
            "p00p is a Weird Storage demo, not a real password manager.\n\n"
            "Hidden files, strange extensions, and reversible camouflage do not stop hackers. "
            "Only store fake credentials here.",
            parent=self,
        )

    def OnSecretKey(self, Event):
        if self.SecretSequence.Feed(Event.keysym):
            ModernSecretWindow(
                self, "Sewer mode unlocked", "🚽",
                "The ancient directional ritual worked.\n\n"
                "You now have administrator access to absolutely nothing.",
            )
            self.SetStatus("Secret sewer mode unlocked")

    def OnMascotClick(self, _Event=None):
        self.MascotClicks += 1
        if self.MascotClicks < 5:
            return
        self.MascotClicks = 0
        ModernSecretWindow(
            self, "Golden poop discovered", "🏆",
            "You clicked the mascot five times. This achievement has no value, "
            "cannot be exported, and adds zero security.",
        )
        self.SetStatus("Easter egg found: golden poop")

    def ShowError(self, Title, Error):
        MessageBox.showerror(Title, str(Error), parent=self)

    def SetStatus(self, Message):
        self.StatusText.set(Message)


class ModernEntryDialog(Ctk.CTkToplevel):
    def __init__(self, Parent, Title, OnSave, Name="", Entry=None):
        super().__init__(Parent, fg_color=BG)
        self.Parent = Parent
        self.OnSave = OnSave
        self.Entry = Entry or {}
        self.title(Title)
        self.geometry("560x650")
        self.minsize(520, 600)
        self.transient(Parent)
        self.grab_set()

        self.NameText = Tk.StringVar(value=Name)
        self.UsernameText = Tk.StringVar(value=self.Entry.get("username", ""))
        self.PasswordText = Tk.StringVar(value=self.Entry.get("password", ""))
        self.PasswordLength = Tk.StringVar(value=str(Main.DEFAULT_PASSWORD_LENGTH))
        self.ShowPassword = Tk.BooleanVar(value=False)
        self.UseSymbols = Tk.BooleanVar(value=True)
        self.HealthText = Tk.StringVar(value="No fake password yet")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        Card = Ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=16,
                           border_width=1, border_color=BORDER)
        Card.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        Card.grid_columnconfigure(0, weight=1)
        Card.grid_rowconfigure(9, weight=1)

        Ctk.CTkLabel(
            Card, text=Title, text_color=TEXT,
            font=Ctk.CTkFont(family=FONT, size=22, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(22, 16))
        self.NameEntry = self.Field(Card, 1, "Name", self.NameText)
        self.Field(Card, 3, "Username", self.UsernameText)

        Ctk.CTkLabel(Card, text="PASSWORD", text_color=MUTED,
                     font=Ctk.CTkFont(family=FONT, size=9, weight="bold")).grid(
            row=5, column=0, sticky="w", padx=24)
        PasswordRow = Ctk.CTkFrame(Card, fg_color="transparent")
        PasswordRow.grid(row=6, column=0, sticky="ew", padx=24, pady=(5, 8))
        PasswordRow.grid_columnconfigure(0, weight=1)
        self.PasswordEntry = Ctk.CTkEntry(
            PasswordRow, textvariable=self.PasswordText, show="•", height=40,
            corner_radius=10, fg_color=SURFACE_HIGH, border_color=BORDER, text_color=TEXT,
        )
        self.PasswordEntry.grid(row=0, column=0, sticky="ew")
        Ctk.CTkButton(
            PasswordRow, text="Generate", command=self.Generate, width=92, height=40,
            corner_radius=10, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#1a0f09", font=Ctk.CTkFont(family=FONT, size=11, weight="bold"),
        ).grid(row=0, column=1, padx=(8, 0))

        Options = Ctk.CTkFrame(Card, fg_color="transparent")
        Options.grid(row=7, column=0, sticky="ew", padx=24)
        self.ShowSwitch = Ctk.CTkSwitch(
            Options, text="Show", variable=self.ShowPassword,
            command=self.UpdatePasswordVisibility, progress_color=ACCENT,
            button_color=TEXT, text_color=MUTED,
        )
        self.ShowSwitch.pack(side="left")
        Ctk.CTkLabel(Options, text="Length", text_color=MUTED).pack(side="left", padx=(18, 6))
        Ctk.CTkEntry(
            Options, textvariable=self.PasswordLength, width=54, height=30,
            corner_radius=8, fg_color=SURFACE_HIGH, border_color=BORDER,
        ).pack(side="left")
        Ctk.CTkSwitch(
            Options, text="Symbols", variable=self.UseSymbols,
            progress_color=ACCENT, button_color=TEXT, text_color=MUTED,
        ).pack(side="left", padx=(16, 0))

        self.HealthLabel = Ctk.CTkLabel(
            Card, textvariable=self.HealthText, anchor="w", justify="left",
            wraplength=450, corner_radius=9, fg_color="#2b211b", text_color=WARNING,
            font=Ctk.CTkFont(family=FONT, size=10, weight="bold"),
        )
        self.HealthLabel.grid(row=8, column=0, sticky="ew", padx=24, pady=(12, 10), ipady=7)

        NotesFrame = Ctk.CTkFrame(Card, fg_color="transparent")
        NotesFrame.grid(row=9, column=0, sticky="nsew", padx=24)
        NotesFrame.grid_columnconfigure(0, weight=1)
        NotesFrame.grid_rowconfigure(1, weight=1)
        Ctk.CTkLabel(NotesFrame, text="NOTES", text_color=MUTED,
                     font=Ctk.CTkFont(family=FONT, size=9, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 5))
        self.Notes = Ctk.CTkTextbox(
            NotesFrame, height=100, corner_radius=10, fg_color=SURFACE_HIGH,
            border_width=1, border_color=BORDER, text_color=TEXT,
        )
        self.Notes.grid(row=1, column=0, sticky="nsew")
        self.Notes.insert("1.0", self.Entry.get("notes", ""))

        Buttons = Ctk.CTkFrame(Card, fg_color="transparent")
        Buttons.grid(row=10, column=0, sticky="ew", padx=24, pady=(18, 24))
        Buttons.grid_columnconfigure((0, 1), weight=1)
        Ctk.CTkButton(
            Buttons, text="Cancel", command=self.destroy, height=40, corner_radius=10,
            fg_color=SURFACE_HIGH, hover_color=SURFACE_HOVER, text_color=TEXT,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        Ctk.CTkButton(
            Buttons, text="Save entry", command=self.Save, height=40, corner_radius=10,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#1a0f09",
            font=Ctk.CTkFont(family=FONT, size=11, weight="bold"),
        ).grid(row=0, column=1, sticky="ew", padx=(5, 0))

        self.PasswordText.trace_add("write", lambda *_: self.UpdatePasswordHealth())
        self.UpdatePasswordHealth()
        self.bind("<Escape>", lambda _Event: self.destroy())
        self.bind("<Command-Return>", lambda _Event: self.Save())
        self.bind("<Control-Return>", lambda _Event: self.Save())
        self.after_idle(self.NameEntry.focus_set)

    def Field(self, Parent, Row, Label, Variable):
        Frame = Ctk.CTkFrame(Parent, fg_color="transparent")
        Frame.grid(row=Row, column=0, sticky="ew", padx=24, pady=(0, 10))
        Frame.grid_columnconfigure(0, weight=1)
        Ctk.CTkLabel(Frame, text=Label.upper(), text_color=MUTED,
                     font=Ctk.CTkFont(family=FONT, size=9, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 5))
        Entry = Ctk.CTkEntry(
            Frame, textvariable=Variable, height=40, corner_radius=10,
            fg_color=SURFACE_HIGH, border_color=BORDER, text_color=TEXT,
        )
        Entry.grid(row=1, column=0, sticky="ew")
        return Entry

    def Generate(self):
        try:
            Length = GeneratorLength(self.PasswordLength.get())
            Password = Main.GeneratePassword(Length, Symbols=self.UseSymbols.get())
        except Main.P00PError as Exc:
            MessageBox.showerror("Generator error", str(Exc), parent=self)
            return
        self.PasswordText.set(Password)
        self.ShowPassword.set(True)
        self.UpdatePasswordVisibility()

    def UpdatePasswordVisibility(self):
        self.PasswordEntry.configure(show="" if self.ShowPassword.get() else "•")

    def UpdatePasswordHealth(self):
        Summary = PasswordHealthSummary(self.PasswordText.get())
        self.HealthText.set(Summary["text"])
        if Summary["healthy"]:
            self.HealthLabel.configure(fg_color="#17251c", text_color=GREEN)
        else:
            self.HealthLabel.configure(fg_color="#2b211b", text_color=WARNING)

    def Save(self):
        Name = self.NameText.get().strip()
        Password = self.PasswordText.get()
        if not Name:
            MessageBox.showerror("Missing name", "Give this entry a name", parent=self)
            self.NameEntry.focus_set()
            return
        if not Password:
            MessageBox.showerror("Missing password", "The password cannot be empty", parent=self)
            self.PasswordEntry.focus_set()
            return
        Summary = PasswordHealthSummary(Password)
        if Summary["issues"] and not MessageBox.askyesno(
            "Save a weak fake password?",
            f"The basic checker found {len(Summary['issues'])} issue(s):\n\n"
            + "\n".join(f"• {Issue}" for Issue in Summary["issues"])
            + "\n\nSave it anyway?",
            parent=self, icon="warning",
        ):
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


class ModernTextWindow(Ctk.CTkToplevel):
    def __init__(self, Parent, Title, Content, Monospace=False):
        super().__init__(Parent, fg_color=BG)
        self.title(Title)
        self.geometry("640x480")
        self.minsize(520, 360)
        self.transient(Parent)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        Card = Ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=16,
                           border_width=1, border_color=BORDER)
        Card.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        Card.grid_columnconfigure(0, weight=1)
        Card.grid_rowconfigure(1, weight=1)
        Ctk.CTkLabel(
            Card, text=Title, text_color=TEXT,
            font=Ctk.CTkFont(family=FONT, size=22, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(22, 14))
        FontName = MONO_FONT if Monospace else FONT
        TextBox = Ctk.CTkTextbox(
            Card, corner_radius=10, fg_color=SURFACE_HIGH, border_width=1,
            border_color=BORDER, text_color=TEXT,
            font=Ctk.CTkFont(family=FontName, size=12), wrap="word",
        )
        TextBox.grid(row=1, column=0, sticky="nsew", padx=24)
        TextBox.insert("1.0", Content)
        TextBox.configure(state="disabled")
        Ctk.CTkButton(
            Card, text="Done", command=self.destroy, width=100, height=38,
            corner_radius=10, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#1a0f09",
        ).grid(row=2, column=0, sticky="e", padx=24, pady=22)
        self.bind("<Escape>", lambda _Event: self.destroy())


class ModernSecretWindow(Ctk.CTkToplevel):
    def __init__(self, Parent, Title, Emoji, Message):
        super().__init__(Parent, fg_color=BG)
        self.Parent = Parent
        self.title(Title)
        self.geometry("480x330")
        self.resizable(False, False)
        self.transient(Parent)
        Card = Ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=18,
                           border_width=1, border_color=ACCENT)
        Card.pack(fill="both", expand=True, padx=16, pady=16)
        Ctk.CTkLabel(
            Card, text=Emoji, font=Ctk.CTkFont(family="Apple Color Emoji", size=50),
        ).pack(pady=(24, 8))
        Ctk.CTkLabel(
            Card, text=Title, text_color=TEXT,
            font=Ctk.CTkFont(family=FONT, size=20, weight="bold"),
        ).pack()
        Ctk.CTkLabel(
            Card, text=Message, text_color=MUTED, justify="center", wraplength=390,
            font=Ctk.CTkFont(family=FONT, size=12),
        ).pack(padx=28, pady=(12, 20))
        Ctk.CTkButton(
            Card, text="Return to vault", command=self.destroy, width=150, height=38,
            corner_radius=10, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#1a0f09",
        ).pack()
        self.bind("<Escape>", lambda _Event: self.destroy())


def RunModernGui(StartPath=None):
    App = ModernP00PWindow(StartPath=StartPath)
    App.mainloop()


if __name__ == "__main__":
    RunModernGui()
