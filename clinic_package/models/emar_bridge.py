# -*- coding: utf-8 -*-
"""Traceable integration between package redemptions and ClinicOne eMAR.

``clinic_emar`` remains the owner of medication orders, schedules and
administration records.  ``clinic_package`` only stores entitlement-redemption
references and exposes reverse navigation through non-stored One2many/count
fields on eMAR models.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicPackageUsage(models.Model):
    _inherit = "clinic.package.usage"

    emar_order_id = fields.Many2one(
        "clinic.emar.order",
        string="eMAR Order",
        ondelete="set null",
        check_company=True,
        tracking=True,
        index=True,
    )
    emar_schedule_id = fields.Many2one(
        "clinic.emar.schedule",
        string="eMAR Schedule",
        ondelete="set null",
        check_company=True,
        tracking=True,
        index=True,
    )
    emar_administration_id = fields.Many2one(
        "clinic.emar.administration",
        string="eMAR Administration",
        ondelete="set null",
        check_company=True,
        tracking=True,
        index=True,
    )
    emar_prescription_id = fields.Many2one(
        "clinic.emar.prescription",
        string="eMAR Prescription",
        compute="_compute_emar_prescription_id",
        store=False,
        readonly=True,
    )

    @api.depends(
        "emar_order_id.prescription_id",
        "emar_schedule_id.prescription_id",
        "emar_administration_id.prescription_id",
    )
    def _compute_emar_prescription_id(self):
        for usage in self:
            usage.emar_prescription_id = (
                usage.emar_administration_id.prescription_id
                or usage.emar_schedule_id.prescription_id
                or usage.emar_order_id.prescription_id
            )

    @api.onchange("emar_order_id")
    def _onchange_emar_order_id(self):
        for usage in self:
            if (
                usage.emar_schedule_id
                and usage.emar_schedule_id.order_id != usage.emar_order_id
            ):
                usage.emar_schedule_id = False
                usage.emar_administration_id = False

    @api.onchange("emar_schedule_id")
    def _onchange_emar_schedule_id(self):
        for usage in self:
            if usage.emar_schedule_id:
                usage.emar_order_id = usage.emar_schedule_id.order_id
                if (
                    usage.emar_administration_id
                    and usage.emar_administration_id.schedule_id
                    != usage.emar_schedule_id
                ):
                    usage.emar_administration_id = False

    @api.onchange("emar_administration_id")
    def _onchange_emar_administration_id(self):
        for usage in self:
            administration = usage.emar_administration_id
            if administration:
                usage.emar_schedule_id = administration.schedule_id
                usage.emar_order_id = administration.order_id

    @api.constrains(
        "emar_order_id",
        "emar_schedule_id",
        "emar_administration_id",
        "patient_id",
        "allocation_line_id",
    )
    def _check_emar_traceability(self):
        for usage in self:
            patient = usage.patient_id
            order = usage.emar_order_id
            schedule = usage.emar_schedule_id
            administration = usage.emar_administration_id

            for label, record in (
                (_("eMAR Order"), order),
                (_("eMAR Schedule"), schedule),
                (_("eMAR Administration"), administration),
            ):
                if record and record.patient_id and patient and record.patient_id != patient:
                    raise ValidationError(
                        _("%(label)s patient must match the package redemption patient.")
                        % {"label": label}
                    )

            if schedule and order and schedule.order_id and schedule.order_id != order:
                raise ValidationError(
                    _("The selected eMAR Schedule does not belong to the selected eMAR Order.")
                )
            if administration and schedule and administration.schedule_id and administration.schedule_id != schedule:
                raise ValidationError(
                    _("The selected eMAR Administration does not belong to the selected eMAR Schedule.")
                )
            if administration and order and administration.order_id and administration.order_id != order:
                raise ValidationError(
                    _("The selected eMAR Administration does not belong to the selected eMAR Order.")
                )

            line = usage.allocation_line_id
            if (
                administration
                and line
                and line.line_type == "product"
                and line.product_id
                and administration.product_id
                and administration.product_id != line.product_id
            ):
                raise ValidationError(
                    _("The administered medication/product does not match the redeemed package product.")
                )

    @api.model
    def _normalize_emar_traceability_vals(self, vals):
        """Fill the eMAR hierarchy for RPC/import/create paths, not only onchange."""
        values = dict(vals)
        administration_id = values.get("emar_administration_id")
        schedule_id = values.get("emar_schedule_id")

        if administration_id:
            administration = self.env["clinic.emar.administration"].browse(
                administration_id
            ).exists()
            if administration:
                values.setdefault(
                    "emar_schedule_id", administration.schedule_id.id or False
                )
                values.setdefault(
                    "emar_order_id", administration.order_id.id or False
                )

        if values.get("emar_schedule_id"):
            schedule = self.env["clinic.emar.schedule"].browse(
                values["emar_schedule_id"]
            ).exists()
            if schedule:
                values.setdefault("emar_order_id", schedule.order_id.id or False)

        return values

    @api.model_create_multi
    def create(self, vals_list):
        normalized = [
            self._normalize_emar_traceability_vals(vals)
            for vals in vals_list
        ]
        return super().create(normalized)

    def write(self, vals):
        emar_fields = {
            "emar_order_id",
            "emar_schedule_id",
            "emar_administration_id",
        }
        if emar_fields.intersection(vals) and any(
            record.state != "draft" for record in self
        ):
            raise UserError(
                _("eMAR traceability links are locked after redemption confirmation.")
            )
        values = (
            self._normalize_emar_traceability_vals(vals)
            if emar_fields.intersection(vals)
            else vals
        )
        return super().write(values)

    def action_view_emar_order(self):
        self.ensure_one()
        if not self.emar_order_id:
            raise UserError(_("No eMAR Order is linked to this redemption."))
        return self._clinic_pkg_emar_form_action(
            self.emar_order_id, _("eMAR Order")
        )

    def action_view_emar_schedule(self):
        self.ensure_one()
        if not self.emar_schedule_id:
            raise UserError(_("No eMAR Schedule is linked to this redemption."))
        return self._clinic_pkg_emar_form_action(
            self.emar_schedule_id, _("eMAR Schedule")
        )

    def action_view_emar_administration(self):
        self.ensure_one()
        if not self.emar_administration_id:
            raise UserError(_("No eMAR Administration is linked to this redemption."))
        return self._clinic_pkg_emar_form_action(
            self.emar_administration_id, _("eMAR Administration")
        )

    def action_view_emar_prescription(self):
        self.ensure_one()
        if not self.emar_prescription_id:
            raise UserError(_("No eMAR Prescription is linked to this redemption."))
        return self._clinic_pkg_emar_form_action(
            self.emar_prescription_id, _("eMAR Prescription")
        )

    @api.model
    def _clinic_pkg_emar_form_action(self, record, title):
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": record._name,
            "view_mode": "form",
            "res_id": record.id,
        }


class ClinicPackageAllocation(models.Model):
    _inherit = "clinic.package.allocation"

    emar_usage_count = fields.Integer(
        compute="_compute_emar_usage_count",
        string="eMAR-linked Redemptions",
    )

    def _compute_emar_usage_count(self):
        Usage = self.env["clinic.package.usage"]
        for record in self:
            record.emar_usage_count = Usage.search_count(
                [
                    "&",
                    ("allocation_id", "=", record.id),
                    "|",
                    "|",
                    ("emar_order_id", "!=", False),
                    ("emar_schedule_id", "!=", False),
                    ("emar_administration_id", "!=", False),
                ]
            )

    def action_view_emar_usages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("eMAR-linked Package Redemptions"),
            "res_model": "clinic.package.usage",
            "view_mode": "list,form",
            "domain": [
                "&",
                ("allocation_id", "=", self.id),
                "|",
                "|",
                ("emar_order_id", "!=", False),
                ("emar_schedule_id", "!=", False),
                ("emar_administration_id", "!=", False),
            ],
            "context": {"default_allocation_id": self.id},
        }


class ClinicEmarOrder(models.Model):
    _inherit = "clinic.emar.order"

    package_usage_ids = fields.One2many(
        "clinic.package.usage",
        "emar_order_id",
        string="Package Redemptions",
        readonly=True,
    )
    package_usage_count = fields.Integer(
        compute="_compute_package_usage_count",
        string="Package Redemptions",
    )

    def _compute_package_usage_count(self):
        for record in self:
            record.package_usage_count = len(record.package_usage_ids)

    def action_view_package_usages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Package Redemptions"),
            "res_model": "clinic.package.usage",
            "view_mode": "list,form",
            "domain": [("emar_order_id", "=", self.id)],
            "context": {"default_emar_order_id": self.id},
        }


class ClinicEmarSchedule(models.Model):
    _inherit = "clinic.emar.schedule"

    package_usage_ids = fields.One2many(
        "clinic.package.usage",
        "emar_schedule_id",
        string="Package Redemptions",
        readonly=True,
    )
    package_usage_count = fields.Integer(
        compute="_compute_package_usage_count",
        string="Package Redemptions",
    )

    def _compute_package_usage_count(self):
        for record in self:
            record.package_usage_count = len(record.package_usage_ids)

    def action_view_package_usages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Package Redemptions"),
            "res_model": "clinic.package.usage",
            "view_mode": "list,form",
            "domain": [("emar_schedule_id", "=", self.id)],
            "context": {
                "default_emar_order_id": self.order_id.id,
                "default_emar_schedule_id": self.id,
            },
        }


class ClinicEmarAdministration(models.Model):
    _inherit = "clinic.emar.administration"

    package_usage_ids = fields.One2many(
        "clinic.package.usage",
        "emar_administration_id",
        string="Package Redemptions",
        readonly=True,
    )
    package_usage_count = fields.Integer(
        compute="_compute_package_usage_count",
        string="Package Redemptions",
    )

    def _compute_package_usage_count(self):
        for record in self:
            record.package_usage_count = len(record.package_usage_ids)

    def action_view_package_usages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Package Redemptions"),
            "res_model": "clinic.package.usage",
            "view_mode": "list,form",
            "domain": [("emar_administration_id", "=", self.id)],
            "context": {
                "default_emar_order_id": self.order_id.id,
                "default_emar_schedule_id": self.schedule_id.id,
                "default_emar_administration_id": self.id,
            },
        }


class ClinicEmarPrescription(models.Model):
    _inherit = "clinic.emar.prescription"

    package_usage_count = fields.Integer(
        compute="_compute_package_usage_count",
        string="Package Redemptions",
    )

    def _compute_package_usage_count(self):
        Usage = self.env["clinic.package.usage"]
        for record in self:
            record.package_usage_count = Usage.search_count(
                [("emar_order_id.prescription_id", "=", record.id)]
            )

    def action_view_package_usages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Package Redemptions"),
            "res_model": "clinic.package.usage",
            "view_mode": "list,form",
            "domain": [("emar_order_id.prescription_id", "=", self.id)],
        }
