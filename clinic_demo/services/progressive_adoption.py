"""Small, pure helpers for stage-aware progressive build adoption."""


def prompt_stage_adoption(run, completed_generators, sequence):
    """Return exact progressive/failed-prefix adoption facts for one stage."""
    stage_generators = set(sequence)
    generated = set(run.reference_ids.mapped("generator_key"))
    checkpoints = set(run.checkpoint_ids.mapped("generator_key"))
    previous_complete = all(
        run.checkpoint_ids.filtered(
            lambda checkpoint, key=key: (
                checkpoint.generator_key == key and checkpoint.state == "done"
            )
        )
        for key in completed_generators
    )
    progressive = (
        run.state in {"draft", "ready"}
        and previous_complete
        and checkpoints == completed_generators
        and generated <= completed_generators
        and not (checkpoints & stage_generators)
        and not (generated & stage_generators)
    )
    failed_keys = {
        key for key in sequence
        if run.checkpoint_ids.filtered(
            lambda checkpoint, candidate=key: (
                checkpoint.generator_key == candidate and checkpoint.state == "failed"
            )
        )
    }
    failed_key = next(iter(failed_keys)) if len(failed_keys) == 1 else False
    failed_index = sequence.index(failed_key) if failed_key else -1
    prefix = set(sequence[:failed_index]) if failed_key else set()
    suffix = set(sequence[failed_index:]) if failed_key else stage_generators
    prefix_complete = bool(failed_key) and all(
        run.checkpoint_ids.filtered(
            lambda checkpoint, key=key: (
                checkpoint.generator_key == key and checkpoint.state == "done"
            )
        )
        for key in prefix
    )
    repair = (
        run.state == "failed"
        and previous_complete
        and prefix_complete
        and checkpoints == completed_generators | prefix | {failed_key}
        and generated <= completed_generators | prefix
        and not (generated & suffix)
    )
    return progressive, repair, failed_key









