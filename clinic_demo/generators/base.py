"""Human-readable contract for bounded ClinicOne demo generators."""


class BaseDemoGenerator:
    key = None
    phase = None
    sequence = 10
    depends_on = ()
    scenario_keys = ()
    owned_models = ()

    def generate(self, ctx, scenario):
        raise NotImplementedError

    def validate(self, ctx, scenario):
        return []

    def repair_missing(self, ctx, scenario):
        raise NotImplementedError

    def reset(self, ctx, scenario):
        raise NotImplementedError
