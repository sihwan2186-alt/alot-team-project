"""Persist operational review using validation evidence only, leaving selected model untouched."""
from pathlib import Path
import json

out=Path(__file__).resolve().parent/'artifacts'
selection=json.loads((out/'selection.json').read_text(encoding='utf-8'))
selected=selection['validation'][selection['selected']]['recommendation']
baseline=selection['validation']['persistence']['recommendation']
adopt=(selected['top1_regret'] is not None and selected['top1_regret']<=baseline['top1_regret'] and
       selected['future_violation_fraction']<=baseline['future_violation_fraction'])
decision={'use_forecast_for_ranking':adopt,'ranking_key':'prediction' if adopt else 'score_current',
    'evidence':'validation recommendation regret and future violation; test not consulted',
    'note':'conservative operational review distinct from original MAE model-selection rule',
    'selected_validation':selected,'baseline_validation':baseline}
(out/'operational_decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2),encoding='utf-8')
print('Forecast ranking adoption:',adopt)
