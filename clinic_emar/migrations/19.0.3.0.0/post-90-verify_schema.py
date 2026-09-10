# -*- coding: utf-8 -*-
"""Post-upgrade schema assertions for ClinicOne eMAR 19.0.3.0.0."""

import logging

# Keep post-upgrade verification deployable on stock Odoo CE installations:
# do not require the separately distributed odoo.upgrade.util helper library.
from odoo import SUPERUSER_ID
from odoo.api import Environment


_logger = logging.getLogger(__name__)

_EXPECTED_TABLES = (
    "clinic_emar_medication_profile",
    "clinic_emar_prescription",
    "clinic_emar_medication_line",
    "clinic_emar_order",
    "clinic_emar_schedule",
    "clinic_emar_administration",
    "clinic_emar_alert",
    "clinic_emar_reschedule_wizard",
)


def migrate(cr, version):
    # Ensure Odoo's schema synchronization actually materialized every owned
    # eMAR table.  Fail the update with one precise error instead of allowing a
    # partially updated database to produce unrelated HTTP 500 errors later.
    cr.execute(
        """
        SELECT table_name
          FROM information_schema.tables
         WHERE table_schema = current_schema()
           AND table_name = ANY(%s)
        """,
        [list(_EXPECTED_TABLES)],
    )
    present = {row[0] for row in cr.fetchall()}
    missing = sorted(set(_EXPECTED_TABLES) - present)
    if missing:
        raise RuntimeError(
            "clinic_emar schema synchronization incomplete; missing table(s): %s"
            % ", ".join(missing)
        )

    env = Environment(cr, SUPERUSER_ID, {})
    Company = env["res.company"]
    dangerous_stored = [
        name
        for name in (
            "emar_default_warehouse_id",
            "emar_auto_generate_schedules",
            "emar_require_patient_scan",
            "emar_require_product_scan",
            "emar_require_double_check_high_alert",
            "emar_overdue_grace_minutes",
        )
        if name in Company._fields and Company._fields[name].store
    ]
    if dangerous_stored:
        raise RuntimeError(
            "clinic_emar schema-safe contract violated; res.company field(s) "
            "must be non-stored: %s" % ", ".join(dangerous_stored)
        )

    _logger.info(
        "[clinic_emar] Post-upgrade schema assertions PASS for %s owned tables.",
        len(_EXPECTED_TABLES),
    )

