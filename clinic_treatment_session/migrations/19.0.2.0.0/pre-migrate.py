
# -*- coding: utf-8 -*-
"""Conservative historical upgrade hygiene retained from 19.0.2.0.2."""


def _table_exists(cr, table_name):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = current_schema() AND table_name = %s
        """,
        [table_name],
    )
    return bool(cr.fetchone())


def _column_exists(cr, table_name, column_name):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s AND column_name = %s
        """,
        [table_name, column_name],
    )
    return bool(cr.fetchone())


def _repair_session_numbers(cr):
    if not _table_exists(cr, "clinic_treatment_session"):
        return
    cr.execute(
        """
        UPDATE clinic_treatment_session
           SET name = 'TS-MIG/' || id::text
         WHERE name IS NULL OR btrim(name) = '' OR name IN ('New', '/')
        """
    )
    cr.execute(
        """
        SELECT company_id, name, array_agg(id ORDER BY id)
          FROM clinic_treatment_session
         GROUP BY company_id, name HAVING count(*) > 1
        """
    )
    for _company_id, name, ids in cr.fetchall():
        for record_id in ids[1:]:
            cr.execute(
                """
                UPDATE clinic_treatment_session
                   SET name = %s || '/MIG-' || id::text
                 WHERE id = %s
                """,
                [name, record_id],
            )


def _repair_stage_names(cr):
    if not _table_exists(cr, "clinic_treatment_session_stage"):
        return
    cr.execute(
        """
        SELECT company_id, name, array_agg(id ORDER BY id)
          FROM clinic_treatment_session_stage
         GROUP BY company_id, name HAVING count(*) > 1
        """
    )
    for _company_id, name, ids in cr.fetchall():
        for record_id in ids[1:]:
            cr.execute(
                """
                UPDATE clinic_treatment_session_stage
                   SET name = %s || ' (Migrated ' || id::text || ')'
                 WHERE id = %s
                """,
                [name, record_id],
            )


def _normalize_negative_line_quantities(cr):
    if not _table_exists(cr, "clinic_treatment_session_line"):
        return
    if _column_exists(cr, "clinic_treatment_session_line", "quantity"):
        cr.execute(
            "UPDATE clinic_treatment_session_line SET quantity = 0 WHERE quantity < 0"
        )
    if _column_exists(cr, "clinic_treatment_session_line", "consumed_qty"):
        cr.execute(
            "UPDATE clinic_treatment_session_line SET consumed_qty = 0 WHERE consumed_qty < 0"
        )


def migrate(cr, version):
    del version
    _repair_session_numbers(cr)
    _repair_stage_names(cr)
    _normalize_negative_line_quantities(cr)
