"""One ordered execution registry, retaining every existing generator contract."""
from dataclasses import dataclass
from .generator_registry import GENERATOR_REGISTRY
from .scenario_registry import ScenarioRegistry
from .journey_model_owners import MODEL_OWNER_ADDONS

SOURCE_FAMILIES = {
    'source.insurance': ('FIN-INS', 'Insurance authorization', 'clinic_insurance_authorization', 'clinic.insurance.authorization'),
    'source.membership': ('OPS-MEM', 'Membership enrollment', 'clinic_membership', 'membership.contract'),
    'source.inventory': ('OPS-INV', 'Receipt and clinical consumption', 'clinic_inventory', 'clinic.treatment.product.usage'),
    'source.wallet': ('OPS-WALLET', 'Wallet top-up and accounting', 'clinic_wallet', 'clinic.wallet.transaction'),
    'source.procedure': ('CLN-PROC', 'Procedure execution and events', 'clinic_encounter', 'clinic.procedure.session'),
}

SOURCE_MODELS = {
    'FIN-INS': ('clinic.insurance.authorization','clinic.insurance.policy','clinic.insurance.authorization.line'),
    'OPS-MEM': ('membership.contract',),
    'OPS-INV': ('clinic.treatment.product.usage','clinic.treatment.product.usage.line','stock.move','stock.move.line','stock.location','product.product','product.template','product.category'),
    'OPS-WALLET': ('clinic.wallet.transaction','clinic.wallet','account.move','account.move.line','account.account','account.journal'),
    'CLN-PROC': ('clinic.procedure.session','clinic.execution.log'),
}

@dataclass(frozen=True)
class Journey:
    key: str
    sequence: int
    name: str
    owner: str
    primary_model: str
    models: tuple
    dependencies: tuple
    master_prompt: str
    generator: object = None
    family: str = ''
    expected_records: str = ''
    generation_callable: str = ''
    validation_callable: str = ''
    identity_policy: str = 'Run-scoped DEMO key / canonical reference; never numeric ID as identity'
    scope_policy: str = 'Run company and owner branch rules, explicit allowed_company_ids'
    reset_policy: str = 'Existing reference ownership and owner reset/reverse/retain policy'
    workflow_policy: str = 'Existing owner API; parent and children remain one aggregate'
    validation_policy: str = 'Reference identity/scope + existing generator semantic/relational validator'
    idempotency_policy: str = 'Validate and adopt existing evidence before any creation'


def ordered_journeys():
    GENERATOR_REGISTRY.validate()
    items = {}
    for generator in GENERATOR_REGISTRY.all():
        models = tuple(generator.owned_models)
        deps = tuple(generator.depends_on)
        if generator.key == 'management.reports':
            deps = tuple(dict.fromkeys((*deps, *SOURCE_FAMILIES)))
        items[generator.key] = Journey(
            generator.key, generator.sequence, generator.key.replace('.', ' / '),
            MODEL_OWNER_ADDONS.get(models[0], 'clinic_demo') if models else 'clinic_demo', ('clinic.encounter' if generator.key == 'operations.encounter' else models[0]) if models else 'validation evidence', models,
            deps, 'MP-' + generator.phase.split('_')[0], generator,
            expected_records='; '.join(ScenarioRegistry.get(key).golden_refs for key in generator.scenario_keys),
            generation_callable=generator.__name__+'.generate', validation_callable=generator.__name__+'.validate',
        )
    for index,(key,(family,name,owner,model)) in enumerate(SOURCE_FAMILIES.items()):
        items[key] = Journey(key, 2000+index, name, owner, model, SOURCE_MODELS[family],
                             ('operations.future_pipeline',), 'MP-11/16/18/21', family=family, expected_records='Run-owned '+family+' source aggregate and children',
                             generation_callable='ReportSourceJourneys.generate_family',validation_callable='ReportSourceJourneys.validate(families)')
    return topological_order(items)


def topological_order(items):
    result=[]; done=set()
    while len(done)<len(items):
        ready=[item for key,item in items.items() if key not in done and set(item.dependencies)<=done]
        if not ready:
            raise ValueError('Journey dependency graph has a cycle or unknown dependency')
        for item in sorted(ready,key=lambda item:(item.sequence,item.key)):
            result.append(item);done.add(item.key)
    return tuple(result)








