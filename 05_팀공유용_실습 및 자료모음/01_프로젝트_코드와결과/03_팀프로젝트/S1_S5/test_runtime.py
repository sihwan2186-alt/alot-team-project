from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from runtime import Controller, recommend_live

BASE = datetime.fromisoformat('2026-10-18T10:00:00+09:00')
ROOM = ('team02','학생회관','101')
OTHER = ('team02','학생회관','102')


def at(seconds=0):
    return (BASE+timedelta(seconds=seconds)).isoformat()


def reading(**changes):
    return dict(team_id='team02',building='학생회관',room='101',observed_at=at(),
                temp=23,humi=50,co2=600,light=400,noise_db=35,current_people=1,
                assumed_capacity=8,sensor_valid=True,data_origin='test_fixture',**changes)


class RecommendationTests(unittest.TestCase):
    def test_required_light_and_empty_result(self):
        row=reading(); row['light']=68.2
        result=recommend_live([row],at())
        self.assertEqual(result['status'],'no_matching_room')
        self.assertIn('below_required_light',result['excluded'][0]['reason'])
        self.assertEqual(len(recommend_live([row],at(),min_light=None)['rankings']),1)

    def test_age_and_timezone(self):
        row=reading()
        self.assertEqual(len(recommend_live([row],at(120))['rankings']),1)
        self.assertFalse(recommend_live([row],at(121))['rankings'])
        self.assertFalse(recommend_live([row],at(-1))['rankings'])
        row['observed_at']='2026-10-18T10:00:00'
        self.assertFalse(recommend_live([row],at())['rankings'])

    def test_latest_and_conflict(self):
        old=reading(); old['light']=100
        new={**old,'light':400,'observed_at':at(10)}
        self.assertEqual(len(recommend_live([new,old],at(20))['rankings']),1)
        conflict={**new,'co2':1000}
        for rows in ([new,conflict],[conflict,new]):
            self.assertFalse(recommend_live(rows,at(20))['rankings'])

    def test_unknown_reservation_and_sensor(self):
        row=reading()
        self.assertFalse(recommend_live([row],at(),require_reservation=True)['rankings'])
        row['reservation_available']=True
        self.assertTrue(recommend_live([row],at(),require_reservation=True)['rankings'])
        row['sensor_valid']=False
        self.assertFalse(recommend_live([row],at())['rankings'])

    def test_required_ranges_and_integer_count(self):
        for field,value in [('temp',27),('humi',61),('current_people',1.5),('co2',890),('noise_db','nan')]:
            row=reading(); row[field]=value
            self.assertFalse(recommend_live([row],at())['rankings'],field)


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'mock.db'
        self.c=Controller(self.path)

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def start(self, room=ROOM):
        self.c.reconcile(room,False,at(),at())
        return self.c.request(room,890,at(),at())['command_id']

    def test_initial_unknown_and_persisted_pending(self):
        self.assertEqual(self.c.request(ROOM,1000,at(),at())['status'],'reconcile_device_state_first')
        cmd=self.start()
        self.c.close(); self.c=Controller(self.path)
        self.assertEqual(self.c.request(ROOM,1000,at(1),at(1))['status'],'pending_no_duplicate')
        self.assertEqual(self.c.ack(ROOM,cmd,True,at(2)),'acked')
        self.c.close(); self.c=Controller(self.path)
        self.assertEqual(self.c.verify(ROOM,cmd,840,at(482),at(482)),'target_reached')

    def test_multi_room_wrong_ack_and_replay(self):
        a=self.start(); b=self.start(OTHER)
        self.assertNotEqual(a,b)
        self.assertEqual(self.c.ack(OTHER,a,True,at(1)),'ignored_ack')
        self.assertEqual(self.c.ack(ROOM,a,True,at(1)),'acked')
        self.assertEqual(self.c.ack(ROOM,a,True,at(2)),'ignored_ack')
        self.assertEqual(self.c.ack(OTHER,b,True,at(2)),'acked')

    def test_expiry_and_recovery(self):
        cmd=self.start()
        self.assertEqual(self.c.tick(ROOM,at(5)),'ack_timeout')
        self.assertEqual(self.c.ack(ROOM,cmd,True,at(6)),'ignored_ack')
        self.assertEqual(self.c.request(ROOM,1000,at(7),at(7))['status'],'reconcile_device_state_first')
        self.c.reconcile(ROOM,True,at(8),at(8))
        self.assertEqual(self.c.request(ROOM,870,at(9),at(9))['status'],'hold')

    def test_late_ack_without_tick(self):
        cmd=self.start()
        self.assertEqual(self.c.ack(ROOM,cmd,True,at(5)),'ignored_ack')
        self.assertIsNone(self.c.export()['rooms'][0]['confirmed'])

    def test_manual_cancels_pending_and_requires_reconcile(self):
        cmd=self.start(); self.c.set_manual(ROOM,True,at(1))
        self.assertEqual(self.c.ack(ROOM,cmd,True,at(2)),'ignored_ack')
        self.assertEqual(self.c.request(ROOM,1000,at(3),at(3))['status'],'blocked_manual')
        self.c.set_manual(ROOM,False,at(4))
        self.assertEqual(self.c.request(ROOM,1000,at(5),at(5))['status'],'reconcile_device_state_first')

    def test_remeasurement_uses_observed_time(self):
        cmd=self.start(); self.c.ack(ROOM,cmd,True,at(1))
        self.assertEqual(self.c.verify(ROOM,cmd,840,at(470),at(490)),'wait_new_observation_after_8_minutes')
        self.assertEqual(self.c.verify(ROOM,cmd,1005,at(491),at(491)),'target_not_reached')

    def test_switch_off_and_superseded_verification(self):
        cmd=self.start(); self.c.ack(ROOM,cmd,True,at(1))
        off=self.c.request(ROOM,850,at(2),at(2))['command_id']
        self.assertEqual(self.c.verify(ROOM,cmd,840,at(3),at(3)),'superseded_command')
        self.c.ack(ROOM,off,False,at(4))
        self.assertEqual(self.c.verify(ROOM,off,840,at(484),at(484)),'off_state_confirmed_environment_ok')

    def test_invalid_stale_and_clock(self):
        self.start()
        self.assertEqual(self.c.request(ROOM,1000,at(),at(121))['status'],'blocked_invalid_or_stale_sensor')
        self.c.tick(ROOM,at(2))
        with self.assertRaises(ValueError): self.c.tick(ROOM,at(1))
        with self.assertRaises(ValueError): self.c.ack(ROOM,'x','true',at(3))


if __name__=='__main__': unittest.main(verbosity=2)
