# -*- coding: utf-8 -*-
"""Upgrade hygiene for the historical ClinicOne Treatment Session draft.

This migration is intentionally conservative:
- it repairs placeholder/duplicate technical session numbers before the new
  Odoo 19 uniqueness constraint is applied;
- it normalizes impossible negative quantities while leaving an audit note on
  affected lines;
- it binds a pre-existing historical sequence to the new stable XML-ID when
  possible, preventing duplicate sequence definitions during upgrade.
"""


def _table_exists(cr, table_name):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.tables
         WHERE table_schema = current_schema()
           AND table_name = %s
        """,
        [table_name],
    )
    return bool(cr.fetchone())


def _column_exists(cr, table_name, column_name):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = %s
           AND column_name = %s
        """,
        [table_name, column_name],
    )
    return bool(cr.fetchone())


def _repair_session_numbers(cr):
    table = "clinic_treatment_session"
    if not _table_exists(cr, table):
        return

    cr.execute(
        """
        UPDATE clinic_treatment_session
           SET name = 'TS-MIG/' || id::text
         WHERE name IS NULL
            OR btrim(name) = ''
            OR name IN ('New', '/')
        """
    )

    cr.execute(
        """
        SELECT company_id, name, array_agg(id ORDER BY id)
          FROM clinic_treatment_session
         GROUP BY company_id, name
        HAVING count(*) > 1
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
    table = "clinic_treatment_session_stage"
    if not _table_exists(cr, table):
        return

    cr.execute(
        """
        SELECT company_id, name, array_agg(id ORDER BY id)
          FROM clinic_treatment_session_stage
         GROUP BY company_id, name
        HAVING count(*) > 1
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
    table = "clinic_treatment_session_line"
    if not _table_exists(cr, table):
        return

    if not (
        _column_exists(cr, table, "quantity")
        and _column_exists(cr, table, "consumed_qty")
    ):
        return

    note_column = _column_exists(cr, table, "note_internal")

    if note_column:
        cr.execute(
            """
            UPDATE clinic_treatment_session_line
               SET note_internal = concat_ws(
                       E'\n',
                       NULLIF(note_internal, ''),
                       '[Migration 19.0.2.0.0] Negative quantity normalized to zero.'
                   ),
                   quantity = GREATEST(quantity, 0),
                   consumed_qty = GREATEST(consumed_qty, 0)
             WHERE quantity < 0
                OR consumed_qty < 0
            """
        )
    else:
        cr.execute(
            """
            UPDATE clinic_treatment_session_line
               SET quantity = GREATEST(quantity, 0),
                   consumed_qty = GREATEST(consumed_qty, 0)
             WHERE quantity < 0
                OR consumed_qty < 0
            """
        )


def _bind_existing_sequence_xmlid(cr):
    if not _table_exists(cr, "ir_sequence"):
        return

    cr.execute(
        """
        SELECT id
          FROM ir_sequence
         WHERE code = 'clinic_treatment_session.session'
         ORDER BY company_id NULLS FIRST, id
         LIMIT 1
        """
    )
    row = cr.fetchone()
    if not row:
        return

    sequence_id = row[0]

    cr.execute(
        """
        SELECT 1
          FROM ir_model_data
         WHERE module = 'clinic_treatment_session'
           AND name = 'seq_treatment_session'
        """
    )
    if cr.fetchone():
        return

    cr.execute(
        """
        INSERT INTO ir_model_data
                    (module, name, model, res_id, noupdate,
                     create_uid, create_date, write_uid, write_date)
             VALUES ('clinic_treatment_session',
                     'seq_treatment_session',
                     'ir.sequence',
                     %s,
                     TRUE,
                     1,
                     NOW(),
                     1,
                     NOW())
        """,
        [sequence_id],
    )


def migrate(cr, version):
    del version
    _repair_session_numbers(cr)
    _repair_stage_names(cr)
    _normalize_negative_line_quantities(cr)
    _bind_existing_sequence_xmlid(cr)
