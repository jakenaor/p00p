#------------------------------------------------------------------#
# p00p session undo paperwork                                     #
# keeps old bowls in memory so ctrl-z can unclog recent mistakes   #
#------------------------------------------------------------------#

import copy as Copy


DEFAULT_HISTORY_LIMIT = 50


class HistoryFrame:
    def __init__(self, Label, Vault, SelectedName=""):
        self.Label = str(Label).strip() or "MYSTERIOUS CHANGE"
        # copies are important here. otherwise the "past" keeps changing with the present.
        self.Vault = Copy.deepcopy(Vault)
        self.SelectedName = str(SelectedName or "")


class HistoryMove:
    def __init__(self, Direction, Target, Current):
        if Direction not in {"undo", "redo"}:
            raise ValueError("history direction must be undo or redo")
        self.Direction = Direction
        self.Target = Target
        self.Current = Current
        self.Committed = False


class HistoryBook:
    def __init__(self, Limit=DEFAULT_HISTORY_LIMIT):
        self.Limit = max(1, int(Limit))
        self.Past = []
        self.Future = []

    @property
    def CanUndo(self):
        return bool(self.Past)

    @property
    def CanRedo(self):
        return bool(self.Future)

    @property
    def UndoLabel(self):
        return f"UNDO {self.Past[-1].Label}" if self.Past else "UNDO"

    @property
    def RedoLabel(self):
        return f"REDO {self.Future[-1].Label}" if self.Future else "REDO"

    def Clear(self):
        self.Past.clear()
        self.Future.clear()

    def Remember(self, Label, VaultBeforeChange, SelectedName=""):
        self.Past.append(HistoryFrame(Label, VaultBeforeChange, SelectedName))
        if len(self.Past) > self.Limit:
            del self.Past[:len(self.Past) - self.Limit]
        # making a new edit after undo forks the timeline. the abandoned future goes away.
        self.Future.clear()

    def PlanUndo(self, CurrentVault, SelectedName=""):
        if not self.Past:
            return None
        Target = self.Past[-1]
        Current = HistoryFrame(Target.Label, CurrentVault, SelectedName)
        return HistoryMove("undo", Target, Current)

    def PlanRedo(self, CurrentVault, SelectedName=""):
        if not self.Future:
            return None
        Target = self.Future[-1]
        Current = HistoryFrame(Target.Label, CurrentVault, SelectedName)
        return HistoryMove("redo", Target, Current)

    def Commit(self, Move):
        if not isinstance(Move, HistoryMove):
            raise TypeError("HistoryBook.Commit needs a HistoryMove")
        if Move.Committed:
            raise ValueError("that history move was already committed")
        if Move.Direction == "undo":
            if not self.Past or self.Past[-1] is not Move.Target:
                raise ValueError("undo plan is stale")
            self.Past.pop()
            self.Future.append(Move.Current)
        else:
            if not self.Future or self.Future[-1] is not Move.Target:
                raise ValueError("redo plan is stale")
            self.Future.pop()
            self.Past.append(Move.Current)
        Move.Committed = True
