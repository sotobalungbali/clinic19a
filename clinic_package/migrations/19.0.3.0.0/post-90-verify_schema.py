# -*- coding: utf-8 -*-
"""Fail the upgrade clearly if the package schema is incomplete."""

import logging

_logger = logging.getLogger(__name__)

_REQUIRED_TABLES = (
    "clinic_package",
    "clinic_package_line",
    "clinic_package_allocation",
    "clinic_package_allocation_line",
    "clinic_package_usage",
    "clinic_package_voucher",
    "clinic_package_integration_event",
)

_REQUIRED_USAGE_COLUMNS = (
    "emar_order_id",
    "emar_schedule_id",
    "emar_administration_id",
)


def migrate(cr, version):
    missing_tables = []
    for table in _REQUIRED_TABLES:
        cr.execute("SELECT to_regclass(%s)", (table,))
        if not cr.fetchone()[0]:
            missing_tables.append(table)

    if missing_tables:
        raise RuntimeError(
            "clinic_package schema verification failed; missing table(s): %s"
            % ", ".join(missing_tables)
        )

    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = 'clinic_package_usage'
           AND column_name = ANY(%s)
        """,
        (list(_REQUIRED_USAGE_COLUMNS),),
    )
    existing_columns = {row[0] for row in cr.fetchall()}
    missing_columns = sorted(set(_REQUIRED_USAGE_COLUMNS) - existing_columns)
    if missing_columns:
        raise RuntimeError(
            "clinic_package schema verification failed; "
            "clinic_package_usage missing column(s): %s"
            % ", ".join(missing_columns)
        )

    _logger.info(
        "clinic_package schema verification PASS: core tables and eMAR linkage columns exist."
    )
