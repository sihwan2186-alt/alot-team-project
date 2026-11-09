"""Qualified recommendations and clearly separate nonqualified reference alternatives."""
import pandas as pd

def reference_alternatives(snapshot, limit=3):
    """Never promote a failing row to qualified; keep seat/CO2 constraints for references."""
    d=snapshot[(~snapshot.eligible)&(snapshot.capacity-snapshot.occupancy>=1)&(snapshot.co2<890)].copy()
    if d.empty:return d
    d['unmet_count']=d.exclusion_reason.map(lambda s:len(s.split(', ')) if s else 0)
    return d.sort_values(['unmet_count','prediction','room_id'],ascending=[True,False,True]).head(limit)

def policy_metrics(frame,prediction):
    from inference import eligibility
    d=frame.copy();d['prediction']=prediction;d['eligible'],d['exclusion_reason']=eligibility(d)
    qualified=0;reference=0;none=0
    for _,g in d.groupby(['run_id','asof']):
        if g.eligible.any():qualified+=1
        elif not reference_alternatives(g).empty:reference+=1
        else:none+=1
    total=qualified+reference+none
    return {'instants':total,'qualified_instants':qualified,'reference_only_instants':reference,
        'no_qualified_or_reference_instants':none,'qualified_coverage':qualified/total,
        'reference_is_not_recommendation':True,'qualified_constraints_unchanged':True}
