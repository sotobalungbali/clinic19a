


# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Normalize old membership rows and assert the authoritative schema exists."""
    cr.execute("SELECT to_regclass('public.membership_plan')")
    if cr.fetchone()[0]:
        cr.execute("""UPDATE membership_plan SET state = CASE WHEN active IS TRUE THEN 'active' ELSE 'retired' END WHERE state IS NULL OR state = ''""")
    required = [
        'membership_plan','membership_plan_benefit','membership_contract','membership_contract_benefit',
        'membership_usage','membership_voucher','membership_point_tx','membership_hold','membership_integration_event',
    ]
    missing=[]
    for table in required:
        cr.execute("SELECT to_regclass(%s)", (f'public.{table}',))
        if not cr.fetchone()[0]: missing.append(table)
    if missing:
        raise RuntimeError('clinic_membership schema incomplete after upgrade: ' + ', '.join(missing))
    _logger.info('[clinic_membership] Upgrade schema verified: %s tables', len(required))


