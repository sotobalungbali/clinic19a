




"""Small execution context passed to bounded domain generators."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationContext:
    env: object
    run: object
    profile: str
    scenario: object
    seed_service: object
    reference_service: object
    safe_mode_service: object
    checkpoint_service: object
    logging_service: object









