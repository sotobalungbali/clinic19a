# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# Helpers Mixin (safe checks for optional models/fields)
# =============================================================================
class _TreatmentImagingHelpers(models.AbstractModel):
    _name = "clinic.treatment.imaging.helpers"
    _description = "Treatment Imaging Helpers"

    def _has_model(self, model):
        return model in self.env

    def _has_field(self, model, fname):
        try:
            return fname in self.env[model]._fields
        except Exception:
            return False


# =============================================================================
# Inherit clinic.treatment — Imaging Integrations
# =============================================================================
class ClinicTreatment(models.Model, _TreatmentImagingHelpers):
    _inherit = "clinic.treatment"

    # -------------------------------------------------------------------------
    # Core links (read-only relations for convenience)
    # -------------------------------------------------------------------------
    imaging_plan_ids = fields.One2many(
        "clinic.treatment.imaging.plan",
        "treatment_id",
        string="Imaging Plans",
        help="Planned imaging examinations linked to this treatment."
    )

    # Hard relations (if the related models exist). These are safe even if those
    # modules are loaded later; Odoo will resolve models by name.
    imaging_ids = fields.One2many(
        "clinical.imaging",
        "treatment_id",
        string="Imaging Records",
        help="Imaging records performed under this treatment."
    )
    imaging_request_ids = fields.One2many(
        "clinical.imaging.request",
        "treatment_id",
        string="Imaging Requests",
        help="Imaging requests created from this treatment."
    )

    # -------------------------------------------------------------------------
    # Counters & Status
    # -------------------------------------------------------------------------
    imaging_request_count = fields.Integer(
        string="Imaging Requests",
        compute="_compute_imaging_counts",
        store=False
    )
    imaging_count = fields.Integer(
        string="Imaging Records",
        compute="_compute_imaging_counts",
        store=False
    )
    imaging_result_count = fields.Integer(
        string="Imaging Results",
        compute="_compute_imaging_counts",
        store=False
    )
    imaging_finding_count = fields.Integer(
        string="Findings",
        compute="_compute_imaging_counts",
        store=False
    )
    imaging_key_image_count = fields.Integer(
        string="Key Images",
        compute="_compute_imaging_counts",
        store=False
    )
    has_imaging_pending = fields.Boolean(
        string="Has Pending Imaging",
        compute="_compute_imaging_status",
        store=False,
        help="True if there are pending imaging requests or non-final results."
    )
    last_imaging_datetime = fields.Datetime(
        string="Last Imaging Datetime",
        compute="_compute_last_dates",
        store=False
    )
    last_result_datetime = fields.Datetime(
        string="Last Result Signed",
        compute="_compute_last_dates",
        store=False
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_imaging_counts(self):
        Imaging = self.env["clinical.imaging"].sudo() if self._has_model("clinical.imaging") else None
        Request = self.env["clinical.imaging.request"].sudo() if self._has_model("clinical.imaging.request") else None
        Result = self.env["clinical.imaging.result"].sudo() if self._has_model("clinical.imaging.result") else None
        Finding = self.env["clinical.imaging.finding"].sudo() if self._has_model("clinical.imaging.finding") else None
        Image = self.env["clinical.imaging.image"].sudo() if self._has_model("clinical.imaging.image") else None

        for rec in self:
            # Defaults
            rec.imaging_request_count = 0
            rec.imaging_count = 0
            rec.imaging_result_count = 0
            rec.imaging_finding_count = 0
            rec.imaging_key_image_count = 0

            if Request:
                rec.imaging_request_count = Request.search_count([("treatment_id", "=", rec.id)])
            if Imaging:
                rec.imaging_count = Imaging.search_count([("treatment_id", "=", rec.id)])
            if Result:
                # Prefer direct link if exists; fall back by imaging_id of this treatment
                if self._has_field("clinical.imaging.result", "treatment_id"):
                    rec.imaging_result_count = Result.search_count([("treatment_id", "=", rec.id)])
                elif Imaging:
                    imaging_ids = Imaging.search([("treatment_id", "=", rec.id)]).ids
                    rec.imaging_result_count = Result.search_count([("imaging_id", "in", imaging_ids)]) if imaging_ids else 0
            if Finding:
                if self._has_field("clinical.imaging.finding", "treatment_id"):
                    rec.imaging_finding_count = Finding.search_count([("treatment_id", "=", rec.id)])
                elif Imaging:
                    imaging_ids = Imaging.search([("treatment_id", "=", rec.id)]).ids
                    rec.imaging_finding_count = Finding.search_count([("imaging_id", "in", imaging_ids)]) if imaging_ids else 0
            if Image and Imaging:
                imaging_ids = Imaging.search([("treatment_id", "=", rec.id)]).ids
                if imaging_ids and self._has_field("clinical.imaging.image", "is_key"):
                    rec.imaging_key_image_count = Image.search_count([
                        ("imaging_id", "in", imaging_ids), ("is_key", "=", True)
                    ])

    def _compute_imaging_status(self):
        Request = self.env["clinical.imaging.request"].sudo() if self._has_model("clinical.imaging.request") else None
        Result = self.env["clinical.imaging.result"].sudo() if self._has_model("clinical.imaging.result") else None
        for rec in self:
            pending_req = 0
            pending_res = 0
            if Request and self._has_field("clinical.imaging.request", "state"):
                pending_req = Request.search_count([
                    ("treatment_id", "=", rec.id),
                    ("state", "in", ["draft", "submitted", "approved", "scheduled", "in_progress"])
                ])
            if Result and self._has_field("clinical.imaging.result", "state"):
                pending_res = Result.search_count([
                    ("treatment_id", "=", rec.id)
                ]) if self._has_field("clinical.imaging.result", "treatment_id") else 0
                # If no direct link, count via imaging_id
                if not pending_res:
                    Imaging = self.env["clinical.imaging"].sudo() if self._has_model("clinical.imaging") else None
                    if Imaging:
                        imaging_ids = Imaging.search([("treatment_id", "=", rec.id)]).ids
                        pending_res = Result.search_count([
                            ("imaging_id", "in", imaging_ids),
                            ("state", "not in", ["final", "amended"])
                        ]) if imaging_ids else 0
            rec.has_imaging_pending = bool(pending_req or pending_res)

    def _compute_last_dates(self):
        Imaging = self.env["clinical.imaging"].sudo() if self._has_model("clinical.imaging") else None
        Study = self.env["clinical.imaging.study"].sudo() if self._has_model("clinical.imaging.study") else None
        Result = self.env["clinical.imaging.result"].sudo() if self._has_model("clinical.imaging.result") else None

        for rec in self:
            rec.last_imaging_datetime = False
            rec.last_result_datetime = False
            if Study and Imaging:
                # Latest study time among imaging of this treatment
                imaging_ids = Imaging.search([("treatment_id", "=", rec.id)]).ids
                if imaging_ids:
                    last_study = Study.search([("imaging_id", "in", imaging_ids)], limit=1, order="study_datetime desc")
                    rec.last_imaging_datetime = last_study.study_datetime if last_study else False
            if Result:
                # Prefer direct link if exists, else by imaging
                if self._has_field("clinical.imaging.result", "treatment_id"):
                    last_res = Result.search([("treatment_id", "=", rec.id), ("signed_datetime", "!=", False)],
                                             limit=1, order="signed_datetime desc")
                elif Imaging:
                    imaging_ids = Imaging.search([("treatment_id", "=", rec.id)]).ids
                    last_res = Result.search([("imaging_id", "in", imaging_ids), ("signed_datetime", "!=", False)],
                                             limit=1, order="signed_datetime desc") if imaging_ids else Result.browse()
                else:
                    last_res = Result.browse()
                rec.last_result_datetime = last_res.signed_datetime if last_res else False

    # -------------------------------------------------------------------------
    # ACTIONS (Smart Buttons)
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
            "context": {"default_treatment_id": self.id, "default_patient_id": getattr(self, "patient_id", False) and self.patient_id.id or False},
        }

    def action_open_imaging_requests(self):
        return self._action_window(_("Imaging Requests"), "clinical.imaging.request", [("treatment_id", "=", self.id)])

    def action_open_imaging_records(self):
        return self._action_window(_("Imaging Records"), "clinical.imaging", [("treatment_id", "=", self.id)])

    def action_open_imaging_results(self):
        Result = "clinical.imaging.result"
        domain = [("treatment_id", "=", self.id)] if self._has_field(Result, "treatment_id") else []
        if not domain:
            # fallback via imaging
            Imaging = self.env["clinical.imaging"].sudo() if self._has_model("clinical.imaging") else None
            if Imaging:
                imaging_ids = Imaging.search([("treatment_id", "=", self.id)]).ids
                domain = [("imaging_id", "in", imaging_ids)] if imaging_ids else [("id", "=", 0)]
            else:
                domain = [("id", "=", 0)]
        return self._action_window(_("Imaging Results"), Result, domain, view_mode="list,form")

    def action_open_imaging_findings(self):
        Finding = "clinical.imaging.finding"
        domain = [("treatment_id", "=", self.id)] if self._has_field(Finding, "treatment_id") else []
        if not domain:
            Imaging = self.env["clinical.imaging"].sudo() if self._has_model("clinical.imaging") else None
            if Imaging:
                imaging_ids = Imaging.search([("treatment_id", "=", self.id)]).ids
                domain = [("imaging_id", "in", imaging_ids)] if imaging_ids else [("id", "=", 0)]
            else:
                domain = [("id", "=", 0)]
        return self._action_window(_("Imaging Findings"), Finding, domain, view_mode="list,form,kanban")

    def action_open_imaging_plans(self):
        return self._action_window(_("Imaging Plans"), "clinic.treatment.imaging.plan", [("treatment_id", "=", self.id)], view_mode="list,form")

    def action_new_imaging_request(self):
        """Quick create a new Imaging Request from this treatment."""
        self.ensure_one()
        if not self._has_model("clinical.imaging.request"):
            raise UserError(_("Imaging Request model is not available."))
        return {
            "name": _("New Imaging Request"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.request",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_treatment_id": self.id,
                "default_patient_id": getattr(self, "patient_id", False) and self.patient_id.id or False,
                "default_encounter_id": getattr(self, "encounter_id", False) and self.encounter_id.id or False,
                "default_appointment_id": getattr(self, "appointment_id", False) and self.appointment_id.id or False,
                "default_referring_partner_id": getattr(self, "patient_id", False) and self.patient_id.id or False,
            },
        }

    def action_generate_requests_from_plans(self):
        """Generate Imaging Requests for all PLANNED plan lines that don't have a request yet."""
        self.ensure_one()
        if not self._has_model("clinical.imaging.request"):
            raise UserError(_("Imaging Request model is not available."))
        created = 0
        for plan in self.imaging_plan_ids.filtered(lambda p: p.state == "planned" and not p.request_id):
            plan._action_create_request_from_plan()
            created += 1
        if created:
            return self.action_open_imaging_requests()
        raise UserError(_("No pending imaging plans to generate requests."))


# =============================================================================
# clinic.treatment.imaging.plan — Planned tests under a Treatment
# =============================================================================
class ClinicTreatmentImagingPlan(models.Model, _TreatmentImagingHelpers):
    # _name = "clinic.treatment.imaging.plan"
    # _description = "Treatment Imaging Plan"
    # _inherit = ["mail.thread", "mail.activity.mixin"]
    # _order = "treatment_id, sequence, id"
    # _check_company_auto = True
    _name = "clinic.treatment.imaging.plan"
    _description = "Treatment Imaging Plan"
    _order = "id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Ownership
    # -------------------------------------------------------------------------
    # name = fields.Char(
    #     string="Plan Number",
    #     required=True,
    #     copy=False,
    #     default=lambda s: _("New"),
    #     help="Unique identifier generated from sequence at creation time."
    # )
    name = fields.Char(
        string="Plan Reference",
        default=lambda self: _("New"),
        copy=False,
        index=True,
        help="Internal reference for the imaging plan."
    )
    sequence = fields.Integer(string="Sequence", default=10)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda s: s.env.company)
    active = fields.Boolean(default=True)

    # -------------------------------------------------------------------------
    # Treatment Context
    # -------------------------------------------------------------------------
    # treatment_id = fields.Many2one(
    #     "clinic.treatment",
    #     string="Treatment",
    #     required=True,
    #     ondelete="cascade",
    #     index=True,
    #     help="Treatment to which this imaging plan belongs."
    # )
    
    # Hubungan utama ke treatment
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        required=True,
        index=True,
        help="The treatment this imaging plan is attached to."
    )

    # patient_id = fields.Many2one(
    #     "res.partner",
    #     string="Patient",
    #     related="treatment_id.patient_id",
    #     store=True,
    #     readonly=True
    # )
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        compute="_compute_links",
        store=True,
        readonly=True,
        index=True,
        help="Patient derived from encounter/appointment/treatment."
    )
    # appointment_id = fields.Many2one(
    #     "clinic.appointment",
    #     string="Appointment",
    #     help="Appointment context for scheduling request (optional)."
    # )
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        compute="_compute_links",
        store=True,
        readonly=True,
        help="Appointment/booking derived from the treatment when available."
    )
    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     help="Encounter context for the imaging."
    # )
    # Jangan pakai 'related' yang mengasumsikan field tertentu ada di clinic.treatment
    # Kita hitung secara robust dari beberapa kemungkinan jalur.
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        compute="_compute_links",
        store=True,
        readonly=True,
        help="Encounter derived from the treatment when available."
    )
    requesting_doctor_id = fields.Many2one(
        "hr.employee",
        string="Requesting Doctor",
        domain=[("is_doctor", "=", True)],
        help="Doctor who planned this imaging test."
    )

    # -------------------------------------------------------------------------
    # What to perform
    # -------------------------------------------------------------------------
    imaging_type_id = fields.Many2one(
        "clinical.imaging.type",
        string="Imaging Type",
        required=True,
        help="Type of imaging examination (e.g., 'CT Abdomen with contrast')."
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
        help="Preferred modality (auto-derived from Imaging Type if set)."
    )
    modality_id = fields.Many2one(
        "clinical.imaging.type",
        string="Modality",
        required=False,
        help="Preferred imaging modality for this plan (e.g. US, X-ray)."
    )
    device_id = fields.Many2one(
        "clinical.imaging.device",
        string="Preferred Device",
        help="Preferred device to run the exam (optional)."
    )
    priority = fields.Selection(
        [
            ("routine", "Routine"),
            ("urgent", "Urgent"),
            ("stat", "STAT"),
        ],
        string="Priority",
        default="routine",
        help="Clinical priority of the planned exam."
    )
    indication = fields.Text(
        string="Clinical Indication",
        help="Clinical question or reason for this exam."
    )
    instructions = fields.Text(
        string="Special Instructions",
        help="Preparation or special instructions for the exam."
    )

    # -------------------------------------------------------------------------
    # Scheduling
    # -------------------------------------------------------------------------
    planned_datetime = fields.Datetime(
        string="Planned Datetime",
        help="Preferred datetime to schedule and perform the exam."
    )
    # If you have a booking module integration, you may use slot_id, room_id, etc.

    # -------------------------------------------------------------------------
    # Lifecycle & Links
    # -------------------------------------------------------------------------
    # state = fields.Selection(
    #     [
    #         ("planned", "Planned"),
    #         ("requested", "Requested"),
    #         ("in_progress", "In Progress"),
    #         ("done", "Done"),
    #         ("cancelled", "Cancelled"),
    #     ],
    #     string="Status",
    #     default="planned",
    #     tracking=True,
    #     index=True,
    #     help="Lifecycle of this imaging plan."
    # )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("requested", "Requested"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        help="Lifecycle state of this imaging plan."
    )
    notes = fields.Text(
        string="Clinical Notes",
        help="Clinical indications or notes for the imaging plan."
    )
    request_id = fields.Many2one(
        "clinical.imaging.request",
        string="Generated Request",
        help="The imaging request generated from this plan."
    )
    request_ids = fields.One2many(
        "clinical.imaging.request",
        "plan_id",
        string="Imaging Requests",
        help="Requests generated from this plan."
    )
    imaging_id = fields.Many2one(
        "clinical.imaging",
        string="Imaging Record",
        help="The resulting imaging record (once performed)."
    )
    result_id = fields.Many2one(
        "clinical.imaging.result",
        string="Imaging Result",
        help="Final report linked to this planned exam."
    )

    # -------------------------------------------------------------------------
    # Auditing
    # -------------------------------------------------------------------------
    created_by_id = fields.Many2one("res.users", string="Created By", default=lambda s: s.env.user, readonly=True)
    created_datetime = fields.Datetime(string="Created At", default=fields.Datetime.now, readonly=True)
    last_transition = fields.Datetime(string="Last Status Change", readonly=True)

    _name_uniq = models.Constraint(
        'unique(name)',
        'Plan Reference must be unique.',
    )

    @api.depends("treatment_id")  # sengaja tidak merinci sub-field supaya tidak pecah saat setup
    def _compute_links(self):
        """
        Safely derive encounter, appointment, and patient from the treatment
        without assuming those fields must exist. This protects registry setup.
        """
        for rec in self:
            enc = False
            app = False
            pat = False
            t = rec.treatment_id

            # Ambil encounter dari treatment bila ada
            if t and hasattr(t, "encounter_id") and t.encounter_id:
                enc = t.encounter_id

            # Ambil appointment dari treatment bila ada
            if t and hasattr(t, "appointment_id") and t.appointment_id:
                app = t.appointment_id

            # 1) Jika treatment langsung punya patient_id (jika suatu modul menambahkannya)
            if t and hasattr(t, "patient_id") and t.patient_id:
                pat = t.patient_id

            # 2) Jika belum dapat, ambil dari encounter
            if not pat and enc and hasattr(enc, "patient_id") and enc.patient_id:
                pat = enc.patient_id

            # 3) Jika belum dapat, ambil dari appointment
            if not pat and app and hasattr(app, "patient_id") and app.patient_id:
                pat = app.patient_id

            rec.encounter_id = enc or False
            rec.appointment_id = app or False
            rec.patient_id = pat or False

    # -------------------------------------------------------------------------
    # ONCHANGE / CONSTRAINS
    # -------------------------------------------------------------------------
    @api.onchange("imaging_type_id")
    def _onchange_imaging_type(self):
        for rec in self:
            if rec.imaging_type_id and not rec.modality and self._has_field("clinical.imaging.type", "modality"):
                rec.modality = rec.imaging_type_id.modality

    @api.constrains("planned_datetime")
    def _check_planned_datetime(self):
        for rec in self:
            # Optional guard: planned time cannot be too far in the past relative to creation
            if rec.planned_datetime and rec.created_datetime and rec.planned_datetime < rec.created_datetime.replace(year=rec.created_datetime.year - 1):
                raise ValidationError(_("Planned Datetime appears too far in the past."))

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinic.treatment.imaging.plan") or _("New")
            # default requesting doctor from treatment's primary doctor if possible
            if not vals.get("requesting_doctor_id") and vals.get("treatment_id"):
                tr = self.env["clinic.treatment"].browse(vals["treatment_id"])
                if tr and hasattr(tr, "doctor_id") and tr.doctor_id:
                    vals["requesting_doctor_id"] = tr.doctor_id.id
        recs = super().create(vals_list)
        return recs

    @api.model_create_multi
    def create(self, vals_list):
        # Generate sequence kalau masih "New"
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("clinic.treatment.imaging.plan") or _("New")
        return super().create(vals_list)

    def write(self, vals):
        if "state" in vals:
            vals["last_transition"] = fields.Datetime.now()
        return super().write(vals)

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("state", "planned")
        default.setdefault("request_id", False)
        default.setdefault("imaging_id", False)
        default.setdefault("result_id", False)
        return super().copy(default)

    def action_generate_request(self):
        self.ensure_one()
        req = self._action_create_request_from_plan()
        return {
            "name": _("Imaging Request"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.request",
            "view_mode": "form",
            "target": "current",
            "res_id": req.id,
        }


    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    # def _action_create_request_from_plan(self):
    #     """Create a clinical.imaging.request from this plan (internal helper)."""
    #     self.ensure_one()
    #     if not self._has_model("clinical.imaging.request"):
    #         raise UserError(_("Imaging Request model is not available."))
    #     if self.request_id:
    #         return self.request_id

    #     # Build request values safely
    #     vals = {
    #         "patient_id": self.patient_id.id,
    #         "treatment_id": self.treatment_id.id,
    #         "appointment_id": self.appointment_id.id if self.appointment_id else False,
    #         "encounter_id": self.encounter_id.id if self.encounter_id else False,
    #         "requesting_doctor_id": self.requesting_doctor_id.id if self.requesting_doctor_id else False,
    #         "imaging_type_id": self.imaging_type_id.id,
    #         "priority": self.priority,
    #         "clinical_indication": self.indication or "",
    #         "special_instructions": self.instructions or "",
    #         "preferred_device_id": self.device_id.id if self.device_id else False,
    #         "request_datetime": self.planned_datetime or fields.Datetime.now(),
    #     }
    #     # Extra interop: referring partner defaults to patient if field exists
    #     if self._has_field("clinical.imaging.request", "referring_partner_id"):
    #         vals["referring_partner_id"] = self.patient_id.id

    #     request = self.env["clinical.imaging.request"].create(vals)
    #     self.write({"state": "requested", "request_id": request.id})
    #     self.message_post(body=_("Imaging Request %s has been created from the plan.") % (request.display_name or request.name))
    #     return request

    def _action_create_request_from_plan(self):
        """Create a clinical.imaging.request from this Plan and link both ways."""
        self.ensure_one()
        Request = self.env["clinical.imaging.request"].sudo()

        vals = {
            # konteks pasien & klinis (gunakan apa yang tersedia di plan Anda)
            "patient_id": self.patient_id.id if self.patient_id else False,
            "treatment_id": self.treatment_id.id if self.treatment_id else False,
            "appointment_id": self.appointment_id.id if getattr(self, "appointment_id", False) else False,
            "encounter_id": self.encounter_id.id if getattr(self, "encounter_id", False) else False,

            # parameter imaging
            "imaging_type_id": self.imaging_type_id.id if getattr(self, "imaging_type_id", False) else False,
            "preferred_device_id": self.device_id.id if getattr(self, "device_id", False) else False,
            "priority": getattr(self, "priority", False) or "routine",
            "clinical_indication": (getattr(self, "indication", False) or getattr(self, "notes", False) or "")[:1024],
            "special_instructions": getattr(self, "instructions", False) or "",
            "request_datetime": getattr(self, "planned_datetime", False) or fields.Datetime.now(),

            # kunci relasi balik ke Plan (WAJIB agar O2M di Plan tidak error)
            "plan_id": self.id,

            # opsional lain bila ada di Plan Anda
            "requesting_doctor_id": self.requesting_doctor_id.id if getattr(self, "requesting_doctor_id", False) else False,
            "prescription_order_id": self.prescription_order_id.id if getattr(self, "prescription_order_id", False) else False,
        }

        req = Request.create(vals)

        # jika Plan menyimpan "primary" request via M2O request_id, isi di sini
        if "request_id" in self._fields and not self.request_id:
            self.write({"request_id": req.id})

        # catat di chatter Plan bila ada
        if hasattr(self, "message_post"):
            self.message_post(body=_("Imaging Request %s has been generated from this plan.") % (req.display_name))

        return req


    def action_create_request(self):
        """Public button to create request from plan."""
        self.ensure_one()
        req = self._action_create_request_from_plan()
        return {
            "name": _("Imaging Request"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.request",
            "view_mode": "form",
            "res_id": req.id,
            "target": "current",
        }

    def action_open_request(self):
        self.ensure_one()
        if not self.request_id:
            raise UserError(_("No linked Imaging Request."))
        return {
            "name": _("Imaging Request"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.request",
            "view_mode": "form",
            "res_id": self.request_id.id,
            "target": "current",
        }

    def action_open_imaging(self):
        self.ensure_one()
        if not self.imaging_id:
            raise UserError(_("No linked Imaging record yet."))
        return {
            "name": _("Imaging"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging",
            "view_mode": "form",
            "res_id": self.imaging_id.id,
            "target": "current",
        }

    def action_open_result(self):
        self.ensure_one()
        if not self.result_id:
            raise UserError(_("No linked Result yet."))
        return {
            "name": _("Imaging Result"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.result",
            "view_mode": "form",
            "res_id": self.result_id.id,
            "target": "current",
        }

    def action_mark_in_progress(self):
        for rec in self:
            if rec.state not in ("planned", "requested"):
                raise UserError(_("Only Planned/Requested plans can be marked In Progress."))
            rec.state = "in_progress"

    def action_mark_requested(self):
        for rec in self:
            rec.state = "requested"

    # def action_mark_done(self):
    #     for rec in self:
    #         if rec.state not in ("in_progress", "requested"):
    #             raise UserError(_("Only Requested/In Progress plans can be marked Done."))
    #         rec.state = "done"
    def action_mark_done(self):
        for rec in self:
            rec.state = "done"

    # def action_cancel(self):
    #     for rec in self:
    #         if rec.state == "done":
    #             raise UserError(_("Completed plans cannot be cancelled."))
    #         rec.state = "cancelled"

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    @api.depends("name", "imaging_type_id", "treatment_id")
    def _compute_display_name(self):
        for rec in self:
            title = rec.name or _("New")
            if rec.imaging_type_id:
                title = f"{title} - {rec.imaging_type_id.display_name}"
            if rec.treatment_id:
                title = f"{title} ({rec.treatment_id.display_name})"
            rec.display_name = title

    # -------------------------------------------------------------------------
    # SQL Constraints
    # -------------------------------------------------------------------------
    # _sql_constraints = [
    #     ("name_company_unique", "unique(name, company_id)", "Plan Number must be unique per company."),
    # ]
