from odoo import fields, models, _


def _quality_checks_action(record, domain, defaults=None, title=None):
    record.ensure_one()
    return {
        "type": "ir.actions.act_window",
        "name": title or _("Quality Checks"),
        "res_model": "clinic.quality.check",
        "view_mode": "kanban,list,form,pivot,graph",
        "domain": domain,
        "context": dict(defaults or {}),
    }


class ClinicBranchQualityBridge(models.Model):
    """Reverse navigation without taking Clinic Branch ownership."""

    _inherit = "clinic.branch"

    quality_check_ids = fields.One2many(
        "clinic.quality.check",
        "branch_id",
        string="Quality Checks",
        readonly=True,
    )
    quality_check_count = fields.Integer(
        compute="_compute_quality_check_count"
    )

    def _compute_quality_check_count(self):
        for record in self:
            record.quality_check_count = len(record.quality_check_ids)

    def action_open_quality_checks(self):
        return _quality_checks_action(
            self,
            [("branch_id", "=", self.id)],
            defaults={
                "default_company_id": self.company_id.id,
                "default_branch_id": self.id,
            },
            title=_("Branch Quality Checks"),
        )


class ClinicRoomQualityBridge(models.Model):
    """Reverse navigation only; Room lifecycle remains upstream."""

    _inherit = "clinic.room"

    quality_check_ids = fields.One2many(
        "clinic.quality.check",
        "room_id",
        string="Quality Checks",
        readonly=True,
    )
    quality_check_count = fields.Integer(
        compute="_compute_quality_check_count"
    )

    def _compute_quality_check_count(self):
        for record in self:
            record.quality_check_count = len(record.quality_check_ids)

    def action_open_quality_checks(self):
        return _quality_checks_action(
            self,
            [("room_id", "=", self.id)],
            defaults={
                "default_company_id": self.company_id.id,
                "default_scope_type": "room",
                "default_room_id": self.id,
            },
            title=_("Room Quality Checks"),
        )


class ClinicStaffQualityBridge(models.Model):
    """Quality Check and SOP acknowledgement navigation for Clinic Staff."""

    _inherit = "clinic.staff"

    quality_check_ids = fields.One2many(
        "clinic.quality.check",
        "staff_id",
        string="Quality Checks",
        readonly=True,
    )
    quality_check_count = fields.Integer(
        compute="_compute_quality_counts"
    )
    quality_sop_acknowledgement_ids = fields.One2many(
        "clinic.quality.sop.acknowledgement",
        "staff_id",
        string="SOP Acknowledgements",
        readonly=True,
    )
    quality_sop_acknowledgement_count = fields.Integer(
        compute="_compute_quality_counts"
    )

    def _compute_quality_counts(self):
        for record in self:
            record.quality_check_count = len(record.quality_check_ids)
            record.quality_sop_acknowledgement_count = len(
                record.quality_sop_acknowledgement_ids.filtered(
                    lambda acknowledgement:
                    acknowledgement.state == "acknowledged"
                )
            )

    def action_open_quality_checks(self):
        return _quality_checks_action(
            self,
            [("staff_id", "=", self.id)],
            defaults={
                "default_company_id": self.company_id.id,
                "default_branch_id": self.branch_id.id if self.branch_id else False,
                "default_scope_type": "staff",
                "default_staff_id": self.id,
            },
            title=_("Staff Quality Checks"),
        )

    def action_open_quality_sop_acknowledgements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Staff SOP Acknowledgements"),
            "res_model": "clinic.quality.sop.acknowledgement",
            "view_mode": "list,form",
            "domain": [("staff_id", "=", self.id)],
        }


class ClinicDoctorQualityBridge(models.Model):
    """Reverse navigation only; Doctor ownership remains upstream."""

    _inherit = "clinic.doctor"

    quality_check_ids = fields.One2many(
        "clinic.quality.check",
        "doctor_id",
        string="Quality Checks",
        readonly=True,
    )
    quality_check_count = fields.Integer(
        compute="_compute_quality_check_count"
    )

    def _compute_quality_check_count(self):
        for record in self:
            record.quality_check_count = len(record.quality_check_ids)

    def action_open_quality_checks(self):
        return _quality_checks_action(
            self,
            [("doctor_id", "=", self.id)],
            defaults={
                "default_company_id": self.company_id.id,
                "default_scope_type": "doctor",
                "default_doctor_id": self.id,
            },
            title=_("Doctor Quality Checks"),
        )


class ClinicTreatmentQualityBridge(models.Model):
    """Reverse navigation only; Treatment/Catalog ownership stays upstream."""

    _inherit = "clinic.treatment"

    quality_check_ids = fields.One2many(
        "clinic.quality.check",
        "treatment_id",
        string="Quality Checks",
        readonly=True,
    )
    quality_check_count = fields.Integer(
        compute="_compute_quality_check_count"
    )

    def _compute_quality_check_count(self):
        for record in self:
            record.quality_check_count = len(record.quality_check_ids)

    def action_open_quality_checks(self):
        return _quality_checks_action(
            self,
            [("treatment_id", "=", self.id)],
            defaults={
                "default_company_id": self.company_id.id,
                "default_scope_type": "treatment",
                "default_treatment_id": self.id,
            },
            title=_("Treatment Quality Checks"),
        )


class StockLotQualityBridge(models.Model):
    """Quality evidence around a Lot without taking disposition ownership.

    `clinic_inventory` remains owner of `clinic_quality_state` and
    `clinic_quarantine_reason`; this addon only links compliance evidence.
    """

    _inherit = "stock.lot"

    quality_check_ids = fields.One2many(
        "clinic.quality.check",
        "stock_lot_id",
        string="Quality Checks",
        readonly=True,
    )
    quality_check_count = fields.Integer(
        compute="_compute_quality_check_count"
    )

    def _compute_quality_check_count(self):
        for record in self:
            record.quality_check_count = len(record.quality_check_ids)

    def action_open_quality_checks(self):
        self.ensure_one()
        company = (
            self.company_id
            if "company_id" in self._fields and self.company_id
            else self.env.company
        )
        return _quality_checks_action(
            self,
            [("stock_lot_id", "=", self.id)],
            defaults={
                "default_company_id": company.id,
                "default_scope_type": "inventory_lot",
                "default_stock_lot_id": self.id,
            },
            title=_("Inventory Lot Quality Checks"),
        )
