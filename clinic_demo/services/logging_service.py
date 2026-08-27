"""Structured logging helper with conservative text sanitization."""

import re


_SENSITIVE_RE = re.compile(
    r"(?i)(password|passwd|token|secret|authorization)\s*[:=]\s*([^\s,;]+)"
)


class DemoLoggingService:
    def __init__(self, env):
        self.env = env

    @staticmethod
    def sanitize(value, limit=4000):
        text = str(value or "")
        text = _SENSITIVE_RE.sub(r"\1=[REDACTED]", text)
        return text[:limit]

    def log(
        self,
        run,
        level,
        message,
        checkpoint=None,
        phase_key=None,
        generator_key=None,
        scenario_key=None,
        operation=None,
        model_name=None,
        demo_key=None,
        exception_class=None,
        traceback_excerpt=None,
    ):
        run.ensure_one()
        return self.env["clinic.demo.log"].create({
            "run_id": run.id,
            "checkpoint_id": checkpoint.id if checkpoint else False,
            "level": level,
            "phase_key": phase_key or False,
            "generator_key": generator_key or False,
            "scenario_key": scenario_key or False,
            "operation": operation or False,
            "model_name": model_name or False,
            "demo_key": demo_key or False,
            "message": self.sanitize(message),
            "exception_class": exception_class or False,
            "traceback_excerpt": self.sanitize(traceback_excerpt),
        })
