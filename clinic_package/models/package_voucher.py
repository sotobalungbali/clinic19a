
# -*- coding: utf-8 -*-
"""Voucher issuance and redemption into package allocations."""

import secrets
import string
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicPackageVoucher(models.Model):
    _name = "clinic.package.voucher"
    _description = "Clinic Package Voucher"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "issue_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, readonly=True, copy=False, default="/", index=True)
    code = fields.Char(required=True, readonly=True, copy=False, index=True)
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("issued", "Issued"),
            ("redeemed", "Redeemed"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
    )
    package_id = fields.Many2one(
        "clinic.package", required=True, ondelete="restrict", tracking=True, check_company=True
    )
    partner_id = fields.Many2one("res.partner", string="Locked Contact", ondelete="restrict")
    patient_id = fields.Many2one("clinic.patient", string="Locked Patient", ondelete="restrict", check_company=True)
    is_bearer = fields.Boolean(compute="_compute_is_bearer")
    channel = fields.Selection(
        [
            ("frontdesk", "Front Desk"),
            ("campaign", "Campaign"),
            ("gift", "Gift"),
            ("online", "Online"),
            ("other", "Other"),
        ],
        default="frontdesk",
        required=True,
    )
    branch_id = fields.Many2one("clinic.branch", ondelete="restrict", check_company=True)
    batch_id = fields.Many2one("clinic.package.voucher.batch", ondelete="set null", index=True)
    issue_date = fields.Date(readonly=True)
    valid_from = fields.Date()
    valid_to = fields.Date()
    is_expired = fields.Boolean(compute="_compute_is_expired")
    redeemed_on = fields.Datetime(readonly=True)
    redeemed_by_user_id = fields.Many2one("res.users", readonly=True)
    redeemed_allocation_id = fields.Many2one("clinic.package.allocation", readonly=True, ondelete="set null")
    sale_order_id = fields.Many2one("sale.order", ondelete="set null", check_company=True)
    invoice_id = fields.Many2one("account.move", ondelete="set null", check_company=True)
    enforce_branch = fields.Boolean(default=True)
    allow_redeem_when_package_paused = fields.Boolean(default=False)
    note = fields.Text()
    internal_note = fields.Text()

    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "Voucher code must be unique per company.",
    )
    _name_company_uniq = models.Constraint(
        "unique(name, company_id)",
        "Voucher number must be unique per company.",
    )

    @api.depends("partner_id", "patient_id")
    def _compute_is_bearer(self):
        for record in self:
            record.is_bearer = not record.partner_id and not record.patient_id

    @api.depends("valid_to", "state")
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_expired = bool(record.valid_to and record.valid_to < today and record.state != "redeemed")

    @api.constrains("valid_from", "valid_to")
    def _check_validity_dates(self):
        for record in self:
            if record.valid_from and record.valid_to and record.valid_to < record.valid_from:
                raise ValidationError(_("Voucher Valid To cannot be before Valid From."))

    @api.constrains("patient_id", "partner_id")
    def _check_locked_identity(self):
        for record in self:
            if record.patient_id.partner_id and record.partner_id and record.patient_id.partner_id != record.partner_id:
                raise ValidationError(_("Locked contact must match the selected patient's linked contact."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("state", "draft") != "draft" and not self.env.context.get("clinic_package_state_change"):
                raise UserError(_("Vouchers must be created in Draft and issued through the approved action."))
            vals.setdefault("company_id", self.env.company.id)
            if vals.get("name") in (False, "/", None):
                vals["name"] = self.env["ir.sequence"].next_by_code("clinic.package.voucher") or "/"
            if not vals.get("code"):
                vals["code"] = self._generate_unique_code(vals["company_id"])
            if vals.get("patient_id") and not vals.get("partner_id"):
                patient = self.env["clinic.patient"].browse(vals["patient_id"])
                vals["partner_id"] = patient.partner_id.id or False
        return super().create(vals_list)

    @api.model
    def _generate_unique_code(self, company_id):
        company = self.env["res.company"].browse(company_id)
        prefix = company.clinic_pkg_voucher_prefix or "PKG"
        length = max(company.clinic_pkg_voucher_code_length or 10, 6)
        alphabet = string.ascii_uppercase + string.digits
        for _attempt in range(20):
            token = "".join(secrets.choice(alphabet) for _ in range(length))
            code = f"{prefix}-{token}"
            if not self.search_count([("company_id", "=", company_id), ("code", "=", code)]):
                return code
        raise UserError(_("Unable to generate a unique voucher code. Please try again."))

    def write(self, vals):
        if "state" in vals and not self.env.context.get("clinic_package_state_change"):
            raise UserError(_("Voucher status can only be changed through workflow actions."))
        protected = {"package_id", "partner_id", "patient_id", "company_id", "code"}
        if protected.intersection(vals) and any(record.state != "draft" for record in self):
            raise UserError(_("Issued vouchers cannot change package or locked recipient identity."))
        return super().write(vals)

    def action_issue(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only Draft vouchers can be issued."))
            if record.package_id.state not in ("active", "paused"):
                raise UserError(_("Voucher package must be Active or Paused."))
            valid_from = record.valid_from or today
            valid_to = record.valid_to
            if not valid_to:
                days = record.company_id.clinic_pkg_voucher_valid_days or 30
                valid_to = valid_from + timedelta(days=days)
            record.with_context(clinic_package_state_change=True).write({"state": "issued", "issue_date": today, "valid_from": valid_from, "valid_to": valid_to})
            record._enqueue_integration_event("voucher.issued")
        return True

    def action_cancel(self):
        for record in self:
            if record.state not in ("draft", "issued"):
                raise UserError(_("Only Draft or Issued vouchers can be cancelled."))
            record.with_context(clinic_package_state_change=True).write({"state": "cancelled", "active": False})
            record._enqueue_integration_event("voucher.cancelled")
        return True

    def action_redeem(self):
        self.ensure_one()
        patient = self.patient_id
        if not patient:
            raise UserError(_("Select or lock a patient before redeeming the voucher from the back office."))
        return self._redeem_to_patient(patient, self.branch_id)

    def _redeem_to_patient(self, patient, branch=False):
        self.ensure_one()
        today = fields.Date.context_today(self)
        if self.state != "issued":
            raise UserError(_("Only Issued vouchers can be redeemed."))
        if self.valid_from and today < self.valid_from:
            raise UserError(_("This voucher is not valid yet."))
        if self.valid_to and today > self.valid_to:
            self.with_context(clinic_package_state_change=True).write({"state": "expired"})
            raise UserError(_("This voucher has expired."))
        if self.patient_id and self.patient_id != patient:
            raise UserError(_("This voucher is locked to another patient."))
        if self.partner_id and patient.partner_id != self.partner_id:
            raise UserError(_("This voucher is locked to another contact."))
        if self.enforce_branch and self.branch_id and branch and self.branch_id != branch:
            raise UserError(_("This voucher must be redeemed at its issuing branch."))
        if self.package_id.state == "paused" and not self.allow_redeem_when_package_paused:
            raise UserError(_("This voucher cannot be redeemed while the package catalog is paused."))
        if self.package_id.state not in ("active", "paused"):
            raise UserError(_("This voucher package is not currently redeemable."))

        allocation = self.env["clinic.package.allocation"].create(
            {
                "package_id": self.package_id.id,
                "patient_id": patient.id,
                "partner_id": patient.partner_id.id or False,
                "branch_id": (branch or self.branch_id).id,
                "source_voucher_id": self.id,
                "company_id": self.company_id.id,
            }
        )
        allocation.action_activate()
        self.with_context(clinic_package_state_change=True).write(
            {
                "state": "redeemed",
                "patient_id": patient.id,
                "partner_id": patient.partner_id.id or False,
                "redeemed_on": fields.Datetime.now(),
                "redeemed_by_user_id": self.env.user.id,
                "redeemed_allocation_id": allocation.id,
            }
        )
        self._enqueue_integration_event("voucher.redeemed", {"allocation_id": allocation.id})
        return {
            "type": "ir.actions.act_window",
            "name": _("Package Allocation"),
            "res_model": "clinic.package.allocation",
            "view_mode": "form",
            "res_id": allocation.id,
        }

    def action_view_allocation(self):
        self.ensure_one()
        if not self.redeemed_allocation_id:
            raise UserError(_("This voucher has not created an allocation."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Package Allocation"),
            "res_model": "clinic.package.allocation",
            "view_mode": "form",
            "res_id": self.redeemed_allocation_id.id,
        }

    @api.model
    def _cron_expire_vouchers(self):
        today = fields.Date.context_today(self)
        companies = self.env["res.company"].sudo().search([]).filtered(
            lambda company: company.clinic_pkg_auto_expire_vouchers
        )
        vouchers = self.sudo().search(
            [
                ("company_id", "in", companies.ids),
                ("state", "=", "issued"),
                ("valid_to", "<", today),
            ]
        )
        if vouchers:
            vouchers.with_context(clinic_package_state_change=True).write({"state": "expired"})
        return True

    def _enqueue_integration_event(self, event_code, payload=None):
        self.ensure_one()
        return self.env["clinic.package.integration.event"].enqueue(event_code, self, payload=payload)


class ClinicPackageVoucherBatch(models.Model):
    _name = "clinic.package.voucher.batch"
    _description = "Clinic Package Voucher Batch"
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(required=True, readonly=True, copy=False, default="/", index=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    package_id = fields.Many2one("clinic.package", required=True, ondelete="restrict", check_company=True)
    quantity = fields.Integer(default=10, required=True)
    channel = fields.Selection(
        [("frontdesk", "Front Desk"), ("campaign", "Campaign"), ("gift", "Gift"), ("online", "Online"), ("other", "Other")],
        default="campaign",
        required=True,
    )
    branch_id = fields.Many2one("clinic.branch", ondelete="restrict", check_company=True)
    partner_id = fields.Many2one("res.partner", string="Default Locked Contact")
    patient_id = fields.Many2one("clinic.patient", string="Default Locked Patient", check_company=True)
    valid_from = fields.Date()
    valid_to = fields.Date()
    voucher_ids = fields.One2many("clinic.package.voucher", "batch_id", readonly=True)
    voucher_count = fields.Integer(compute="_compute_voucher_count")
    state = fields.Selection(
        [("draft", "Draft"), ("generated", "Generated"), ("issued", "Issued"), ("cancelled", "Cancelled")],
        default="draft",
        required=True,
        index=True,
    )
    note = fields.Text()

    _quantity_positive = models.Constraint(
        "CHECK(quantity > 0)",
        "Voucher batch quantity must be greater than zero.",
    )

    def _compute_voucher_count(self):
        for record in self:
            record.voucher_count = len(record.voucher_ids)

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("state", "draft") != "draft" and not self.env.context.get("clinic_package_state_change"):
                raise UserError(_("Voucher batches must be created in Draft."))
            if vals.get("name") in (False, "/", None):
                vals["name"] = sequence.next_by_code("clinic.package.voucher.batch") or "/"
        return super().create(vals_list)

    def write(self, vals):
        if "state" in vals and not self.env.context.get("clinic_package_state_change"):
            raise UserError(_("Voucher batch status can only be changed through workflow actions."))
        return super().write(vals)

    def action_generate(self):
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only Draft batches can generate vouchers."))
            commands = []
            for _index in range(record.quantity):
                commands.append(
                    (0, 0, {
                        "package_id": record.package_id.id,
                        "company_id": record.company_id.id,
                        "channel": record.channel,
                        "branch_id": record.branch_id.id,
                        "partner_id": record.partner_id.id,
                        "patient_id": record.patient_id.id,
                        "valid_from": record.valid_from,
                        "valid_to": record.valid_to,
                    })
                )
            record.with_context(clinic_package_state_change=True).write({"voucher_ids": commands, "state": "generated"})
        return True

    def action_issue_all(self):
        for record in self:
            if record.state not in ("generated", "draft"):
                raise UserError(_("Only Draft or Generated batches can be issued."))
            if record.state == "draft":
                record.action_generate()
            record.voucher_ids.filtered(lambda voucher: voucher.state == "draft").action_issue()
            record.with_context(clinic_package_state_change=True).write({"state": "issued"})
        return True

    def action_view_vouchers(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Batch Vouchers"),
            "res_model": "clinic.package.voucher",
            "view_mode": "list,form",
            "domain": [("batch_id", "=", self.id)],
        }
