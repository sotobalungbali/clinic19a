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
V61_SOURCE = '6904ebf6d62ae5f60371fd91287d99b00eba10addb2d7f952602fb0165ef5c2b'
V62_SOURCE = '966196761e66e9f3bbd89b62da8f96614e7f594b2201bfb125942cd96cdf6bf3'
V63_SOURCE = '7b8d6c35823ca72ba4a1201dd8619db7f74089c640eb2da03c1969401e563331'
V64_SOURCE = 'f4824014fa721f7bdd8897cd0c19f999d2f25bde2a341672d1f5151b9132ca35'
V65_SOURCE = '9a44df67d97340518c9f2a8fa52740604fa40293b16105976a0d8b2657e4021e'
V66_SOURCE = '43f34a938070769898ca707b4709048d0b36ad1463c9c5812a3690c04f7601d1'
V67_SOURCE = '9bb362cc260bd2fe971cf7bcbfd0ca349f5d4d00291714dadb29a14bb2cee1ba'
V68_SOURCE = '2b3e4a55763fc4df66a7afac5578e37e1c0f136cf5d8fb366670bc7c13423f4a'
V69_SOURCE = 'c5a95e772934589098798f16104bc0304af4dd188cc7fca87a4766636b13d6ac'
V70_SOURCE = '61a48a00add40aca872e9e0faad19593a41443c232e143b52ae70c227690b1da'
V71_SOURCE = 'a524b7543be8e158b5058017083be778abf6c8f4d001519bd78d1511cc8ebe63'
V72_SOURCE = '333045234c874a5bc6279778ce50d32c24a8fd9e810f1451028720278cc9914d'
V73_SOURCE = 'aa911d159d54212e8c9cb2f699d2c2e004d7903fe7d5e67fc2d132b416e9c4ed'
V74_SOURCE = 'd755105adadb2907585be0e5940578b0f89ee3604dc1c4e1ac2388558b8f5b66'
V75_SOURCE = 'c32b8ad5699716828f0e02e1f78128831b5b56bb0f6e03643c1c3b9da0968009'
SUPPORTED_LINEAGE = {
    V75_SOURCE: frozenset({'19.0.1.0.75'}),
    V74_SOURCE: frozenset({'19.0.1.0.74'}),
    V73_SOURCE: frozenset({'19.0.1.0.73'}),
    V72_SOURCE: frozenset({'19.0.1.0.72'}),
    V71_SOURCE: frozenset({'19.0.1.0.71'}),
    V70_SOURCE: frozenset({'19.0.1.0.70'}),
    V69_SOURCE: frozenset({'19.0.1.0.69'}),
    V68_SOURCE: frozenset({'19.0.1.0.68'}),
    V67_SOURCE: frozenset({'19.0.1.0.67'}),
    V66_SOURCE: frozenset({'19.0.1.0.66'}),
    V65_SOURCE: frozenset({'19.0.1.0.65'}),
    V64_SOURCE: frozenset({'19.0.1.0.64'}),
    V63_SOURCE: frozenset({'19.0.1.0.63'}),
    V62_SOURCE: frozenset({'19.0.1.0.62'}),
    V61_SOURCE: frozenset({'19.0.1.0.61'}),
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















