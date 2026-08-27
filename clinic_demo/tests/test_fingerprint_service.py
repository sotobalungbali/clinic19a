from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.constants import (
    EXPECTED_SUITE_FINGERPRINT,
    EXPECTED_SUITE_VERSIONS,
)
from ..services.fingerprint_service import SourceFingerprintService


@tagged("post_install", "-at_install")
class TestSourceFingerprintService(TransactionCase):

    def test_expected_version_vector_fingerprint_is_stable(self):
        actual = SourceFingerprintService.canonical_fingerprint(
            EXPECTED_SUITE_VERSIONS
        )
        self.assertEqual(actual, EXPECTED_SUITE_FINGERPRINT)

    def test_expected_suite_has_41_clinicone_modules(self):
        self.assertEqual(len(EXPECTED_SUITE_VERSIONS), 41)
        self.assertIn("clinic_referral", EXPECTED_SUITE_VERSIONS)
        self.assertIn("clinic_treatment_session", EXPECTED_SUITE_VERSIONS)
