# -*- coding: utf-8 -*-
"""Preserve legacy stored res.company package settings before proxy conversion."""

import logging

_logger = logging.getLogger(__name__)

_COLUMNS = (
    "clinic_pkg_default_pricing_id",
    "clinic_pkg_default_policy_id",
    "clinic_pkg_voucher_prefix",
    "clinic_pkg_voucher_code_length",
    "clinic_pkg_voucher_valid_days",
    "clinic_pkg_auto_expire_allocations",
    "clinic_pkg_auto_expire_vouchers",
)

_SUFFIXES = {
    "clinic_pkg_default_pricing_id": "default_pricing_id",
    "clinic_pkg_default_policy_id": "default_policy_id",
    "clinic_pkg_voucher_prefix": "voucher_prefix",
    "clinic_pkg_voucher_code_length": "voucher_code_length",
    "clinic_pkg_voucher_valid_days": "voucher_valid_days",
    "clinic_pkg_auto_expire_allocations": "auto_expire_allocations",
    "clinic_pkg_auto_expire_vouchers": "auto_expire_vouchers",
}


def _existing_columns(cr):
    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = 'res_company'
           AND column_name = ANY(%s)
        """,
        (list(_COLUMNS),),
    )
    return {row[0] for row in cr.fetchall()}


def _set_param(cr, key, value):
    cr.execute(
        """
        INSERT INTO ir_config_parameter
            (key, value, create_uid, create_date, write_uid, write_date)
        VALUES (%s, %s, 1, NOW(), 1, NOW())
        ON CONFLICT (key)
        DO UPDATE SET
            value = EXCLUDED.value,
            write_uid = 1,
            write_date = NOW()
        """,
        (key, value),
    )


def migrate(cr, version):
    existing = _existing_columns(cr)
    if not existing:
        _logger.info(
            "clinic_package migration: no legacy res_company package columns exist; "
            "company-setting preservation is a safe no-op."
        )
        return

    ordered = ["id"] + [column for column in _COLUMNS if column in existing]
    cr.execute("SELECT %s FROM res_company" % ", ".join(ordered))
    rows = cr.fetchall()

    migrated = 0
    for row in rows:
        values = dict(zip(ordered, row))
        company_id = values.pop("id")
        for field_name, value in values.items():
            if value is None:
                continue
            if isinstance(value, bool):
                value = "1" if value else "0"
            key = "clinic_package.company.%s.%s" % (
                company_id,
                _SUFFIXES[field_name],
            )
            _set_param(cr, key, str(value))
            migrated += 1

    _logger.info(
        "clinic_package migration preserved %s legacy company configuration values.",
        migrated,
    )
