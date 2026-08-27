# -*- coding: utf-8 -*-
"""Defensive presentation hooks for ClinicOne Treatment Catalog.

The treatment catalog owns a valid local root menu. A fresh installation may
attach that root below the ClinicOne menu exposed by clinic_patient, but a
stale/missing sibling XML-ID must never block business-model installation.
"""

import logging

_logger = logging.getLogger(__name__)

EXPECTED_CLINICONE_MENU_XMLID = "clinic_patient.menu_root"
TREATMENT_ROOT_MENU_XMLID = "clinic_treatment_catalog.menu_treatment_catalog"


def _find_clinicone_root_menu(env):
    """Find a safe ClinicOne root without guessing a nested operational menu."""
    menu = env.ref(EXPECTED_CLINICONE_MENU_XMLID, raise_if_not_found=False)
    if menu:
        return menu

    xml_rows = env["ir.model.data"].sudo().search(
        [
            ("module", "=", "clinic_patient"),
            ("model", "=", "ir.ui.menu"),
        ]
    )
    menus = env["ir.ui.menu"].sudo().browse(xml_rows.mapped("res_id")).exists()
    roots = menus.filtered(lambda record: not record.parent_id)

    named = roots.filtered(lambda record: record.name == "ClinicOne")
    if len(named) == 1:
        return named
    if len(roots) == 1:
        return roots
    return env["ir.ui.menu"]


def _ensure_treatment_menu_parent(env):
    """Attach Treatment Catalog below ClinicOne only when the parent is safe."""
    treatment_root = env.ref(TREATMENT_ROOT_MENU_XMLID, raise_if_not_found=False)
    if not treatment_root:
        _logger.warning(
            "ClinicOne Treatment Catalog: local root menu %s is unavailable; "
            "optional menu re-parenting was skipped.",
            TREATMENT_ROOT_MENU_XMLID,
        )
        return False

    clinicone_root = _find_clinicone_root_menu(env)
    if not clinicone_root:
        _logger.warning(
            "ClinicOne Treatment Catalog: no compatible ClinicOne root menu "
            "exists. Treatment Catalog remains available as its own root menu."
        )
        return False

    if treatment_root.parent_id != clinicone_root:
        treatment_root.sudo().write({"parent_id": clinicone_root.id})

    _logger.info(
        "ClinicOne Treatment Catalog: root menu attached below %s.",
        clinicone_root.display_name,
    )
    return True


def _post_init_hook(env):
    """Apply optional navigation integration without risking core installation."""
    try:
        with env.cr.savepoint():
            _ensure_treatment_menu_parent(env)
    except Exception:
        _logger.exception(
            "ClinicOne Treatment Catalog: optional menu integration failed. "
            "Core treatment catalog installation remains valid."
        )
