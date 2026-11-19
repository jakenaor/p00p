#------------------------------------------------------------------#
# p00p decoy credential foundry                                   #
# manufactures obviously fake demo bowls at irresponsible speed    #
#------------------------------------------------------------------#

import hashlib as Hashlib
import json as Json
import random as Random
from pathlib import Path


MIN_DECOY_COUNT = 1
MAX_DECOY_COUNT = 500

ADJECTIVES = (
    "lunar", "suspicious", "wobbly", "forbidden", "plastic", "orbital",
    "discount", "haunted", "turbo", "ceremonial", "radioactive", "invisible",
    "premium", "intergalactic", "crunchy", "recursive", "quantum", "rubber",
)

NOUNS = (
    "bank", "toilet", "moonbase", "payroll", "sewer", "spaceship", "goblin",
    "snack", "satellite", "bureau", "warehouse", "laboratory", "pigeon",
    "turnip", "mainframe", "laundromat", "museum", "volcano",
)

DEPARTMENTS = (
    "night shift", "snack accounting", "orbital maintenance", "sewer research",
    "fake finance", "goblin relations", "moon weather", "toilet logistics",
    "totally normal operations", "password camouflage", "vibe compliance",
)

PASSWORD_WORDS = (
    "MoonCheese", "FakeMoney", "GoblinSocks", "SpaceToilet", "RubberFirewall",
    "LaserTurnip", "HauntedModem", "QuantumPoop", "SnackProtocol", "SewerRocket",
)


class DecoyError(Exception):
    pass


def SeedInteger(Seed):
    Digest = Hashlib.sha256(str(Seed).encode("utf-8")).digest()
    return int.from_bytes(Digest, "big")


class DecoyRecipe:
    def __init__(self, Count=12, Seed=None):
        try:
            Count = int(Count)
        except (TypeError, ValueError) as Exc:
            raise DecoyError("decoy count must be a whole number") from Exc
        if not MIN_DECOY_COUNT <= Count <= MAX_DECOY_COUNT:
            raise DecoyError(
                f"decoy count must be between {MIN_DECOY_COUNT} and {MAX_DECOY_COUNT}"
            )
        self.Count = Count
        self.Seed = None if Seed is None else str(Seed)

    @property
    def Deterministic(self):
        return self.Seed is not None


class DecoyReceipt:
    def __init__(self, FilePath, Count, Deterministic):
        self.FilePath = Path(FilePath)
        self.Count = int(Count)
        self.Deterministic = bool(Deterministic)

    def AsDictionary(self):
        return {
            "protocol": "p00p-decoy-foundry",
            "file": str(self.FilePath),
            "entries": self.Count,
            "deterministic": self.Deterministic,
            "contains_real_credentials": False,
            "security_notice": "demo data only; the vault format is not encryption",
        }

    def AsJson(self):
        return Json.dumps(self.AsDictionary(), indent=2, sort_keys=True)

    def AsText(self):
        Mode = "REPEATABLE SEED" if self.Deterministic else "FRESH NONDETERMINISTIC BATCH"
        return "\n".join((
            "P00P DECOY FOUNDRY COMPLETE",
            f"bowl:       {self.FilePath}",
            f"entries:    {self.Count}",
            f"mode:       {Mode}",
            "credentials: EXTREMELY FAKE",
            "warning: decoys make demos safer, not the file format",
        ))


#MARK: assembly line with too many moving parts
class DecoyFactory:
    def __init__(self, Recipe, TimestampFactory, Entropy=None):
        if not isinstance(Recipe, DecoyRecipe):
            raise TypeError("DecoyFactory needs a DecoyRecipe")
        self.Recipe = Recipe
        self.TimestampFactory = TimestampFactory
        if Entropy is not None:
            self.Random = Entropy
        elif Recipe.Deterministic:
            self.Random = Random.Random(SeedInteger(Recipe.Seed))
        else:
            self.Random = Random.SystemRandom()
        self.UsedNames = set()

    def _choose(self, Options):
        return Options[self.Random.randrange(len(Options))]

    def _identifier(self, Length=8):
        Alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
        return "".join(self._choose(Alphabet) for _ in range(Length))

    def _unique_name(self, Index):
        Base = f"{self._choose(ADJECTIVES).title()} {self._choose(NOUNS).title()}"
        Candidate = f"{Base} // DEMO"
        Suffix = 2
        while Candidate.casefold() in self.UsedNames:
            Candidate = f"{Base} #{Suffix} // DEMO"
            Suffix += 1
        self.UsedNames.add(Candidate.casefold())
        return Candidate

    def _username(self, Index):
        Adjective = self._choose(ADJECTIVES)
        Noun = self._choose(NOUNS)
        return f"fake-{Adjective}-{Noun}-{Index + 1}@demo.invalid"

    def _password(self, Index):
        # the FAKE prefix is a safety label, not a cryptographic ingredient.
        Word = self._choose(PASSWORD_WORDS)
        Number = self.Random.randrange(1000, 9999)
        return f"FAKE-{Word}-{Number}!{self._identifier(10)}"

    def _notes(self):
        return (
            f"DEMO ONLY // {self._choose(DEPARTMENTS).upper()} // "
            "DOES NOT UNLOCK A REAL ACCOUNT"
        )

    def MakeEntry(self, Index):
        return self._unique_name(Index), {
            "username": self._username(Index),
            "password": self._password(Index),
            "notes": self._notes(),
            "updated_at": self.TimestampFactory(),
        }

    def FillVault(self, Vault):
        if not isinstance(Vault, dict) or not isinstance(Vault.get("entries"), dict):
            raise DecoyError("decoy foundry received a malformed vault")
        if Vault["entries"]:
            raise DecoyError("decoy foundry only fills a brand-new empty vault")
        for Index in range(self.Recipe.Count):
            Name, Entry = self.MakeEntry(Index)
            Vault["entries"][Name] = Entry
        return Vault


def PopulateVault(Vault, Count, TimestampFactory, Seed=None):
    Recipe = DecoyRecipe(Count=Count, Seed=Seed)
    return DecoyFactory(Recipe, TimestampFactory).FillVault(Vault)
