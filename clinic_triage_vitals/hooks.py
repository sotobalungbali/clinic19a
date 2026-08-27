
# -*- coding: utf-8 -*-
"""Installation hooks for ClinicOne Triage & Vitals.

The patient form extension is intentionally installed defensively.

Why:
    clinic_triage_vitals depends on clinic_patient, but an existing database may
    have clinic_patient installed from an older source revision that does not yet
    contain the XML-ID ``clinic_patient.view_clinic_patient_form``. Odoo does not
    automatically upgrade an already-installed dependency when another addon is
    installed.

The core triage models, menus, security and workflows must never be blocked by
that optional presentation-layer mismatch.
"""

import logging
from pathlib import Path

from lxml import etree


_logger = logging.getLogger(__name__)

PATIENT_EXTENSION_XMLID = "view_clinic_patient_form_triage_vitals"
EXPECTED_PATIENT_FORM_XMLID = "clinic_patient.view_clinic_patient_form"

EXPECTED_PATIENT_MENU_XMLID = "clinic_patient.menu_root"
TRIAGE_ROOT_MENU_XMLID = "clinic_triage_vitals.menu_clinic_triage_root"


def _load_patient_extension_arch():
    """Read the human-maintainable inheritance template and return its arch."""
    template_path = Path(__file__).resolve().parent / "views" / "patient_triage_views.xml"
    root = etree.parse(str(template_path)).getroot()

    records = root.xpath(
        ".//record[@id='view_clinic_patient_form_triage_vitals'][@model='ir.ui.view']"
    )
    if not records:
        raise ValueError("Patient triage extension template record was not found.")

    arch_fields = records[0].xpath("./field[@name='arch']")
    if not arch_fields:
        raise ValueError("Patient triage extension template has no arch field.")

    children = [
        etree.tostring(child, encoding="unicode")
        for child in arch_fields[0]
    ]
    return "<data>%s</data>" % "".join(children)


def _find_patient_form_view(env):
    """Return a usable clinic.patient primary form without requiring one XML-ID."""
    view = env.ref(EXPECTED_PATIENT_FORM_XMLID, raise_if_not_found=False)
    if view:
        return view

    # Database/source drift fallback:
    # find the primary form already registered for clinic.patient.
    return env["ir.ui.view"].sudo().search(
        [
            ("model", "=", "clinic.patient"),
            ("type", "=", "form"),
            ("mode", "=", "primary"),
            ("active", "=", True),
        ],
        order="priority, id",
        limit=1,
    )


def _parent_supports_patient_extension(parent_view):
    """Check that the target contains the two anchors used by our template."""
    combined_arch = parent_view._get_combined_arch()
    return bool(
        combined_arch.xpath(".//div[@name='button_box']")
        and combined_arch.xpath(".//notebook")
    )


def _get_existing_extension(env):
    """Locate the optional extension through XML-ID or by its stable view name."""
    xml_data = env["ir.model.data"].sudo().search(
        [
            ("module", "=", "clinic_triage_vitals"),
            ("name", "=", PATIENT_EXTENSION_XMLID),
            ("model", "=", "ir.ui.view"),
        ],
        limit=1,
    )
    if xml_data:
        view = env["ir.ui.view"].sudo().browse(xml_data.res_id).exists()
        if view:
            return view, xml_data

    view = env["ir.ui.view"].sudo().search(
        [
            ("name", "=", "clinic.patient.form.triage.vitals"),
            ("model", "=", "clinic.patient"),
        ],
        limit=1,
    )
    return view, xml_data


def _ensure_patient_triage_view(env):
    """Install/update the optional patient-form integration if a parent exists."""
    parent_view = _find_patient_form_view(env)
    if not parent_view:
        _logger.warning(
            "ClinicOne Triage: clinic.patient has no primary form view in the "
            "database. Triage installation will continue without patient-form "
            "smart buttons; triage remains available from its own menus."
        )
        return False

    if not _parent_supports_patient_extension(parent_view):
        _logger.warning(
            "ClinicOne Triage: clinic.patient form view %s does not expose the "
            "button_box/notebook anchors expected by the optional extension. "
            "Triage installation will continue without extending that form.",
            parent_view.display_name,
        )
        return False

    arch = _load_patient_extension_arch()
    view, xml_data = _get_existing_extension(env)

    values = {
        "name": "clinic.patient.form.triage.vitals",
        "model": "clinic.patient",
        "type": "form",
        "mode": "extension",
        "priority": 50,
        "inherit_id": parent_view.id,
        "arch": arch,
        "active": True,
    }

    if view:
        view.write(values)
    else:
        view = env["ir.ui.view"].sudo().create(values)

    if not xml_data:
        env["ir.model.data"].sudo().create(
            {
                "module": "clinic_triage_vitals",
                "name": PATIENT_EXTENSION_XMLID,
                "model": "ir.ui.view",
                "res_id": view.id,
                "noupdate": False,
            }
        )
    elif xml_data.res_id != view.id:
        xml_data.write({"res_id": view.id})

    _logger.info(
        "ClinicOne Triage: patient form extension installed on parent view %s.",
        parent_view.display_name,
    )
    return True



def _find_patient_root_menu(env):
    """Return a usable Clinic Patient root menu without requiring one XML-ID."""
    menu = env.ref(EXPECTED_PATIENT_MENU_XMLID, raise_if_not_found=False)
    if menu:
        return menu

    # Database/source drift fallback:
    # inspect menu records already owned by clinic_patient. Prefer a root menu
    # because a downstream addon must not guess a nested operational menu.
    xml_rows = env["ir.model.data"].sudo().search(
        [
            ("module", "=", "clinic_patient"),
            ("model", "=", "ir.ui.menu"),
        ]
    )
    menus = env["ir.ui.menu"].sudo().browse(xml_rows.mapped("res_id")).exists()
    root_menus = menus.filtered(lambda record: not record.parent_id)
    if len(root_menus) == 1:
        return root_menus

    # If an older revision exposed multiple roots, prefer the stable ClinicOne
    # label and otherwise leave Triage as its own root rather than guessing.
    named = root_menus.filtered(lambda record: record.name == "ClinicOne")
    return named[:1]


def _ensure_triage_menu_parent(env):
    """Attach the local Triage root below Patient when a compatible menu exists.

    The XML file deliberately creates a valid local root with no cross-addon
    parent.  This prevents a stale installed dependency from blocking module
    installation merely because one menu XML-ID is absent.
    """
    triage_menu = env.ref(TRIAGE_ROOT_MENU_XMLID, raise_if_not_found=False)
    if not triage_menu:
        _logger.warning(
            "ClinicOne Triage: local root menu %s is unavailable; menu "
            "re-parenting was skipped.",
            TRIAGE_ROOT_MENU_XMLID,
        )
        return False

    patient_root = _find_patient_root_menu(env)
    if not patient_root:
        _logger.warning(
            "ClinicOne Triage: no compatible clinic_patient root menu exists "
            "in this database. Triage will remain available as its own root "
            "menu; business functions are unaffected."
        )
        return False

    if triage_menu.parent_id != patient_root:
        triage_menu.sudo().write({"parent_id": patient_root.id})

    _logger.info(
        "ClinicOne Triage: root menu attached below patient menu %s.",
        patient_root.display_name,
    )
    return True


def _post_init_hook(env):
    """Install optional cross-addon presentation integrations defensively."""
    try:
        # The savepoint prevents a partially-created optional view from leaking
        # into the transaction if the parent layout differs from expectations.
        with env.cr.savepoint():
            _ensure_patient_triage_view(env)
    except Exception:
        # This integration is presentation-only. Core triage models, security,
        # menus and workflows must remain installable even on an older database.
        _logger.exception(
            "ClinicOne Triage: optional clinic.patient form integration could "
            "not be installed. Core triage installation remains valid."
        )

    try:
        # Menu hierarchy is presentation/navigation only. A stale sibling
        # XML-ID must never block installation of the clinical workflow.
        with env.cr.savepoint():
            _ensure_triage_menu_parent(env)
    except Exception:
        _logger.exception(
            "ClinicOne Triage: optional clinic.patient menu integration could "
            "not be applied. Triage remains available from its local root menu."
        )
