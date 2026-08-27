# -*- coding: utf-8 -*-
"""Installation-time integration helpers for clinic_consent_legal.

Presentation integration with sibling ClinicOne addons is deliberately
non-blocking.  The business models are hard dependencies, but their XML-ID
revision can differ in an already-installed database.  We therefore:
- keep all core Consent & Legal menus/views local and installable;
- optionally re-parent the local root menu under ClinicOne when available;
- optionally add smart UI extensions to clinic.treatment and clinic.appointment
  by discovering a compatible primary form at runtime.

No sibling addon is modified or force-upgraded.
"""

import logging

from odoo import _

_logger = logging.getLogger(__name__)


def _find_primary_form(env, model_name, preferred_xmlids=()):
    for xmlid in preferred_xmlids:
        view = env.ref(xmlid, raise_if_not_found=False)
        if view and view._name == "ir.ui.view" and view.model == model_name and view.type == "form":
            return view

    return env["ir.ui.view"].sudo().search(
        [
            ("model", "=", model_name),
            ("type", "=", "form"),
            ("mode", "=", "primary"),
            ("active", "=", True),
        ],
        order="priority, id",
        limit=1,
    )


def _upsert_view_xmlid(env, xml_name, values):
    """Create/update a local integration view and its XML-ID idempotently."""
    full_xmlid = f"clinic_consent_legal.{xml_name}"
    existing = env.ref(full_xmlid, raise_if_not_found=False)
    if existing:
        existing.sudo().write(values)
        return existing

    view = env["ir.ui.view"].sudo().create(values)
    env["ir.model.data"].sudo().create(
        {
            "module": "clinic_consent_legal",
            "name": xml_name,
            "model": "ir.ui.view",
            "res_id": view.id,
            "noupdate": False,
        }
    )
    return view


def _install_optional_form_extension(
    env,
    *,
    xml_name,
    view_name,
    model_name,
    preferred_xmlids=(),
    smart_button_xml="",
    notebook_page_xml="",
):
    parent = _find_primary_form(env, model_name, preferred_xmlids)
    if not parent:
        _logger.warning(
            "Consent & Legal UI integration skipped: no primary form for %s.",
            model_name,
        )
        return False

    arch = parent.arch_db or ""
    fragments = []

    if smart_button_xml and 'name="button_box"' in arch:
        fragments.append(
            '<xpath expr="//div[@name=\'button_box\']" position="inside">'
            + smart_button_xml
            + "</xpath>"
        )

    if notebook_page_xml and "<notebook" in arch:
        fragments.append(
            '<xpath expr="//notebook" position="inside">'
            + notebook_page_xml
            + "</xpath>"
        )

    if not fragments:
        _logger.warning(
            "Consent & Legal UI integration skipped for %s: compatible anchors not found.",
            model_name,
        )
        return False

    values = {
        "name": view_name,
        "model": model_name,
        "type": "form",
        "mode": "extension",
        "priority": 90,
        "inherit_id": parent.id,
        "arch_db": "<data>%s</data>" % "".join(fragments),
    }

    try:
        with env.cr.savepoint():
            _upsert_view_xmlid(env, xml_name, values)
        return True
    except Exception:
        _logger.exception(
            "Consent & Legal optional UI integration failed for %s; core addon remains installed.",
            model_name,
        )
        return False


def _reparent_root_menu(env):
    root = env.ref(
        "clinic_consent_legal.menu_consent_legal_root",
        raise_if_not_found=False,
    )
    parent = env.ref("clinic_base.menu_root", raise_if_not_found=False)
    if root and parent and root.parent_id != parent:
        try:
            with env.cr.savepoint():
                root.sudo().write({"parent_id": parent.id})
        except Exception:
            _logger.exception(
                "Could not re-parent Consent & Legal menu under ClinicOne; keeping local root."
            )


def _install_treatment_extension(env):
    smart = """
        <button name="action_view_consents" type="object"
                class="oe_stat_button" icon="fa-file-text-o">
            <field name="consent_count_total" widget="statinfo" string="Consents"/>
        </button>
        <button name="action_view_templates" type="object"
                class="oe_stat_button" icon="fa-copy">
            <field name="consent_count_signed" widget="statinfo" string="Signed"/>
        </button>
    """
    page = """
        <page string="Consent &amp; Legal" name="consent_legal">
            <group>
                <group string="Policy">
                    <field name="consent_required"/>
                    <field name="consent_required_timing"/>
                    <field name="consent_default_template_id"/>
                    <field name="consent_validity_days_override"/>
                    <field name="consent_autogenerate_on_booking"/>
                </group>
                <group string="Operational Snapshot">
                    <field name="consent_count_total" readonly="1"/>
                    <field name="consent_count_pending" readonly="1"/>
                    <field name="consent_count_signed" readonly="1"/>
                    <field name="consent_count_archived" readonly="1"/>
                    <field name="has_published_specific_template" readonly="1"/>
                </group>
            </group>
            <field name="consent_advisory" placeholder="Operational/legal notes for staff..."/>
            <field name="consent_template_ids" readonly="1">
                <list>
                    <field name="name"/>
                    <field name="title"/>
                    <field name="state"/>
                    <field name="effective_date"/>
                    <field name="consent_version"/>
                </list>
            </field>
        </page>
    """
    _install_optional_form_extension(
        env,
        xml_name="view_clinic_treatment_form_consent_legal_optional",
        view_name="clinic.treatment.form.consent.legal.optional",
        model_name="clinic.treatment",
        preferred_xmlids=(),
        smart_button_xml=smart,
        notebook_page_xml=page,
    )


def _install_appointment_extension(env):
    smart = """
        <button name="action_view_consent" type="object"
                class="oe_stat_button" icon="fa-file-text-o">
            <div class="o_stat_info">
                <span class="o_stat_text">Consent</span>
                <span class="o_stat_value"><field name="consent_status"/></span>
            </div>
        </button>
    """
    page = """
        <page string="Consent &amp; Legal" name="consent_legal">
            <group>
                <group string="Policy">
                    <field name="consent_policy"/>
                    <field name="consent_template_id"/>
                    <field name="consent_validity_days_override"/>
                </group>
                <group string="Status">
                    <field name="consent_required_effective" readonly="1"/>
                    <field name="consent_status" readonly="1"/>
                    <field name="consent_id" readonly="1"/>
                    <field name="consent_status_hint" readonly="1"/>
                </group>
            </group>
            <button name="action_create_consent" type="object"
                    string="Create Consent" class="btn-primary"
                    icon="fa-plus"/>
        </page>
    """
    _install_optional_form_extension(
        env,
        xml_name="view_clinic_appointment_form_consent_legal_optional",
        view_name="clinic.appointment.form.consent.legal.optional",
        model_name="clinic.appointment",
        preferred_xmlids=(),
        smart_button_xml=smart,
        notebook_page_xml=page,
    )


def _install_partner_extension(env):
    smart = """
        <button name="action_view_all_related_consents" type="object"
                class="oe_stat_button" icon="fa-file-text-o"
                invisible="is_company">
            <field name="consent_count" widget="statinfo" string="Consents"/>
        </button>
        <button name="action_view_pending_consents" type="object"
                class="oe_stat_button" icon="fa-clock-o"
                invisible="is_company or consent_pending_count == 0">
            <field name="consent_pending_count" widget="statinfo" string="Pending"/>
        </button>
    """
    page = """
        <page string="Consent &amp; Legal" name="consent_legal" invisible="is_company">
            <group>
                <group string="Consent Snapshot">
                    <field name="consent_count" readonly="1"/>
                    <field name="consent_pending_count" readonly="1"/>
                    <field name="consent_signed_count" readonly="1"/>
                    <field name="consent_guardian_count" readonly="1"/>
                </group>
                <group string="Latest Consent">
                    <field name="last_consent_id" readonly="1"/>
                    <field name="last_consent_signed_on" readonly="1"/>
                    <field name="consent_portal_opt_out"/>
                    <field name="consent_portal_url" readonly="1"/>
                </group>
            </group>
            <button name="action_request_new_consent" type="object"
                    string="Request New Consent" class="btn-primary" icon="fa-plus"/>
            <button name="action_open_portal_consents" type="object"
                    string="Open Portal" icon="fa-external-link"/>
            <separator string="Consent History"/>
            <field name="consent_form_ids" readonly="1">
                <list>
                    <field name="name"/>
                    <field name="title"/>
                    <field name="treatment_id"/>
                    <field name="signature_datetime"/>
                    <field name="expiry_date"/>
                    <field name="state"/>
                </list>
            </field>
        </page>
    """
    _install_optional_form_extension(
        env,
        xml_name="view_res_partner_form_consent_legal_optional",
        view_name="res.partner.form.consent.legal.optional",
        model_name="res.partner",
        preferred_xmlids=("base.view_partner_form",),
        smart_button_xml=smart,
        notebook_page_xml=page,
    )


def _install_account_move_extension(env):
    smart = """
        <button name="action_view_consent" type="object"
                class="oe_stat_button" icon="fa-file-text-o"
                invisible="not consent_id">
            <div class="o_stat_info">
                <span class="o_stat_text">Consent</span>
                <span class="o_stat_value"><field name="consent_status"/></span>
            </div>
        </button>
    """
    page = """
        <page string="Consent &amp; Legal" name="consent_legal">
            <group>
                <group string="Policy">
                    <field name="consent_policy"/>
                    <field name="consent_validity_days_override"/>
                    <field name="enforce_consent_on_post"/>
                </group>
                <group string="Status">
                    <field name="patient_id" readonly="1"/>
                    <field name="doctor_id"/>
                    <field name="room_session_id"/>
                    <field name="treatment_ids" widget="many2many_tags" readonly="1"/>
                    <field name="consent_required_effective" readonly="1"/>
                    <field name="consent_status" readonly="1"/>
                    <field name="consent_id" readonly="1"/>
                </group>
            </group>
            <field name="consent_status_hint" readonly="1"/>
            <button name="action_request_consent" type="object"
                    string="Create Consent" class="btn-primary" icon="fa-plus"/>
            <button name="action_view_all_related_consents" type="object"
                    string="View Patient Consents" icon="fa-files-o"/>
        </page>
    """
    _install_optional_form_extension(
        env,
        xml_name="view_account_move_form_consent_legal_optional",
        view_name="account.move.form.consent.legal.optional",
        model_name="account.move",
        preferred_xmlids=("account.view_move_form",),
        smart_button_xml=smart,
        notebook_page_xml=page,
    )

def post_init_hook(env):
    """Finish optional cross-addon presentation integration after install."""
    _reparent_root_menu(env)
    _install_partner_extension(env)
    _install_treatment_extension(env)
    _install_appointment_extension(env)
    _install_account_move_extension(env)
