# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


# =============================================================================
# Helpers (safe checks)
# =============================================================================
class _PrescriptionImagingHelpers(models.AbstractModel):
    _name = "clinical.imaging.prescription.helpers"
    _description = "Prescription ↔ Imaging Helpers"

    def _has_model(self, model_name):
        return model_name in self.env

    def _has_field(self, model_name, field_name):
        try:
            return field_name in self.env[model_name]._fields
        except Exception:
            return False

    def _now(self):
        return fields.Datetime.now()

    def _today_bounds(self):
        start = fields.Datetime.to_datetime(fields.Date.to_string(fields.Date.context_today(self)))
        end = start + timedelta(days=1, seconds=-1)
        return start, end


# =============================================================================
# Premedication Protocol (Contrast)
# =============================================================================
class ClinicalImagingPremedProtocol(models.Model):
    _name = "clinical.imaging.premed.protocol"
    _description = "Imaging Contrast Premedication Protocol"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(string="Protocol Name", required=True)
    code = fields.Char(string="Code")
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one("res.company", string="Company", default=lambda s: s.env.company, required=True)
    active = fields.Boolean(default=True)

    allergy_type = fields.Selection(
        [("iodinated", "Iodinated Contrast"), ("gadolinium", "Gadolinium"), ("unknown", "Unknown/Other")],
        string="Allergy Type", default="iodinated",
        help="Contrast type for which this premedication protocol applies."
    )
    regimen = fields.Text(
        string="Regimen",
        help="Textual instruction for premedication regimen (e.g., steroids/antihistamines with timing)."
    )
    precautions = fields.Text(string="Precautions / Notes")
    reference = fields.Char(string="Reference")

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Protocol Code must be unique per company.',
    )


# =============================================================================
# Inherit clinic.prescription.order — Imaging Integrations
# =============================================================================
class ClinicPrescriptionOrder(models.Model, _PrescriptionImagingHelpers):
    _inherit = "clinic.emar.order" # "clinic.prescription.order"

    # -------------------------------------------------------------------------
    # Imaging linkage and planning
    # -------------------------------------------------------------------------
    imaging_type_id = fields.Many2one(
        "clinical.imaging.type",
        string="Imaging Type",
        help="If set, this prescription intends to request the selected imaging exam."
    )
    imaging_priority = fields.Selection(
        [("routine", "Routine"), ("urgent", "Urgent"), ("stat", "STAT")],
        string="Imaging Priority", default="routine"
    )
    imaging_indication = fields.Text(
        string="Imaging Clinical Indication",
        help="Clinical question/reason for the imaging exam."
    )
    imaging_instructions = fields.Text(
        string="Imaging Special Instructions",
        help="Preparation/special instructions (fasting, hydration, etc.)."
    )

    # Safety & protocols
    contrast_premed_required = fields.Boolean(
        string="Contrast Premedication Required",
        help="Check if premedication must be given before contrast administration."
    )
    contrast_type = fields.Selection(
        [("iodinated", "Iodinated Contrast"), ("gadolinium", "Gadolinium"), ("other", "Other/Unknown")],
        string="Contrast Type"
    )
    premed_protocol_id = fields.Many2one(
        "clinical.imaging.premed.protocol",
        string="Premedication Protocol",
        help="Selected protocol for contrast premedication."
    )
    hydration_required = fields.Boolean(
        string="Hydration Required",
        help="Check if pre- or post-procedure hydration is required (renal risk)."
    )
    hydration_plan = fields.Text(string="Hydration Plan/Instruction")

    sedation_required = fields.Boolean(string="Sedation Required")
    sedation_plan = fields.Selection(
        [("minimal", "Minimal"), ("conscious", "Conscious Sedation"),
         ("deep", "Deep Sedation"), ("ga", "General Anesthesia")],
        string="Sedation Plan"
    )
    sedation_supervised_by_id = fields.Many2one(
        "hr.employee", string="Sedation Supervisor",
        domain=[("is_doctor", "=", True)],
        help="Doctor who will supervise sedation if required."
    )

    consent_id = fields.Many2one("clinic.consent.form", string="Consent", help="Related consent document if applicable.")
    portal_share_imaging = fields.Boolean(
        string="Share Imaging on Portal",
        default=True,
        help="When enabled, related imaging key images/results can be shared with the patient portal (subject to portal settings)."
    )

    # -------------------------------------------------------------------------
    # Back-links to Imaging objects (One2many via field added in this file)
    # -------------------------------------------------------------------------
    imaging_request_ids = fields.One2many(
        "clinical.imaging.request",
        "prescription_order_id",
        string="Imaging Requests"
    )
    imaging_request_count = fields.Integer(string="Imaging Requests", compute="_compute_imaging_counts", store=False)

    imaging_result_count = fields.Integer(string="Imaging Results", compute="_compute_imaging_counts", store=False)
    imaging_count = fields.Integer(string="Imaging Records", compute="_compute_imaging_counts", store=False)
    imaging_key_image_count = fields.Integer(string="Key Images", compute="_compute_imaging_counts", store=False)

    has_imaging_pending = fields.Boolean(
        string="Has Pending Imaging",
        compute="_compute_pending",
        store=False
    )

    # -------------------------------------------------------------------------
    # Contextual links (read-only via related if present on base model)
    # -------------------------------------------------------------------------
    patient_id = fields.Many2one(
        "res.partner", string="Patient",
        help="Patient for this prescription (if available in the base model)."
    )
    doctor_id = fields.Many2one(
        "hr.employee", string="Prescribing Doctor",
        help="Doctor who authored this prescription (if available)."
    )
    appointment_id = fields.Many2one("clinic.appointment", string="Appointment")
    encounter_id = fields.Many2one("clinic.encounter", string="Clinical Encounter")
    treatment_id = fields.Many2one("clinic.treatment", string="Treatment")

    # Catatan: Bila di base model field-field di atas sudah ada, field definisi ini
    # akan dianggap sebagai override (type/label sama). Jika belum ada, field akan
    # tersedia untuk integrasi lintas modul.

    # -------------------------------------------------------------------------
    # ONCHANGE / CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.onchange("contrast_premed_required", "contrast_type")
    def _onchange_premed_required(self):
        for rec in self:
            if rec.contrast_premed_required and not rec.premed_protocol_id:
                # pilih protokol default berdasarkan contrast_type
                proto = self.env["clinical.imaging.premed.protocol"].search([
                    ("company_id", "=", rec.company_id.id),
                    ("active", "=", True),
                    ("allergy_type", "in", [rec.contrast_type or "unknown", "unknown"]),
                ], limit=1, order="sequence, id")
                if proto:
                    rec.premed_protocol_id = proto.id

    @api.constrains("sedation_required", "sedation_plan", "sedation_supervised_by_id")
    def _check_sedation_supervision(self):
        for rec in self:
            if rec.sedation_required and not rec.sedation_supervised_by_id:
                raise ValidationError(_("Sedation Supervisor must be set when Sedation is required."))

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------
    def _compute_imaging_counts(self):
        Imaging = self.env["clinical.imaging"].sudo() if self._has_model("clinical.imaging") else None
        Result = self.env["clinical.imaging.result"].sudo() if self._has_model("clinical.imaging.result") else None
        Image = self.env["clinical.imaging.image"].sudo() if self._has_model("clinical.imaging.image") else None

        for rec in self:
            # Requests via O2M
            rec.imaging_request_count = len(rec.imaging_request_ids)

            # Imaging & Results via request/imaging linkage
            imaging_ids = []
            if Imaging and rec.imaging_request_ids:
                imaging_ids = Imaging.search([("request_id", "in", rec.imaging_request_ids.ids)]).ids \
                    if self._has_field("clinical.imaging", "request_id") else []

            rec.imaging_count = len(imaging_ids)

            if Result:
                # Prefer direct link if we add field prescription_order_id to Result below
                res_cnt = Result.search_count([("prescription_order_id", "=", rec.id)])
                if not res_cnt and imaging_ids:
                    res_cnt = Result.search_count([("imaging_id", "in", imaging_ids)])
                rec.imaging_result_count = res_cnt
            else:
                rec.imaging_result_count = 0

            if Image and imaging_ids and self._has_field("clinical.imaging.image", "is_key"):
                rec.imaging_key_image_count = Image.search_count([("imaging_id", "in", imaging_ids), ("is_key", "=", True)])
            else:
                rec.imaging_key_image_count = 0

    def _compute_pending(self):
        Result = self.env["clinical.imaging.result"].sudo() if self._has_model("clinical.imaging.result") else None
        for rec in self:
            pending = False
            if rec.imaging_request_ids:
                if self._has_field("clinical.imaging.request", "state"):
                    pending_req = rec.imaging_request_ids.filtered(lambda r: r.state in ("draft", "submitted", "approved", "scheduled", "in_progress"))
                    pending = bool(pending_req)
            if not pending and Result and self._has_field("clinical.imaging.result", "state"):
                # any non-final results linked to this prescription?
                res = Result.search_count([("prescription_order_id", "=", rec.id), ("state", "not in", ["final", "amended"])])
                pending = pending or bool(res)
            rec.has_imaging_pending = pending

    # -------------------------------------------------------------------------
    # Actions (Smart buttons + generator)
    # -------------------------------------------------------------------------
    def _action_window(self, name, model, domain, view_mode="list,form,kanban"):
        self.ensure_one()
        return {
            "name": name,
            "type": "ir.actions.act_window",
            "res_model": model,
            "view_mode": view_mode,
            "domain": domain,
            "target": "current",
        }

    def action_open_imaging_requests(self):
        return self._action_window(_("Imaging Requests"), "clinical.imaging.request", [("prescription_order_id", "=", self.id)])

    def action_open_imaging_records(self):
        # Find imaging via request linkage
        Imaging = "clinical.imaging"
        domain = []
        if self._has_field("clinical.imaging", "request_id"):
            domain = [("request_id", "in", self.imaging_request_ids.ids)] if self.imaging_request_ids else [("id", "=", 0)]
        return self._action_window(_("Imaging Records"), Imaging, domain)

    def action_open_imaging_results(self):
        Result = "clinical.imaging.result"
        domain = [("prescription_order_id", "=", self.id)]
        if not self._has_field(Result, "prescription_order_id"):
            # fallback via imaging
            if self._has_field("clinical.imaging", "request_id"):
                Imaging = self.env["clinical.imaging"].sudo()
                imaging_ids = Imaging.search([("request_id", "in", self.imaging_request_ids.ids)]).ids if self.imaging_request_ids else []
                domain = [("imaging_id", "in", imaging_ids)] if imaging_ids else [("id", "=", 0)]
            else:
                domain = [("id", "=", 0)]
        return self._action_window(_("Imaging Results"), Result, domain, view_mode="list,form")

    def action_new_imaging_request(self):
        """Create a new Imaging Request seeded from this prescription."""
        self.ensure_one()
        if not self._has_model("clinical.imaging.request"):
            raise UserError(_("Imaging Request model is not available."))
        if not self.imaging_type_id:
            raise UserError(_("Please select an Imaging Type on the prescription first."))

        # Guess best requester (doctor) and patient context if present on order
        requesting_doctor_id = False
        for fname in ["doctor_id", "prescribing_doctor_id", "primary_doctor_id"]:
            if self._has_field(self._name, fname) and getattr(self, fname):
                requesting_doctor_id = getattr(self, fname).id
                break

        vals = {
            "patient_id": getattr(self, "patient_id", False) and self.patient_id.id or False,
            "appointment_id": getattr(self, "appointment_id", False) and self.appointment_id.id or False,
            "encounter_id": getattr(self, "encounter_id", False) and self.encounter_id.id or False,
            "treatment_id": getattr(self, "treatment_id", False) and self.treatment_id.id or False,
            "request_datetime": self._now(),
            "imaging_type_id": self.imaging_type_id.id,
            "priority": self.imaging_priority or "routine",
            "clinical_indication": self.imaging_indication or "",
            "special_instructions": self.imaging_instructions or "",
            "requesting_doctor_id": requesting_doctor_id,
            "prescription_order_id": self.id,  # backlink
        }
        # referring partner default to patient if supported
        if self._has_field("clinical.imaging.request", "referring_partner_id") and getattr(self, "patient_id", False):
            vals["referring_partner_id"] = self.patient_id.id
        # device preference (derive from order line device if any)
        if self._has_field("clinical.imaging.request", "preferred_device_id"):
            # try to get device from lines flagged preferred_device_id
            preferred_device = False
            if self.order_line_ids:
                dev_field = "preferred_device_id"
                for line in self.order_line_ids.filtered(lambda l: getattr(l, "is_imaging_device", False)):
                    if hasattr(line, dev_field) and line.preferred_device_id:
                        preferred_device = line.preferred_device_id.id
                        break
            if preferred_device:
                vals["preferred_device_id"] = preferred_device

        req = self.env["clinical.imaging.request"].create(vals)
        # push auxiliary flags into request note
        notes = []
        if self.contrast_premed_required:
            notes.append(_("Contrast premedication required.") + (f" {_('Protocol')}: {self.premed_protocol_id.name}" if self.premed_protocol_id else ""))
        if self.hydration_required:
            notes.append(_("Hydration required.") + (f" {_('Plan')}: {self.hydration_plan}" if self.hydration_plan else ""))
        if self.sedation_required:
            notes.append(_("Sedation required.") + (f" {_('Plan')}: {dict(self._fields['sedation_plan'].selection).get(self.sedation_plan) or ''}" if self.sedation_plan else ""))
        if notes and hasattr(req, "message_post"):
            req.message_post(body="<br/>".join(notes))

        # link on this order
        self.message_post(body=_("Imaging Request %s has been created from this prescription.") % (req.display_name or req.name))
        return {
            "name": _("Imaging Request"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.request",
            "view_mode": "form",
            "res_id": req.id,
            "target": "current",
        }


# =============================================================================
# Inherit clinic.prescription.order.line — Mark imaging-related lines
# =============================================================================
class ClinicPrescriptionOrderLine(models.Model, _PrescriptionImagingHelpers):
    _inherit = "clinic.emar.medication.line" # "clinic.prescription.order.line"

    # Imaging related flags
    is_contrast_agent = fields.Boolean(
        string="Contrast Agent",
        help="This line is a contrast media for imaging."
    )
    contrast_agent_type = fields.Selection(
        [("iodinated", "Iodinated"), ("gadolinium", "Gadolinium"), ("other", "Other")],
        string="Contrast Agent Type"
    )
    contrast_concentration = fields.Char(string="Concentration", help="e.g., 300 mgI/mL")
    contrast_volume_ml = fields.Float(string="Volume (mL)", help="Planned volume.")

    is_sedation_med = fields.Boolean(
        string="Sedation Medication",
        help="This line is part of sedation protocol for imaging."
    )
    is_hydration_fluid = fields.Boolean(
        string="Hydration Fluid",
        help="This line is for hydration around imaging."
    )
    is_imaging_device = fields.Boolean(
        string="Preferred Device Hint",
        help="Use this line to hint a preferred device for the exam (if the product encodes a device)."
    )
    preferred_device_id = fields.Many2one(
        "clinical.imaging.device",
        string="Preferred Device",
        help="If set, Imaging Request generated from this order may default to this device."
    )

    @api.onchange("is_contrast_agent", "contrast_agent_type")
    def _onchange_line_contrast(self):
        """If a contrast agent is selected, try to set order-level flags for convenience."""
        for rec in self:
            order = rec.order_id
            if not order or order._name != "clinic.emar.order":
                continue
            if rec.is_contrast_agent and not order.contrast_type:
                order.contrast_type = rec.contrast_agent_type or "other"
            if rec.is_contrast_agent and not order.contrast_premed_required:
                order.contrast_premed_required = True


# =============================================================================
# Backlink on Imaging Request — tie to Prescription Order
# =============================================================================
class ClinicalImagingRequest(models.Model):
    _inherit = "clinical.imaging.request"

    prescription_order_id = fields.Many2one(
        "clinic.emar.order",
        string="Source Prescription",
        help="If this request originates from a prescription order, link it here for traceability."
    )

    @api.depends("name", "prescription_order_id")
    def _compute_display_name(self):
        super()._compute_display_name()
        for rec in self:
            if rec.prescription_order_id:
                rec.display_name = (
                    f"{rec.display_name} [{_('RX')}: "
                    f"{rec.prescription_order_id.display_name}]"
                )


# =============================================================================
# Convenience link on Imaging Result (auto-derive from request/imaging)
# =============================================================================
class ClinicalImagingResult(models.Model, _PrescriptionImagingHelpers):
    _inherit = "clinical.imaging.result"

    prescription_order_id = fields.Many2one(
        "clinic.emar.order",
        string="Source Prescription",
        help="Prescription order from which this imaging originated (if any).",
        compute="_compute_prescription_from_context",
        store=False,
    )

    def _compute_prescription_from_context(self):
        for rec in self:
            rx = False
            # Direct: if imaging.request has prescription
            if self._has_field("clinical.imaging", "request_id") and rec.imaging_id and rec.imaging_id.request_id:
                rx = getattr(rec.imaging_id.request_id, "prescription_order_id", False)
            # Fallback: latest request for same imaging that has prescription linked
            if not rx and rec.imaging_id and "clinical.imaging.request" in self.env:
                req = self.env["clinical.imaging.request"].sudo().search([
                    ("imaging_id", "=", rec.imaging_id.id),
                    ("prescription_order_id", "!=", False),
                ], limit=1, order="create_date desc")
                rx = req.prescription_order_id if req else False
            rec.prescription_order_id = rx.id if rx else False
