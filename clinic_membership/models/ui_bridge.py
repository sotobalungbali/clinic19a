


# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class MembershipPlanUiBridge(models.Model):
    """Install optional Smart Button decorations without hard XML-ID coupling.

    The related business models remain hard dependencies. Only decoration of an
    external form is optional, because an installed ClinicOne database may have
    a historical view XML-ID that differs from the current source tree.
    """

    _inherit = "membership.plan"

    @api.model
    def _membership_upsert_optional_view(self, xmlid, name, model, parent_xmlid, arch):
        parent = self.env.ref(parent_xmlid, raise_if_not_found=False)
        if not parent or parent._name != "ir.ui.view" or parent.model != model:
            _logger.info("[clinic_membership] Optional UI bridge skipped: %s", parent_xmlid)
            return False
        module, record_name = xmlid.split(".", 1)
        data = self.env["ir.model.data"].sudo().search([
            ("module", "=", module), ("name", "=", record_name), ("model", "=", "ir.ui.view")
        ], limit=1)
        vals = {"name": name, "model": model, "inherit_id": parent.id, "arch_db": arch, "active": True}
        try:
            with self.env.cr.savepoint():
                if data and data.res_id:
                    view = self.env["ir.ui.view"].sudo().browse(data.res_id).exists()
                    if view:
                        view.write(vals)
                        return view
                view = self.env["ir.ui.view"].sudo().create(vals)
                if data:
                    data.write({"res_id": view.id})
                else:
                    self.env["ir.model.data"].sudo().create({
                        "module": module, "name": record_name, "model": "ir.ui.view",
                        "res_id": view.id, "noupdate": False,
                    })
                return view
        except Exception:
            _logger.exception("[clinic_membership] Optional UI bridge failed: %s", parent_xmlid)
            return False

    @api.model
    def _ensure_optional_cross_addon_views(self):
        button = lambda method, field, label, icon='fa-id-card': f"""<xpath expr="//div[@name='button_box']" position="inside"><button name="{method}" type="object" class="oe_stat_button" icon="{icon}"><field name="{field}" widget="statinfo" string="{label}"/></button></xpath>"""
        bridges = [
            ("clinic_membership.view_partner_form_membership_bridge", "res.partner.form.membership.bridge", "res.partner", "base.view_partner_form", button("action_view_membership_contracts", "membership_contract_count", "Memberships", "fa-star")),
            ("clinic_membership.view_patient_form_membership_bridge", "clinic.patient.form.membership.bridge", "clinic.patient", "clinic_patient.view_clinic_patient_form", button("action_view_membership_contracts", "membership_contract_count", "Memberships", "fa-star")),
            ("clinic_membership.view_booking_form_membership_bridge", "booking.booking.form.membership.bridge", "booking.booking", "clinic_booking.view_booking_booking_form", button("action_view_membership_usages", "membership_usage_count", "Member Usage", "fa-gift") + """<xpath expr="//notebook" position="inside"><page string="Membership" name="membership"><group><group><field name="membership_contract_id"/><field name="membership_entitlement_id" readonly="1"/></group><group><field name="membership_discount_preview" readonly="1"/><field name="membership_price_after_preview" readonly="1"/><field name="membership_priority" readonly="1"/></group></group><button name="action_create_membership_usage" type="object" string="Create Membership Usage" class="btn-primary" icon="fa-gift"/></page></xpath>"""),
            ("clinic_membership.view_encounter_form_membership_bridge", "clinic.encounter.form.membership.bridge", "clinic.encounter", "clinic_encounter.view_clinic_encounter_form", button("action_view_membership_usages", "membership_usage_count", "Member Usage", "fa-gift")),
            ("clinic_membership.view_care_plan_form_membership_bridge", "clinic.care.plan.form.membership.bridge", "clinic.care.plan", "clinic_care_plan.view_clinic_care_plan_form", button("action_view_membership_usages", "membership_usage_count", "Member Usage", "fa-gift")),
            ("clinic_membership.view_package_allocation_form_membership_bridge", "clinic.package.allocation.form.membership.bridge", "clinic.package.allocation", "clinic_package.view_clinic_package_allocation_form", button("action_view_membership_usages", "membership_usage_count", "Member Usage", "fa-gift")),
            ("clinic_membership.view_package_usage_form_membership_bridge", "clinic.package.usage.form.membership.bridge", "clinic.package.usage", "clinic_package.view_clinic_package_usage_form", button("action_view_membership_usages", "membership_usage_count", "Member Usage", "fa-gift")),
            ("clinic_membership.view_emar_administration_form_membership_bridge", "clinic.emar.administration.form.membership.bridge", "clinic.emar.administration", "clinic_emar.view_emar_administration_form", button("action_view_membership_usages", "membership_usage_count", "Member Usage", "fa-gift")),
        ]
        for args in bridges:
            self._membership_upsert_optional_view(*args)
        return True


