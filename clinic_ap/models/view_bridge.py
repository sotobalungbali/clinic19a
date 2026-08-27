# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ClinicAPViewBridge(models.Model):
    _inherit = "clinic.ap"

    @api.model
    def _upsert_optional_view(self, parent_xmlid, local_name, view_name, model_name, arch_candidates):
        parent = self.env.ref(parent_xmlid, raise_if_not_found=False)
        if not parent or parent._name != "ir.ui.view" or parent.model != model_name:
            _logger.warning("Clinic AP optional UI bridge skipped for %s", parent_xmlid)
            return False

        View = self.env["ir.ui.view"].sudo()
        Data = self.env["ir.model.data"].sudo()
        data = Data.search([
            ("module", "=", "clinic_ap"),
            ("name", "=", local_name),
            ("model", "=", "ir.ui.view"),
        ], limit=1)
        child = View.browse(data.res_id).exists() if data else View.browse()

        for arch in arch_candidates:
            vals = {
                "name": view_name,
                "model": model_name,
                "inherit_id": parent.id,
                "priority": 90,
                "arch_db": arch,
                "active": True,
            }
            try:
                with self.env.cr.savepoint():
                    if child:
                        child.write(vals)
                    else:
                        child = View.create(vals)
                    if data:
                        if data.res_id != child.id:
                            data.write({"res_id": child.id, "noupdate": False})
                    else:
                        data = Data.create({
                            "module": "clinic_ap",
                            "name": local_name,
                            "model": "ir.ui.view",
                            "res_id": child.id,
                            "noupdate": False,
                        })
                    return child
            except Exception:
                child = View.browse(data.res_id).exists() if data else View.browse()
                continue

        _logger.warning("Clinic AP optional UI bridge could not decorate %s", parent_xmlid)
        return False

    @api.model
    def _button_arches(self, method, count_field, label, icon="fa-money"):
        return (
            f"""<data><xpath expr=\"//div[@name='button_box']\" position=\"inside\">
                <button name=\"{method}\" type=\"object\" class=\"oe_stat_button\" icon=\"{icon}\" groups=\"clinic_ap.group_clinic_ap_user\">
                    <field name=\"{count_field}\" string=\"{label}\" widget=\"statinfo\"/>
                </button>
            </xpath></data>""",
            f"""<data><xpath expr=\"//sheet/*[1]\" position=\"before\">
                <div class=\"oe_button_box\" name=\"clinic_ap_button_box\">
                    <button name=\"{method}\" type=\"object\" class=\"oe_stat_button\" icon=\"{icon}\" groups=\"clinic_ap.group_clinic_ap_user\">
                        <field name=\"{count_field}\" string=\"{label}\" widget=\"statinfo\"/>
                    </button>
                </div>
            </xpath></data>""",
        )

    @api.model
    def _ensure_optional_cross_addon_views(self):
        specs = [
            (
                "base.view_partner_form",
                "view_partner_form_clinic_ap",
                "res.partner.form.clinic.ap",
                "res.partner",
                self._button_arches("action_view_clinic_ap", "ap_open_count", "Open AP", "fa-truck"),
            ),
            (
                "account.view_move_form",
                "view_account_move_form_clinic_ap",
                "account.move.form.clinic.ap",
                "account.move",
                self._button_arches("action_view_clinic_ap", "clinic_ap_count", "Clinic AP", "fa-file-text-o"),
            ),
            (
                "purchase.purchase_order_form",
                "view_purchase_order_form_clinic_ap",
                "purchase.order.form.clinic.ap",
                "purchase.order",
                self._button_arches("action_view_clinic_ap", "clinic_ap_count", "Clinic AP", "fa-shopping-cart"),
            ),
            (
                "clinic_billing.view_clinic_billing_invoice_form",
                "view_billing_invoice_form_clinic_ap",
                "clinic.billing.invoice.form.clinic.ap",
                "clinic.billing.invoice",
                self._button_arches("action_view_ap_costs", "ap_cost_count", "AP Costs", "fa-money"),
            ),
        ]
        for parent_xmlid, local_name, view_name, model_name, candidates in specs:
            self._upsert_optional_view(parent_xmlid, local_name, view_name, model_name, candidates)
        return True
