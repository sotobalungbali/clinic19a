from odoo import models, _
from odoo.exceptions import UserError


class ClinicQualityCheckNavigation(models.Model):
    """Human-friendly source, smart-button and report navigation."""

    _inherit = "clinic.quality.check"

    def action_open_template(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Quality Template"),
            "res_model": "clinic.quality.check.template",
            "view_mode": "form",
            "res_id": self.template_id.id,
        }

    def action_open_sop_version(self):
        self.ensure_one()
        if not self.sop_version_id:
            raise UserError(
                _("This Quality Check has no governing SOP Version.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Governing SOP Version"),
            "res_model": "clinic.quality.sop.version",
            "view_mode": "form",
            "res_id": self.sop_version_id.id,
        }

    def action_open_incidents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Quality Incident Cases"),
            "res_model": "clinic.incident",
            "view_mode": "kanban,list,form",
            "domain": [("quality_check_id", "=", self.id)],
        }

    def _open_scope_record(self, record, title):
        self.ensure_one()
        if not record:
            raise UserError(_("No %(scope)s is linked.") % {"scope": title})
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": record._name,
            "view_mode": "form",
            "res_id": record.id,
        }

    def action_open_scope_branch(self):
        return self._open_scope_record(
            self.branch_id,
            _("Branch"),
        )

    def action_open_scope_room(self):
        return self._open_scope_record(
            self.room_id,
            _("Room"),
        )

    def action_open_scope_staff(self):
        return self._open_scope_record(
            self.staff_id,
            _("Staff"),
        )

    def action_open_scope_doctor(self):
        return self._open_scope_record(
            self.doctor_id,
            _("Doctor"),
        )

    def action_open_scope_inventory_lot(self):
        return self._open_scope_record(
            self.stock_lot_id,
            _("Inventory Lot / Batch"),
        )

    def action_open_scope_treatment(self):
        return self._open_scope_record(
            self.treatment_id,
            _("Treatment / Service"),
        )

    def action_print_quality_check(self):
        self.ensure_one()
        return self.env.ref(
            "clinic_quality.action_report_quality_check"
        ).report_action(self)
