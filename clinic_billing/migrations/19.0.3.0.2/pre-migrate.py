# -*- coding: utf-8 -*-
"""Repair legacy res.partner.credit_limit storage before Odoo 19 auto-init.

Historical ClinicOne billing code redeclared Odoo's core ``credit_limit`` field
as Monetary.  On databases where that produced a scalar numeric column,
Odoo 19 now expects the core field to be company-dependent JSONB and its
generic ALTER COLUMN cast fails (numeric -> jsonb).

This pre-migration converts the legacy scalar value to the Odoo 19 JSONB
contract while preserving the previous global value for every existing
company.  It is deliberately idempotent and does nothing when the column is
already JSONB.
"""

import logging

_logger = logging.getLogger(__name__)


def _column_udt(cr, table, column):
    cr.execute(
        """
        SELECT c.udt_name
          FROM information_schema.columns c
         WHERE c.table_schema = current_schema()
           AND c.table_name = %s
           AND c.column_name = %s
        """,
        (table, column),
    )
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    udt = _column_udt(cr, "res_partner", "credit_limit")
    if not udt:
        _logger.info(
            "[clinic_billing] res_partner.credit_limit does not exist yet; "
            "no legacy credit-limit migration required."
        )
        return
    if udt == "jsonb":
        _logger.info(
            "[clinic_billing] res_partner.credit_limit already uses JSONB; "
            "migration is idempotently skipped."
        )
        return

    # Accept the scalar numeric families that historical ClinicOne/Odoo
    # installations may have used.  Refuse unknown storage rather than
    # silently destroying data.
    numeric_udts = {
        "numeric", "float4", "float8", "int2", "int4", "int8",
    }
    if udt not in numeric_udts:
        raise RuntimeError(
            "ClinicOne cannot safely migrate res_partner.credit_limit from "
            f"PostgreSQL type {udt!r}; expected scalar numeric or jsonb."
        )

    cr.execute("SELECT id FROM res_company ORDER BY id")
    company_ids = [row[0] for row in cr.fetchall()]
    if not company_ids:
        raise RuntimeError(
            "ClinicOne cannot migrate res_partner.credit_limit because no "
            "res.company records exist."
        )

    # Build one JSONB object containing the previous scalar value under every
    # existing company key. Company ids are integers read from res_company, so
    # embedding them as SQL string literals is deterministic and injection-safe.
    object_args = []
    for company_id in company_ids:
        object_args.extend([f"'{int(company_id)}'", '"credit_limit"'])
    jsonb_expr = "jsonb_build_object(" + ", ".join(object_args) + ")"

    # Keep the same physical column instead of drop/rename, so database
    # dependencies remain attached. Odoo's failed generic cast used
    # ``credit_limit::jsonb``; this explicit USING expression creates the
    # company-keyed JSONB representation Odoo 19 expects.
    cr.execute(
        'ALTER TABLE "res_partner" ALTER COLUMN "credit_limit" DROP DEFAULT'
    )
    cr.execute(
        f"""
        ALTER TABLE "res_partner"
        ALTER COLUMN "credit_limit" TYPE jsonb
        USING (
            CASE
                WHEN "credit_limit" IS NULL THEN NULL
                ELSE {jsonb_expr}
            END
        )
        """
    )

    _logger.warning(
        "[clinic_billing] Migrated res_partner.credit_limit from %s to Odoo 19 "
        "company-dependent JSONB for %s existing companies.",
        udt,
        len(company_ids),
    )



