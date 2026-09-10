# -*- coding: utf-8 -*-
"""Runtime-safe form decorations between Accounts Receivable and Billing.

The AR business contract with ``clinic_billing`` is mandatory and expressed
through normal Python model inheritance.  Form decorations are different:
upstream Billing forms may legitimately change layout without changing their
business API.  A hard XML ``inherit_id`` + fragile XPath would therefore make
AR installation depend on presentation details.

This bridge resolves parent views at runtime, tries compatible architecture
candidates inside database savepoints, and creates stable XML IDs only after a
candidate validates successfully.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


BILLING_INVOICE_AR_ARCH_CANDIDATES = (
    """
    <data>
        <xpath expr="//div[@name='button_box']" position="inside">
            <button name="action_create_or_open_ar"
                    type="object"
                    class="oe_stat_button"
                    icon="fa-credit-card"
                    groups="clinic_ar.group_clinic_ar_user">
                <field name="ar_invoice_count"
                       string="Accounts Receivable"
                       widget="statinfo"/>
            </button>
        </xpath>
    </data>
    """,
    """
    <data>
        <xpath expr="//sheet/*[1]" position="before">
            <div class="oe_button_box" name="clinic_ar_button_box">
                <button name="action_create_or_open_ar"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-credit-card"
                        groups="clinic_ar.group_clinic_ar_user">
                    <field name="ar_invoice_count"
                           string="Accounts Receivable"
                           widget="statinfo"/>
                </button>
            </div>
        </xpath>
    </data>
    """,
)


BILLING_PAYMENT_AR_ARCH_CANDIDATES = (
    """
    <data>
        <xpath expr="//div[@name='button_box']" position="inside">
            <button name="action_view_ar_receipts"
                    type="object"
                    class="oe_stat_button"
                    icon="fa-money"
                    invisible="ar_payment_count == 0"
                    groups="clinic_ar.group_clinic_ar_user">
                <field name="ar_payment_count"
                       string="AR Receipts"
                       widget="statinfo"/>
            </button>
        </xpath>
    </data>
    """,
    """
    <data>
        <xpath expr="//sheet/*[1]" position="before">
            <div class="oe_button_box" name="clinic_ar_button_box">
                <button name="action_view_ar_receipts"
                        type="object"
                        class="oe_stat_button"
                        icon="fa-money"
                        invisible="ar_payment_count == 0"
                        groups="clinic_ar.group_clinic_ar_user">
                    <field name="ar_payment_count"
                           string="AR Receipts"
                           widget="statinfo"/>
                </button>
            </div>
        </xpath>
    </data>
    """,
)


class ClinicARViewBridge(models.Model):
    """Technical extension used only to maintain optional form decorations."""

    _inherit = "clinic.ar.invoice"

    @api.model
    def _upsert_optional_inherited_view(
        self,
        *,
        parent_xmlid,
        local_xmlid_name,
        view_name,
        model_name,
        arch_candidates,
    ):
        """Create or update an inherited view using the first valid candidate.

        Missing parent XML IDs and incompatible parent layouts are deliberately
        non-fatal.  AR business models, security, accounting and reconciliation
        remain fully active even when a cosmetic Smart Button cannot be placed.
        """
        parent_view = self.env.ref(parent_xmlid, raise_if_not_found=False)
        if not parent_view:
            _logger.warning(
                "ClinicOne AR UI bridge skipped: parent XML ID %s is missing.",
                parent_xmlid,
            )
            return False

        if parent_view._name != "ir.ui.view" or parent_view.model != model_name:
            _logger.warning(
                "ClinicOne AR UI bridge skipped: %s does not resolve to a "
                "form view for model %s.",
                parent_xmlid,
                model_name,
            )
            return False

        View = self.env["ir.ui.view"].sudo()
        ModelData = self.env["ir.model.data"].sudo()

        xmlid_record = ModelData.search(
            [
                ("module", "=", "clinic_ar"),
                ("name", "=", local_xmlid_name),
                ("model", "=", "ir.ui.view"),
            ],
            limit=1,
        )
        inherited_view = (
            View.browse(xmlid_record.res_id).exists()
            if xmlid_record
            else View.browse()
        )

        for candidate_no, arch_db in enumerate(arch_candidates, start=1):
            values = {
                "name": view_name,
                "model": model_name,
                "inherit_id": parent_view.id,
                "priority": 90,
                "arch_db": arch_db,
                "active": True,
            }
            try:
                with self.env.cr.savepoint():
                    if inherited_view:
                        inherited_view.write(values)
                    else:
                        inherited_view = View.create(values)

                    if xmlid_record:
                        if xmlid_record.res_id != inherited_view.id:
                            xmlid_record.write(
                                {
                                    "res_id": inherited_view.id,
                                    "noupdate": False,
                                }
                            )
                    else:
                        xmlid_record = ModelData.create(
                            {
                                "module": "clinic_ar",
                                "name": local_xmlid_name,
                                "model": "ir.ui.view",
                                "res_id": inherited_view.id,
                                "noupdate": False,
                            }
                        )
            except Exception:
                _logger.info(
                    "ClinicOne AR UI bridge %s candidate %s is incompatible "
                    "with parent %s; trying the next candidate.",
                    local_xmlid_name,
                    candidate_no,
                    parent_xmlid,
                    exc_info=True,
                )
                # If creation failed, make sure the next candidate starts with
                # an empty recordset.  Existing valid views remain reusable.
                if not xmlid_record:
                    inherited_view = View.browse()
                continue

            _logger.info(
                "ClinicOne AR UI bridge %s is active using candidate %s on %s.",
                local_xmlid_name,
                candidate_no,
                parent_xmlid,
            )
            return True

        _logger.warning(
            "ClinicOne AR UI bridge %s skipped: none of its architecture "
            "candidates validate against parent %s.",
            local_xmlid_name,
            parent_xmlid,
        )
        return False

    @api.model
    def _ensure_optional_billing_views(self):
        """Install/update Billing Smart Buttons without hard XPath coupling."""
        bridge_specs = (
            {
                "parent_xmlid": "clinic_billing." "view_clinic_billing_invoice_form",
                "local_xmlid_name": "view_billing_invoice_form_clinic_ar",
                "view_name": "clinic.billing.invoice.form.clinic.ar",
                "model_name": "clinic.billing.invoice",
                "arch_candidates": BILLING_INVOICE_AR_ARCH_CANDIDATES,
            },
            {
                "parent_xmlid": "clinic_billing." "view_clinic_billing_payment_form",
                "local_xmlid_name": "view_billing_payment_form_clinic_ar",
                "view_name": "clinic.billing.payment.form.clinic.ar",
                "model_name": "clinic.billing.payment",
                "arch_candidates": BILLING_PAYMENT_AR_ARCH_CANDIDATES,
            },
        )

        results = [
            self._upsert_optional_inherited_view(**spec)
            for spec in bridge_specs
        ]
        return any(results)



