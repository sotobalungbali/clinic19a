# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Preserve semantics of policies created by the unfinished 19.0.1.0.0 addon.

    Legacy policies had no workflow state: `active=True` meant operational.
    The new governance state defaults to Draft, so an upgrade must promote only
    rows carrying the legacy required `trigger` contract back to Active.
    """
    cr.execute(
        """
        UPDATE clinic_audit_policy
           SET state = 'active'
         WHERE active IS TRUE
           AND trigger IS NOT NULL
           AND (state IS NULL OR state = 'draft')
        """
    )
