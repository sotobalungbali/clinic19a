# -*- coding: utf-8 -*-
# ClinicOne Billing — authoritative clinical traceability bridge for Odoo 19 CE.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicTreatmentBillingLink(models.Model):
    """Immutable uniqueness bridge from an upstream clinical source to one billing line."""

    _name = "clinic.treatment.billing.link"
    _description = "Clinical Source to Billing Link"
    _order = "id desc"
    _check_company_auto = True

    billing_line_id = fields.Many2one(
        "clinic.billing.line", required=True, ondelete="cascade", index=True, check_company=True
    )
    invoice_id = fields.Many2one(
        related="billing_line_id.invoice_id", store=True, readonly=True
    )
    patient_id = fields.Many2one(
        related="invoice_id.patient_id", store=True, readonly=True
    )
    company_id = fields.Many2one(
        related="invoice_id.company_id", store=True, readonly=True
    )
    origin_model = fields.Char(required=True, index=True)
    origin_id = fields.Integer(required=True, index=True)
    origin_name = fields.Char()
    note = fields.Char()

    _origin_unique = models.Constraint(
        "UNIQUE(origin_model, origin_id)",
        "This clinical source record has already been billed.",
    )

    def action_open_origin(self):
        self.ensure_one()
        if self.origin_model not in self.env:
            raise UserError(_("Origin model '%s' is not available.") % self.origin_model)
        record = self.env[self.origin_model].browse(self.origin_id).exists()
        if not record:
            raise UserError(_("The source record no longer exists."))
        return {
            "type": "ir.actions.act_window",
            "name": self.origin_name or _("Clinical Source"),
            "res_model": self.origin_model,
            "view_mode": "form",
            "res_id": record.id,
            "target": "current",
        }


class ClinicBillingLineClinicalTraceability(models.Model):
    _inherit = "clinic.billing.line"

    treatment_id = fields.Many2one(
        "clinic.treatment", string="Treatment", index=True, check_company=True
    )
    booking_id = fields.Many2one(
        "booking.booking", string="Booking", index=True, check_company=True
    )
    encounter_id = fields.Many2one(
        "clinic.encounter", string="Encounter", index=True, check_company=True
    )
    care_plan_id = fields.Many2one(
        "clinic.care.plan", string="Care Plan", index=True, check_company=True
    )
    care_plan_line_id = fields.Many2one(
        "clinic.care.plan.line", string="Care Plan Line", index=True, check_company=True
    )
    package_usage_id = fields.Many2one(
        "clinic.package.usage", string="Package Redemption", index=True, check_company=True
    )
    emar_administration_id = fields.Many2one(
        "clinic.emar.administration", string="eMAR Administration", index=True, check_company=True
    )
    treatment_usage_id = fields.Many2one(
        "clinic.treatment.product.usage", string="Inventory Treatment Usage", index=True, check_company=True
    )
    room_id = fields.Many2one(
        "clinic.room", string="Room", index=True, check_company=True
    )
    device_id = fields.Many2one(
        "clinic.device", string="Device", index=True, check_company=True
    )
    performed_datetime = fields.Datetime(string="Performed On", index=True)

    # Compatibility references retained for existing databases/import integrations.
    treatment_ref = fields.Reference(
        selection="_selection_treatment_ref",
        string="Treatment Reference",
        help="Compatibility reference. New code should prefer the typed fields above.",
    )
    booking_ref = fields.Reference(
        selection="_selection_booking_ref",
        string="Booking Reference",
        help="Compatibility reference. New code should prefer booking_id.",
    )
    room_ref = fields.Reference(
        selection="_selection_room_ref",
        string="Room Reference",
        help="Compatibility reference. New code should prefer room_id.",
    )
    device_ref = fields.Reference(
        selection="_selection_device_ref",
        string="Device Reference",
        help="Compatibility reference. New code should prefer device_id.",
    )
    treatment_origin_model = fields.Char(string="Origin Model (Legacy)", index=True)
    treatment_origin_id = fields.Integer(string="Origin Record ID (Legacy)", index=True)
    treatment_link_id = fields.Many2one(
        "clinic.treatment.billing.link", string="Clinical Source Link", copy=False
    )

    @api.model
    def _selection_treatment_ref(self):
        candidates = [
            ("clinic.treatment", _("Treatment")),
            ("clinic.encounter", _("Encounter")),
            ("clinic.care.plan.line", _("Care Plan Line")),
            ("clinic.emar.administration", _("eMAR Administration")),
            ("clinic.treatment.product.usage", _("Treatment Product Usage")),
        ]
        return [(model, label) for model, label in candidates if model in self.env]

    @api.model
    def _selection_booking_ref(self):
        return [("booking.booking", _("Booking"))] if "booking.booking" in self.env else []

    @api.model
    def _selection_room_ref(self):
        return [("clinic.room", _("Clinic Room"))] if "clinic.room" in self.env else []

    @api.model
    def _selection_device_ref(self):
        return [("clinic.device", _("Clinic Device"))] if "clinic.device" in self.env else []

    @api.constrains("treatment_origin_model", "treatment_origin_id")
    def _check_unique_legacy_origin(self):
        for rec in self.filtered(lambda item: item.treatment_origin_model and item.treatment_origin_id):
            duplicate = self.search_count([
                ("id", "!=", rec.id),
                ("treatment_origin_model", "=", rec.treatment_origin_model),
                ("treatment_origin_id", "=", rec.treatment_origin_id),
            ])
            if duplicate:
                raise ValidationError(_("The same clinical source has been billed more than once."))

    def _ensure_treatment_link(self, origin_record):
        self.ensure_one()
        origin_record = origin_record.exists()
        if not origin_record:
            return False

        Link = self.env["clinic.treatment.billing.link"].sudo()
        existing = Link.search([
            ("origin_model", "=", origin_record._name),
            ("origin_id", "=", origin_record.id),
        ], limit=1)
        if existing and existing.billing_line_id != self:
            raise ValidationError(_("This clinical source is already linked to another billing line."))

        link = existing or Link.create({
            "billing_line_id": self.id,
            "origin_model": origin_record._name,
            "origin_id": origin_record.id,
            "origin_name": origin_record.display_name,
        })
        if self.treatment_link_id != link:
            self.treatment_link_id = link
        return link

    def action_open_clinical_source(self):
        self.ensure_one()
        if self.treatment_link_id:
            return self.treatment_link_id.action_open_origin()

        for field_name in (
            "emar_administration_id",
            "package_usage_id",
            "care_plan_line_id",
            "booking_id",
            "encounter_id",
            "treatment_id",
            "treatment_usage_id",
        ):
            record = self[field_name]
            if record:
                return {
                    "type": "ir.actions.act_window",
                    "name": record.display_name,
                    "res_model": record._name,
                    "view_mode": "form",
                    "res_id": record.id,
                    "target": "current",
                }
        raise UserError(_("No clinical source is linked to this billing line."))


class ClinicBillingInvoiceClinicalTraceability(models.Model):
    _inherit = "clinic.billing.invoice"

    treatment_line_count = fields.Integer(
        string="Clinical Source Lines", compute="_compute_treatment_line_count"
    )
    emar_line_count = fields.Integer(
        string="eMAR Lines", compute="_compute_traceability_counts"
    )
    package_line_count = fields.Integer(
        string="Package Lines", compute="_compute_traceability_counts"
    )

    @api.depends(
        "line_ids.treatment_link_id",
        "line_ids.emar_administration_id",
        "line_ids.package_usage_id",
    )
    def _compute_treatment_line_count(self):
        for rec in self:
            rec.treatment_line_count = len(rec.line_ids.filtered("treatment_link_id"))

    @api.depends("line_ids.emar_administration_id", "line_ids.package_usage_id")
    def _compute_traceability_counts(self):
        for rec in self:
            rec.emar_line_count = len(rec.line_ids.filtered("emar_administration_id"))
            rec.package_line_count = len(rec.line_ids.filtered("package_usage_id"))

    def _assert_importable(self):
        self.ensure_one()
        if self.state not in ("draft", "confirmed"):
            raise UserError(_("Clinical lines can only be imported while the billing document is Draft or Confirmed."))
        if self.move_id and self.move_id.state == "posted":
            raise UserError(_("Clinical lines cannot be changed after the accounting invoice is posted."))

    def _create_billable_line(self, source, values):
        self.ensure_one()
        source = source.exists()
        if not source:
            return self.env["clinic.billing.line"]

        existing = self.env["clinic.treatment.billing.link"].sudo().search([
            ("origin_model", "=", source._name),
            ("origin_id", "=", source.id),
        ], limit=1)
        if existing:
            if existing.invoice_id == self:
                return existing.billing_line_id
            raise ValidationError(
                _("Clinical source %s has already been billed on %s.")
                % (source.display_name, existing.invoice_id.display_name)
            )

        product = values.get("product")
        tax_ids = values.get("tax_ids") or (product.taxes_id if product else self.env["account.tax"])
        uom = values.get("uom") or (product.uom_id if product else False)
        line = self.env["clinic.billing.line"].create({
            "invoice_id": self.id,
            "name": values.get("name") or (product.display_name if product else source.display_name),
            "product_id": product.id if product else False,
            "product_uom_id": uom.id if uom else False,
            "quantity": values.get("quantity", 1.0) or 1.0,
            "unit_price": values.get("unit_price", 0.0) or 0.0,
            "discount_percent": values.get("discount_percent", 0.0) or 0.0,
            "tax_ids": [(6, 0, tax_ids.ids)] if tax_ids else False,
            "treatment_id": values.get("treatment_id") and values["treatment_id"].id or False,
            "booking_id": values.get("booking_id") and values["booking_id"].id or False,
            "encounter_id": values.get("encounter_id") and values["encounter_id"].id or False,
            "care_plan_id": values.get("care_plan_id") and values["care_plan_id"].id or False,
            "care_plan_line_id": values.get("care_plan_line_id") and values["care_plan_line_id"].id or False,
            "package_usage_id": values.get("package_usage_id") and values["package_usage_id"].id or False,
            "emar_administration_id": values.get("emar_administration_id") and values["emar_administration_id"].id or False,
            "treatment_usage_id": values.get("treatment_usage_id") and values["treatment_usage_id"].id or False,
            "room_id": values.get("room_id") and values["room_id"].id or False,
            "device_id": values.get("device_id") and values["device_id"].id or False,
            "performed_datetime": values.get("performed_datetime") or False,
            "provider_partner_id": values.get("provider_partner_id") and values["provider_partner_id"].id or False,
        })
        line._ensure_treatment_link(source)
        return line

    def action_import_from_booking(self):
        self._assert_importable()
        booking = self.booking_id
        if not booking:
            raise UserError(_("Select a Booking first."))

        created = self.env["clinic.billing.line"]
        for source_line in booking.line_ids.filtered(lambda line: not line.display_type):
            created |= self._create_billable_line(source_line, {
                "product": source_line.product_id,
                "name": source_line.name,
                "quantity": source_line.product_uom_qty,
                "unit_price": source_line.price_unit,
                "discount_percent": source_line.discount,
                "tax_ids": source_line.tax_ids,
                "uom": source_line.product_uom,
                "treatment_id": source_line.treatment_id or booking.treatment_id,
                "booking_id": booking,
                "room_id": booking.room_id,
                "provider_partner_id": booking.doctor_id.partner_id if booking.doctor_id else False,
                "performed_datetime": booking.start_datetime,
            })
        if not created:
            raise UserError(_("No new billable booking lines were found."))
        self._sync_draft_account_move_if_needed()
        return True

    def action_import_from_care_plan(self):
        self._assert_importable()
        care_plan = self.care_plan_id
        if not care_plan:
            raise UserError(_("Select a Care Plan first."))

        created = self.env["clinic.billing.line"]
        for source_line in care_plan.line_ids.filtered(lambda line: line.state != "cancelled"):
            product = source_line.product_id
            if not product and not source_line.treatment_id:
                continue
            created |= self._create_billable_line(source_line, {
                "product": product,
                "name": source_line.name or source_line.description,
                "quantity": source_line.qty,
                "unit_price": source_line.price_unit,
                "tax_ids": source_line.tax_ids,
                "uom": source_line.uom_id,
                "treatment_id": source_line.treatment_id,
                "booking_id": source_line.booking_id,
                "care_plan_id": care_plan,
                "care_plan_line_id": source_line,
                "provider_partner_id": source_line.doctor_id.partner_id if source_line.doctor_id else False,
                "performed_datetime": source_line.start_datetime or source_line.scheduled_datetime,
            })
        if not created:
            raise UserError(_("No new billable care-plan lines were found."))
        self._sync_draft_account_move_if_needed()
        return True

    def action_import_from_emar(self):
        self._assert_importable()
        if not self.clinic_patient_id:
            raise UserError(_("Set the Clinic Patient before importing eMAR administrations."))

        Administration = self.env["clinic.emar.administration"]
        administrations = Administration.search([
            ("patient_id", "=", self.clinic_patient_id.id),
            ("company_id", "=", self.company_id.id),
            ("state", "=", "done"),
        ])
        if self.encounter_id:
            administrations = administrations.filtered(
                lambda adm: adm.order_id.encounter_id == self.encounter_id
            )

        created = self.env["clinic.billing.line"]
        for administration in administrations:
            product = administration.product_id
            if not product:
                continue
            qty = administration.inventory_qty or 1.0
            created |= self._create_billable_line(administration, {
                "product": product,
                "name": _("Medication administration: %s") % product.display_name,
                "quantity": qty,
                "unit_price": product.lst_price,
                "uom": administration.inventory_uom_id or product.uom_id,
                "treatment_id": administration.order_id.treatment_id,
                "booking_id": administration.order_id.booking_id,
                "encounter_id": administration.order_id.encounter_id,
                "emar_administration_id": administration,
                "room_id": administration.room_session_id.room_id if (
                    administration.room_session_id and "room_id" in administration.room_session_id._fields
                ) else False,
                "provider_partner_id": administration.doctor_id.partner_id if administration.doctor_id else False,
                "performed_datetime": administration.administered_datetime,
            })
        if not created:
            raise UserError(_("No new completed eMAR administrations were available to bill."))
        self._sync_draft_account_move_if_needed()
        return True

    def _sync_draft_account_move_if_needed(self):
        self.ensure_one()
        if self.move_id and self.move_id.state == "draft":
            self.action_sync_lines_to_account_move()

    def action_open_treatment_links(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinical Source Links"),
            "res_model": "clinic.treatment.billing.link",
            "view_mode": "list,form",
            "domain": [("invoice_id", "=", self.id)],
            "context": {"default_invoice_id": self.id},
        }

    def action_open_emar_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("eMAR Billing Lines"),
            "res_model": "clinic.billing.line",
            "view_mode": "list,form",
            "domain": [("invoice_id", "=", self.id), ("emar_administration_id", "!=", False)],
            "context": {"default_invoice_id": self.id},
        }

    def action_open_package_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Package-linked Billing Lines"),
            "res_model": "clinic.billing.line",
            "view_mode": "list,form",
            "domain": [("invoice_id", "=", self.id), ("package_usage_id", "!=", False)],
            "context": {"default_invoice_id": self.id},
        }

    def action_unlink_treatment_links(self):
        for rec in self:
            if rec.move_id and rec.move_id.state == "posted":
                raise UserError(_("Clinical source links cannot be removed after posting."))
            rec.line_ids.mapped("treatment_link_id").unlink()
        return True
