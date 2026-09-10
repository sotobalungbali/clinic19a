# -*- coding: utf-8 -*-
# Runtime-safe smart-button bridge into upstream ClinicOne forms.

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ClinicBillingRuntimeViewBridge(models.Model):
    _inherit = "clinic.billing.invoice"

    @api.model
    def _ensure_cross_addon_billing_views(self):
        """Decorate upstream forms without making external XML IDs an install-time single point of failure."""
        specs = [
            {
                "key": "clinic_billing.patient.smart_button",
                "model": "clinic.patient",
                "parent": "clinic_patient.view_clinic_patient_form",
                "method": "action_view_billing_invoices",
                "field": "billing_invoice_count",
                "label": "Billing",
                "icon": "fa-credit-card",
            },
            {
                "key": "clinic_billing.booking.smart_button",
                "model": "booking.booking",
                "parent": "clinic_booking.view_booking_booking_form",
                "method": "action_view_billing_invoices",
                "field": "billing_invoice_count",
                "label": "Billing",
                "icon": "fa-credit-card",
            },
            {
                "key": "clinic_billing.encounter.smart_button",
                "model": "clinic.encounter",
                "parent": "clinic_encounter.view_clinic_encounter_form",
                "method": "action_view_billing_invoices",
                "field": "billing_invoice_count",
                "label": "Billing",
                "icon": "fa-credit-card",
            },
            {
                "key": "clinic_billing.care_plan.smart_button",
                "model": "clinic.care.plan",
                "parent": "clinic_care_plan.view_clinic_care_plan_form",
                "method": "action_view_billing_documents",
                "field": "billing_document_count",
                "label": "Billing",
                "icon": "fa-credit-card",
            },
            {
                "key": "clinic_billing.package_allocation.smart_button",
                "model": "clinic.package.allocation",
                "parent": "clinic_package.view_clinic_package_allocation_form",
                "method": "action_view_billing_documents",
                "field": "billing_document_count",
                "label": "Billing",
                "icon": "fa-credit-card",
            },
            {
                "key": "clinic_billing.package_usage.smart_button",
                "model": "clinic.package.usage",
                "parent": "clinic_package.view_clinic_package_usage_form",
                "method": "action_view_billing_lines",
                "field": "billing_line_count",
                "label": "Billing Lines",
                "icon": "fa-list",
            },
            {
                "key": "clinic_billing.emar_administration.smart_button",
                "model": "clinic.emar.administration",
                "parent": "clinic_emar.view_emar_administration_form",
                "method": "action_view_billing_lines",
                "field": "billing_line_count",
                "label": "Billing Lines",
                "icon": "fa-list",
            },
        ]

        View = self.env["ir.ui.view"].sudo()
        for spec in specs:
            parent = self.env.ref(spec["parent"], raise_if_not_found=False)
            if not parent or parent.model != spec["model"]:
                _logger.info(
                    "[clinic_billing] Optional UI bridge skipped: parent %s unavailable for %s.",
                    spec["parent"],
                    spec["model"],
                )
                continue

            arch = f"""
                <xpath expr="//div[@name='button_box']" position="inside">
                    <button name="{spec['method']}" type="object"
                            class="oe_stat_button" icon="{spec['icon']}">
                        <field name="{spec['field']}" widget="statinfo" string="{spec['label']}"/>
                    </button>
                </xpath>
            """
            try:
                with self.env.cr.savepoint():
                    view = View.search([
                        ("name", "=", spec["key"]),
                        ("model", "=", spec["model"]),
                        ("inherit_id", "=", parent.id),
                    ], limit=1)
                    values = {
                        "name": spec["key"],
                        "model": spec["model"],
                        "inherit_id": parent.id,
                        "arch": arch,
                        "active": True,
                    }
                    if view:
                        view.write(values)
                    else:
                        View.create(values)
            except Exception as exc:
                _logger.warning(
                    "[clinic_billing] Optional UI bridge %s skipped safely: %s",
                    spec["key"],
                    exc,
                )
        return True



