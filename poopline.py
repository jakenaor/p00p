#------------------------------------------------------------------#
# the needlessly ceremonial p00p payload pipeline                  #
# three simple operations wearing a very large trench coat         #
#------------------------------------------------------------------#

import hashlib as Hashlib
import json as Json
import zlib as Zlib


class PooplineError(Exception):
    def __init__(self, StageName, OriginalError):
        self.StageName = StageName
        self.OriginalError = OriginalError
        super().__init__(f"the {StageName} ritual failed")


#MARK: the parcel everybody keeps passing around
class PoopParcel:
    def __init__(self, Cargo, Receipts=()):
        self.Cargo = Cargo
        self.Receipts = tuple(Receipts)

    def HandToNextGoblin(self, StageName, NewCargo):
        Receipt = {
            "stage": StageName,
            "before_type": type(self.Cargo).__name__,
            "before_size": MeasureCargo(self.Cargo),
            "after_type": type(NewCargo).__name__,
            "after_size": MeasureCargo(NewCargo),
        }
        return PoopParcel(NewCargo, self.Receipts + (Receipt,))


def MeasureCargo(Cargo):
    if isinstance(Cargo, bytes):
        return len(Cargo)
    if isinstance(Cargo, str):
        return len(Cargo.encode("utf-8"))
    if isinstance(Cargo, dict):
        Packed = Json.dumps(Cargo, separators=(",", ":"), sort_keys=True)
        return len(Packed.encode("utf-8"))
    try:
        return len(Cargo)
    except TypeError:
        return len(str(Cargo).encode("utf-8"))


#MARK: context that absolutely could have been two arguments
class RitualContext:
    def __init__(self, Salt, CamouflageKey):
        self.Salt = Salt
        self.CamouflageKey = CamouflageKey

    def StreamFor(self, Length):
        Shaker = Hashlib.shake_256(self.CamouflageKey + self.Salt)
        return Shaker.digest(Length)


#MARK: reversible goblins
class JsonGoblin:
    Name = "json goblin"

    def IntoBowl(self, Cargo, _Context):
        Packed = Json.dumps(Cargo, separators=(",", ":"), sort_keys=True)
        return Packed.encode("utf-8")

    def OutOfBowl(self, Cargo, _Context):
        return Json.loads(Cargo.decode("utf-8"))


class TrashCompactor:
    Name = "trash compactor"

    def IntoBowl(self, Cargo, _Context):
        return Zlib.compress(Cargo, level=9)

    def OutOfBowl(self, Cargo, _Context):
        return Zlib.decompress(Cargo)


class ToiletCurtain:
    Name = "toilet curtain"

    def IntoBowl(self, Cargo, Context):
        return XorWithCeremonialStream(Cargo, Context)

    def OutOfBowl(self, Cargo, Context):
        # xor is its own undo button, which feels suspiciously convenient.
        return XorWithCeremonialStream(Cargo, Context)


def XorWithCeremonialStream(Data, Context):
    Stream = Context.StreamFor(len(Data))
    return bytes(Left ^ Right for Left, Right in zip(Data, Stream))


#MARK: the ritual book (this is where two loops became architecture)
class RitualBook:
    Directions = {
        "into bowl": {
            "method": "IntoBowl",
            "reverse_stages": False,
        },
        "out of bowl": {
            "method": "OutOfBowl",
            "reverse_stages": True,
        },
    }

    def __init__(self, Stages=None):
        self.Stages = tuple(Stages or (JsonGoblin(), TrashCompactor(), ToiletCurtain()))

    def Perform(self, Cargo, Direction, Salt, CamouflageKey):
        if Direction not in self.Directions:
            raise ValueError(f"unknown poopline direction: {Direction}")

        Instructions = self.Directions[Direction]
        Stages = self.Stages
        if Instructions["reverse_stages"]:
            Stages = tuple(reversed(Stages))

        Context = RitualContext(Salt, CamouflageKey)
        Parcel = PoopParcel(Cargo)
        for Stage in Stages:
            Method = getattr(Stage, Instructions["method"])
            try:
                NewCargo = Method(Parcel.Cargo, Context)
            except (Json.JSONDecodeError, UnicodeDecodeError, Zlib.error, TypeError) as Exc:
                raise PooplineError(Stage.Name, Exc) from Exc
            Parcel = Parcel.HandToNextGoblin(Stage.Name, NewCargo)
        return Parcel


DEFAULT_RITUAL_BOOK = RitualBook()


#MARK: tiny public door hiding the giant hallway
def EncodePayload(Vault, Salt, CamouflageKey):
    return DEFAULT_RITUAL_BOOK.Perform(
        Vault, "into bowl", Salt, CamouflageKey
    ).Cargo


def DecodePayload(Payload, Salt, CamouflageKey):
    return DEFAULT_RITUAL_BOOK.Perform(
        Payload, "out of bowl", Salt, CamouflageKey
    ).Cargo


def InspectPayloadRitual(Vault, Salt, CamouflageKey):
    return DEFAULT_RITUAL_BOOK.Perform(
        Vault, "into bowl", Salt, CamouflageKey
    ).Receipts


def CamouflageBytes(Data, Salt, CamouflageKey):
    Context = RitualContext(Salt, CamouflageKey)
    return XorWithCeremonialStream(Data, Context)
