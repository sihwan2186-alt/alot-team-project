"""Virtual rooms, virtual actuator ACKs, ML and closed-loop control."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
from pathlib import Path
import tempfile

from ml_model import Tree, environment_features, infer
from runtime import Controller, recommend_live

BASE=datetime.fromisoformat('2026-10-19T10:00:00+09:00')


def stamp(seconds):
    return (BASE+timedelta(seconds=seconds)).isoformat()


@dataclass
class VirtualRoom:
    name: str
    co2: float = 1200
    temp: float = 27
    humi: float = 65
    light: float = 120
    noise: float = 35
    people: int = 2
    mode: str = 'normal'
    ventilation: bool = False
    targets: dict = field(default_factory=dict)

    @property
    def key(self):
        return ('simulation-team02','가상스터디룸',self.name)

    def advance(self,seconds):
        minutes=seconds/60
        # Well-mixed one-zone simulation assumption, not a calibrated room.
        # Outdoor CO2=420ppm, per-person generation=5ppm/min,
        # baseline exchange=.2/h, effective ventilation=6/h.
        exchange=(6 if self.ventilation and self.mode != 'ineffective' else .2)/60
        equilibrium=420+5*self.people/exchange
        self.co2=equilibrium+(self.co2-equilibrium)*math.exp(-exchange*minutes)
        for attr,tau in [('temp',4),('humi',4),('light',.25)]:
            if attr in self.targets:
                target=self.targets[attr]
                setattr(self,attr,target+(getattr(self,attr)-target)*math.exp(-minutes/tau))

    def observe(self,seconds,trend):
        return dict(team_id=self.key[0],building=self.key[1],room=self.name,
                    observed_at=stamp(seconds),sensor_valid=self.mode!='sensor_fault',
                    temp=round(self.temp,3),humi=round(self.humi,3),co2=round(self.co2,3),
                    light=round(self.light,3),noise_db=self.noise,current_people=self.people,
                    assumed_capacity=8,reservation_available=True,
                    co2_trend_ppm_per_min=round(trend,3),
                    data_origin='virtual_dynamic_model_not_real_measurement')

    def apply_ventilation(self,desired):
        self.ventilation=desired
        return self.mode!='ack_lost'

    def apply_environment(self):
        # Virtual HVAC/humidity/lighting aggregate actuators. Fixed design setpoints.
        self.targets={'temp':23,'humi':50,'light':400}
        return {'targets':dict(self.targets),'virtual_ack':True}


def recommend_ml(bundle,rows,now):
    baseline=recommend_live(rows,now,max_noise=45,require_reservation=True)
    lookup={(r.get('team_id'),r.get('building'),r.get('room'),r.get('observed_at')):r for r in rows}
    predictions=[]; accepted=[]
    for ranked in baseline['rankings']:
        key=(ranked['team_id'],ranked['building'],ranked['room'])
        prediction=Tree(root=bundle['models']['environment']).predict_one(
            environment_features(lookup[(*key,ranked['observed_at'])]))
        predictions.append({'room':key[-1],**prediction})
        if prediction['prediction']==1:
            accepted.append({**ranked,'ml_environment':prediction})
        else:
            baseline['excluded'].append({'key':list(key),'reason':['ml_environment_not_suitable']})
    return {'rankings':accepted,'excluded':baseline['excluded'],'ml_predictions':predictions,
            'status':'recommendations_available' if accepted else 'no_matching_room'}


def run_simulation(bundle,out_dir=None):
    rooms=[VirtualRoom('A_정상환기'),VirtualRoom('B_ACK누락'),VirtualRoom('C_환기효과없음'),
           VirtualRoom('D_수동모드'),VirtualRoom('E_센서오류'),
           VirtualRoom('F_ML조기환기',co2=870,temp=23,humi=50,light=400,people=4)]
    rooms[1].mode='ack_lost'; rooms[2].mode='ineffective'
    rooms[3].mode='manual'; rooms[4].mode='sensor_fault'
    samples=[]; events=[]; recommendations=[]; current_commands={}; deadlines={}
    previous={r.name:r.co2 for r in rooms}
    with tempfile.TemporaryDirectory() as tmp:
        database=Path(tmp)/'closed_loop.db'; c=Controller(database)
        try:
            for room in rooms:
                c.reconcile(room.key,False,stamp(0),stamp(0))
                if room.mode=='manual': c.set_manual(room.key,True,stamp(0))
            for seconds in range(0,1801,30):
                observations=[]
                for room in rooms:
                    if seconds:
                        room.advance(30)
                    trend=(room.co2-previous[room.name])/.5 if seconds else 0
                    previous[room.name]=room.co2
                    row=room.observe(seconds,trend)
                    observations.append(row)
                    ml=infer(bundle,row) if row['sensor_valid'] else None
                    c.tick(room.key,stamp(seconds))
                    # Explicit virtual status query recovers the lost ACK case.
                    if room.mode=='ack_lost' and seconds>0 and seconds % 120 == 0:
                        c.reconcile(room.key,room.ventilation,stamp(seconds),stamp(seconds))
                        events.append({'at':seconds,'room':room.name,'event':'virtual_state_query_reconciled','actual':room.ventilation})
                    if room.name in deadlines and seconds >= deadlines[room.name] and row['sensor_valid']:
                        result=c.verify(room.key,current_commands[room.name],row['co2'],row['observed_at'],stamp(seconds))
                        events.append({'at':seconds,'room':room.name,'event':'remeasurement','status':result,'co2':row['co2']})
                        del deadlines[room.name]
                    if row['sensor_valid'] and room.mode!='manual' and not room.targets:
                        applied=room.apply_environment()
                        events.append({'at':seconds+1,'room':room.name,'event':'virtual_environment_command_ack',**applied})
                    if room.name in deadlines and not room.ventilation and row['co2'] >= 890:
                        events.append({'at':seconds,'room':room.name,'event':'off_verification_interrupted_by_high_co2','co2':row['co2']})
                        del deadlines[room.name]
                    # Minimum verification window: retain the commanded state
                    # until its eight-minute check, then allow the next command.
                    # Manual/invalid inputs are still blocked by the controller.
                    if room.name in deadlines and row['sensor_valid'] and room.mode!='manual':
                        command={'status':'hold_until_scheduled_verification'}
                    else:
                        command=c.request(room.key,row['co2'],row['observed_at'],stamp(seconds),
                                          sensor_valid=row['sensor_valid'],predicted_ventilation=bool(ml and ml['ventilation']['prediction']))
                    if command['status']=='mock_command_created':
                        current_commands[room.name]=command['command_id']
                        acknowledged=room.apply_ventilation(command['desired'])
                        event={'at':seconds,'room':room.name,'event':'virtual_ventilation_command',
                               'desired':command['desired'],'co2':row['co2'],'ml_prediction':ml['ventilation']['prediction'],
                               'ack_delivered':acknowledged,'command_id':command['command_id']}
                        if acknowledged:
                            event['ack_status']=c.ack(room.key,command['command_id'],room.ventilation,stamp(seconds+1))
                            deadlines[room.name]=seconds+1+480
                        events.append(event)
                    samples.append({**row,'simulation_seconds':seconds,'mode':room.mode,
                                    'virtual_ventilation_on':room.ventilation,
                                    'ml_environment_suitable':ml['environment']['prediction'] if ml else None,
                                    'ml_ventilation_needed':ml['ventilation']['prediction'] if ml else None,
                                    'controller_status':command['status']})
                ranking=recommend_ml(bundle,observations,stamp(seconds))
                recommendations.append({'simulation_seconds':seconds,**ranking})
            c.db.executescript('''
                CREATE TABLE simulation_samples(id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE simulation_events(id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
            ''')
            import json
            c.db.executemany('INSERT INTO simulation_samples(payload) VALUES (?)',
                             [(json.dumps(r,ensure_ascii=False),) for r in samples])
            c.db.executemany('INSERT INTO simulation_events(payload) VALUES (?)',
                             [(json.dumps(e,ensure_ascii=False),) for e in events])
            export=c.export()
        finally:
            c.close()
        if out_dir:
            (out_dir/'simulation.db').write_bytes(database.read_bytes())
    summary={}
    for room in rooms:
        part=[r for r in samples if r['room']==room.name]
        summary[room.name]={'mode':room.mode,'initial_co2':part[0]['co2'],'final_co2':part[-1]['co2'],
                            'minimum_co2':min(r['co2'] for r in part),'final_temp':part[-1]['temp'],
                            'final_humi':part[-1]['humi'],'final_light':part[-1]['light'],
                            'ever_recommended':any(any(r['room']==room.name for r in t['rankings']) for t in recommendations),
                            'verification':[e for e in events if e['room']==room.name and e['event']=='remeasurement']}
    return {'origin':'fully_virtual_closed_loop_simulation','duration_seconds':1800,'step_seconds':30,
            'assumptions':{'outdoor_co2_ppm':420,'generation_ppm_per_person_per_minute':5,
                           'baseline_air_changes_per_hour':.2,'ventilation_air_changes_per_hour':6,
                           'thermal_humidity_time_constant_minutes':4,'lighting_time_constant_minutes':.25,
                           'setpoints':{'temp':23,'humi':50,'light':400}},
            'rooms':summary,'samples':samples,'events':events,'recommendations':recommendations,'database_export':export}
