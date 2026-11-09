import json
import math
import tempfile
import unittest

from ml_model import Tree, generate_dataset, infer, metrics, train_bundle
from runtime import Controller
from simulation import VirtualRoom, run_simulation, stamp


class MLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle,cls.rows=train_bundle()

    def test_room_disjoint_splits(self):
        groups={s:{r['virtual_room'] for r in self.rows if r['split']==s} for s in ('train','validation','test')}
        self.assertFalse(groups['train'] & groups['test'])
        self.assertFalse(groups['validation'] & groups['test'])
        self.assertFalse(groups['train'] & groups['validation'])
        self.assertEqual(len(self.rows),2880)

    def test_reproducible_dataset_and_model(self):
        bundle,rows=train_bundle()
        self.assertEqual(rows,self.rows)
        self.assertEqual(bundle,self.bundle)

    def test_serialization_prediction(self):
        restored=json.loads(json.dumps(self.bundle))
        for row in self.rows[-10:]:
            self.assertEqual(infer(restored,row),infer(self.bundle,row))

    def test_confusion_counts_and_nonfinite(self):
        self.assertEqual(metrics([1,1,0,0],[1,0,1,0])['f1'],.5)
        with self.assertRaises(ValueError): Tree().fit([[math.nan]],[1])
        for model in self.bundle['evaluation'].values():
            for score in model.values():
                self.assertEqual(score['n'],sum(score[k] for k in ('tp','tn','fp','fn')))

    def test_ml_early_start_respects_hard_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=Controller(tmp+'/test.db')
            try:
                key=('test','virtual','1')
                c.reconcile(key,False,stamp(0),stamp(0))
                self.assertEqual(c.request(key,850,stamp(0),stamp(0),predicted_ventilation=True)['status'],'hold')
                cmd=c.request(key,870,stamp(1),stamp(1),predicted_ventilation=True)
                self.assertTrue(cmd['desired'])
                c.ack(key,cmd['command_id'],True,stamp(2))
                self.assertFalse(c.request(key,850,stamp(3),stamp(3),predicted_ventilation=True)['desired'])
            finally:
                c.close()


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle,_=train_bundle()
        cls.result=run_simulation(cls.bundle)

    def test_feedback_target_and_failed_effect(self):
        rooms=self.result['rooms']
        self.assertLess(rooms['A_정상환기']['final_co2'],850)
        self.assertIn('target_reached',[r['status'] for r in rooms['A_정상환기']['verification']])
        self.assertIn('target_not_reached',[r['status'] for r in rooms['C_환기효과없음']['verification']])
        self.assertGreater(rooms['C_환기효과없음']['final_co2'],1200)

    def test_no_auto_actuation_or_recommendation_for_blocked_rooms(self):
        blocked={'D_수동모드','E_센서오류'}
        self.assertFalse(any(e['room'] in blocked and e['event'].startswith('virtual_') for e in self.result['events']))
        self.assertFalse(self.result['rooms']['E_센서오류']['ever_recommended'])
        self.assertFalse(self.result['rooms']['C_환기효과없음']['ever_recommended'])

    def test_ml_triggers_below_fixed_on_boundary(self):
        commands=[e for e in self.result['events'] if e['event']=='virtual_ventilation_command'
                  and e['room']=='F_ML조기환기' and e['desired']]
        self.assertTrue(commands)
        self.assertTrue(850 < commands[0]['co2'] < 890)
        self.assertEqual(commands[0]['ml_prediction'],1)

    def test_ack_timeout_and_virtual_reconciliation(self):
        audit=self.result['database_export']['audit']
        self.assertTrue(any(e['event']=='ack_timeout' for e in audit))
        self.assertTrue(any(e['event']=='virtual_state_query_reconciled' for e in self.result['events']))

    def test_plant_step_consistency_and_effect(self):
        a=VirtualRoom('a',ventilation=True); b=VirtualRoom('b',ventilation=True)
        a.advance(60); b.advance(30); b.advance(30)
        self.assertAlmostEqual(a.co2,b.co2,places=8)
        failed=VirtualRoom('failure',ventilation=True,mode='ineffective'); failed.advance(60)
        self.assertLess(a.co2,failed.co2)

    def test_recommendation_obeys_required_limits(self):
        for frame in self.result['recommendations']:
            for row in frame['rankings']:
                v=row['values']
                self.assertLess(v['co2'],890)
                self.assertGreaterEqual(v['light'],300)
                self.assertTrue(20 <= v['temp'] <= 26 and 40 <= v['humi'] <= 60)
                self.assertEqual(row['ml_environment']['prediction'],1)


if __name__=='__main__': unittest.main(verbosity=2)
