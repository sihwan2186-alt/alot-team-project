"""Small supervised CART classifiers using only the Python standard library.

Labels are explicit simulation design rules, not independently measured truth.
The holdout measures imitation of those rules on unseen synthetic rooms only.
"""
import hashlib
import json
import math
import random

ENV_FEATURES = ['temp_deviation', 'humidity_deviation', 'co2', 'light', 'noise_db', 'crowding']
VENT_FEATURES = ['co2', 'co2_trend_ppm_per_min']


def environment_features(row):
    result = [abs(float(row['temp'])-23), abs(float(row['humi'])-50), float(row['co2']),
              float(row['light']), float(row['noise_db']), float(row['current_people'])/float(row['assumed_capacity'])]
    if not all(math.isfinite(x) for x in result):
        raise ValueError('Finite ML features required')
    return result


def environment_label(row):
    return int(20 <= row['temp'] <= 26 and 40 <= row['humi'] <= 60 and row['co2'] < 890
               and row['light'] >= 300 and row['noise_db'] <= 45
               and row['current_people']/row['assumed_capacity'] <= .75)


def ventilation_label(row):
    return int(row['co2'] >= 890 or (row['co2'] > 850 and row['co2_trend_ppm_per_min'] >= 12))


class Tree:
    def __init__(self, depth=8, min_leaf=6, root=None):
        self.depth, self.min_leaf, self.root = depth, min_leaf, root

    def fit(self, x, y):
        if not x or len(x) != len(y) or any(len(row) != len(x[0]) or not all(math.isfinite(v) for v in row) for row in x):
            raise ValueError('Invalid training matrix')
        def build(indices, depth):
            n=len(indices); positives=sum(y[i] for i in indices)
            node={'probability':positives/n, 'samples':n}
            if depth == 0 or positives in (0,n) or n < 2*self.min_leaf:
                return node
            base=2*positives*(n-positives)/n
            best=None
            for feature in range(len(x[0])):
                order=sorted(indices,key=lambda i:x[i][feature]); left_positive=0
                for cut in range(1,n):
                    left_positive+=y[order[cut-1]]
                    if cut < self.min_leaf or n-cut < self.min_leaf or x[order[cut-1]][feature] == x[order[cut]][feature]:
                        continue
                    right_positive=positives-left_positive
                    loss=2*left_positive*(cut-left_positive)/cut + 2*right_positive*(n-cut-right_positive)/(n-cut)
                    if loss < base-1e-12 and (best is None or loss < best[0]-1e-12):
                        threshold=(x[order[cut-1]][feature]+x[order[cut]][feature])/2
                        best=(loss,feature,threshold,order[:cut],order[cut:])
            if best is not None:
                _,feature,threshold,left,right=best
                node.update(feature=feature,threshold=threshold,left=build(left,depth-1),right=build(right,depth-1))
            return node
        self.root=build(list(range(len(x))),self.depth)
        return self

    def predict_one(self, row):
        if not self.root or not all(math.isfinite(v) for v in row):
            raise ValueError('Model and finite input required')
        node=self.root; path=[]
        while 'feature' in node:
            f=node['feature']; left=row[f] <= node['threshold']
            path.append({'feature_index':f,'value':row[f],'threshold':node['threshold'],'branch':'left' if left else 'right'})
            node=node['left'] if left else node['right']
        return {'prediction':int(node['probability'] >= .5),'leaf_positive_fraction':node['probability'],
                'leaf_samples':node['samples'],'path':path}


def metrics(truth, predicted):
    tp=sum(a==b==1 for a,b in zip(truth,predicted)); tn=sum(a==b==0 for a,b in zip(truth,predicted))
    fp=sum(a==0 and b==1 for a,b in zip(truth,predicted)); fn=sum(a==1 and b==0 for a,b in zip(truth,predicted))
    return dict(n=len(truth),tp=tp,tn=tn,fp=fp,fn=fn,
                precision=tp/(tp+fp) if tp+fp else 0,recall=tp/(tp+fn) if tp+fn else 0,
                f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,accuracy=(tp+tn)/len(truth))


def generate_dataset(seed=20261019):
    rng=random.Random(seed); data=[]
    # Separate virtual rooms per split: no room key appears in two splits.
    for room in range(120):
        split='train' if room < 72 else 'validation' if room < 96 else 'test'
        for tick in range(24):
            comfortable=rng.random() < .5
            row=dict(virtual_room=f'ml-room-{room:03}',split=split,tick=tick,
                     temp=rng.uniform(20,26) if comfortable else rng.uniform(17,30),
                     humi=rng.uniform(40,60) if comfortable else rng.uniform(25,75),
                     co2=rng.uniform(450,880) if comfortable else rng.uniform(450,1500),
                     light=rng.uniform(300,700) if comfortable else rng.uniform(50,700),
                     noise_db=rng.uniform(28,45) if comfortable else rng.uniform(28,65),
                     current_people=rng.randint(0,6) if comfortable else rng.randint(0,8),assumed_capacity=8,
                     co2_trend_ppm_per_min=rng.uniform(-40,40))
            row.update(environment_suitable=environment_label(row),ventilation_needed=ventilation_label(row))
            data.append(row)
    return data


def train_bundle():
    rows=generate_dataset(); models={}; scores={}
    train=[r for r in rows if r['split']=='train']
    for name,features,label in [('environment',environment_features,'environment_suitable'),
                                ('ventilation',lambda r:[r[k] for k in VENT_FEATURES],'ventilation_needed')]:
        model=Tree().fit([features(r) for r in train],[r[label] for r in train])
        models[name]=model.root; scores[name]={}
        for split in ('train','validation','test'):
            part=[r for r in rows if r['split']==split]
            scores[name][split]=metrics([r[label] for r in part],[model.predict_one(features(r))['prediction'] for r in part])
    return dict(version=1,algorithm='standard_library_CART_gini_depth8_minleaf6',seed=20261019,
                origin='synthetic_design_rule_labels_not_real_user_or_device_truth',
                feature_order={'environment':ENV_FEATURES,'ventilation':VENT_FEATURES},models=models,
                dataset_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),
                evaluation=scores,split_rooms={'train':72,'validation':24,'test':24},
                split_rows={'train':1728,'validation':576,'test':576}),rows


def infer(bundle,row):
    env=Tree(root=bundle['models']['environment']).predict_one(environment_features(row))
    vent=Tree(root=bundle['models']['ventilation']).predict_one([float(row[k]) for k in VENT_FEATURES])
    return {'environment':env,'ventilation':vent}
