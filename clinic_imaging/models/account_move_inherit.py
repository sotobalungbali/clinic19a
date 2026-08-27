# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# Helpers (safe checks)
# =============================================================================
class _AccountingImagingHelpers(models.AbstractModel):
    _name = "clinical.imaging.accounting.helpers"
    _description = "Imaging ↔ Accounting Helpers"

    def _has_model(self, model_name):
        return model_name in self.env

    def _has_field(self, model_name, field_name):
        try:
            return field_name in self.env[model_name]._fields
        except Exception:
            return False


# =============================================================================
# account.move — Imaging-aware Invoice/Refund/Journal Entry
# =============================================================================
class AccountMove(models.Model, _AccountingImagingHelpers):
    _inherit = "account.move"

    # -------------------------------------------------------------------------
    # Context Links (Imaging & Clinical)
    # -------------------------------------------------------------------------
    imaging_id = fields.Many2one(
        "clinical.imaging",
        string="Imaging Record",
        help="The imaging record this invoice refers to."
    )
    imaging_request_id = fields.Many2one(
        "clinical.imaging.request",
        string="Imaging Request",
        help="The imaging request that originated this invoice."
    )
    imaging_result_id = fields.Many2one(
        "clinical.imaging.result",
        string="Imaging Result",
        help="Result/report related to this invoice (if applicable)."
    )
    imaging_type_id = fields.Many2one(
        "clinical.imaging.type",
        string="Imaging Type",
        help="Type of imaging being billed (used for reporting)."
    )
    modality = fields.Selection(
        [
            ("XR", "X-Ray"),
            ("CT", "CT"),
            ("MR", "MRI"),
            ("US", "Ultrasound"),
            ("DX", "Digital Radiography"),
            ("MG", "Mammography"),
            ("NM", "Nuclear Medicine"),
            ("OT", "Other"),
        ],
        string="Modality",
        help="Modality inferred from the Imaging Type or Imaging record."
    )

    # sudah di definisikan sebelumnya
    # di addon clinic_consent_legal file 
    # Clinical context (payer may differ from patient)
    # patient_id = fields.Many2one(
    #     "res.partner",
    #     string="Patient",
    #     help="Patient receiving the service. May differ from the invoice customer."
    # )
    doctor_id = fields.Many2one(
        "hr.employee", string="Ordering/Reading Doctor",
        domain=[("is_doctor", "=", True)]
    )
    appointment_id = fields.Many2one("clinic.appointment", string="Appointment")
    encounter_id = fields.Many2one("clinic.encounter", string="Clinical Encounter")
    treatment_id = fields.Many2one("clinic.treatment", string="Treatment")
    prescription_order_id = fields.Many2one("clinic.emar.order", string="Prescription Order")

    # -------------------------------------------------------------------------
    # Flags & KPIs
    # -------------------------------------------------------------------------
    is_imaging_invoice = fields.Boolean(
        string="Imaging Invoice",
        compute="_compute_imaging_flags_amounts",
        store=False,
        help="Enabled if the invoice has imaging links or imaging lines."
    )
    imaging_amount_untaxed = fields.Monetary(
        string="Imaging Untaxed", currency_field="currency_id",
        compute="_compute_imaging_flags_amounts", store=False
    )
    imaging_amount_tax = fields.Monetary(
        string="Imaging Taxes", currency_field="currency_id",
        compute="_compute_imaging_flags_amounts", store=False
    )
    imaging_amount_total = fields.Monetary(
        string="Imaging Total", currency_field="currency_id",
        compute="_compute_imaging_flags_amounts", store=False
    )

    # Convenience counters
    imaging_line_count = fields.Integer(
        string="Imaging Lines",
        compute="_compute_imaging_flags_amounts",
        store=False
    )

    # -------------------------------------------------------------------------
    # ONCHANGE: propagate links & defaults
    # -------------------------------------------------------------------------
    @api.onchange("imaging_id", "imaging_request_id", "imaging_result_id")
    def _onchange_imaging_links(self):
        """When user picks Imaging/Request/Result, propagate patient/modality/type and clinical context."""
        for rec in self:
            # Resolve from Imaging first
            img = rec.imaging_id
            req = rec.imaging_request_id
            res = rec.imaging_result_id

            # If only Request/Result given, try to find Imaging
            if not img:
                if req and self._has_field("clinical.imaging.request", "imaging_id"):
                    img = req.imaging_id
                elif res and self._has_field("clinical.imaging.result", "imaging_id"):
                    img = res.imaging_id
            if img and not rec.imaging_id:
                rec.imaging_id = img

            # Patient resolution
            patient = False
            if img and self._has_field("clinical.imaging", "patient_id"):
                patient = img.patient_id
            elif req and self._has_field("clinical.imaging.request", "patient_id"):
                patient = req.patient_id
            elif res and self._has_field("clinical.imaging.result", "patient_id"):
                patient = res.patient_id
            if patient:
                rec.patient_id = patient
                # Default customer to patient if empty
                if not rec.partner_id:
                    rec.partner_id = patient

            # Doctor
            if not rec.doctor_id:
                if req and self._has_field("clinical.imaging.request", "requesting_doctor_id"):
                    rec.doctor_id = req.requesting_doctor_id
                elif res and self._has_field("clinical.imaging.result", "author_doctor_id"):
                    rec.doctor_id = res.author_doctor_id

            # Clinical context
            if img:
                if self._has_field("clinical.imaging", "appointment_id") and img.appointment_id:
                    rec.appointment_id = img.appointment_id
                if self._has_field("clinical.imaging", "encounter_id") and img.encounter_id:
                    rec.encounter_id = img.encounter_id
                if self._has_field("clinical.imaging", "treatment_id") and img.treatment_id:
                    rec.treatment_id = img.treatment_id
                if self._has_field("clinical.imaging", "prescription_order_id") and img.prescription_order_id:
                    rec.prescription_order_id = img.prescription_order_id
            elif req:
                if self._has_field("clinical.imaging.request", "appointment_id") and req.appointment_id:
                    rec.appointment_id = req.appointment_id
                if self._has_field("clinical.imaging.request", "encounter_id") and req.encounter_id:
                    rec.encounter_id = req.encounter_id
                if self._has_field("clinical.imaging.request", "treatment_id") and req.treatment_id:
                    rec.treatment_id = req.treatment_id
                if self._has_field("clinical.imaging.request", "prescription_order_id") and req.prescription_order_id:
                    rec.prescription_order_id = req.prescription_order_id

            # Modality & Type
            if not rec.imaging_type_id:
                if img and self._has_field("clinical.imaging", "imaging_type_id"):
                    rec.imaging_type_id = img.imaging_type_id
                elif req and self._has_field("clinical.imaging.request", "imaging_type_id"):
                    rec.imaging_type_id = req.imaging_type_id
                elif res and self._has_field("clinical.imaging.result", "imaging_type_id"):
                    rec.imaging_type_id = res.imaging_type_id
            if not rec.modality and rec.imaging_type_id and self._has_field("clinical.imaging.type", "modality"):
                rec.modality = rec.imaging_type_id.modality

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_imaging_flags_amounts(self):
        for rec in self:
            lines = rec.invoice_line_ids.filtered(lambda l: l.is_imaging_line)
            rec.imaging_line_count = len(lines)
            rec.imaging_amount_untaxed = sum(lines.mapped("price_subtotal"))
            rec.imaging_amount_tax = sum((lines.mapped("price_total"))) - rec.imaging_amount_untaxed
            rec.imaging_amount_total = rec.imaging_amount_untaxed + rec.imaging_amount_tax
            rec.is_imaging_invoice = bool(rec.imaging_id or rec.imaging_request_id or rec.imaging_result_id or rec.imaging_line_count)

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("patient_id", "imaging_id", "imaging_request_id", "imaging_result_id")
    def _check_patient_consistency(self):
        for rec in self:
            if not rec.patient_id:
                continue
            # From Imaging
            if rec.imaging_id and self._has_field("clinical.imaging", "patient_id"):
                if rec.imaging_id.patient_id and rec.imaging_id.patient_id.id != rec.patient_id.id:
                    raise ValidationError(_("Patient on the invoice does not match the linked Imaging record."))
            # From Request
            if rec.imaging_request_id and self._has_field("clinical.imaging.request", "patient_id"):
                if rec.imaging_request_id.patient_id and rec.imaging_request_id.patient_id.id != rec.patient_id.id:
                    raise ValidationError(_("Patient on the invoice does not match the linked Imaging Request."))
            # From Result
            if rec.imaging_result_id and self._has_field("clinical.imaging.result", "patient_id"):
                if rec.imaging_result_id.patient_id and rec.imaging_result_id.patient_id.id != rec.patient_id.id:
                    raise ValidationError(_("Patient on the invoice does not match the linked Imaging Result."))

    # -------------------------------------------------------------------------
    # POSTING HOOKS — mark billed & chatter back to Imaging
    # -------------------------------------------------------------------------
    def _post(self, soft=True):
        """When posting an invoice/refund:
        - Mark imaging as billed if supported.
        - Leave a message on Imaging/Request/Result with invoice info.
        """
        moves = super()._post(soft=soft)
        for move in moves:
            try:
                if move.move_type not in ("out_invoice", "out_refund"):
                    continue
                # Prefer Imaging record
                img = move.imaging_id
                req = move.imaging_request_id
                res = move.imaging_result_id

                # Try to set billed flags if exist
                def _mark_billed(record):
                    if not record:
                        return
                    # common fields to try: billed, billing_state, invoice_ids
                    if self._has_field(record._name, "billed"):
                        record.sudo().write({"billed": True})
                    if self._has_field(record._name, "billing_state"):
                        # Do not overwrite if already 'paid'
                        val = getattr(record, "billing_state", "unbilled")
                        if val not in ("paid", "refunded"):
                            record.sudo().write({"billing_state": "invoiced"})
                    if self._has_field(record._name, "invoice_ids"):
                        record.sudo().write({"invoice_ids": [(4, move.id)]})

                _mark_billed(img)
                _mark_billed(req)
                _mark_billed(res)

                # Chatter note back
                msg = _("Invoiced: %s — Total %s") % (move.name or move.display_name or move.id, move.amount_total_signed)
                if img and hasattr(img, "message_post"):
                    img.message_post(body=msg)
                if req and hasattr(req, "message_post"):
                    req.message_post(body=msg)
                if res and hasattr(res, "message_post"):
                    res.message_post(body=msg)
            except Exception:
                # Never block accounting due to optional modules
                continue
        return moves

    # -------------------------------------------------------------------------
    # ACTIONS (smart buttons / navigations)
    # -------------------------------------------------------------------------
    def action_open_imaging(self):
        self.ensure_one()
        if not self.imaging_id:
            raise UserError(_("No Imaging record linked to this invoice."))
        return {
            "name": _("Imaging"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging",
            "view_mode": "form",
            "res_id": self.imaging_id.id,
            "target": "current",
        }

    def action_open_imaging_request(self):
        self.ensure_one()
        if not self.imaging_request_id:
            raise UserError(_("No Imaging Request linked to this invoice."))
        return {
            "name": _("Imaging Request"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.request",
            "view_mode": "form",
            "res_id": self.imaging_request_id.id,
            "target": "current",
        }

    def action_open_imaging_result(self):
        self.ensure_one()
        if not self.imaging_result_id:
            raise UserError(_("No Imaging Result linked to this invoice."))
        return {
            "name": _("Imaging Result"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.result",
            "view_mode": "form",
            "res_id": self.imaging_result_id.id,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    @api.depends("name", "modality", "imaging_type_id")
    def _compute_display_name(self):
        super()._compute_display_name()
        for rec in self:
            suffix = []
            if rec.modality:
                suffix.append(rec.modality)
            if rec.imaging_type_id:
                suffix.append(rec.imaging_type_id.display_name)
            if suffix:
                rec.display_name = f"{rec.display_name} [{', '.join(suffix)}]"


# =============================================================================
# account.move.line — Imaging-aware Invoice Lines
# =============================================================================
class AccountMoveLine(models.Model, _AccountingImagingHelpers):
    _inherit = "account.move.line"

    # -------------------------------------------------------------------------
    # Imaging linkage at line level (optional, for granular reporting)
    # -------------------------------------------------------------------------
    is_imaging_line = fields.Boolean(
        string="Imaging Line",
        help="Tick if this line corresponds to an imaging service/charge."
    )
    imaging_id = fields.Many2one("clinical.imaging", string="Imaging")
    imaging_request_id = fields.Many2one("clinical.imaging.request", string="Imaging Request")
    imaging_result_id = fields.Many2one("clinical.imaging.result", string="Imaging Result")
    imaging_type_id = fields.Many2one("clinical.imaging.type", string="Imaging Type")
    modality = fields.Selection(
        [
            ("XR", "X-Ray"),
            ("CT", "CT"),
            ("MR", "MRI"),
            ("US", "Ultrasound"),
            ("DX", "Digital Radiography"),
            ("MG", "Mammography"),
            ("NM", "Nuclear Medicine"),
            ("OT", "Other"),
        ],
        string="Modality"
    )
    patient_id = fields.Many2one("res.partner", string="Patient")
    doctor_id = fields.Many2one("hr.employee", string="Doctor", domain=[("is_doctor", "=", True)])

    # -------------------------------------------------------------------------
    # ONCHANGE: Auto-derive flags from product or parent invoice
    # -------------------------------------------------------------------------
    @api.onchange("product_id")
    def _onchange_product_set_imaging_flag(self):
        """Heuristik ringan: tandai sebagai Imaging Line jika produk berkaitan imaging.
        Implementasi minimal: jika nama/categ mengandung 'imaging'/'radiology'.
        Engineer dapat memperkuat heuristik ini pada modul pricing/produk.
        """
        for line in self:
            if not line.product_id:
                continue
            # Keep user control: don't override if already set
            if line.is_imaging_line is False:
                name = (line.product_id.display_name or "").lower()
                categ = (line.product_id.categ_id.display_name or "").lower() if line.product_id.categ_id else ""
                if "imaging" in name or "radiolog" in name or "ct" in name or "mri" in name or "x-ray" in name or "xray" in name or "ultrasound" in name:
                    line.is_imaging_line = True
            # If parent move has context, inherit fields
            move = line.move_id
            if move:
                for f in ("imaging_id", "imaging_request_id", "imaging_result_id", "imaging_type_id", "modality", "patient_id", "doctor_id"):
                    if not getattr(line, f) and hasattr(move, f):
                        setattr(line, f, getattr(move, f))

    @api.onchange("imaging_id", "imaging_request_id", "imaging_result_id")
    def _onchange_line_imaging_links(self):
        for line in self:
            # Default to true when any imaging link set
            if line.imaging_id or line.imaging_request_id or line.imaging_result_id:
                line.is_imaging_line = True
            # Patient/type/modality
            patient = False
            if line.imaging_id and self._has_field("clinical.imaging", "patient_id"):
                patient = line.imaging_id.patient_id
            elif line.imaging_request_id and self._has_field("clinical.imaging.request", "patient_id"):
                patient = line.imaging_request_id.patient_id
            elif line.imaging_result_id and self._has_field("clinical.imaging.result", "patient_id"):
                patient = line.imaging_result_id.patient_id
            if patient and not line.patient_id:
                line.patient_id = patient

            if not line.imaging_type_id:
                if line.imaging_id and self._has_field("clinical.imaging", "imaging_type_id"):
                    line.imaging_type_id = line.imaging_id.imaging_type_id
                elif line.imaging_request_id and self._has_field("clinical.imaging.request", "imaging_type_id"):
                    line.imaging_type_id = line.imaging_request_id.imaging_type_id
                elif line.imaging_result_id and self._has_field("clinical.imaging.result", "imaging_type_id"):
                    line.imaging_type_id = line.imaging_result_id.imaging_type_id

            if not line.modality and line.imaging_type_id and self._has_field("clinical.imaging.type", "modality"):
                line.modality = line.imaging_type_id.modality

            # Propagate to parent move if empty
            mv = line.move_id
            if mv:
                changed = {}
                if not mv.patient_id and line.patient_id:
                    changed["patient_id"] = line.patient_id.id
                if not mv.imaging_type_id and line.imaging_type_id:
                    changed["imaging_type_id"] = line.imaging_type_id.id
                if not mv.modality and line.modality:
                    changed["modality"] = line.modality
                if changed:
                    mv.update(changed)

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("patient_id")
    def _check_line_patient_matches_move(self):
        for line in self:
            if line.patient_id and line.move_id and line.move_id.patient_id and line.patient_id.id != line.move_id.patient_id.id:
                raise ValidationError(_("Line Patient must match the invoice Patient to avoid ambiguity."))

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    @api.depends("name", "is_imaging_line", "modality", "imaging_type_id")
    def _compute_display_name(self):
        super()._compute_display_name()
        for line in self:
            tag = []
            if line.is_imaging_line:
                tag.append(_("Imaging"))
            if line.modality:
                tag.append(line.modality)
            if line.imaging_type_id:
                tag.append(line.imaging_type_id.display_name)
            if tag:
                line.display_name = f"{line.display_name} [{' / '.join(tag)}]"
