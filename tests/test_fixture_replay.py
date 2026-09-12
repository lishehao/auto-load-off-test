from __future__ import annotations

import unittest

from app.domain.models import SweepPoint, SweepResult
from app.presentation.tk.fixture_replay import FixtureReplay


class Scheduler:
    def __init__(self):
        self.pending = {}
        self.next_id = 0

    def schedule(self, _delay, callback):
        self.next_id += 1
        self.pending[self.next_id] = callback
        return self.next_id

    def cancel(self, key):
        self.pending.pop(key, None)

    def tick(self):
        key = min(self.pending)
        self.pending.pop(key)()


class FixtureReplayTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = Scheduler()
        self.updates = []
        self.finished = []
        self.replay = FixtureReplay(schedule=self.scheduler.schedule, cancel=self.scheduler.cancel,
                                    on_update=lambda result, index, total, elapsed: self.updates.append(result),
                                    on_finish=self.finished.append)
        self.result = SweepResult([SweepPoint(float(i + 1), 1.0, 0.0) for i in range(72)],
                                  {"source": "mock_fixture", "nested": {"value": 1}})

    def test_empty_partial_complete_and_independent_snapshots(self):
        self.replay.start(self.result)
        self.assertEqual(len(self.updates[0].points), 0)
        for _ in range(72):
            self.scheduler.tick()
        self.assertEqual([len(r.points) for r in self.updates], list(range(73)))
        self.assertEqual(self.finished, ["completed"])
        self.assertFalse(self.replay.active)
        self.result.points[0].gain_db = 20.0
        self.assertEqual(self.updates[-1].points[0].gain_db, 0.0)
        self.updates[1].meta['nested']['value'] = 3
        self.assertEqual(self.updates[-1].meta['nested']['value'], 1)

    def test_stop_invalidates_even_already_dequeued_callback_and_restart(self):
        self.replay.start(self.result)
        self.scheduler.tick()
        stale = next(iter(self.scheduler.pending.values()))
        self.replay.stop()
        self.assertEqual(self.updates[-1].meta['run_status'], 'stopped')
        self.assertEqual(len(self.updates[-1].points), 1)
        self.replay.start(self.result)
        stale()
        self.assertEqual(len(self.updates[-1].points), 0)
        self.scheduler.tick()
        self.assertEqual(len(self.updates[-1].points), 1)

    def test_close_cancels_without_touching_destroyed_widgets(self):
        self.replay.start(self.result)
        stale = next(iter(self.scheduler.pending.values()))
        self.replay.stop(notify=False)
        stale()
        self.assertEqual(len(self.updates), 1)
        self.assertEqual(self.finished, [])

    def test_reentry_and_empty_data_are_rejected(self):
        with self.assertRaises(ValueError):
            self.replay.start(SweepResult())
        self.replay.start(self.result)
        with self.assertRaises(RuntimeError):
            self.replay.start(self.result)


if __name__ == '__main__':
    unittest.main()
