"""Human-readable contract for bounded ClinicOne demo generators."""


class BaseDemoGenerator:
    """One generator owns one bounded business responsibility."""

    key = None
    phase = None
    sequence = 10
    depends_on = ()
    scenario_keys = ()
    owned_models = ()
    required_groups = ()

    def generate(self, ctx, scenario):
        raise NotImplementedError

    def validate(self, ctx, scenario):
        return []

    def repair_missing(self, ctx, scenario):
        raise NotImplementedError

    def reset(self, ctx, scenario):
        raise NotImplementedError
