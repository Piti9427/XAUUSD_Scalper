"""B1-FINAL EA outbox -> durable consumer -> notification sink (no real recipients)."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.b1_outbox import consume, EXECUTED_TYPES


def event(eid, etype, confirmed, **fields):
    return {'event_id': eid, 'type': etype, 'confirmed': confirmed, 'utc_ms': 1790000000000,
            'utc': '2026-09-21T10:15:00.000Z', 'strategy': 'B1-FINAL', 'version': 'B1-FINAL-v1', 'symbol': 'XAUUSDm',
            'fields': fields, 'private': {'position_ticket': 987654}}


class RecordingSink:
    def __init__(self, fail=None):
        self.cards, self.fail = [], fail

    def send(self, text):
        if self.fail == 'timeout':
            raise TimeoutError('no response')
        if self.fail == 'down':
            raise ConnectionError('unavailable')
        self.cards.append(text)


class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.events = Path(self.dir.name)/'events.jsonl'
        self.state = Path(self.dir.name)/'outbox_state.json'

    def tearDown(self):
        self.dir.cleanup()

    def write(self, *items, partial=''):
        self.events.write_text(''.join(json.dumps(x)+'\n' for x in items)+partial)

    def stream(self):
        return (event('s', 'SIGNAL', False, direction=1),
                event('a', 'ADMISSION', False, outcome='SUBMITTED'),
                event('r', 'REQUEST_REJECTED', False, reason='x'),
                event('u', 'REQUEST_UNKNOWN', False, reason='x'),
                event('f', 'FILL_CONFIRMED', True, direction=1, volume=0.1, fill_price=4300.5, sl=4280.0, tp=4371.75),
                event('m', 'SL_MODIFIED_CONFIRMED', True, confirmed_sl=4300.6),
                event('c', 'CLOSE_CONFIRMED', True, reason='TP', net_profit=712.5, net_r=3.5, exit_price=4371.75))

    def test_only_broker_confirmed_events_become_executed_cards(self):
        self.write(*self.stream())
        sink = RecordingSink()
        result = consume(self.events, self.state, sink)
        self.assertEqual(len(sink.cards), 3)
        self.assertEqual(result['delivered'], 3)
        self.assertEqual(result['diagnostic'], 4)
        self.assertTrue(all('987654' not in card for card in sink.cards))
        self.assertIn('FILL', sink.cards[0])
        self.assertEqual(EXECUTED_TYPES, {'FILL_CONFIRMED', 'SL_MODIFIED_CONFIRMED', 'CLOSE_CONFIRMED'})

    def test_unconfirmed_fill_type_is_never_a_card(self):
        self.write(event('x', 'FILL_CONFIRMED', False, volume=1), event('y', 'SIGNAL', True))
        sink = RecordingSink()
        consume(self.events, self.state, sink)
        self.assertEqual(sink.cards, [])

    def test_acknowledged_replay_is_deduplicated_across_restart(self):
        self.write(*self.stream())
        consume(self.events, self.state, RecordingSink())
        self.write(*self.stream(), self.stream()[4])
        sink = RecordingSink()
        result = consume(self.events, self.state, sink)
        self.assertEqual(sink.cards, [])
        self.assertEqual(result['delivered'], 0)

    def test_timeout_is_persisted_as_delivery_unknown_and_not_resent(self):
        self.write(self.stream()[4])
        result = consume(self.events, self.state, RecordingSink(fail='timeout'))
        self.assertEqual(result['delivery_unknown'], 1)
        state = json.loads(self.state.read_text())
        self.assertEqual(state['events']['f'], 'DELIVERY_UNKNOWN')
        sink = RecordingSink()
        consume(self.events, self.state, sink)
        self.assertEqual(sink.cards, [])

    def test_unavailable_notifier_keeps_events_pending_in_order(self):
        self.write(*self.stream())
        result = consume(self.events, self.state, RecordingSink(fail='down'))
        self.assertEqual(result['pending'], 3)
        self.assertEqual(result['delivered'], 0)
        sink = RecordingSink()
        consume(self.events, self.state, sink)
        self.assertEqual(len(sink.cards), 3)
        self.assertIn('FILL', sink.cards[0])
        self.assertIn('CLOSE', sink.cards[2])

    def test_incomplete_trailing_line_waits_for_writer(self):
        self.write(self.stream()[4], partial='{"event_id": "c", "type": "CLO')
        sink = RecordingSink()
        result = consume(self.events, self.state, sink)
        self.assertEqual(len(sink.cards), 1)
        self.assertEqual(result['incomplete_tail'], True)

    def test_corrupt_complete_line_fails_closed(self):
        self.events.write_text('not json\n')
        with self.assertRaises(ValueError):
            consume(self.events, self.state, RecordingSink())

    def test_corrupt_state_fails_closed(self):
        self.write(self.stream()[4])
        self.state.write_text('{broken')
        with self.assertRaises(ValueError):
            consume(self.events, self.state, RecordingSink())


if __name__ == '__main__':
    unittest.main()
