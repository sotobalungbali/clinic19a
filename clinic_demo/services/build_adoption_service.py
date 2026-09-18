"""Explicit supported build lineage, independent of mutable run version labels.

Compatibility migration updates control metadata only. Completed business
checkpoints keep their original source fingerprint and execution history.
"""
import json

from .historical_checkpoint_contracts import historical_scenarios, is_historical_checkpoint

LEGACY_SOURCE = '8e0d2be47034b5841642ba056df294825f71a6040f7f27b77cd6da32ef417ab2'
V48_SOURCE = 'b087fa986bed9b26d1ee87b10d02f277ffd4557dad05f81d236fdcf552b8fb0e'
V49_SOURCE = 'bfd0a2595ea03a6128bfb87d1aa129926c09414d97628ca06aefce9eef4f2cf7'
V50_SOURCE = 'bc1a2c4bbaae99e279c91c23f3ad5b8bd8da5e6d2960e84a397491134386755c'
V51_SOURCE = '7d2561b386c6526edba7af76e0287d2d438dec8a7c976bff9b97bd66a1c3aafe'
V52_SOURCE = 'cedb612b1b826c6db8d9cd34f174c3cf6ca67bbfb9c2fdf0c79d8020aec7d0e7'
V53_SOURCE = 'f61e5c5a23b01744e5cc3111e5f34dd6c2274014a2de8efd6013743987204a1c'
V54_SOURCE = 'dec6e50eb21ef44c85ad213cdef56b47f51382d3b79dbba07f1ef66541e5c9b0'
V55_SOURCE = '659b3a3a2b6ca2ab8423edc55f6fb1f4b5ae3cb331dc1011ea67e1c0d9929897'
V56_SOURCE = '161dbaeaa76a8611aa1008fe676c76fee26d6b9f7d9c8b4fa732801bd99c755c'
V57_SOURCE = '3b3f89fcf29667651849539fbc5f17fe0d46f7cc03f6e460995847ecd2b4e0d0'
V58_SOURCE = '13ccd2087b45bdbdd2449dab71a55c655ac691c652abe6c8b475e99f8229c59f'
V59_SOURCE = '8f01b48ec0c689129c5142a25c254211c35308761fd00b22d2dfc2174a48b110'
V60_SOURCE = '2180735b8e86e50c7c015f8edd5410bd959af066161e9cb32d91e0c06ceb8e78'
SUPPORTED_LINEAGE = {
    V60_SOURCE: frozenset({'19.0.1.0.60'}),
    V59_SOURCE: frozenset({'19.0.1.0.59'}),
    V58_SOURCE: frozenset({'19.0.1.0.58'}),
    V57_SOURCE: frozenset({'19.0.1.0.57'}),
    V56_SOURCE: frozenset({'19.0.1.0.56'}),
    V55_SOURCE: frozenset({'19.0.1.0.55'}),
    V54_SOURCE: frozenset({'19.0.1.0.54'}),
    V53_SOURCE: frozenset({'19.0.1.0.53'}),
    V52_SOURCE: frozenset({'19.0.1.0.52'}),
    V51_SOURCE: frozenset({'19.0.1.0.51'}),
    V50_SOURCE: frozenset({'19.0.1.0.50'}),
    V49_SOURCE: frozenset({'19.0.1.0.49'}),
    LEGACY_SOURCE: frozenset(f'19.0.1.0.{patch}' for patch in range(31, 48)),
    V48_SOURCE: frozenset({'19.0.1.0.48'}),
}


def adoption_issues(version, source, state, checkpoints, references, contracts):
    """Pure decision: explicit lineage + canonical evidence + dependency closure.

    More than one historical scenario checkpoint is permitted. Readiness is
    assessed separately; a failed acceptance gate is not a build mismatch.
    """
    issues = []
    if version not in SUPPORTED_LINEAGE.get(source, ()):
        issues.append(f'Unsupported predecessor version/source: {version!r} / {source!r}')
    if state not in {'draft', 'ready', 'failed'}:
        issues.append(f'Run is busy: {state}')
    done = set()
    for row in checkpoints:
        key = row['generator_key']
        contract = contracts.get(key)
        if not contract:
            issues.append(f'Unknown checkpoint generator: {key}')
            continue
        phase, scenarios, _dependencies = contract
        scenario = row['scenario_key']
        expected = f'{phase}:{key}:{scenario}'
        historical = is_historical_checkpoint(phase, key, scenario, row['checkpoint_key'], scenarios)
        canonical = scenario in scenarios and row['checkpoint_key'] == expected
        if row['phase_key'] != phase or not (canonical or historical):
            issues.append(f'Checkpoint contract mismatch: {row["checkpoint_key"]}')
        if historical and not any(ref['generator_key'] == key for ref in references):
            issues.append(f'Historical checkpoint has no owner provenance: {key}')
        if row['state'] == 'running':
            issues.append(f'Checkpoint still running: {key}')
        if row['state'] == 'done':
            done.add(key)
    # Source closure starts after all existing producers and consumers through
    # Analytics. MP23 can be pending/failed, and is resumed through the normal execution engine.
    if 'management.analytics' not in done:
        issues.append('management.analytics has no Done checkpoint; use progressive generation first')
    for key in sorted(done):
        missing = set(contracts[key][2]) - done
        if missing:
            issues.append(f'{key} has incomplete dependencies: {sorted(missing)}')
    if not references:
        issues.append('No dataset provenance exists')
    for row in references:
        if row['generator_key'] not in contracts:
            issues.append(f'Unknown reference producer: {row["generator_key"]}')
        if not row['demo_key'].startswith('DEMO-'):
            issues.append(f'Invalid reference identity: {row["demo_key"]}')
    return issues


def adopt_supported_build(run):
    from .constants import GENERATOR_VERSION, AUTHORITATIVE_SOURCE_FINGERPRINT, EXPECTED_SUITE_FINGERPRINT
    from .generator_registry import GENERATOR_REGISTRY
    from .fingerprint_service import SourceFingerprintService

    if run.source_fingerprint == AUTHORITATIVE_SOURCE_FINGERPRINT:
        return False
    contracts = {
        generator.key: (generator.phase, generator.scenario_keys, generator.depends_on)
        for generator in GENERATOR_REGISTRY.all()
    }
    checkpoints = [{field: row[field] for field in (
        'generator_key', 'phase_key', 'scenario_key', 'checkpoint_key', 'state'
    )} for row in run.checkpoint_ids]
    references = [{field: row[field] for field in ('generator_key', 'demo_key')}
                  for row in run.reference_ids]
    issues = adoption_issues(run.generator_version, run.source_fingerprint, run.state,
                             checkpoints, references, contracts)
    # Never adopt merely because a historical source hash is recognized.
    # Disk manifests AND installed database module versions must match this build.
    runtime = SourceFingerprintService(run.env).check_compatibility()
    if not runtime['compatible']:
        issues.append(runtime['message'])
    if issues:
        run.patch_compatibility_status = 'Build adoption blocked: ' + '; '.join(issues)
        return False
    previous = {'version': run.generator_version, 'source': run.source_fingerprint,
                'suite': run.expected_suite_fingerprint}
    run.write({
        'generator_version': GENERATOR_VERSION,
        'source_fingerprint': AUTHORITATIVE_SOURCE_FINGERPRINT,
        'expected_suite_fingerprint': EXPECTED_SUITE_FINGERPRINT,
        'patch_compatibility_status': 'Supported source lineage and canonical checkpoint dependencies verified; business history retained.',
    })
    run._log_control_event('info', 'adopt_build_contract', json.dumps({
        'previous': previous,
        'adopted': {'version': GENERATOR_VERSION, 'source': AUTHORITATIVE_SOURCE_FINGERPRINT,
                    'suite': EXPECTED_SUITE_FINGERPRINT},
        'checkpoint_rows_retained': len(checkpoints),
        'done_generators': sorted({row['generator_key'] for row in checkpoints if row['state'] == 'done'}),
        'reference_rows_retained': len(references),
    }, sort_keys=True))
    return True












