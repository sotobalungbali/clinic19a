# -*- coding: utf-8 -*-
"""Move legacy stored Referral company settings into bootstrap-safe config.

Safe both when the old res_company columns exist and when they were never
created.
"""


LEGACY_COLUMNS = {
    "clinic_referral_default_valid_days": (
        "default_valid_days",
        lambda value: str(value if value is not None else 90),
    ),
    "clinic_referral_require_source": (
        "require_source",
        lambda value: "True" if value else "False",
    ),
    "clinic_referral_require_program_for_reward": (
        "require_program_for_reward",
        lambda value: "True" if value is not False else "False",
    ),
}


def _column_exists(cr, column_name):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = 'res_company'
           AND column_name = %s
        """,
        [column_name],
    )
    return bool(cr.fetchone())


def _set_parameter(cr, key, value):
    cr.execute(
        """
        UPDATE ir_config_parameter
           SET value = %s,
               write_uid = 1,
               write_date = NOW()
         WHERE key = %s
        """,
        [value, key],
    )
    if cr.rowcount:
        return

    cr.execute(
        """
        INSERT INTO ir_config_parameter
                    (key, value, create_uid, create_date, write_uid, write_date)
             VALUES (%s, %s, 1, NOW(), 1, NOW())
        """,
        [key, value],
    )


def migrate(cr, version):
    del version

    for column_name, (setting_name, serializer) in LEGACY_COLUMNS.items():
        if not _column_exists(cr, column_name):
            continue

        cr.execute('SELECT id, "%s" FROM res_company' % column_name)
        for company_id, raw_value in cr.fetchall():
            key = "clinic_referral.%s.company_%s" % (
                setting_name,
                company_id,
            )
            _set_parameter(cr, key, serializer(raw_value))

