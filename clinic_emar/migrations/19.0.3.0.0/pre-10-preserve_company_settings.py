# -*- coding: utf-8 -*-
"""Preserve legacy stored res.company eMAR settings before schema-safe migration.

Release 19.0.3.0.0 deliberately changes the six public ``res.company.emar_*``
fields from stored columns to non-stored, company-scoped proxies backed by
``ir.config_parameter``.  If an older database already has the columns, copy
their values first.  If the columns never existed (the runtime failure that
triggered this repair), this migration is a no-op.
"""

import logging

# Use only Odoo core runtime APIs here. The optional odoo.upgrade.util helper
# library is not guaranteed to be installed in Community/Windows deployments.
from odoo import SUPERUSER_ID
from odoo.api import Environment


_logger = logging.getLogger(__name__)

_PREFIX = "clinic_emar.company"

_LEGACY_COLUMNS = {
    "emar_default_warehouse_id": ("default_warehouse_id", "many2one"),
    "emar_auto_generate_schedules": ("auto_generate_schedules", "bool"),
    "emar_require_patient_scan": ("require_patient_scan", "bool"),
    "emar_require_product_scan": ("require_product_scan", "bool"),
    "emar_require_double_check_high_alert": (
        "require_double_check_high_alert",
        "bool",
    ),
    "emar_overdue_grace_minutes": ("overdue_grace_minutes", "int"),
}


def _parameter_value(kind, value):
    if kind == "bool":
        return "1" if bool(value) else "0"
    if kind == "int":
        return str(max(0, int(value or 0)))
    if kind == "many2one":
        return str(int(value)) if value else ""
    return str(value or "")


def migrate(cr, version):
    env = Environment(cr, SUPERUSER_ID, {})
    Param = env["ir.config_parameter"].sudo()

    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = 'res_company'
           AND column_name = ANY(%s)
        """,
        [list(_LEGACY_COLUMNS)],
    )
    present = {row[0] for row in cr.fetchall()}
    if not present:
        _logger.info(
            "[clinic_emar] No legacy res_company eMAR columns found; "
            "schema-safe configuration migration is a no-op."
        )
        return

    columns = ["id"] + sorted(present)
    query = "SELECT %s FROM res_company" % ", ".join(
        '"%s"' % name for name in columns
    )
    cr.execute(query)

    migrated = 0
    for row in cr.fetchall():
        values = dict(zip(columns, row))
        company_id = values["id"]
        for field_name in sorted(present):
            suffix, kind = _LEGACY_COLUMNS[field_name]
            key = f"{_PREFIX}.{company_id}.{suffix}"

            # Respect an already-migrated explicit parameter.  This makes the
            # script idempotent across repeated module-upgrade attempts.
            existing = Param.search([("key", "=", key)], limit=1)
            if existing:
                continue

            Param.set_param(key, _parameter_value(kind, values[field_name]))
            migrated += 1

    _logger.info(
        "[clinic_emar] Preserved %s legacy company setting value(s) in "
        "schema-safe company-scoped parameters.",
        migrated,
    )

