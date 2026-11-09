"""Offline integration prototype; never connects to devices or MQTT."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import sqlite3
from uuid import uuid4

from demo import recommend


def instant(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timezone is required')
    return parsed.astimezone(timezone.utc)


def age_seconds(observed_at, now):
    return (instant(now) - instant(observed_at)).total_seconds()


def finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def recommend_live(rows, now, *, min_light=300, max_noise=None,
                   temperature=(20, 26), humidity=(40, 60),
                   require_reservation=False, max_age=120, weights=None):
    """Apply explicit hard constraints before the original preference score.

    Default hard constraints are design assumptions, configurable by the caller.
    Legacy naive timestamps are rejected rather than silently localized.
    """
    instant(now)
    recommend([], weights)  # Validate weights even if there are no candidates.
    if not finite(max_age) or max_age < 0:
        raise ValueError('Invalid max_age')
    for bounds in (temperature, humidity):
        if bounds is not None and (len(bounds) != 2 or not all(finite(x) for x in bounds) or bounds[0] > bounds[1]):
            raise ValueError('Invalid bounds')
    for bound in (min_light, max_noise):
        if bound is not None and (not finite(bound) or bound < 0):
            raise ValueError('Invalid light/noise bound')
    latest, excluded = {}, []
    for row in rows:
        key = tuple(row.get(k) for k in ('team_id', 'building', 'room'))
        if not all(isinstance(x, str) and x.strip() for x in key):
            excluded.append({'key': list(key), 'reason': ['missing_room_key']})
            continue
        try:
            stamp = instant(row['observed_at'])
        except (ValueError, KeyError, TypeError, AttributeError):
            excluded.append({'key': list(key), 'reason': ['invalid_observed_at']})
            continue
        if key not in latest or stamp > latest[key][0]:
            latest[key] = (stamp, row, False)
        elif stamp == latest[key][0]:
            # A conflicting same-time reading cannot be chosen by file order.
            prior = latest[key]
            latest[key] = (stamp, prior[1], prior[2] or row != prior[1])
    accepted = []
    for key, (_, row, conflict) in sorted(latest.items()):
        reasons = []
        age = age_seconds(row['observed_at'], now)
        if age < 0 or age > max_age:
            reasons.append('future_or_stale_observation')
        if conflict:
            reasons.append('conflicting_latest_observation')
        if row.get('sensor_valid') is not True:
            reasons.append('sensor_not_confirmed_valid')
        if require_reservation and row.get('reservation_available') is not True:
            reasons.append('reservation_not_confirmed_available')
        try:
            v = {k: float(row[k]) for k in ('light', 'noise_db', 'temp', 'humi', 'current_people', 'assumed_capacity')}
            if not all(math.isfinite(x) for x in v.values()):
                raise ValueError('nonfinite')
            if any(not v[k].is_integer() for k in ('current_people','assumed_capacity')):
                reasons.append('people_and_capacity_must_be_integer')
            if min_light is not None and v['light'] < min_light:
                reasons.append('below_required_light')
            if max_noise is not None and v['noise_db'] > max_noise:
                reasons.append('above_required_noise')
            for field, bounds in [('temp',temperature), ('humi',humidity)]:
                if bounds is not None and not bounds[0] <= v[field] <= bounds[1]:
                    reasons.append('outside_required_' + field)
        except (ValueError, TypeError, KeyError):
            reasons.append('missing_or_invalid_input')
        if reasons:
            excluded.append({'key': list(key), 'reason': reasons})
            continue
        scored = recommend([row], weights)
        if scored['rankings']:
            accepted.append({**scored['rankings'][0], 'team_id': key[0],
                             'observed_at': row['observed_at'], 'age_seconds': age,
                             'reservation_available': row.get('reservation_available'),
                             'data_origin': row.get('data_origin','unknown')})
        else:
            excluded.append({'key': list(key), 'reason': scored['excluded'][0]['reason']})
    accepted.sort(key=lambda r: (-r['score'], r['team_id'], r['building'], r['room']))
    return {'rankings': accepted, 'excluded': excluded,
            'status': 'recommendations_available' if accepted else 'no_matching_room',
            'message': '조건을 만족하는 방이 없습니다. 조건 변경 또는 환경 조정 후 새 관측이 필요합니다.' if not accepted else '필수 조건 통과 후 선호 점수 순위입니다.'}


class Controller:
    """Persistent, multi-room mock command lifecycle. ISO timestamps required.

    Room keys must come from a common team mapping. Callers supply trusted
    device responses; identity/authentication and transport are outside scope.
    """
    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS rooms(
          room_key TEXT PRIMARY KEY, confirmed INTEGER,
          manual INTEGER NOT NULL DEFAULT 0, last_time TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS commands(
          command_id TEXT PRIMARY KEY, room_key TEXT NOT NULL REFERENCES rooms(room_key),
          desired INTEGER NOT NULL, sent_at TEXT NOT NULL, status TEXT NOT NULL,
          ack_at TEXT, actual INTEGER, verified_at TEXT);
        CREATE UNIQUE INDEX IF NOT EXISTS one_pending_per_room
          ON commands(room_key) WHERE status='pending';
        CREATE TABLE IF NOT EXISTS audit(
          id INTEGER PRIMARY KEY, room_key TEXT NOT NULL, at TEXT NOT NULL,
          event TEXT NOT NULL, detail TEXT NOT NULL);
        ''')

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def room(self, key, now):
        if not isinstance(key, (tuple,list)) or len(key) != 3 or not all(isinstance(x,str) and x.strip() for x in key):
            raise ValueError('Use (team_id, building, room)')
        now = instant(now).isoformat()
        key = json.dumps(list(key), ensure_ascii=False)
        self.db.execute('INSERT OR IGNORE INTO rooms(room_key,last_time) VALUES (?,?)',(key,now))
        room = self.db.execute('SELECT * FROM rooms WHERE room_key=?',(key,)).fetchone()
        if instant(now) < instant(room['last_time']):
            raise ValueError('Time cannot move backwards')
        self.db.execute('UPDATE rooms SET last_time=? WHERE room_key=?',(now,key))
        return key, now

    def log(self, key, now, event, detail=None):
        self.db.execute('INSERT INTO audit(room_key,at,event,detail) VALUES (?,?,?,?)',
                        (key,now,event,json.dumps(detail or {},ensure_ascii=False)))

    def expire(self, key, now):
        cmd = self.db.execute("SELECT * FROM commands WHERE room_key=? AND status='pending'",(key,)).fetchone()
        if cmd and age_seconds(cmd['sent_at'],now) >= 5:
            self.db.execute("UPDATE commands SET status='timeout' WHERE command_id=?",(cmd['command_id'],))
            self.db.execute('UPDATE rooms SET confirmed=NULL WHERE room_key=?',(key,))
            self.log(key,now,'ack_timeout',dict(cmd))
            return True
        return False

    def reconcile(self, key, actual, observed_at, now):
        if type(actual) is not bool or not 0 <= age_seconds(observed_at,now) <= 120:
            raise ValueError('Fresh device state and boolean actual required')
        with self.transaction():
            key,now = self.room(key,now)
            self.db.execute("UPDATE commands SET status='cancelled_by_reconciliation' WHERE room_key=? AND status='pending'",(key,))
            self.db.execute("UPDATE commands SET status='superseded_by_reconciliation' WHERE room_key=? AND status='acked'",(key,))
            self.db.execute('UPDATE rooms SET confirmed=? WHERE room_key=?',(int(actual),key))
            self.log(key,now,'device_state_reconciled',{'actual':actual,'observed_at':observed_at})

    def set_manual(self, key, enabled, now):
        if type(enabled) is not bool:
            raise ValueError('Boolean manual flag required')
        with self.transaction():
            key,now = self.room(key,now)
            # Manual transition invalidates automatic state and in-flight command.
            self.db.execute('UPDATE rooms SET manual=?,confirmed=NULL WHERE room_key=?',(int(enabled),key))
            self.db.execute("UPDATE commands SET status='cancelled_by_manual' WHERE room_key=? AND status='pending'",(key,))
            self.db.execute("UPDATE commands SET status='superseded_by_manual' WHERE room_key=? AND status='acked'",(key,))
            self.log(key,now,'manual_mode',{'enabled':enabled})

    def request(self, key, co2, observed_at, now, *, sensor_valid=True, predicted_ventilation=False):
        if type(predicted_ventilation) is not bool:
            raise ValueError('Boolean ML ventilation prediction required')
        if not finite(co2) or co2 <= 0 or sensor_valid is not True or not 0 <= age_seconds(observed_at,now) <= 120:
            return {'status':'blocked_invalid_or_stale_sensor'}
        with self.transaction():
            key,now = self.room(key,now)
            self.expire(key,now)
            room = self.db.execute('SELECT * FROM rooms WHERE room_key=?',(key,)).fetchone()
            if room['manual']:
                return {'status':'blocked_manual'}
            if room['confirmed'] is None:
                return {'status':'reconcile_device_state_first'}
            if self.db.execute("SELECT 1 FROM commands WHERE room_key=? AND status='pending'",(key,)).fetchone():
                return {'status':'pending_no_duplicate'}
            # Fixed boundaries remain authoritative; ML may start early only
            # inside the hysteresis band above the off threshold.
            desired = 1 if co2 >= 890 else 0 if co2 <= 850 else 1 if predicted_ventilation else room['confirmed']
            if desired == room['confirmed']:
                return {'status':'hold'}
            command_id = 'mock-' + uuid4().hex
            self.db.execute('INSERT INTO commands(command_id,room_key,desired,sent_at,status) VALUES (?,?,?,?,?)',
                            (command_id,key,desired,now,'pending'))
            self.log(key,now,'mock_command_created',{'command_id':command_id,'desired':bool(desired),'co2':co2,
                                                   'predicted_ventilation':predicted_ventilation})
            return {'status':'mock_command_created','command_id':command_id,'desired':bool(desired),'room_key':json.loads(key)}

    def ack(self, key, command_id, actual, now):
        if type(actual) is not bool:
            raise ValueError('Boolean device actual required')
        with self.transaction():
            key,now = self.room(key,now)
            self.expire(key,now)
            cmd = self.db.execute('SELECT * FROM commands WHERE command_id=? AND room_key=?',(command_id,key)).fetchone()
            if not cmd or cmd['status'] != 'pending':
                self.log(key,now,'ignored_ack',{'command_id':command_id})
                return 'ignored_ack'
            status = 'acked' if int(actual) == cmd['desired'] else 'device_state_mismatch'
            self.db.execute('UPDATE commands SET status=?,ack_at=?,actual=? WHERE command_id=?',
                            (status,now,int(actual),command_id))
            self.db.execute('UPDATE rooms SET confirmed=? WHERE room_key=?',
                            (int(actual) if status == 'acked' else None,key))
            self.log(key,now,status,{'command_id':command_id,'actual':actual})
            return status

    def tick(self, key, now):
        with self.transaction():
            key,now = self.room(key,now)
            return 'ack_timeout' if self.expire(key,now) else 'idle'

    def verify(self, key, command_id, co2, observed_at, now):
        if not finite(co2) or co2 <= 0 or not 0 <= age_seconds(observed_at,now) <= 120:
            return 'invalid_remeasurement'
        with self.transaction():
            key,now = self.room(key,now)
            self.expire(key,now)
            room = self.db.execute('SELECT * FROM rooms WHERE room_key=?',(key,)).fetchone()
            cmd = self.db.execute('SELECT * FROM commands WHERE command_id=? AND room_key=?',(command_id,key)).fetchone()
            if room['manual'] or room['confirmed'] is None or not cmd or cmd['status'] != 'acked':
                return 'not_ready'
            if self.db.execute('SELECT 1 FROM commands WHERE room_key=? AND rowid>(SELECT rowid FROM commands WHERE command_id=?)',
                               (key,command_id)).fetchone():
                return 'superseded_command'
            if age_seconds(cmd['ack_at'],observed_at) < 480:
                return 'wait_new_observation_after_8_minutes'
            if cmd['desired'] == 0:
                status = 'off_state_confirmed_environment_ok' if co2 < 890 else 'off_state_confirmed_co2_high'
            else:
                status = 'target_reached' if co2 <= 850 else 'target_not_reached'
            self.db.execute('UPDATE commands SET status=?,verified_at=? WHERE command_id=?',(status,now,command_id))
            self.log(key,now,status,{'command_id':command_id,'co2':co2,'observed_at':observed_at})
            return status

    def export(self):
        return {table:[dict(row) for row in self.db.execute('SELECT * FROM '+table)]
                for table in ('rooms','commands','audit')}
