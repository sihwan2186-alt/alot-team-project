"""Offline S1/S5 review prototype. No broker, sensor, or device access."""
from pathlib import Path
import csv
import hashlib
import json
import math
import sys
import unittest

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / '이전모의검증/synthetic_snapshot.csv'
WEIGHTS = dict(noise=.35, crowding=.20, co2=.20, temp=.10, humi=.10, light=.05)


def recommend(rows, weights=None):
    weights = WEIGHTS if weights is None else weights
    if set(weights) != set(WEIGHTS) or any(not math.isfinite(v) or v < 0 for v in weights.values()) or abs(sum(weights.values()) - 1) > 1e-9:
        raise ValueError('Six finite nonnegative weights summing to one required')
    accepted, excluded = [], []
    for row in rows:
        key = {'building': row.get('building'), 'room': row.get('room')}
        try:
            v = {k: float(row[k]) for k in ('noise_db', 'current_people', 'assumed_capacity', 'co2', 'temp', 'humi', 'light')}
            if not all(math.isfinite(x) for x in v.values()):
                raise ValueError('nonfinite')
            if not (0 <= v['humi'] <= 100 and v['co2'] > 0 and v['light'] >= 0 and v['noise_db'] >= 0 and 0 <= v['current_people'] <= v['assumed_capacity'] and v['assumed_capacity'] > 0):
                raise ValueError('invalid range')
        except (ValueError, KeyError, TypeError):
            excluded.append({**key, 'reason': 'missing_or_invalid_input'})
            continue
        reasons = []
        if v['co2'] >= 890:
            reasons.append('co2_at_or_above_890')
        if v['assumed_capacity'] - v['current_people'] < 1:
            reasons.append('no_assumed_seat')
        if reasons:
            excluded.append({**key, 'reason': reasons})
            continue
        clip = lambda x: max(0, min(1, x))
        costs = dict(noise=clip((v['noise_db']-30)/30), crowding=v['current_people']/v['assumed_capacity'],
                     co2=clip((v['co2']-400)/490), temp=clip(abs(v['temp']-23)/7),
                     humi=clip(abs(v['humi']-50)/30), light=clip((300-v['light'])/300))
        penalties = {k: round(100*weights[k]*costs[k], 6) for k in weights}
        accepted.append({**key, 'score': round(100-sum(penalties.values()), 4),
                         'penalty_points': penalties, 'values': v,
                         'explanation': '가중 감점이 작을수록 선호 조건에 가까움. 정원·소음·인원은 가정값, 예약 미확인.'})
    accepted.sort(key=lambda r: (-r['score'], r['building'], r['room']))
    return {'rankings': accepted, 'excluded': excluded}


class Ventilation:
    """One-room mock controller. Caller supplies elapsed seconds, no real waits."""
    def __init__(self, state=False):
        self.confirmed = state
        self.pending = None
        self.sequence = 0
        self.uncertain = False
        self.acked_at = None

    def request(self, co2, now, *, manual=False, fresh=True):
        if manual or not fresh or not math.isfinite(co2) or co2 <= 0:
            return 'blocked_input_or_manual'
        if self.uncertain:
            return 'reconcile_device_state_first'
        if self.pending:
            return 'pending_no_duplicate'
        desired = True if co2 >= 890 else False if co2 <= 850 else self.confirmed
        if desired == self.confirmed:
            return 'hold'
        self.sequence += 1
        self.pending = {'command_id': f'mock-{self.sequence}', 'desired': desired, 'sent_at': now}
        return dict(self.pending)

    def ack(self, command_id, actual, now):
        if not self.pending or command_id != self.pending['command_id']:
            return 'unmatched_ack'
        if now < self.pending['sent_at'] or now >= self.pending['sent_at'] + 5:
            self.uncertain = True
            self.pending = None
            return 'late_ack_reconcile_required'
        if type(actual) is not bool or actual != self.pending['desired']:
            self.uncertain = True
            self.pending = None
            return 'device_state_mismatch'
        self.confirmed = actual
        self.pending = None
        self.acked_at = now
        return 'device_ack_received'

    def tick(self, now):
        if self.pending and now >= self.pending['sent_at'] + 5:
            self.pending = None
            self.uncertain = True
            return 'ack_timeout_state_unknown'
        return 'waiting_or_idle'

    def verify(self, co2, now):
        if self.uncertain or not self.confirmed or self.acked_at is None:
            return 'not_ready'
        if now < self.acked_at + 480:
            return 'wait_8_minutes'
        if not math.isfinite(co2) or co2 <= 0:
            return 'invalid_remeasurement'
        return 'target_reached' if co2 <= 850 else 'target_not_reached_review_required'


class Checks(unittest.TestCase):
    def test_boundaries(self):
        for state, ppm, expected in [(False,890,True),(True,850,False)]:
            c = Ventilation(state)
            self.assertEqual(c.request(ppm,0)['desired'],expected)
        for state in [False, True]:
            self.assertEqual(Ventilation(state).request(870,0),'hold')

    def test_duplicate_and_ack_identity(self):
        c=Ventilation(); cmd=c.request(1000,0)
        self.assertEqual(c.request(1000,1),'pending_no_duplicate')
        self.assertEqual(c.ack('other',True,1),'unmatched_ack')
        self.assertFalse(c.confirmed)
        self.assertEqual(c.ack(cmd['command_id'],True,2),'device_ack_received')
        self.assertEqual(c.verify(840,481),'wait_8_minutes')
        self.assertEqual(c.verify(840,482),'target_reached')
        self.assertEqual(c.verify(1005,482),'target_not_reached_review_required')

    def test_timeout(self):
        c=Ventilation(); cmd=c.request(1000,0)
        self.assertEqual(c.tick(5),'ack_timeout_state_unknown')
        self.assertEqual(c.ack(cmd['command_id'],True,6),'unmatched_ack')
        self.assertEqual(c.request(1000,7),'reconcile_device_state_first')

    def test_late_and_wrong_state_ack(self):
        for actual,now in [(True,5),(False,1)]:
            c=Ventilation(); cmd=c.request(1000,0)
            c.ack(cmd['command_id'],actual,now)
            self.assertTrue(c.uncertain)

    def test_input_manual(self):
        self.assertEqual(Ventilation().request(1000,0,manual=True),'blocked_input_or_manual')
        self.assertEqual(Ventilation().request(1000,0,fresh=False),'blocked_input_or_manual')

    def test_recommendation(self):
        with SOURCE.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
        result=recommend(rows)
        self.assertEqual(len(result['rankings'])+len(result['excluded']),63)
        self.assertTrue(all(0 <= r['score'] <= 100 for r in result['rankings']))
        self.assertTrue(all(r['values']['co2'] < 890 for r in result['rankings']))
        self.assertEqual(recommend([{**rows[0], 'co2':'nan'}])['rankings'],[])
        self.assertEqual(recommend([{**rows[0], 'humi':''}])['rankings'],[])
        with self.assertRaises(ValueError): recommend(rows, {**WEIGHTS,'humi':-1})


def main():
    before=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    with SOURCE.open(encoding='utf-8-sig',newline='') as f: result=recommend(list(csv.DictReader(f)))
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    tests=unittest.TextTestRunner(verbosity=2).run(suite)
    result.update(origin='Codex offline synthetic demonstration 2026-10-18', python=sys.version.split()[0],
                  weights=WEIGHTS, source_sha256=before, tests_run=tests.testsRun, tests_passed=tests.wasSuccessful(),
                  source_unchanged=before==hashlib.sha256(SOURCE.read_bytes()).hexdigest())
    (HERE/'demo_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'candidates':len(result['rankings']),'excluded':len(result['excluded']),
                      'top3':result['rankings'][:3],'tests_passed':tests.wasSuccessful()},ensure_ascii=False,indent=2))
    if not tests.wasSuccessful(): raise SystemExit(1)


if __name__ == '__main__': main()
