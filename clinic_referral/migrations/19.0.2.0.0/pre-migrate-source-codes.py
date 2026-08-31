# -*- coding: utf-8 -*-
"""Prepare historical Referral Source codes before Odoo 19 UNIQUE creation.

The legacy draft called a sequence that was never loaded by its manifest. On
an already-used database, multiple sources can therefore carry the placeholder
``New``. The new Odoo 19 ``models.Constraint`` must not make such a database
un-upgradable, so only conflicting legacy placeholders/duplicates are assigned
a deterministic technical code based on their immutable database ID.
"""


def migrate(cr, version):
    del version

    cr.execute("SELECT to_regclass('clinic_referral_source')")
    if not cr.fetchone()[0]:
        return

    # Blank/placeholder codes are converted first. The ID suffix is stable and
    # does not pretend to be a business sequence number.
    cr.execute(
        """
        UPDATE clinic_referral_source
           SET code = 'LEGACY-' || LPAD(id::text, 8, '0')
         WHERE code IS NULL
            OR BTRIM(code) = ''
            OR LOWER(BTRIM(code)) = 'new'
        """
    )

    # If an old database already contains duplicate custom codes, preserve the
    # oldest row and give later rows a deterministic legacy suffix.
    cr.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY company_id, code
                       ORDER BY id
                   ) AS row_number
              FROM clinic_referral_source
        )
        UPDATE clinic_referral_source AS source
           SET code = LEFT(source.code, 45)
                      || '-LEGACY-'
                      || LPAD(source.id::text, 8, '0')
          FROM ranked
         WHERE ranked.id = source.id
           AND ranked.row_number > 1
        """
    )

