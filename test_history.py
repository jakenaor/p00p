import unittest as Unittest

import history as History


def Bowl(*Names):
    return {
        "protocol": "p00p",
        "entries": {
            Name: {"password": f"fake-{Name}"}
            for Name in Names
        },
    }


#MARK: timeline paperwork stuffs
class HistoryBookTests(Unittest.TestCase):
    def testRememberMakesUndoPlanWithoutMovingStacksYet(self):
        Book = History.HistoryBook()
        Book.Remember("ADD MOON", Bowl(), "")

        Move = Book.PlanUndo(Bowl("moon"), "moon")

        self.assertEqual(Move.Direction, "undo")
        self.assertEqual(Move.Target.Vault, Bowl())
        self.assertEqual(Move.Current.Vault, Bowl("moon"))
        self.assertTrue(Book.CanUndo)
        self.assertFalse(Book.CanRedo)

    def testCommittedUndoAndRedoWalkBothDirections(self):
        Book = History.HistoryBook()
        Book.Remember("ADD MOON", Bowl(), "")

        Undo = Book.PlanUndo(Bowl("moon"), "moon")
        Book.Commit(Undo)
        self.assertFalse(Book.CanUndo)
        self.assertTrue(Book.CanRedo)
        self.assertEqual(Book.RedoLabel, "REDO ADD MOON")

        Redo = Book.PlanRedo(Bowl(), "")
        self.assertEqual(Redo.Target.Vault, Bowl("moon"))
        Book.Commit(Redo)
        self.assertTrue(Book.CanUndo)
        self.assertFalse(Book.CanRedo)

    def testFramesAreDeepCopiesInsteadOfTimeTravelingReferences(self):
        Vault = Bowl("one")
        Book = History.HistoryBook()
        Book.Remember("EDIT ONE", Vault, "one")

        Vault["entries"]["one"]["password"] = "changed later"

        self.assertEqual(
            Book.Past[0].Vault["entries"]["one"]["password"],
            "fake-one",
        )

    def testNewChangeAfterUndoThrowsAwayAbandonedFuture(self):
        Book = History.HistoryBook()
        Book.Remember("ADD ONE", Bowl(), "")
        Undo = Book.PlanUndo(Bowl("one"), "one")
        Book.Commit(Undo)
        self.assertTrue(Book.CanRedo)

        Book.Remember("ADD TWO", Bowl(), "")

        self.assertFalse(Book.CanRedo)
        self.assertEqual(Book.UndoLabel, "UNDO ADD TWO")

    def testHistoryLimitDropsOnlyTheOldestFrames(self):
        Book = History.HistoryBook(Limit=3)
        for Number in range(5):
            Book.Remember(f"CHANGE {Number}", Bowl(str(Number)), str(Number))

        self.assertEqual(
            [Frame.Label for Frame in Book.Past],
            ["CHANGE 2", "CHANGE 3", "CHANGE 4"],
        )

    def testStaleOrRepeatedPlanCannotBeCommitted(self):
        Book = History.HistoryBook()
        Book.Remember("ADD ONE", Bowl(), "")
        Move = Book.PlanUndo(Bowl("one"), "one")
        Book.Commit(Move)

        with self.assertRaisesRegex(ValueError, "already committed"):
            Book.Commit(Move)

    def testClearFlushesBothDirections(self):
        Book = History.HistoryBook()
        Book.Remember("ADD ONE", Bowl(), "")
        Book.Commit(Book.PlanUndo(Bowl("one"), "one"))

        Book.Clear()

        self.assertFalse(Book.CanUndo)
        self.assertFalse(Book.CanRedo)
        self.assertEqual(Book.UndoLabel, "UNDO")
        self.assertEqual(Book.RedoLabel, "REDO")


if __name__ == "__main__":
    Unittest.main()
