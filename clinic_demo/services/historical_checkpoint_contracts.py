"""Explicit persisted checkpoint aliases; never expand new-generation scenarios.

The resource/queue tuple is evidenced by the v45 run reported on 14 September 2026.
The normal resource scenario remains SCN-BOOKING-TODAY-01. Historical rows are
retained and reused by identity, including on retry; no business row is reset.
"""
HISTORICAL_SCENARIOS = {
    ('12_resources', 'resources.rooms_devices', 'SCN-BOOKING-TODAY-01'):
        ('SCN-QUEUE-01',),
}


def historical_scenarios(phase, generator, canonical_scenarios):
    return tuple(alias for scenario in canonical_scenarios
                 for alias in HISTORICAL_SCENARIOS.get((phase, generator, scenario), ()))


def is_historical_checkpoint(phase, generator, scenario, checkpoint_key, canonical_scenarios):
    # Older retries could refresh scenario metadata without renaming the key.
    # Admit only the exact known legacy key with its old OR canonical scenario.
    return any(
        checkpoint_key == f'{phase}:{generator}:{alias}' and scenario in (canonical, alias)
        for canonical in canonical_scenarios
        for alias in HISTORICAL_SCENARIOS.get((phase, generator, canonical), ())
    )











