"""L1-L8 population evidence. Technical report availability is not sufficiency."""
import json
from collections import Counter
from .journey_read_context import read_model

# Conservative minimum observations, not instructions to fabricate filler.
# Each report must also have monthly and dimensional spread. Master Prompt's
# fixed temporal window is retained; volume expansion never changes its dates.
TRANSACTIONS = {
    'booking.booking': ('start_datetime','state','patient_id'),
    'clinic.billing.invoice': ('invoice_date','state','patient_id'),
    'clinic.insurance.authorization': ('request_date','state','patient_id'),
    'membership.contract': ('start_date','state','patient_id'),
    'clinic.treatment.product.usage': ('date_usage','state','warehouse_id'),
    'clinic.wallet.transaction': ('date','state','wallet_id'),
    'clinic.procedure.session': ('date_start','state','encounter_id'),
}
LEVELS = {
    'L1': ('Operational / Transaction','transactions'),
    'L2': ('Exception & Control','exceptions'),
    'L3': ('Management / Tactical','distribution'),
    'L4': ('KPI / Performance','distribution'),
    'L5': ('Analytical / Decision-Support','history'),
    'L6': ('Executive / Scorecard','distribution'),
    'L7': ('Compliance / Audit','exceptions'),
    'L8': ('Stakeholder / External','distribution'),
}

def assess_population(population, exceptions):
    """Return explicit deficits; token records can never pass enterprise density."""
    missing=[model for model,entry in population.items() if entry['count']<20]
    spread=[model for model,entry in population.items() if len(entry['dimensions'])<3 or len(entry['states'])<2]
    history=[model for model,entry in population.items() if len(entry['months'])<12]
    gates={
        'transactions':not missing,
        'distribution':not missing and not spread,
        'history':not missing and not history,
        'exceptions':exceptions>=5,
    }
    return {key:{'name':name,'state':'PASS' if gates[gate] else 'FAIL',
                 'reason':{'transactions':missing,'distribution':missing+spread,'history':missing+history,'exceptions':[] if exceptions>=5 else ['Fewer than five exception cases']}[gate]}
            for key,(name,gate) in LEVELS.items()}


def evaluate(run):
    # All counts come from unique run-bound source records. No global production
    # populations and no duplicate counting of alternate provenance keys.
    population={model:dict(count=0,months=Counter(),states=Counter(),dimensions=Counter()) for model in TRANSACTIONS}
    seen=set();exceptions=0;errors=[];masters=0;events=0
    for ref in run.reference_ids:
        identity=(ref.model_name,ref.res_id)
        if identity in seen:continue
        seen.add(identity)
        try:
            rec=read_model(run,ref).browse(ref.res_id).exists()
            if not rec:continue
            rec.check_access('read')
            if 'company_id' in rec._fields and rec.company_id and rec.company_id!=run.company_id:raise ValueError('Company mismatch')
            if ref.model_name in population:
                date_field,state_field,dimension=TRANSACTIONS[ref.model_name];item=population[ref.model_name]
                item['count']+=1
                date_value=rec[date_field] if date_field in rec._fields else False
                if date_value:item['months'][str(date_value)[:7]]+=1
                if state_field in rec._fields:item['states'][str(rec[state_field])]+=1
                if dimension in rec._fields and rec[dimension]:item['dimensions'][str(rec[dimension].id)]+=1
            elif ref.model_name == 'clinic.incident':
                exceptions+=1
            elif ref.model_name == 'clinic.quality.check':
                exceptions+=int(rec.overall_result == 'fail')
            elif ref.model_name == 'clinic.feedback.escalation':
                exceptions+=1
            elif 'log' in ref.model_name or 'event' in ref.model_name:events+=1
            else:masters+=1
        except Exception as exc:errors.append(f'{ref.demo_key}: {exc}')
    levels=assess_population(population,exceptions)
    passed=not errors and all(item['state']=='PASS' for item in levels.values())
    result={'levels':levels,'source_populations':population,'exceptions':exceptions,'master_and_other_records':masters,
            'event_records':events,'unique_bound_records':len(seen),'errors':errors,
            'limitations':'Counts are provenance-bound records, not unbound child/event totals. PASS here proves minimum density only; owner KPI/relationship checks and full readiness remain mandatory.',
            'minimum_policy':'20 observations per tracked domain, 3 dimensions, 2 states, 12 populated months; at least 5 exception cases. Conservative technical floor, not the preferred enterprise volume target.'}
    run.write({'reporting_status':'pass' if passed else 'fail','reporting_evidence':json.dumps(result,sort_keys=True,indent=2)})
    return passed








