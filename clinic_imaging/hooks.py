# -*- coding: utf-8 -*-
"""Installation hooks for optional ClinicOne presentation integration.

The business dependency on ``clinic_base`` is hard, but presentation XML-IDs can
legitimately drift between an installed database and the current source tree.
The Imaging root menu is therefore created locally and re-parented only when a
compatible ClinicOne root menu is present.
"""

import logging

_logger = logging.getLogger(__name__)


def _post_init_hook(env):
    menu = env.ref("clinic_imaging.menu_clinic_imaging_root", raise_if_not_found=False)
    if not menu:
        return

    parent = env.ref("clinic_base.menu_root", raise_if_not_found=False)
    if not parent:
        # Fallback: locate a root menu owned by clinic_base without making its
        # exact presentation XML-ID an installation-time dependency.
        data = env["ir.model.data"].sudo().search([
            ("module", "=", "clinic_base"),
            ("model", "=", "ir.ui.menu"),
        ], limit=20)
        candidate_ids = [res_id for res_id in data.mapped("res_id") if res_id]
        if candidate_ids:
            parent = env["ir.ui.menu"].sudo().browse(candidate_ids).filtered(
                lambda item: not item.parent_id
            )[:1]

    if parent:
        menu.sudo().parent_id = parent.id
    else:
        _logger.info(
            "Clinic Imaging root menu left standalone because no compatible "
            "ClinicOne parent menu was found."
        )
