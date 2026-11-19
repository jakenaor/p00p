#------------------------------------------------------------------#
# p00p bowl merger                                                 #
# pours two bowls into a third one without silently eating entries #
#------------------------------------------------------------------#

import copy as Copy
import json as Json
from pathlib import Path


POLICY_ERROR = "error"
POLICY_KEEP_LEFT = "keep-left"
POLICY_KEEP_RIGHT = "keep-right"
POLICY_RENAME_RIGHT = "rename-right"
POLICIES = (
    POLICY_ERROR,
    POLICY_KEEP_LEFT,
    POLICY_KEEP_RIGHT,
    POLICY_RENAME_RIGHT,
)


class MergeError(Exception):
    pass


def CredentialContent(Entry):
    return {
        "username": Entry.get("username", ""),
        "password": Entry.get("password", ""),
        "notes": Entry.get("notes", ""),
    }


def SameCredential(LeftEntry, RightEntry):
    return CredentialContent(LeftEntry) == CredentialContent(RightEntry)


class MergeReceipt:
    def __init__(
        self,
        LeftPath,
        RightPath,
        OutputPath,
        Policy,
        LeftEntries,
        RightEntries,
        Added,
        Identical,
        Conflicts,
        KeptLeft,
        KeptRight,
        RenamedRight,
        FinalEntries,
    ):
        self.LeftPath = Path(LeftPath)
        self.RightPath = Path(RightPath)
        self.OutputPath = Path(OutputPath)
        self.Policy = str(Policy)
        self.LeftEntries = int(LeftEntries)
        self.RightEntries = int(RightEntries)
        self.Added = int(Added)
        self.Identical = int(Identical)
        self.Conflicts = int(Conflicts)
        self.KeptLeft = int(KeptLeft)
        self.KeptRight = int(KeptRight)
        self.RenamedRight = int(RenamedRight)
        self.FinalEntries = int(FinalEntries)

    def AsDictionary(self):
        return {
            "protocol": "p00p-merge-receipt",
            "left": str(self.LeftPath),
            "right": str(self.RightPath),
            "output": str(self.OutputPath),
            "policy": self.Policy,
            "counts": {
                "left_entries": self.LeftEntries,
                "right_entries": self.RightEntries,
                "added_from_right": self.Added,
                "identical_duplicates": self.Identical,
                "conflicts": self.Conflicts,
                "kept_left": self.KeptLeft,
                "kept_right": self.KeptRight,
                "renamed_right": self.RenamedRight,
                "final_entries": self.FinalEntries,
            },
            "security_notice": "receipt contains counts, not credential values",
        }

    def AsJson(self):
        return Json.dumps(self.AsDictionary(), indent=2, sort_keys=True)

    def AsText(self):
        return "\n".join((
            "P00P BOWL MERGE COMPLETE",
            f"left:          {self.LeftPath} ({self.LeftEntries} entries)",
            f"right:         {self.RightPath} ({self.RightEntries} entries)",
            f"output:        {self.OutputPath}",
            f"policy:        {self.Policy}",
            f"added:         {self.Added}",
            f"identical:     {self.Identical}",
            f"conflicts:     {self.Conflicts}",
            f"kept left:     {self.KeptLeft}",
            f"kept right:    {self.KeptRight}",
            f"renamed right: {self.RenamedRight}",
            f"final entries: {self.FinalEntries}",
            "receipt safety: counts only; no credential values",
        ))


#MARK: actual pouring machinery
class MergePlan:
    def __init__(self, LeftVault, RightVault, Policy, TimestampFactory):
        if Policy not in POLICIES:
            raise MergeError(f"unknown merge policy: {Policy}")
        for Side, Vault in (("left", LeftVault), ("right", RightVault)):
            if not isinstance(Vault, dict) or not isinstance(Vault.get("entries"), dict):
                raise MergeError(f"{Side} bowl is malformed")
        self.LeftVault = LeftVault
        self.RightVault = RightVault
        self.Policy = Policy
        self.TimestampFactory = TimestampFactory
        Now = TimestampFactory()
        self.MergedVault = {
            "protocol": "p00p",
            "created_at": Now,
            "updated_at": Now,
            "entries": Copy.deepcopy(LeftVault["entries"]),
        }
        self.Added = 0
        self.Identical = 0
        self.Conflicts = 0
        self.KeptLeft = 0
        self.KeptRight = 0
        self.RenamedRight = 0

    def _case_index(self):
        return {
            Name.casefold(): Name
            for Name in self.MergedVault["entries"]
        }

    def _unique_right_name(self, Name, CaseIndex):
        Candidate = f"{Name} (RIGHT COPY)"
        Number = 2
        while Candidate.casefold() in CaseIndex:
            Candidate = f"{Name} (RIGHT COPY {Number})"
            Number += 1
        return Candidate

    def Run(self):
        Entries = self.MergedVault["entries"]
        CaseIndex = self._case_index()
        for RightName in sorted(self.RightVault["entries"], key=str.casefold):
            RightEntry = self.RightVault["entries"][RightName]
            LeftName = CaseIndex.get(RightName.casefold())
            if LeftName is None:
                Entries[RightName] = Copy.deepcopy(RightEntry)
                CaseIndex[RightName.casefold()] = RightName
                self.Added += 1
                continue
            if SameCredential(Entries[LeftName], RightEntry):
                self.Identical += 1
                continue

            self.Conflicts += 1
            if self.Policy == POLICY_ERROR:
                continue
            if self.Policy == POLICY_KEEP_LEFT:
                self.KeptLeft += 1
                continue
            if self.Policy == POLICY_KEEP_RIGHT:
                del Entries[LeftName]
                Entries[RightName] = Copy.deepcopy(RightEntry)
                CaseIndex[RightName.casefold()] = RightName
                self.KeptRight += 1
                continue

            NewName = self._unique_right_name(RightName, CaseIndex)
            Entries[NewName] = Copy.deepcopy(RightEntry)
            CaseIndex[NewName.casefold()] = NewName
            self.RenamedRight += 1

        if self.Policy == POLICY_ERROR and self.Conflicts:
            raise MergeError(
                f"found {self.Conflicts} conflicting entry name(s); choose "
                "--conflict keep-left, keep-right, or rename-right"
            )
        return self.MergedVault

    def Receipt(self, LeftPath, RightPath, OutputPath):
        return MergeReceipt(
            LeftPath=LeftPath,
            RightPath=RightPath,
            OutputPath=OutputPath,
            Policy=self.Policy,
            LeftEntries=len(self.LeftVault["entries"]),
            RightEntries=len(self.RightVault["entries"]),
            Added=self.Added,
            Identical=self.Identical,
            Conflicts=self.Conflicts,
            KeptLeft=self.KeptLeft,
            KeptRight=self.KeptRight,
            RenamedRight=self.RenamedRight,
            FinalEntries=len(self.MergedVault["entries"]),
        )


def MergeVaults(LeftVault, RightVault, Policy, TimestampFactory):
    Plan = MergePlan(LeftVault, RightVault, Policy, TimestampFactory)
    return Plan, Plan.Run()
