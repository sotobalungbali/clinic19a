"""L1-L8 population evidence. Technical report availability is not sufficiency."""
import json
from odoo import fields
from collections import Counter
from .journey_read_context import read_model, actor_key

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
EXCEPTION_MODELS = frozenset({
    'clinic.incident', 'clinic.quality.check', 'clinic.feedback.escalation',
})
REPORTING_MODELS = frozenset(TRANSACTIONS) | EXCEPTION_MODELS

# Expansion acceptance now requires the declared domain scale, not token floors.
DOMAIN_MINIMUMS = {
    'booking.booking': 500, 'clinic.billing.invoice': 500,
    'clinic.insurance.authorization': 120, 'membership.contract': 120,
    'clinic.treatment.product.usage': 500, 'clinic.wallet.transaction': 500,
    'clinic.procedure.session': 500,
}

def assess_population(population, exceptions):
    """Return explicit deficits; token records can never pass enterprise density."""
    missing=[model for model,entry in population.items() if entry['count']<DOMAIN_MINIMUMS.get(model,500)]
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
    # All counts come from unique run-bound source records.  References are
    # grouped by model and declared reader, then fetched in bounded ORM batches.
    # This keeps normal ACL/record rules while avoiding one exists/read query
    # per provenance row on enterprise populations.
    population={model:dict(count=0,months=Counter(),states=Counter(),dimensions=Counter()) for model in TRANSACTIONS}
    seen=set();bound_seen=set();exceptions=0;errors=[];masters=0;events=0
    groups={}
    for ref in run.reference_ids:
        identity=(ref.model_name,ref.res_id)
        if identity in seen:continue
        seen.add(identity)
        # Integrity of every non-reporting master/child is owned by its already
        # PASS bounded journey.  Reporting Sufficiency measures only the
        # declared L1-L8 source and exception populations; it must not turn an
        # unrelated child reader into a second whole-dataset validator.
        if ref.record_status!='bound':
            if ref.model_name in REPORTING_MODELS:
                errors.append(f'{ref.demo_key}: reporting provenance is {ref.record_status}')
            continue
        bound_seen.add(identity)
        if ref.model_name not in REPORTING_MODELS:
            if 'log' in ref.model_name or 'event' in ref.model_name:events+=1
            else:masters+=1
            continue
        try:
            groups.setdefault((ref.model_name,actor_key(ref)),[]).append(ref)
        except Exception as exc:errors.append(f'{ref.demo_key}: {exc}')

    def relation_id(value):
        if isinstance(value,(tuple,list)):
            return value[0] if value else False
        return getattr(value,'id',value)

    for (_model_name,_reader),refs in groups.items():
        representative=refs[0]
        try:
            Model=read_model(run,representative)
            ids=list(dict.fromkeys(ref.res_id for ref in refs))
            records=Model.browse(ids).exists()
            records.check_access('read')
            field_names=[]
            if 'company_id' in Model._fields:field_names.append('company_id')
            if representative.model_name in TRANSACTIONS:
                field_names += [name for name in TRANSACTIONS[representative.model_name]
                                if name in Model._fields]
            if representative.model_name=='clinic.quality.check' and 'overall_result' in Model._fields:
                field_names.append('overall_result')
            values={value['id']:value for value in records.read(list(dict.fromkeys(field_names)))}
            for ref in refs:
                value=values.get(ref.res_id)
                if not value:
                    errors.append(f'{ref.demo_key}: referenced record is missing')
                    continue
                company=relation_id(value.get('company_id'))
                if company and company!=run.company_id.id:
                    errors.append(f'{ref.demo_key}: Company mismatch')
                    continue
                if ref.model_name in population:
                    date_field,state_field,dimension=TRANSACTIONS[ref.model_name];item=population[ref.model_name]
                    item['count']+=1
                    date_value=value.get(date_field)
                    if date_value:item['months'][str(date_value)[:7]]+=1
                    if state_field in Model._fields:item['states'][str(value.get(state_field))]+=1
                    dimension_value=relation_id(value.get(dimension))
                    if dimension in Model._fields and dimension_value:item['dimensions'][str(dimension_value)]+=1
                elif ref.model_name=='clinic.incident':exceptions+=1
                elif ref.model_name=='clinic.quality.check':exceptions+=int(value.get('overall_result')=='fail')
                elif ref.model_name=='clinic.feedback.escalation':exceptions+=1
        except Exception as exc:
            errors.extend(f'{ref.demo_key}: {exc}' for ref in refs)
    levels=assess_population(population,exceptions)
    passed=not errors and all(item['state']=='PASS' for item in levels.values())
    result={'levels':levels,'source_populations':population,'domain_minimums':DOMAIN_MINIMUMS,'exceptions':exceptions,'master_and_other_records':masters,
            'event_records':events,'unique_bound_records':len(bound_seen),'errors':errors,
            'scope_contract':'L1-L8 reads the seven declared transaction populations and three exception families. Other records are integrity-validated by their 137 bounded journeys.',
            'limitations':'Counts are provenance-bound records, not unbound child/event totals. PASS here proves minimum density only; owner KPI/relationship checks and full readiness remain mandatory.',
            'minimum_policy':'Population v1: at least 500 observations per routine domain; 120 authorizations/enrollments; 3 dimensions, 2 states, 12 populated months; at least 5 exception cases. Exact batch recipes and owner validations must also PASS.'}
    run.write({'reporting_checked_at': fields.Datetime.now(), 'reporting_status':'pass' if passed else 'fail','reporting_evidence':json.dumps(result,sort_keys=True,indent=2)})
    return passed





















