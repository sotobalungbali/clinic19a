"""Build/runtime compatibility checks for the exact ClinicOne suite contract."""

import hashlib

from .constants import (
    AUTHORITATIVE_SOURCE_FINGERPRINT,
    EXPECTED_SUITE_FINGERPRINT,
    EXPECTED_SUITE_VERSIONS,
)


class SourceFingerprintService:
    """Compare the installed ClinicOne modules with the source used to build clinic_demo."""

    def __init__(self, env):
        self.env = env

    @staticmethod
    def canonical_fingerprint(version_vector):
        canonical = "\n".join(
            f"{name}={version_vector.get(name, '')}"
            for name in sorted(version_vector)
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def runtime_version_vectors(self):
        """Return source-on-disk versions, database-installed versions, and states.

        Odoo 19 keeps these historical field names for compatibility:
        ``installed_version`` is the latest manifest version found on disk, while
        ``latest_version`` is the version recorded as installed in the database.
        """
        names = sorted(EXPECTED_SUITE_VERSIONS)
        modules = self.env["ir.module.module"].search([("name", "in", names)])
        by_name = {module.name: module for module in modules}

        source_vector = {}
        database_vector = {}
        states = {}
        for name in names:
            module = by_name.get(name)
            if not module:
                source_vector[name] = ""
                database_vector[name] = ""
                states[name] = "missing"
                continue
            source_vector[name] = str(module.installed_version or "")
            database_vector[name] = str(module.latest_version or "")
            states[name] = module.state
        return source_vector, database_vector, states

    @staticmethod
    def _mismatches(actual_vector):
        return {
            name: {
                "expected": expected,
                "actual": actual_vector.get(name, ""),
            }
            for name, expected in EXPECTED_SUITE_VERSIONS.items()
            if actual_vector.get(name, "") != expected
        }

    def check_compatibility(self, run=None):
        source_vector, database_vector, states = self.runtime_version_vectors()
        missing = [
            name for name in sorted(EXPECTED_SUITE_VERSIONS)
            if states.get(name) != "installed"
        ]
        source_mismatches = self._mismatches(source_vector)
        database_mismatches = self._mismatches(database_vector)

        source_suite_fingerprint = self.canonical_fingerprint(source_vector)
        database_suite_fingerprint = self.canonical_fingerprint(database_vector)

        build_source_mismatch = bool(
            run and run.source_fingerprint != AUTHORITATIVE_SOURCE_FINGERPRINT
        )
        compatible = not (
            missing
            or source_mismatches
            or database_mismatches
            or build_source_mismatch
        )

        messages = []
        if build_source_mismatch:
            messages.append(
                "Demo Run source fingerprint does not match this clinic_demo build."
            )
        if missing:
            messages.append("Modules not installed/ready: " + ", ".join(missing))
        if source_mismatches:
            detail = ", ".join(
                f"{name} expected {data['expected']} / source {data['actual'] or '-'}"
                for name, data in sorted(source_mismatches.items())
            )
            messages.append("Source-on-disk version mismatch: " + detail)
        if database_mismatches:
            detail = ", ".join(
                f"{name} expected {data['expected']} / database {data['actual'] or '-'}"
                for name, data in sorted(database_mismatches.items())
            )
            messages.append(
                "Database-installed version mismatch (upgrade may be pending): " + detail
            )
        if not messages:
            messages.append(
                "ClinicOne source and database-installed versions match the clinic_demo build contract."
            )

        result = {
            "compatible": compatible,
            "state": "compatible" if compatible else "blocked",
            "message": "\n".join(messages),
            "source_suite_fingerprint": source_suite_fingerprint,
            "database_suite_fingerprint": database_suite_fingerprint,
            "expected_suite_fingerprint": EXPECTED_SUITE_FINGERPRINT,
            "missing": missing,
            "source_mismatches": source_mismatches,
            "database_mismatches": database_mismatches,
        }

        if run:
            run.write({
                "source_suite_fingerprint": source_suite_fingerprint,
                "database_suite_fingerprint": database_suite_fingerprint,
                "compatibility_state": result["state"],
                "compatibility_message": result["message"],
            })
        return result
