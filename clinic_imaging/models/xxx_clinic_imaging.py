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
    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Encounter",
    #     compute="_compute_links",
    #     store=True,
    #     readonly=True,
    #     help="Encounter derived from the treatment when available."
    # )
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
    # @api.model_create_multi
    # def create(self, vals_list):
    #     seq = self.env["ir.sequence"]
    #     for vals in vals_list:
    #         vals.setdefault("company_id", self.env.company.id)
    #         if not vals.get("name") or vals.get("name") == _("New"):
    #             vals["name"] = seq.next_by_code("clinic.treatment.imaging.plan") or _("New")
    #         # default requesting doctor from treatment's primary doctor if possible
    #         if not vals.get("requesting_doctor_id") and vals.get("treatment_id"):
    #             tr = self.env["clinic.treatment"].browse(vals["treatment_id"])
    #             if tr and hasattr(tr, "doctor_id") and tr.doctor_id:
    #                 vals["requesting_doctor_id"] = tr.doctor_id.id
    #     recs = super().create(vals_list)
    #     return recs

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
    def name_get(self):
        res = []
        for rec in self:
            title = rec.name or _("New")
            if rec.imaging_type_id:
                title = f"{title} - {rec.imaging_type_id.display_name}"
            if rec.treatment_id:
                title = f"{title} ({rec.treatment_id.display_name})"
            res.append((rec.id, title))
        return res

    # -------------------------------------------------------------------------
    # SQL Constraints
    # -------------------------------------------------------------------------
    # _sql_constraints = [
    #     ("name_company_unique", "unique(name, company_id)", "Plan Number must be unique per company."),
    # ]

# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import date


# =============================================================================
# res.partner — Imaging extensions (Patient profile + smart buttons)
# =============================================================================
class ResPartner(models.Model):
    _inherit = "res.partner"

    # -------------------------------------------------------------------------
    # Imaging Identifiers & Care Team
    # -------------------------------------------------------------------------
    pacs_patient_id = fields.Char(
        string="PACS Patient ID",
        help="External Patient ID used by PACS/RIS/VNA (if different from MRN)."
    )
    dicom_patient_id = fields.Char(
        string="DICOM Patient ID",
        help="DICOM PatientID tag used during acquisition, if enforced."
    )
    primary_doctor_id = fields.Many2one(
        "hr.employee",
        string="Primary Doctor",
        domain=[("is_doctor", "=", True)],
        help="Patient's primary physician in ClinicOne."
    )

    # -------------------------------------------------------------------------
    # Clinical Safety (Imaging)
    # -------------------------------------------------------------------------
    has_metal_implants = fields.Boolean(
        string="Has Metal Implants",
        help="Patient has metallic implants (e.g., orthopedic hardware)."
    )
    implant_description = fields.Char(
        string="Implant Description",
        help="Short description of implant(s), location, or model."
    )
    has_pacemaker = fields.Boolean(
        string="Has Pacemaker/ICD",
        help="Patient has an implanted pacemaker or defibrillator."
    )
    has_cochlear_implant = fields.Boolean(
        string="Has Cochlear Implant",
        help="Patient has cochlear or other otologic implant."
    )
    pregnancy_status = fields.Selection(
        [
            ("unknown", "Unknown"),
            ("no", "Not Pregnant"),
            ("yes", "Pregnant"),
            ("na", "Not Applicable"),
        ],
        string="Pregnancy Status",
        default="unknown",
        help="Relevant for ionizing radiation and MRI safety screening."
    )
    last_menstruation_date = fields.Date(
        string="Last Menstruation Date",
        help="Optional LMP date for pregnancy assessment."
    )

    contrast_allergy = fields.Boolean(
        string="Contrast Allergy",
        help="Known allergy to contrast media (iodinated or gadolinium)."
    )
    contrast_allergy_severity = fields.Selection(
        [
            ("mild", "Mild"),
            ("moderate", "Moderate"),
            ("severe", "Severe"),
            ("anaphylaxis", "Anaphylaxis"),
        ],
        string="Allergy Severity"
    )
    contrast_allergy_notes = fields.Char(
        string="Allergy Notes",
        help="Short notes about the contrast allergy history."
    )
    contrast_premed_required = fields.Boolean(
        string="Premedication Required",
        help="Premedication protocol should be applied before contrast study."
    )
    contrast_premed_protocol = fields.Text(
        string="Premedication Protocol",
        help="Suggested premedication regimen (e.g., steroids/antihistamines)."
    )

    # Renal function (for contrast risk)
    egfr_value = fields.Float(
        string="eGFR (mL/min/1.73m²)",
        help="Latest estimated glomerular filtration rate."
    )
    egfr_date = fields.Date(string="eGFR Date")
    egfr_method = fields.Selection(
        [("ckd_epi", "CKD-EPI"), ("mdrd", "MDRD"), ("other", "Other")],
        string="eGFR Method"
    )
    renal_risk = fields.Selection(
        [
            ("unknown", "Unknown"),
            ("low", "Low"),
            ("moderate", "Moderate"),
            ("high", "High"),
        ],
        string="Renal Risk",
        compute="_compute_renal_risk",
        store=True,
        help="Automated risk estimation based on eGFR and recency."
    )
    metformin_use = fields.Boolean(
        string="On Metformin",
        help="Patient currently uses metformin (consider hold around iodinated contrast)."
    )
    metformin_instructions = fields.Text(
        string="Metformin Hold Instructions",
        help="Instructions for metformin withholding if applicable."
    )

    # Sedation / ASA (high-level)
    asa_class = fields.Selection(
        [
            ("I", "ASA I"),
            ("II", "ASA II"),
            ("III", "ASA III"),
            ("IV", "ASA IV"),
            ("V", "ASA V"),
            ("VI", "ASA VI"),
        ],
        string="ASA Class",
        help="American Society of Anesthesiologists physical status classification."
    )
    sedation_contraindications = fields.Text(
        string="Sedation Contraindications",
        help="Known issues that increase sedation risk."
    )

    # -------------------------------------------------------------------------
    # Anthropometrics (for imaging limits, dose tracking, coil/table limits)
    # -------------------------------------------------------------------------
    height_cm = fields.Float(string="Height (cm)")
    weight_kg = fields.Float(string="Weight (kg)")
    bmi = fields.Float(
        string="BMI",
        compute="_compute_bmi",
        store=True,
        help="Body Mass Index computed from height and weight."
    )

    # -------------------------------------------------------------------------
    # Privacy / Portal preferences (specific to Imaging)
    # -------------------------------------------------------------------------
    imaging_portal_opt_out = fields.Boolean(
        string="Opt-out of Imaging Portal",
        help="If checked, imaging results/key images will not be shown on the patient portal."
    )
    share_images_on_portal = fields.Boolean(
        string="Share Images on Portal",
        default=True,
        help="Allow key images to be visible to the patient on the portal."
    )

    # -------------------------------------------------------------------------
    # KPI Counters (smart buttons)
    # -------------------------------------------------------------------------
    imaging_request_count = fields.Integer(
        string="Imaging Requests", compute="_compute_imaging_counts", store=False
    )
    imaging_count = fields.Integer(
        string="Imaging Records", compute="_compute_imaging_counts", store=False
    )
    imaging_result_count = fields.Integer(
        string="Imaging Results", compute="_compute_imaging_counts", store=False
    )
    imaging_study_count = fields.Integer(
        string="Studies", compute="_compute_imaging_counts", store=False
    )
    imaging_series_count = fields.Integer(
        string="Series", compute="_compute_imaging_counts", store=False
    )
    imaging_image_count = fields.Integer(
        string="Images", compute="_compute_imaging_counts", store=False
    )
    imaging_finding_count = fields.Integer(
        string="Findings", compute="_compute_imaging_counts", store=False
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS / COMPUTES / ONCHANGE
    # -------------------------------------------------------------------------
    @api.constrains("egfr_value")
    def _check_egfr_range(self):
        for rec in self:
            if rec.egfr_value is not None and (rec.egfr_value < 0 or rec.egfr_value > 200):
                raise ValidationError(_("eGFR must be in a realistic range (0..200)."))

    @api.constrains("height_cm", "weight_kg")
    def _check_anthro_non_negative(self):
        for rec in self:
            if rec.height_cm is not None and rec.height_cm < 0:
                raise ValidationError(_("Height cannot be negative."))
            if rec.weight_kg is not None and rec.weight_kg < 0:
                raise ValidationError(_("Weight cannot be negative."))

    @api.depends("height_cm", "weight_kg")
    def _compute_bmi(self):
        for rec in self:
            if rec.height_cm and rec.weight_kg and rec.height_cm > 0:
                h_m = rec.height_cm / 100.0
                rec.bmi = round(rec.weight_kg / (h_m * h_m), 2)
            else:
                rec.bmi = 0.0

    @api.depends("egfr_value", "egfr_date")
    def _compute_renal_risk(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.egfr_value or not rec.egfr_date:
                rec.renal_risk = "unknown"
                continue
            # recency within 365 days
            recent = (rec.egfr_date >= (today - fields.Date.to_date("1970-01-01").replace(year=today.year - 1))) \
                if isinstance(today, date) else True
            # Simple heuristic: <30 high, 30-44 moderate, 45-59 low, >=60 low
            if rec.egfr_value < 30:
                risk = "high"
            elif rec.egfr_value < 45:
                risk = "moderate"
            else:
                risk = "low"
            rec.renal_risk = risk if recent else "unknown"

    @api.onchange("contrast_allergy")
    def _onchange_contrast_allergy(self):
        for rec in self:
            if rec.contrast_allergy and rec.contrast_premed_required is False:
                rec.contrast_premed_required = True

    # -------------------------------------------------------------------------
    # COMPUTE COUNTS
    # -------------------------------------------------------------------------
    def _compute_imaging_counts(self):
        Imaging = self.env["clinical.imaging"].sudo()
        Request = self.env["clinical.imaging.request"].sudo()
        Result = self.env["clinical.imaging.result"].sudo()
        Study = self.env["clinical.imaging.study"].sudo()
        Series = self.env["clinical.imaging.series"].sudo()
        Image = self.env["clinical.imaging.image"].sudo()
        Finding = self.env["clinical.imaging.finding"].sudo()
        for rec in self:
            # If partner is not a patient (from clinic_patient), still compute safely
            domain_patient = [("patient_id", "=", rec.id)]
            rec.imaging_count = Imaging.search_count(domain_patient)
            rec.imaging_request_count = Request.search_count(domain_patient)
            rec.imaging_result_count = Result.search_count(domain_patient)
            rec.imaging_study_count = Study.search_count(domain_patient)
            rec.imaging_series_count = Series.search_count(domain_patient)
            rec.imaging_image_count = Image.search_count(domain_patient)
            rec.imaging_finding_count = Finding.search_count(domain_patient)

    # -------------------------------------------------------------------------
    # NAVIGATION ACTIONS (Smart Buttons)
    # -------------------------------------------------------------------------
    def action_open_imaging_requests(self):
        self.ensure_one()
        return {
            "name": _("Imaging Requests"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.request",
            "view_mode": "list,form,kanban,calendar",
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
            "context": {"default_patient_id": self.id},
        }

    def action_open_imaging(self):
        self.ensure_one()
        return {
            "name": _("Imaging Records"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging",
            "view_mode": "list,form,kanban,calendar",
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
            "context": {"default_patient_id": self.id},
        }

    def action_open_imaging_results(self):
        self.ensure_one()
        return {
            "name": _("Imaging Results"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.result",
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
        }

    def action_open_imaging_studies(self):
        self.ensure_one()
        return {
            "name": _("Studies"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.study",
            "view_mode": "list,form,kanban",
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
        }

    def action_open_imaging_series(self):
        self.ensure_one()
        return {
            "name": _("Series"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.series",
            "view_mode": "list,form,kanban",
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
        }

    def action_open_imaging_images(self):
        self.ensure_one()
        return {
            "name": _("Images"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.image",
            "view_mode": "list,form,kanban",
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
        }

    def action_open_imaging_findings(self):
        self.ensure_one()
        return {
            "name": _("Findings"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.finding",
            "view_mode": "list,form,kanban",
            "domain": [("patient_id", "=", self.id)],
            "target": "current",
        }

    def action_new_imaging_request(self):
        """Quick create a new Imaging Request for this patient."""
        self.ensure_one()
        return {
            "name": _("New Imaging Request"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.request",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_patient_id": self.id,
                "default_referring_partner_id": self.id,
                "default_primary_doctor_id": self.primary_doctor_id.id if self.primary_doctor_id else False,
            },
        }

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _pacs_patient_id_company_unique = models.Constraint(
        'unique(pacs_patient_id, company_id)',
        'PACS Patient ID must be unique per company.',
    )
    _dicom_patient_id_company_unique = models.Constraint(
        'unique(dicom_patient_id, company_id)',
        'DICOM Patient ID must be unique per company.',
    )


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
            if not order or order._name != "clinic.prescription.order":
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
        "clinic.prescription.order",
        string="Source Prescription",
        help="If this request originates from a prescription order, link it here for traceability."
    )

    def name_get(self):
        """Add prescription code context to display name (if linked)."""
        res = super().name_get()
        display = []
        for rec_id, name in res:
            rec = self.browse(rec_id)
            if rec.prescription_order_id:
                name = f"{name} [{_('RX')}: {rec.prescription_order_id.display_name or rec.prescription_order_id.name}]"
            display.append((rec_id, name))
        return display


# =============================================================================
# Convenience link on Imaging Result (auto-derive from request/imaging)
# =============================================================================
class ClinicalImagingResult(models.Model, _PrescriptionImagingHelpers):
    _inherit = "clinical.imaging.result"

    prescription_order_id = fields.Many2one(
        "clinic.prescription.order",
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


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


# =============================================================================
# Helpers Mixin (safe checks)
# =============================================================================
class _ImagingEmployeeHelpersMixin(models.AbstractModel):
    _name = "clinical.imaging.employee.helpers.mixin"
    _description = "Imaging Employee Helpers Mixin"

    def _has_model(self, model_name):
        return model_name in self.env

    def _has_field(self, model_name, field_name):
        try:
            return field_name in self.env[model_name]._fields
        except Exception:
            return False

    def _dt_now(self):
        return fields.Datetime.now()

    def _dt_days_ago(self, days):
        return self._dt_now() - timedelta(days=days)


# =============================================================================
# Modality Tag for Staff Competency
# =============================================================================
class ClinicalImagingModalityTag(models.Model):
    _name = "clinical.imaging.modality.tag"
    _description = "Imaging Modality Tag"
    _order = "sequence, code"
    _check_company_auto = True

    name = fields.Char(string="Modality Name", required=True, help="Display name, e.g., 'CT', 'MRI'.")
    code = fields.Selection(
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
        string="Code",
        required=True,
        help="Standardized modality code."
    )
    sequence = fields.Integer(string="Sequence", default=10)
    description = fields.Char(string="Description")
    company_id = fields.Many2one("res.company", string="Company", default=lambda s: s.env.company)
    active = fields.Boolean(default=True)

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Modality code must be unique per company.',
    )


# =============================================================================
# Staff Credential (License/Certification)
# =============================================================================
class ClinicalImagingStaffCredential(models.Model):
    _name = "clinical.imaging.staff.credential"
    _description = "Imaging Staff Credential"
    _order = "employee_id, credential_type, issue_date, id"
    _check_company_auto = True

    employee_id = fields.Many2one(
        "hr.employee", string="Employee",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="employee_id.company_id", store=True, readonly=True
    )
    credential_type = fields.Selection(
        [
            ("license", "Professional License"),
            ("board", "Board Certification"),
            ("training", "Training/CPD"),
            ("privilege", "Hospital Privilege"),
            ("other", "Other"),
        ],
        string="Credential Type",
        required=True,
        default="license",
    )
    name = fields.Char(
        string="Title / Credential Name",
        required=True,
        help="Credential title, e.g., 'Radiologist License', 'ARRT', 'Ultrasound Certification'."
    )
    number = fields.Char(string="Credential Number", help="Official license/certificate number.")
    issuer = fields.Char(string="Issuer / Authority")
    issue_date = fields.Date(string="Issue Date")
    expiry_date = fields.Date(string="Expiry Date")
    verified = fields.Boolean(string="Verified", help="Checked if HR has verified this credential.")
    attachment_id = fields.Many2one("ir.attachment", string="Attachment", help="Scan or digital certificate.")
    notes = fields.Text(string="Notes")

    status = fields.Selection(
        [
            ("valid", "Valid"),
            ("due", "Due Soon"),
            ("expired", "Expired"),
            ("unknown", "Unknown"),
        ],
        string="Status",
        compute="_compute_status",
        store=True,
    )
    days_to_expiry = fields.Integer(string="Days to Expiry", compute="_compute_status", store=True)

    @api.constrains("issue_date", "expiry_date")
    def _check_issue_expiry(self):
        for rec in self:
            if rec.issue_date and rec.expiry_date and rec.expiry_date < rec.issue_date:
                raise ValidationError(_("Expiry Date cannot be earlier than Issue Date."))

    @api.depends("expiry_date")
    def _compute_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.expiry_date:
                rec.status = "unknown"
                rec.days_to_expiry = 0
                continue
            delta = (rec.expiry_date - today).days
            rec.days_to_expiry = delta
            if delta < 0:
                rec.status = "expired"
            elif delta <= 30:
                rec.status = "due"
            else:
                rec.status = "valid"


# =============================================================================
# hr.employee — Imaging extensions
# =============================================================================
class HrEmployee(models.Model, _ImagingEmployeeHelpersMixin):
    _inherit = "hr.employee"

    # -------------------------------------------------------------------------
    # Roles & Privileges (do NOT redefine is_doctor; assumed from clinic_hr/doctor)
    # -------------------------------------------------------------------------
    is_radiologist = fields.Boolean(
        string="Radiologist",
        help="Checked if this employee is a radiologist who can sign imaging results."
    )
    is_technologist = fields.Boolean(
        string="Imaging Technologist",
        help="Checked if this employee performs image acquisition."
    )
    is_sonographer = fields.Boolean(
        string="Sonographer",
        help="Checked if this employee performs ultrasound scans."
    )
    is_physicist = fields.Boolean(
        string="Medical Physicist",
        help="Checked if this employee handles QA/QC and dose audits."
    )
    is_imaging_nurse = fields.Boolean(
        string="Imaging Nurse",
        help="Checked if this employee provides nursing support for imaging (e.g., IV/contrast/sedation)."
    )
    imaging_active = fields.Boolean(
        string="Active in Imaging",
        default=True,
        help="Uncheck to exclude from imaging rosters and auto-assignments."
    )

    # Signing & Supervision
    can_sign_imaging_result = fields.Boolean(
        string="Can Sign Results",
        help="If checked, this user can finalize imaging results (subject to access rules)."
    )
    sign_policy = fields.Selection(
        [
            ("alone", "Sign Alone"),
            ("cosign_required", "Co-sign Required"),
            ("supervision_required", "Supervision Required"),
        ],
        string="Signing Policy",
        default="alone",
        help="Policy applied when this user signs reports."
    )
    co_signer_id = fields.Many2one(
        "hr.employee", string="Default Co-signer",
        domain=[("is_radiologist", "=", True)],
        help="If co-sign is required, this radiologist will be suggested."
    )

    # -------------------------------------------------------------------------
    # Competency & Preferences
    # -------------------------------------------------------------------------
    modality_tag_ids = fields.Many2many(
        "clinical.imaging.modality.tag",
        "clinical_imaging_modality_tag_employee_rel",
        "employee_id", "tag_id",
        string="Modality Competencies",
        help="Modalities this employee is qualified to perform/read."
    )
    device_ids = fields.Many2many(
        "clinical.imaging.device",
        "clinical_imaging_device_employee_rel",
        "employee_id", "device_id",
        string="Authorized Devices",
        help="Devices this staff is allowed/preferred to operate/read."
    )
    preferred_location = fields.Char(
        string="Preferred Location",
        help="Preferred radiology room/site for rostering."
    )
    max_daily_workload = fields.Integer(
        string="Max Daily Workload",
        default=40,
        help="Target maximum number of studies per day for this staff."
    )
    default_report_template_id = fields.Many2one(
        "clinical.imaging.report.template",
        string="Default Report Template",
        help="Default report template when this staff authors a result."
    )
    worklist_assignment = fields.Selection(
        [
            ("manual", "Manual"),
            ("round_robin", "Round Robin"),
            ("load_based", "Load-based"),
            ("modality_based", "Modality-based"),
        ],
        string="Worklist Assignment",
        default="manual",
        help="Preferred assignment strategy for this staff."
    )

    # -------------------------------------------------------------------------
    # Signature & Identity
    # -------------------------------------------------------------------------
    signature_image = fields.Binary(
        string="Signature Image",
        attachment=True,
        help="Scanned or drawn signature image to display on reports."
    )
    signature_text = fields.Char(
        string="Signature Text",
        help="Textual signature (name with degrees/registrations)."
    )
    sign_pin = fields.Char(
        string="Signing PIN",
        help="Optional PIN required to sign imaging results. Keep confidential."
    )
    provider_identifier = fields.Char(
        string="Provider Identifier",
        help="National or local provider ID (e.g., NPI/STR/DOKTER ID)."
    )

    # -------------------------------------------------------------------------
    # Counters (rolling 30 days) & Today
    # -------------------------------------------------------------------------
    result_signed_30d = fields.Integer(
        string="Results Signed (30d)", compute="_compute_imaging_counters", store=False
    )
    avg_tat_acq_to_sign_30d = fields.Float(
        string="Avg TAT Acq→Sign (h, 30d)", compute="_compute_imaging_counters", store=False
    )
    pending_results_assigned = fields.Integer(
        string="Pending Results Assigned", compute="_compute_imaging_counters", store=False
    )
    studies_acquired_30d = fields.Integer(
        string="Studies Acquired (30d)", compute="_compute_imaging_counters", store=False
    )
    todays_worklist = fields.Integer(
        string="Today's Worklist", compute="_compute_imaging_counters", store=False
    )

    # -------------------------------------------------------------------------
    # Relations
    # -------------------------------------------------------------------------
    credential_ids = fields.One2many(
        "clinical.imaging.staff.credential", "employee_id",
        string="Credentials", copy=True
    )
    credential_count = fields.Integer(string="Credential Count", compute="_compute_counts", store=False)
    credential_due = fields.Integer(string="Credentials Due", compute="_compute_counts", store=False)
    credential_expired = fields.Integer(string="Credentials Expired", compute="_compute_counts", store=False)

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_counts(self):
        for rec in self:
            rec.credential_count = len(rec.credential_ids)
            rec.credential_due = len(rec.credential_ids.filtered(lambda c: c.status == "due"))
            rec.credential_expired = len(rec.credential_ids.filtered(lambda c: c.status == "expired"))

    def _compute_imaging_counters(self):
        """
        Compute rolling 30-day productivity and today's worklist numbers.
        Safe if related models are not installed.
        """
        now = self._dt_now()
        start_30d = self._dt_days_ago(30)
        today_start = fields.Datetime.to_datetime(fields.Date.to_string(fields.Date.context_today(self)))
        today_end = today_start + timedelta(days=1, seconds=-1)

        Result = self.env["clinical.imaging.result"].sudo() if self._has_model("clinical.imaging.result") else None
        Study = self.env["clinical.imaging.study"].sudo() if self._has_model("clinical.imaging.study") else None

        for rec in self:
            # Defaults
            rec.result_signed_30d = 0
            rec.avg_tat_acq_to_sign_30d = 0.0
            rec.pending_results_assigned = 0
            rec.studies_acquired_30d = 0
            rec.todays_worklist = 0

            # Results: signed by this radiologist
            if Result and rec.is_radiologist:
                # Signed within last 30d
                domain_signed = [
                    ("author_doctor_id", "=", rec.id),
                    ("signed_datetime", ">=", start_30d),
                    ("signed_datetime", "<=", now),
                    ("state", "in", ["final", "amended"]),
                ] if self._has_field("clinical.imaging.result", "state") else [
                    ("author_doctor_id", "=", rec.id),
                    ("signed_datetime", ">=", start_30d),
                    ("signed_datetime", "<=", now),
                ]
                signed = Result.search(domain_signed, order="signed_datetime asc")
                rec.result_signed_30d = len(signed)

                # Avg TAT Acq->Sign
                if signed and Study:
                    hours = []
                    for r in signed:
                        st = Study.search([("imaging_id", "=", r.imaging_id.id)], limit=1, order="study_datetime asc")
                        if st and st.study_datetime and r.signed_datetime:
                            delta = fields.Datetime.to_datetime(r.signed_datetime) - fields.Datetime.to_datetime(st.study_datetime)
                            if delta.total_seconds() > 0:
                                hours.append(delta.total_seconds() / 3600.0)
                    rec.avg_tat_acq_to_sign_30d = round(sum(hours) / len(hours), 2) if hours else 0.0

                # Pending results assigned (not yet final)
                if self._has_field("clinical.imaging.result", "state"):
                    pending_states = ["draft", "in_review", "preliminary", "verified", "approved"]
                    rec.pending_results_assigned = Result.search_count([
                        ("author_doctor_id", "=", rec.id),
                        ("state", "in", pending_states),
                    ])
                else:
                    rec.pending_results_assigned = 0

                # Today's worklist (results targeting this radiologist by author or reviewer)
                domain_today = [
                    ("author_doctor_id", "=", rec.id),
                    ("create_date", ">=", today_start),
                    ("create_date", "<=", today_end),
                ]
                rec.todays_worklist = Result.search_count(domain_today)

            # Studies acquired by this technologist (30d)
            if Study and (rec.is_technologist or rec.is_sonographer):
                # Try to detect field 'acquired_by_id' or 'technologist_id' on Study
                tech_field = None
                for fname in ["acquired_by_id", "technologist_id", "operator_id"]:
                    if self._has_field("clinical.imaging.study", fname):
                        tech_field = fname
                        break
                if tech_field:
                    rec.studies_acquired_30d = Study.search_count([
                        (tech_field, "=", rec.id),
                        ("study_datetime", ">=", start_30d),
                        ("study_datetime", "<=", now),
                    ])
                else:
                    rec.studies_acquired_30d = 0

    # -------------------------------------------------------------------------
    # ACTIONS (Smart Buttons / Utilities)
    # -------------------------------------------------------------------------
    def _action_window(self, name, res_model, domain, view_mode="list,form"):
        self.ensure_one()
        return {
            "name": name,
            "type": "ir.actions.act_window",
            "res_model": res_model,
            "view_mode": view_mode,
            "domain": domain,
            "target": "current",
        }

    def action_open_my_results_pending(self):
        """Open Results assigned to me that are not yet final."""
        self.ensure_one()
        if not self.is_radiologist:
            raise UserError(_("Only radiologists have a results worklist."))
        if not self._has_model("clinical.imaging.result"):
            raise UserError(_("Imaging Result model is not available."))
        domain = [("author_doctor_id", "=", self.id)]
        if self._has_field("clinical.imaging.result", "state"):
            domain.append(("state", "in", ["draft", "in_review", "preliminary", "verified", "approved"]))
        return self._action_window(_("My Pending Results"), "clinical.imaging.result", domain)

    def action_open_my_results_signed_30d(self):
        """Open Results signed by me in the last 30 days."""
        self.ensure_one()
        if not self._has_model("clinical.imaging.result"):
            raise UserError(_("Imaging Result model is not available."))
        start_30d = self._dt_days_ago(30)
        domain = [
            ("author_doctor_id", "=", self.id),
            ("signed_datetime", ">=", start_30d),
            ("signed_datetime", "<=", self._dt_now()),
        ]
        return self._action_window(_("My Results (Last 30 days)"), "clinical.imaging.result", domain)

    def action_open_my_studies_acquired_30d(self):
        """Open Studies acquired by me in the last 30 days."""
        self.ensure_one()
        if not self._has_model("clinical.imaging.study"):
            raise UserError(_("Imaging Study model is not available."))
        tech_field = None
        for fname in ["acquired_by_id", "technologist_id", "operator_id"]:
            if self._has_field("clinical.imaging.study", fname):
                tech_field = fname
                break
        if not tech_field:
            raise UserError(_("This database does not track technologist on Study."))
        start_30d = self._dt_days_ago(30)
        domain = [
            (tech_field, "=", self.id),
            ("study_datetime", ">=", start_30d),
            ("study_datetime", "<=", self._dt_now()),
        ]
        return self._action_window(_("My Acquired Studies (Last 30 days)"), "clinical.imaging.study", domain, view_mode="list,form,kanban")

    def action_open_credentials(self):
        self.ensure_one()
        return self._action_window(_("My Credentials"), "clinical.imaging.staff.credential", [("employee_id", "=", self.id)])

    def action_open_authorized_devices(self):
        self.ensure_one()
        if not self._has_model("clinical.imaging.device"):
            raise UserError(_("Imaging Device model is not available."))
        return self._action_window(_("Authorized Devices"), "clinical.imaging.device", [("id", "in", self.device_ids.ids)], view_mode="list,form,kanban")

    def action_open_today_worklist(self):
        """Open today's newly created Results assigned to me (for triage)."""
        self.ensure_one()
        if not self._has_model("clinical.imaging.result"):
            raise UserError(_("Imaging Result model is not available."))
        today_start = fields.Datetime.to_datetime(fields.Date.to_string(fields.Date.context_today(self)))
        today_end = today_start + timedelta(days=1, seconds=-1)
        domain = [
            ("author_doctor_id", "=", self.id),
            ("create_date", ">=", today_start),
            ("create_date", "<=", today_end),
        ]
        return self._action_window(_("Today's Worklist"), "clinical.imaging.result", domain)

    # -------------------------------------------------------------------------
    # DEFAULTING / INTEROP for other modules
    # -------------------------------------------------------------------------
    @api.onchange("is_radiologist")
    def _onchange_is_radiologist(self):
        for rec in self:
            if rec.is_radiologist:
                rec.can_sign_imaging_result = True
                # suggest report template from company default if empty
                if not rec.default_report_template_id and "clinical.imaging.report.template" in self.env:
                    tmpl = self.env["clinical.imaging.report.template"].search([
                        ("company_id", "=", rec.company_id.id),
                        ("is_default_company", "=", True),
                        ("active", "=", True),
                    ], limit=1)
                    if tmpl:
                        rec.default_report_template_id = tmpl.id

    # -------------------------------------------------------------------------
    # SQL Constraints (none for inherited model — use credential uniqueness)
    # -------------------------------------------------------------------------


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


# =============================================================================
# Helpers (safe checks so module works even if other addons not yet installed)
# =============================================================================
class _EncounterImagingHelpers(models.AbstractModel):
    _name = "clinical.imaging.encounter.helpers"
    _description = "Encounter Imaging Helpers"

    def _has_model(self, model_name):
        return model_name in self.env

    def _has_field(self, model_name, field_name):
        try:
            return field_name in self.env[model_name]._fields
        except Exception:
            return False

    def _dt_now(self):
        return fields.Datetime.now()

    def _today_bounds(self):
        start = fields.Datetime.to_datetime(fields.Date.to_string(fields.Date.context_today(self)))
        end = start + timedelta(days=1, seconds=-1)
        return start, end


# =============================================================================
# Inherit clinic.encounter — Imaging Integrations
# =============================================================================
# class ClinicEncounter(models.Model, _EncounterImagingHelpers):
#     _inherit = "clinic.encounter"

#     # -------------------------------------------------------------------------
#     # Relations to Imaging domain
#     # -------------------------------------------------------------------------
#     imaging_request_ids = fields.One2many(
#         "clinical.imaging.request",
#         "encounter_id",
#         string="Imaging Requests",
#         help="Imaging requests created for this encounter."
#     )
#     imaging_ids = fields.One2many(
#         "clinical.imaging",
#         "encounter_id",
#         string="Imaging Records",
#         help="Imaging records performed under this encounter."
#     )
#     imaging_screening_id = fields.Many2one(
#         "clinical.imaging.encounter.screening",
#         string="Imaging Screening",
#         help="Pre-imaging screening summary for this encounter (safety/eligibility)."
#     )
#     imaging_note_ids = fields.One2many(
#         "clinical.imaging.encounter.note",
#         "encounter_id",
#         string="Imaging Notes",
#         help="Notes related to imaging for this encounter (pre/intra/post/safety)."
#     )

#     # -------------------------------------------------------------------------
#     # KPI counters (computed on the fly)
#     # -------------------------------------------------------------------------
#     imaging_request_count = fields.Integer(string="Imaging Requests", compute="_compute_imaging_kpis", store=False)
#     imaging_count = fields.Integer(string="Imaging Records", compute="_compute_imaging_kpis", store=False)
#     imaging_result_count = fields.Integer(string="Imaging Results", compute="_compute_imaging_kpis", store=False)
#     imaging_study_count = fields.Integer(string="Studies", compute="_compute_imaging_kpis", store=False)
#     imaging_series_count = fields.Integer(string="Series", compute="_compute_imaging_kpis", store=False)
#     imaging_image_count = fields.Integer(string="Images", compute="_compute_imaging_kpis", store=False)
#     imaging_finding_count = fields.Integer(string="Findings", compute="_compute_imaging_kpis", store=False)
#     imaging_key_image_count = fields.Integer(string="Key Images", compute="_compute_imaging_kpis", store=False)

#     has_imaging_pending = fields.Boolean(
#         string="Has Pending Imaging",
#         compute="_compute_pending_status",
#         store=False,
#         help="True if there are pending imaging requests or non-final results in this encounter."
#     )
#     last_imaging_datetime = fields.Datetime(string="Last Imaging Datetime", compute="_compute_last_dates", store=False)
#     last_result_datetime = fields.Datetime(string="Last Result Signed", compute="_compute_last_dates", store=False)

#     # -------------------------------------------------------------------------
#     # COMPUTES
#     # -------------------------------------------------------------------------
#     def _compute_imaging_kpis(self):
#         Request = self.env["clinical.imaging.request"].sudo() if self._has_model("clinical.imaging.request") else None
#         Imaging = self.env["clinical.imaging"].sudo() if self._has_model("clinical.imaging") else None
#         Result = self.env["clinical.imaging.result"].sudo() if self._has_model("clinical.imaging.result") else None
#         Study = self.env["clinical.imaging.study"].sudo() if self._has_model("clinical.imaging.study") else None
#         Series = self.env["clinical.imaging.series"].sudo() if self._has_model("clinical.imaging.series") else None
#         Image = self.env["clinical.imaging.image"].sudo() if self._has_model("clinical.imaging.image") else None
#         Finding = self.env["clinical.imaging.finding"].sudo() if self._has_model("clinical.imaging.finding") else None

#         for rec in self:
#             rec.imaging_request_count = Request.search_count([("encounter_id", "=", rec.id)]) if Request else 0
#             rec.imaging_count = Imaging.search_count([("encounter_id", "=", rec.id)]) if Imaging else 0
#             rec.imaging_result_count = Result.search_count([("encounter_id", "=", rec.id)]) if (Result and self._has_field("clinical.imaging.result", "encounter_id")) else (
#                 Result.search_count([("imaging_id.encounter_id", "=", rec.id)]) if Result else 0
#             )
#             rec.imaging_study_count = Study.search_count([("encounter_id", "=", rec.id)]) if (Study and self._has_field("clinical.imaging.study", "encounter_id")) else (
#                 Study.search_count([("imaging_id.encounter_id", "=", rec.id)]) if Study else 0
#             )
#             rec.imaging_series_count = Series.search_count([("encounter_id", "=", rec.id)]) if (Series and self._has_field("clinical.imaging.series", "encounter_id")) else (
#                 Series.search_count([("imaging_id.encounter_id", "=", rec.id)]) if Series else 0
#             )
#             rec.imaging_image_count = Image.search_count([("encounter_id", "=", rec.id)]) if (Image and self._has_field("clinical.imaging.image", "encounter_id")) else (
#                 Image.search_count([("imaging_id.encounter_id", "=", rec.id)]) if Image else 0
#             )
#             # Findings (direct link may not exist)
#             if Finding and self._has_field("clinical.imaging.finding", "encounter_id"):
#                 rec.imaging_finding_count = Finding.search_count([("encounter_id", "=", rec.id)])
#             elif Finding and Imaging:
#                 imaging_ids = Imaging.search([("encounter_id", "=", rec.id)]).ids
#                 rec.imaging_finding_count = Finding.search_count([("imaging_id", "in", imaging_ids)]) if imaging_ids else 0
#             else:
#                 rec.imaging_finding_count = 0

#             # Key images
#             if Image and Imaging:
#                 imaging_ids = Imaging.search([("encounter_id", "=", rec.id)]).ids
#                 rec.imaging_key_image_count = Image.search_count([("imaging_id", "in", imaging_ids), ("is_key", "=", True)]) if imaging_ids and self._has_field("clinical.imaging.image", "is_key") else 0
#             else:
#                 rec.imaging_key_image_count = 0

#     def _compute_pending_status(self):
#         Request = self.env["clinical.imaging.request"].sudo() if self._has_model("clinical.imaging.request") else None
#         Result = self.env["clinical.imaging.result"].sudo() if self._has_model("clinical.imaging.result") else None
#         for rec in self:
#             pending_req = 0
#             pending_res = 0
#             if Request and self._has_field("clinical.imaging.request", "state"):
#                 pending_req = Request.search_count([
#                     ("encounter_id", "=", rec.id),
#                     ("state", "in", ["draft", "submitted", "approved", "scheduled", "in_progress"])
#                 ])
#             if Result and self._has_field("clinical.imaging.result", "state"):
#                 if self._has_field("clinical.imaging.result", "encounter_id"):
#                     pending_res = Result.search_count([
#                         ("encounter_id", "=", rec.id),
#                         ("state", "not in", ["final", "amended"])
#                     ])
#                 else:
#                     # via imaging
#                     pending_res = Result.search_count([
#                         ("imaging_id.encounter_id", "=", rec.id),
#                         ("state", "not in", ["final", "amended"])
#                     ])
#             rec.has_imaging_pending = bool(pending_req or pending_res)

#     def _compute_last_dates(self):
#         Imaging = self.env["clinical.imaging"].sudo() if self._has_model("clinical.imaging") else None
#         Study = self.env["clinical.imaging.study"].sudo() if self._has_model("clinical.imaging.study") else None
#         Result = self.env["clinical.imaging.result"].sudo() if self._has_model("clinical.imaging.result") else None
#         for rec in self:
#             rec.last_imaging_datetime = False
#             rec.last_result_datetime = False
#             if Study and Imaging:
#                 imaging_ids = Imaging.search([("encounter_id", "=", rec.id)]).ids
#                 if imaging_ids:
#                     st = Study.search([("imaging_id", "in", imaging_ids)], limit=1, order="study_datetime desc")
#                     rec.last_imaging_datetime = st.study_datetime if st else False
#             if Result:
#                 if self._has_field("clinical.imaging.result", "encounter_id"):
#                     rs = Result.search([("encounter_id", "=", rec.id), ("signed_datetime", "!=", False)], limit=1, order="signed_datetime desc")
#                 else:
#                     rs = Result.search([("imaging_id.encounter_id", "=", rec.id), ("signed_datetime", "!=", False)], limit=1, order="signed_datetime desc")
#                 rec.last_result_datetime = rs.signed_datetime if rs else False

#     # -------------------------------------------------------------------------
#     # Smart-button actions
#     # -------------------------------------------------------------------------
#     def _action_window(self, name, model, domain, view_mode="list,form,kanban"):
#         self.ensure_one()
#         return {
#             "name": name,
#             "type": "ir.actions.act_window",
#             "res_model": model,
#             "view_mode": view_mode,
#             "domain": domain,
#             "target": "current",
#             "context": {
#                 "default_encounter_id": self.id,
#                 "default_patient_id": getattr(self, "patient_id", False) and self.patient_id.id or False,
#                 "default_appointment_id": getattr(self, "appointment_id", False) and self.appointment_id.id or False,
#                 "default_treatment_id": getattr(self, "treatment_id", False) and self.treatment_id.id or False,
#             },
#         }

#     def action_open_imaging_requests(self):
#         return self._action_window(_("Imaging Requests"), "clinical.imaging.request", [("encounter_id", "=", self.id)])

#     def action_open_imaging_records(self):
#         return self._action_window(_("Imaging Records"), "clinical.imaging", [("encounter_id", "=", self.id)])

#     def action_open_imaging_results(self):
#         Result = "clinical.imaging.result"
#         domain = [("encounter_id", "=", self.id)] if self._has_field(Result, "encounter_id") else [("imaging_id.encounter_id", "=", self.id)]
#         return self._action_window(_("Imaging Results"), Result, domain, view_mode="list,form")

#     def action_open_imaging_studies(self):
#         Study = "clinical.imaging.study"
#         domain = [("encounter_id", "=", self.id)] if self._has_field(Study, "encounter_id") else [("imaging_id.encounter_id", "=", self.id)]
#         return self._action_window(_("Studies"), Study, domain, view_mode="list,form,kanban")

#     def action_open_imaging_series(self):
#         Series = "clinical.imaging.series"
#         domain = [("encounter_id", "=", self.id)] if self._has_field(Series, "encounter_id") else [("imaging_id.encounter_id", "=", self.id)]
#         return self._action_window(_("Series"), Series, domain, view_mode="list,form,kanban")

#     def action_open_imaging_images(self):
#         Image = "clinical.imaging.image"
#         domain = [("encounter_id", "=", self.id)] if self._has_field(Image, "encounter_id") else [("imaging_id.encounter_id", "=", self.id)]
#         return self._action_window(_("Images"), Image, domain, view_mode="list,form,kanban")

#     def action_open_imaging_findings(self):
#         Finding = "clinical.imaging.finding"
#         domain = [("encounter_id", "=", self.id)] if self._has_field(Finding, "encounter_id") else [("imaging_id.encounter_id", "=", self.id)]
#         return self._action_window(_("Findings"), Finding, domain, view_mode="list,form,kanban")

#     def action_open_imaging_screening(self):
#         self.ensure_one()
#         if self.imaging_screening_id:
#             return {
#                 "name": _("Imaging Screening"),
#                 "type": "ir.actions.act_window",
#                 "res_model": "clinical.imaging.encounter.screening",
#                 "view_mode": "form",
#                 "res_id": self.imaging_screening_id.id,
#                 "target": "current",
#             }
#         # If none, open creation form
#         return {
#             "name": _("New Imaging Screening"),
#             "type": "ir.actions.act_window",
#             "res_model": "clinical.imaging.encounter.screening",
#             "view_mode": "form",
#             "target": "current",
#             "context": {
#                 "default_encounter_id": self.id,
#                 "default_patient_id": getattr(self, "patient_id", False) and self.patient_id.id or False,
#                 "default_appointment_id": getattr(self, "appointment_id", False) and self.appointment_id.id or False,
#             },
#         }

#     def action_new_imaging_request(self):
#         """Quick-create Imaging Request from this encounter."""
#         self.ensure_one()
#         if not self._has_model("clinical.imaging.request"):
#             raise UserError(_("Imaging Request model is not available."))
#         return {
#             "name": _("New Imaging Request"),
#             "type": "ir.actions.act_window",
#             "res_model": "clinical.imaging.request",
#             "view_mode": "form",
#             "target": "current",
#             "context": {
#                 "default_encounter_id": self.id,
#                 "default_patient_id": getattr(self, "patient_id", False) and self.patient_id.id or False,
#                 "default_appointment_id": getattr(self, "appointment_id", False) and self.appointment_id.id or False,
#                 "default_treatment_id": getattr(self, "treatment_id", False) and self.treatment_id.id or False,
#                 "default_referring_partner_id": getattr(self, "patient_id", False) and self.patient_id.id or False,
#             },
#         }


# =============================================================================
# clinical.imaging.encounter.screening — Pre-imaging eligibility & safety
# =============================================================================
class ClinicalImagingEncounterScreening(models.Model, _EncounterImagingHelpers):
    _name = "clinical.imaging.encounter.screening"
    _description = "Encounter Imaging Screening"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "encounter_id, create_date desc"
    _check_company_auto = True
    # ganti field related menjadi compute
        
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        compute="_compute_patient_from_encounter",
        store=True,
        readonly=False,
        help="Resolved from encounter when available."
    )

    @api.depends("encounter_id")
    def _compute_patient_from_encounter(self):
        for rec in self:
            patient = False
            enc = rec.encounter_id
            if enc:
                # Prefer exact patient field names if they exist
                if "patient_id" in enc._fields:
                    patient = enc.patient_id
                elif "patient_partner_id" in enc._fields:
                    patient = enc.patient_partner_id
                elif "partner_id" in enc._fields:
                    patient = enc.partner_id
            rec.patient_id = patient

    # -------------------------------------------------------------------------
    # Identity & Ownership
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Screening Number",
        required=True,
        copy=False,
        default=lambda s: _("New"),
        help="Unique identifier generated from sequence at creation."
    )
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda s: s.env.company)
    active = fields.Boolean(default=True)

    # -------------------------------------------------------------------------
    # Encounter context
    # -------------------------------------------------------------------------
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        required=True,
        ondelete="cascade",
        index=True
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="encounter_id.patient_id",
        store=True,
        readonly=True
    )
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        help="Related appointment for this screening."
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        help="Related treatment plan if applicable."
    )

    # -------------------------------------------------------------------------
    # Vitals & Anthropometrics
    # -------------------------------------------------------------------------
    height_cm = fields.Float(string="Height (cm)")
    weight_kg = fields.Float(string="Weight (kg)")
    bmi = fields.Float(string="BMI", compute="_compute_bmi", store=True)
    systolic_bp = fields.Integer(string="Systolic BP (mmHg)")
    diastolic_bp = fields.Integer(string="Diastolic BP (mmHg)")
    heart_rate_bpm = fields.Integer(string="Heart Rate (bpm)")
    temperature_c = fields.Float(string="Temperature (°C)")
    spo2_percent = fields.Float(string="SpO2 (%)")

    # -------------------------------------------------------------------------
    # Safety (contrast/MRI/radiation)
    # -------------------------------------------------------------------------
    pregnancy_status = fields.Selection(
        [("unknown", "Unknown"), ("no", "Not Pregnant"), ("yes", "Pregnant"), ("na", "Not Applicable")],
        string="Pregnancy Status", default="unknown"
    )
    lmp_date = fields.Date(string="Last Menstruation Date")
    pregnancy_test_done = fields.Boolean(string="Pregnancy Test Done")
    pregnancy_test_result = fields.Selection(
        [("unknown", "Unknown"), ("negative", "Negative"), ("positive", "Positive")],
        string="Pregnancy Test Result", default="unknown"
    )

    contrast_allergy = fields.Boolean(string="Contrast Allergy")
    premed_required = fields.Boolean(string="Premedication Required")
    premed_given = fields.Boolean(string="Premedication Given")
    premed_protocol = fields.Text(string="Premedication Protocol")

    egfr_value = fields.Float(string="eGFR (mL/min/1.73m²)")
    egfr_date = fields.Date(string="eGFR Date")
    egfr_method = fields.Selection([("ckd_epi", "CKD-EPI"), ("mdrd", "MDRD"), ("other", "Other")], string="eGFR Method")
    renal_risk = fields.Selection(
        [("unknown", "Unknown"), ("low", "Low"), ("moderate", "Moderate"), ("high", "High")],
        string="Renal Risk", compute="_compute_renal_risk", store=True
    )

    has_metal_implants = fields.Boolean(string="Metal Implants")
    has_pacemaker = fields.Boolean(string="Pacemaker/ICD")
    has_cochlear_implant = fields.Boolean(string="Cochlear Implant")
    implant_description = fields.Char(string="Implant Description")

    iv_access = fields.Selection(
        [("none", "None"), ("peripheral", "Peripheral IV"), ("central", "Central Line")],
        string="IV Access"
    )
    fasting_hours = fields.Float(string="Fasting Hours")

    # Sedation plan
    sedation_plan = fields.Selection(
        [("none", "None"), ("minimal", "Minimal"), ("conscious", "Conscious Sedation"),
         ("deep", "Deep Sedation"), ("ga", "General Anesthesia")],
        string="Sedation Plan", default="none"
    )
    sedation_notes = fields.Text(string="Sedation Notes")

    # -------------------------------------------------------------------------
    # Consent & Documents
    # -------------------------------------------------------------------------
    consent_id = fields.Many2one("clinic.consent.form", string="Consent", help="Linked consent document for the exam.")
    attachment_count = fields.Integer(string="Attachments", compute="_compute_attachment_count", store=False)

    # -------------------------------------------------------------------------
    # Audit & Verification
    # -------------------------------------------------------------------------
    performed_by_id = fields.Many2one("hr.employee", string="Performed By")
    performed_datetime = fields.Datetime(string="Performed At", default=fields.Datetime.now)
    verified_by_id = fields.Many2one("hr.employee", string="Verified By", domain=[("is_doctor", "=", True)])
    verified_datetime = fields.Datetime(string="Verified At")
    state = fields.Selection(
        [("draft", "Draft"), ("verified", "Verified"), ("cancelled", "Cancelled")],
        string="Status", default="draft", tracking=True, index=True
    )
    notes = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # CONSTRAINTS / COMPUTES
    # -------------------------------------------------------------------------
    @api.constrains("height_cm", "weight_kg", "systolic_bp", "diastolic_bp", "heart_rate_bpm", "temperature_c", "spo2_percent", "egfr_value", "fasting_hours")
    def _check_ranges(self):
        for rec in self:
            if rec.height_cm is not None and rec.height_cm < 0:
                raise ValidationError(_("Height cannot be negative."))
            if rec.weight_kg is not None and rec.weight_kg < 0:
                raise ValidationError(_("Weight cannot be negative."))
            if rec.temperature_c is not None and (rec.temperature_c < 30 or rec.temperature_c > 45):
                raise ValidationError(_("Temperature appears out of realistic range."))
            if rec.spo2_percent is not None and (rec.spo2_percent < 0 or rec.spo2_percent > 100):
                raise ValidationError(_("SpO2 must be between 0 and 100%."))
            if rec.egfr_value is not None and (rec.egfr_value < 0 or rec.egfr_value > 200):
                raise ValidationError(_("eGFR must be in a realistic range (0..200)."))
            if rec.fasting_hours is not None and rec.fasting_hours < 0:
                raise ValidationError(_("Fasting Hours cannot be negative."))

    @api.depends("height_cm", "weight_kg")
    def _compute_bmi(self):
        for rec in self:
            if rec.height_cm and rec.weight_kg and rec.height_cm > 0:
                h_m = rec.height_cm / 100.0
                rec.bmi = round(rec.weight_kg / (h_m * h_m), 2)
            else:
                rec.bmi = 0.0

    @api.depends("egfr_value", "egfr_date")
    def _compute_renal_risk(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.egfr_value or not rec.egfr_date:
                rec.renal_risk = "unknown"
                continue
            # simple thresholds
            if rec.egfr_value < 30:
                risk = "high"
            elif rec.egfr_value < 45:
                risk = "moderate"
            else:
                risk = "low"
            # optionally enforce recency window (e.g., last 1 year)
            rec.renal_risk = risk

    @api.onchange("contrast_allergy")
    def _onchange_contrast_allergy(self):
        for rec in self:
            if rec.contrast_allergy and rec.premed_required is False:
                rec.premed_required = True

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging.encounter.screening") or _("New")
            # Link back to encounter default field
            if vals.get("encounter_id") and not vals.get("appointment_id"):
                enc = self.env["clinic.encounter"].browse(vals["encounter_id"])
                if enc and hasattr(enc, "appointment_id") and enc.appointment_id:
                    vals["appointment_id"] = enc.appointment_id.id
        recs = super().create(vals_list)
        # If encounter has no screening set, attach the newly created one
        for rec in recs:
            if rec.encounter_id and not rec.encounter_id.imaging_screening_id:
                rec.encounter_id.imaging_screening_id = rec.id
        return recs

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("state", "draft")
        default.setdefault("verified_by_id", False)
        default.setdefault("verified_datetime", False)
        return super().copy(default)

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def action_verify(self):
        for rec in self:
            if rec.state == "cancelled":
                raise UserError(_("Cancelled screening cannot be verified."))
            rec.state = "verified"
            rec.verified_by_id = self.env.user.employee_id.id if hasattr(self.env.user, "employee_id") else False
            rec.verified_datetime = fields.Datetime.now()
            rec.message_post(body=_("Screening verified."))

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state == "verified":
                raise UserError(_("Verified screening cannot be cancelled."))
            rec.state = "cancelled"
            rec.message_post(body=_("Screening cancelled. %s") % (reason or ""))

    def action_view_attachments(self):
        self.ensure_one()
        return {
            "name": _("Attachments"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    # -------------------------------------------------------------------------
    # Display
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name or _("New")
            if rec.encounter_id:
                label = f"{label} ({rec.encounter_id.display_name})"
            res.append((rec.id, label))
        return res

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Screening Number must be unique per company.',
    )


# =============================================================================
# clinical.imaging.encounter.note — Free-form notes tied to encounter
# =============================================================================
class ClinicalImagingEncounterNote(models.Model, _EncounterImagingHelpers):
    _name = "clinical.imaging.encounter.note"
    _description = "Encounter Imaging Note"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "encounter_id, create_date desc"
    _check_company_auto = True

    # pastikan encounter_id ADA (hapus comment dan definisikan)
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        required=True,
        ondelete="cascade",
        index=True
    )

    # ganti related menjadi compute seperti di screening
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        compute="_compute_patient_from_encounter",
        store=True,
        readonly=False
    )

    @api.depends("encounter_id")
    def _compute_patient_from_encounter(self):
        for rec in self:
            patient = False
            enc = rec.encounter_id
            if enc:
                if "patient_id" in enc._fields:
                    patient = enc.patient_id
                elif "patient_partner_id" in enc._fields:
                    patient = enc.patient_partner_id
                elif "partner_id" in enc._fields:
                    patient = enc.partner_id
            rec.patient_id = patient

    name = fields.Char(
        string="Note Number",
        required=True,
        copy=False,
        default=lambda s: _("New"),
        help="Unique identifier generated from sequence at creation."
    )
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda s: s.env.company)
    active = fields.Boolean(default=True)

    # encounter_id = fields.Many2one("clinic.encounter", string="Encounter", required=True, ondelete="cascade", index=True)
    patient_id = fields.Many2one("res.partner", string="Patient", related="encounter_id.patient_id", store=True, readonly=True)

    note_type = fields.Selection(
        [
            ("general", "General"),
            ("pre", "Pre-Imaging"),
            ("intra", "Intra-Procedural"),
            ("post", "Post-Imaging"),
            ("safety", "Safety"),
        ],
        string="Note Type",
        default="general",
        index=True
    )
    content = fields.Text(string="Content", required=True)
    author_user_id = fields.Many2one("res.users", string="Author User", default=lambda s: s.env.user, readonly=True)
    author_employee_id = fields.Many2one("hr.employee", string="Author Employee", compute="_compute_author_employee", store=False)
    pinned = fields.Boolean(string="Pinned")

    attachment_count = fields.Integer(string="Attachments", compute="_compute_attachment_count", store=False)

    def _compute_author_employee(self):
        for rec in self:
            rec.author_employee_id = rec.author_user_id.employee_id if rec.author_user_id and hasattr(rec.author_user_id, "employee_id") else False

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging.encounter.note") or _("New")
        return super().create(vals_list)

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        return super().copy(default)

    def action_view_attachments(self):
        self.ensure_one()
        return {
            "name": _("Attachments"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    def name_get(self):
        res = []
        for rec in self:
            title = rec.name or _("New")
            if rec.note_type:
                title = f"{title} [{dict(self._fields['note_type'].selection).get(rec.note_type)}]"
            if rec.encounter_id:
                title = f"{title} ({rec.encounter_id.display_name})"
            res.append((rec.id, title))
        return res

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Note Number must be unique per company.',
    )


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


# =============================================================================
# Helpers (safe checks & utilities)
# =============================================================================
class _ImagingConsentHelpers(models.AbstractModel):
    _name = "clinical.imaging.consent.helpers"
    _description = "Imaging Consent Helpers"

    def _has_model(self, model_name):
        return model_name in self.env

    def _has_field(self, model_name, field_name):
        try:
            return field_name in self.env[model_name]._fields
        except Exception:
            return False

    def _dt_now(self):
        return fields.Datetime.now()

    def _today(self):
        return fields.Date.context_today(self)


# =============================================================================
# Consent Template (for Imaging)
# =============================================================================
class ClinicalImagingConsentTemplate(models.Model):
    _name = "clinical.imaging.consent.template"
    _description = "Imaging Consent Template"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(string="Template Name", required=True, tracking=True)
    code = fields.Char(string="Code", index=True, help="Short unique code (e.g., 'CONSENT_CT_CONTRAST').")
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda s: s.env.company)
    active = fields.Boolean(default=True)

    scope = fields.Selection(
        [
            ("imaging_general", "General Imaging"),
            ("contrast", "Contrast Media"),
            ("mri_safety", "MRI Safety"),
            ("radiation_exposure", "Radiation Exposure"),
            ("sedation_anesthesia", "Sedation/Anesthesia"),
            ("ultrasound_procedure", "Ultrasound Procedure"),
            ("interventional", "Interventional Procedure"),
        ],
        string="Scope",
        required=True,
        default="imaging_general",
        help="Defines the consent category; used to determine applicability."
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
        help="If set, this template is intended for a specific modality."
    )
    imaging_type_ids = fields.Many2many(
        "clinical.imaging.type",
        "clinical_imaging_consent_template_type_rel",
        "template_id", "type_id",
        string="Imaging Types",
        help="Restrict applicability to selected imaging types (leave empty for all)."
    )
    default_validity_days = fields.Integer(
        string="Default Validity (days)", default=90,
        help="Default validity period from the signed date."
    )

    require_patient_signature = fields.Boolean(string="Require Patient Signature", default=True)
    require_staff_signature = fields.Boolean(string="Require Staff Signature", default=False)
    require_doctor_signature = fields.Boolean(string="Require Doctor Signature", default=False)

    body_html = fields.Html(
        string="Body (HTML)",
        sanitize=False,
        help="Main consent text. Can be rendered in the form using QWeb/HTML."
    )
    disclaimer = fields.Text(string="Disclaimer / Notes")

    question_ids = fields.One2many(
        "clinical.imaging.consent.template.question", "template_id",
        string="Questions", copy=True
    )

    @api.constrains("code")
    def _check_code_upper(self):
        for rec in self:
            if rec.code and rec.code.strip() != rec.code.strip().upper():
                rec.code = rec.code.strip().upper()

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Template Code must be unique per company.',
    )


class ClinicalImagingConsentTemplateQuestion(models.Model):
    _name = "clinical.imaging.consent.template.question"
    _description = "Imaging Consent Template Question"
    _order = "template_id, sequence, id"
    _check_company_auto = True

    template_id = fields.Many2one("clinical.imaging.consent.template", string="Template", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", string="Company", related="template_id.company_id", store=True, readonly=True)

    sequence = fields.Integer(default=10)
    code = fields.Char(string="Code", help="Short code (unique per template).")
    text = fields.Char(string="Question Text", required=True)
    qtype = fields.Selection(
        [
            ("boolean", "Yes/No"),
            ("text", "Text"),
            ("select", "Selection"),
        ],
        string="Type", required=True, default="boolean"
    )
    selection_options = fields.Text(
        string="Selection Options",
        help="For 'Selection' type, provide one option per line."
    )
    required = fields.Boolean(string="Required", default=False)
    critical = fields.Boolean(
        string="Critical",
        help="If checked and answered 'Yes' (or specific option), this may raise an alert."
    )
    # defaults
    default_boolean = fields.Boolean(string="Default Yes")
    default_text = fields.Char(string="Default Text")
    default_selection = fields.Char(string="Default Selection")

    _code_template_unique = models.Constraint(
        'unique(code, template_id)',
        'Question Code must be unique per template.',
    )


# =============================================================================
# Inherit clinic.consent — Imaging-specific extensions
# =============================================================================
class ClinicConsent(models.Model, _ImagingConsentHelpers):
    _inherit = "clinic.consent.form"

    # -------------------------------------------------------------------------
    # Imaging Context & Links
    # -------------------------------------------------------------------------
    imaging_template_id = fields.Many2one(
        "clinical.imaging.consent.template",
        string="Imaging Consent Template",
        help="Template applied to this consent."
    )
    imaging_scope = fields.Selection(
        related="imaging_template_id.scope",
        string="Imaging Scope",
        store=False,
        readonly=True
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
        help="Modality this consent relates to."
    )
    imaging_type_id = fields.Many2one("clinical.imaging.type", string="Imaging Type")
    device_id = fields.Many2one("clinical.imaging.device", string="Device")

    appointment_id = fields.Many2one("clinic.appointment", string="Appointment")
    # encounter_id = fields.Many2one("clinic.encounter", string="Clinical Encounter")
    treatment_id = fields.Many2one("clinic.treatment", string="Treatment")
    prescription_order_id = fields.Many2one("clinic.prescription.order", string="Prescription Order")

    imaging_request_id = fields.Many2one("clinical.imaging.request", string="Imaging Request", index=True)
    imaging_id = fields.Many2one("clinical.imaging", string="Imaging Record")
    imaging_result_id = fields.Many2one("clinical.imaging.result", string="Imaging Result")

    # -------------------------------------------------------------------------
    # Patient/Staff/Doctor Signatures (digital)
    # -------------------------------------------------------------------------
    patient_signature = fields.Binary(string="Patient Signature", attachment=True)
    patient_signed_datetime = fields.Datetime(string="Patient Signed At")
    patient_signed_by_partner_id = fields.Many2one("res.partner", string="Patient (Signer)")
    patient_signed_by_user_id = fields.Many2one("res.users", string="Captured By (User)")
    patient_signed_ip = fields.Char(string="Signer IP")

    staff_signature = fields.Binary(string="Staff Signature", attachment=True)
    staff_signed_datetime = fields.Datetime(string="Staff Signed At")
    staff_employee_id = fields.Many2one("hr.employee", string="Staff (Witness/Operator)")

    doctor_signature = fields.Binary(string="Doctor Signature", attachment=True)
    doctor_signed_datetime = fields.Datetime(string="Doctor Signed At")
    doctor_employee_id = fields.Many2one("hr.employee", string="Doctor (Supervisor)", domain=[("is_doctor", "=", True)])

    # -------------------------------------------------------------------------
    # Validity & State
    # -------------------------------------------------------------------------
    validity_from = fields.Date(string="Validity From", help="Usually the date the patient signed.")
    validity_to = fields.Date(string="Validity To")
    validity_days = fields.Integer(string="Validity (days)", default=0, help="If >0, used to compute Validity To.")
    is_expired = fields.Boolean(string="Expired", compute="_compute_validity", store=False)
    is_revoked = fields.Boolean(string="Revoked")
    revoked_datetime = fields.Datetime(string="Revoked At")
    revoked_by_user_id = fields.Many2one("res.users", string="Revoked By")
    revoked_reason = fields.Text(string="Revocation Reason")

    imaging_body_html = fields.Html(
        string="Rendered Body (HTML)",
        sanitize=False,
        help="Optional rendered HTML for the consent text. Can be filled from template."
    )

    # Questions/Answers captured for this consent (from template)
    answer_ids = fields.One2many("clinical.imaging.consent.answer", "consent_id", string="Answers", copy=True)
    required_answer_pending = fields.Boolean(string="Required Questions Pending", compute="_compute_required_pending", store=False)

    # -------------------------------------------------------------------------
    # Display helpers (computed patient if base model doesn't provide)
    # -------------------------------------------------------------------------
    consent_patient_id = fields.Many2one("res.partner", string="Patient (Resolved)", compute="_compute_consent_patient", store=False)

    # -------------------------------------------------------------------------
    # Constraints & Computes
    # -------------------------------------------------------------------------
    @api.constrains("validity_from", "validity_to")
    def _check_validity_dates(self):
        for rec in self:
            if rec.validity_from and rec.validity_to and rec.validity_to < rec.validity_from:
                raise ValidationError(_("Validity To cannot be earlier than Validity From."))

    @api.depends("validity_from", "validity_to", "validity_days")
    def _compute_validity(self):
        today = self._today()
        for rec in self:
            # derive validity_to if missing but days set
            if rec.validity_from and rec.validity_days and not rec.validity_to:
                rec.validity_to = rec.validity_from + timedelta(days=int(rec.validity_days))
            rec.is_expired = bool(rec.validity_to and rec.validity_to < today)

    def _compute_required_pending(self):
        for rec in self:
            pending = False
            # if template defines required questions, ensure they are answered
            if rec.imaging_template_id and rec.imaging_template_id.question_ids:
                # build map by code if present
                req_questions = rec.imaging_template_id.question_ids.filtered(lambda q: q.required)
                if req_questions:
                    # answers matched by question_id or code
                    answered_codes = set()
                    for ans in rec.answer_ids:
                        if ans.question_id and ans._is_answer_filled():
                            answered_codes.add(ans.question_id.code or ans.question_id.id)
                        elif ans.code and ans._is_value_filled():
                            answered_codes.add(ans.code)
                    for q in req_questions:
                        key = q.code or q.id
                        if key not in answered_codes:
                            pending = True
                            break
            rec.required_answer_pending = pending

    def _compute_consent_patient(self):
        for rec in self:
            patient = False
            # First, try base model's patient_id if exists
            if self._has_field("clinic.consent.form", "patient_id") and getattr(rec, "patient_id", False):
                patient = rec.patient_id
            # Derive from linked objects
            if not patient and rec.imaging_request_id and self._has_field("clinical.imaging.request", "patient_id"):
                patient = rec.imaging_request_id.patient_id
            if not patient and rec.encounter_id and self._has_field("clinic.encounter", "patient_id"):
                patient = rec.encounter_id.patient_id
            if not patient and rec.treatment_id and self._has_field("clinic.treatment", "patient_id"):
                patient = rec.treatment_id.patient_id
            if not patient and rec.appointment_id and self._has_field("clinic.appointment", "patient_id"):
                patient = rec.appointment_id.patient_id
            if not patient and rec.imaging_id and self._has_field("clinical.imaging", "patient_id"):
                patient = rec.imaging_id.patient_id
            if not patient and rec.imaging_result_id and self._has_field("clinical.imaging.result", "patient_id"):
                patient = rec.imaging_result_id.patient_id
            rec.consent_patient_id = patient.id if patient else False

    @api.constrains("imaging_request_id", "imaging_id", "imaging_result_id")
    def _check_patient_consistency(self):
        """Ensure the consent patient (resolved) matches linked imaging objects if their patient is known."""
        for rec in self:
            pat = rec.consent_patient_id
            if not pat:
                continue
            # request
            if rec.imaging_request_id and self._has_field("clinical.imaging.request", "patient_id"):
                if rec.imaging_request_id.patient_id and rec.imaging_request_id.patient_id.id != pat.id:
                    raise ValidationError(_("Patient on the Imaging Request does not match the consent patient."))
            # imaging
            if rec.imaging_id and self._has_field("clinical.imaging", "patient_id"):
                if rec.imaging_id.patient_id and rec.imaging_id.patient_id.id != pat.id:
                    raise ValidationError(_("Patient on the Imaging record does not match the consent patient."))
            # result
            if rec.imaging_result_id and self._has_field("clinical.imaging.result", "patient_id"):
                if rec.imaging_result_id.patient_id and rec.imaging_result_id.patient_id.id != pat.id:
                    raise ValidationError(_("Patient on the Imaging Result does not match the consent patient."))

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    def write(self, vals):
        # Prevent destructive change after signing unless revoking
        locked_fields = {"imaging_template_id", "modality", "imaging_type_id", "device_id"}
        if any(f in vals for f in locked_fields):
            for rec in self:
                if rec.patient_signed_datetime or rec.staff_signed_datetime or rec.doctor_signed_datetime:
                    raise UserError(_("Cannot change core imaging fields after the consent has been signed. Revoke or duplicate instead."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.patient_signed_datetime or rec.staff_signed_datetime or rec.doctor_signed_datetime:
                raise UserError(_("Signed consents cannot be deleted. Revoke instead."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # Apply template ⇒ populate HTML & questions
    # -------------------------------------------------------------------------
    def action_apply_imaging_template(self):
        for rec in self:
            if not rec.imaging_template_id:
                raise UserError(_("Please choose an Imaging Consent Template first."))
            # Fill HTML body if empty
            if not rec.imaging_body_html and rec.imaging_template_id.body_html:
                rec.imaging_body_html = rec.imaging_template_id.body_html
            # Derive modality if not set
            if not rec.modality and rec.imaging_template_id.modality:
                rec.modality = rec.imaging_template_id.modality
            # Populate questions (replace existing answers)
            rec.answer_ids.unlink()
            lines = []
            for q in rec.imaging_template_id.question_ids.sorted("sequence"):
                val = {
                    "consent_id": rec.id,
                    "template_id": rec.imaging_template_id.id,
                    "question_id": q.id,
                    "code": q.code or False,
                    "text": q.text,
                    "qtype": q.qtype,
                    "required": q.required,
                    "critical": q.critical,
                    "selection_options": q.selection_options,
                }
                # defaults
                if q.qtype == "boolean":
                    val["answer_boolean"] = q.default_boolean
                elif q.qtype == "text":
                    val["answer_text"] = q.default_text or ""
                elif q.qtype == "select":
                    val["answer_selection"] = q.default_selection or ""
                lines.append((0, 0, val))
            if lines:
                rec.write({"answer_ids": lines})
        return True

    # -------------------------------------------------------------------------
    # Signing & Revocation
    # -------------------------------------------------------------------------
    def _check_ready_to_sign(self, role="patient"):
        for rec in self:
            # Required answers must be completed
            if rec.required_answer_pending:
                raise UserError(_("Please complete all required questions before signing."))
            # Template signature requirements
            tmpl = rec.imaging_template_id
            if role == "patient" and tmpl and tmpl.require_patient_signature is False:
                raise UserError(_("This template does not require a patient signature."))
            if role == "staff" and tmpl and tmpl.require_staff_signature is False:
                raise UserError(_("This template does not require a staff signature."))
            if role == "doctor" and tmpl and tmpl.require_doctor_signature is False:
                raise UserError(_("This template does not require a doctor signature."))
            # Already revoked/expired?
            if rec.is_revoked:
                raise UserError(_("This consent has been revoked."))
            # ok

    def action_sign_patient(self, signature=None, signer_partner_id=False, signer_user_id=False, signer_ip=None):
        for rec in self:
            rec._check_ready_to_sign("patient")
            vals = {
                "patient_signed_datetime": self._dt_now(),
                "validity_from": rec.validity_from or fields.Date.context_today(self),
            }
            if signature:
                vals["patient_signature"] = signature
            if signer_partner_id:
                vals["patient_signed_by_partner_id"] = signer_partner_id
            if signer_user_id:
                vals["patient_signed_by_user_id"] = signer_user_id
            if signer_ip:
                vals["patient_signed_ip"] = signer_ip
            # compute validity_to if validity_days set
            if rec.validity_days and not rec.validity_to:
                vals["validity_to"] = (vals["validity_from"] or fields.Date.context_today(self)) + timedelta(days=int(rec.validity_days))
            rec.write(vals)
            rec.message_post(body=_("Patient signed the consent."))

    def action_sign_staff(self, signature=None, staff_employee_id=False):
        for rec in self:
            rec._check_ready_to_sign("staff")
            vals = {"staff_signed_datetime": self._dt_now()}
            if signature:
                vals["staff_signature"] = signature
            if staff_employee_id:
                vals["staff_employee_id"] = staff_employee_id
            rec.write(vals)
            rec.message_post(body=_("Staff signed the consent."))

    def action_sign_doctor(self, signature=None, doctor_employee_id=False):
        for rec in self:
            rec._check_ready_to_sign("doctor")
            vals = {"doctor_signed_datetime": self._dt_now()}
            if signature:
                vals["doctor_signature"] = signature
            if doctor_employee_id:
                vals["doctor_employee_id"] = doctor_employee_id
            rec.write(vals)
            rec.message_post(body=_("Doctor signed the consent."))

    def action_revoke(self, reason=None):
        for rec in self:
            if rec.is_revoked:
                continue
            rec.is_revoked = True
            rec.revoked_datetime = self._dt_now()
            rec.revoked_by_user_id = self.env.user
            rec.revoked_reason = reason or ""
            rec.message_post(body=_("Consent revoked. %s") % (reason or ""))

    # -------------------------------------------------------------------------
    # Convenience checks used by other modules (Request/Result)
    # -------------------------------------------------------------------------
    def is_fully_valid(self):
        """Return True if signatures required by template are present, not expired, not revoked."""
        self.ensure_one()
        if self.is_revoked or self.is_expired:
            return False
        tmpl = self.imaging_template_id
        if not tmpl:
            return True
        if tmpl.require_patient_signature and not self.patient_signed_datetime:
            return False
        if tmpl.require_staff_signature and not self.staff_signed_datetime:
            return False
        if tmpl.require_doctor_signature and not self.doctor_signed_datetime:
            return False
        return True

    # -------------------------------------------------------------------------
    # Display
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            base = rec.display_name if rec.display_name else (rec.name if hasattr(rec, "name") else _("Consent"))
            extras = []
            if rec.imaging_template_id:
                extras.append(rec.imaging_template_id.code or rec.imaging_template_id.name)
            if rec.modality:
                extras.append(rec.modality)
            if rec.imaging_type_id:
                extras.append(rec.imaging_type_id.display_name)
            if rec.validity_to:
                extras.append(_("valid until %s") % fields.Date.to_string(rec.validity_to))
            name = base
            if extras:
                name = f"{base} [{', '.join(extras)}]"
            res.append((rec.id, name))
        return res


# =============================================================================
# Answers captured from Consent (instantiated from template)
# =============================================================================
class ClinicalImagingConsentAnswer(models.Model):
    _name = "clinical.imaging.consent.answer"
    _description = "Imaging Consent Answer"
    _order = "consent_id, sequence, id"
    _check_company_auto = True

    consent_id = fields.Many2one("clinic.consent.form", string="Consent", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", string="Company", related="consent_id.company_id", store=True, readonly=True)

    template_id = fields.Many2one("clinical.imaging.consent.template", string="Template", help="For traceability.")
    question_id = fields.Many2one("clinical.imaging.consent.template.question", string="Question")
    sequence = fields.Integer(string="Sequence", default=10)
    code = fields.Char(string="Code")
    text = fields.Char(string="Question Text", required=True)
    qtype = fields.Selection(
        [("boolean", "Yes/No"), ("text", "Text"), ("select", "Selection")],
        string="Type", required=True, default="boolean"
    )
    selection_options = fields.Text(string="Selection Options")

    required = fields.Boolean(string="Required", default=False)
    critical = fields.Boolean(string="Critical", default=False)

    # answers
    answer_boolean = fields.Boolean(string="Answer (Yes)")
    answer_text = fields.Char(string="Answer (Text)")
    answer_selection = fields.Char(string="Answer (Selection)")

    def _is_answer_filled(self):
        self.ensure_one()
        if self.qtype == "boolean":
            return self.answer_boolean in (True, False)  # always filled (default False counts as filled)
        if self.qtype == "text":
            return bool(self.answer_text and self.answer_text.strip())
        if self.qtype == "select":
            return bool(self.answer_selection and self.answer_selection.strip())
        return False

    def _is_value_filled(self):
        """Alias when question_id is not set (fallback by code)."""
        return self._is_answer_filled()


# =============================================================================
# Inherit clinical.imaging.request — Link to consent & checks
# =============================================================================
class ClinicalImagingRequest(models.Model, _ImagingConsentHelpers):
    _inherit = "clinical.imaging.request"

    consent_id = fields.Many2one(
        "clinic.consent.form",
        string="Consent",
        help="Consent document linked to this request."
    )
    consent_required = fields.Boolean(string="Consent Required", compute="_compute_consent_flags", store=False)
    consent_ok = fields.Boolean(string="Consent OK", compute="_compute_consent_flags", store=False)
    consent_scope_needed = fields.Selection(
        selection=lambda self: self.env["clinical.imaging.consent.template"]._fields["scope"].selection,
        string="Required Consent Scope", compute="_compute_consent_flags", store=False
    )

    def _compute_consent_flags(self):
        for rec in self:
            # Determine if consent is required based on modality/imaging type or flags
            scope_needed = False
            required = False
            if rec.imaging_type_id and self._has_field("clinical.imaging.type", "modality") and rec.imaging_type_id.modality == "MR":
                scope_needed = "mri_safety"
                required = True
            # contrast?
            if hasattr(rec, "contrast_required") and getattr(rec, "contrast_required"):
                scope_needed = scope_needed or "contrast"
                required = True
            # sedation?
            if hasattr(rec, "sedation_required") and getattr(rec, "sedation_required"):
                scope_needed = scope_needed or "sedation_anesthesia"
                required = True
            # radiation exposure for CT/fluoro/NM
            if rec.imaging_type_id and self._has_field("clinical.imaging.type", "modality") and rec.imaging_type_id.modality in ("CT", "DX", "MG", "NM", "XR"):
                scope_needed = scope_needed or "radiation_exposure"
            rec.consent_scope_needed = scope_needed or False
            rec.consent_required = required or bool(scope_needed)

            # Check consent validity
            ok = False
            if rec.consent_id:
                try:
                    ok = rec.consent_id.is_fully_valid()
                except Exception:
                    ok = False
            rec.consent_ok = bool(ok)

    @api.onchange("consent_id")
    def _onchange_consent_id(self):
        for rec in self:
            if rec.consent_id:
                # Set reverse link for visibility on consent
                if self._has_field("clinic.consent.form", "imaging_request_id"):
                    rec.consent_id.imaging_request_id = rec.id


# =============================================================================
# Inherit clinical.imaging.result — Convenience backlink to consent
# =============================================================================
class ClinicalImagingResult(models.Model, _ImagingConsentHelpers):
    _inherit = "clinical.imaging.result"

    consent_id = fields.Many2one(
        "clinic.consent.form",
        string="Consent",
        compute="_compute_consent_id",
        store=False,
        help="Resolved consent document for this result (from request/encounter/treatment if available)."
    )

    def _compute_consent_id(self):
        for rec in self:
            consent = False
            # Prefer from imaging.request if present
            if rec.imaging_id and self._has_field("clinical.imaging", "request_id") and rec.imaging_id.request_id:
                req = rec.imaging_id.request_id
                if self._has_field("clinical.imaging.request", "consent_id"):
                    consent = req.consent_id
            # Fallback: from encounter screening consent if available
            if not consent and rec.encounter_id and "clinical.imaging.encounter.screening" in self.env:
                scr = self.env["clinical.imaging.encounter.screening"].sudo().search([("encounter_id", "=", rec.encounter_id.id)], limit=1, order="create_date desc")
                if scr and self._has_field("clinical.imaging.encounter.screening", "consent_id"):
                    consent = scr.consent_id
            rec.consent_id = consent.id if consent else False


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# Core Clinical Imaging model
# =============================================================================
class ClinicalImaging(models.Model):
    """
    Core model for Clinical Imaging Management in ClinicOne (Odoo 18 CE).

    Represents a single clinical imaging order/record for a patient,
    covering lifecycle from request to review, with integration points
    to the broader ClinicOne suite (appointment, encounter, treatment,
    procedure session, eMAR/prescription order, consent, billing, portal).
    """
    _name = "clinical.imaging"
    _description = "Clinical Imaging"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "request_datetime desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Imaging Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        help="Unique identifier generated from sequence at creation time.",
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, the imaging record is archived from regular views.",
    )

    # -------------------------------------------------------------------------
    # Patient & Care Team
    # -------------------------------------------------------------------------
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        required=True,
        index=True,
        domain=[("is_company", "=", False), ("is_patient", "=", True)],
        help="Linked patient (res.partner) flagged with 'Is a Patient'.",
        tracking=True,
    )
    doctor_id = fields.Many2one(
        "hr.employee",
        string="Responsible Doctor",
        domain=[("is_doctor", "=", True)],
        help="Doctor in charge of this imaging order.",
        tracking=True,
    )
    technician_id = fields.Many2one(
        "hr.employee",
        string="Imaging Technician",
        domain=[("is_imaging_technician", "=", True)],
        help="Technician who performs the imaging acquisition.",
        tracking=True,
    )

    # Membership / coverage (optional)
    # membership_id = fields.Many2one(
    #     "clinic.membership",
    #     string="Membership",
    #     help="Membership used for coverage/benefit of this imaging, if any.",
    # )

    # -------------------------------------------------------------------------
    # Clinical Context (cross-module hooks)
    # -------------------------------------------------------------------------
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        help="Appointment related to this imaging (if scheduled).",
    )
    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     help="Encounter during which imaging is requested or reviewed.",
    # )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        help="Treatment plan that references this imaging.",
    )
    procedure_session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Procedure Session",
        help="Procedure/Treatment session tied to this imaging.",
    )
    prescription_order_id = fields.Many2one(
        "clinic.prescription.order",
        string="Prescription/Order (eMAR)",
        help="Prescription/Order authorizing this imaging.",
    )
    consent_id = fields.Many2one(
        "clinic.consent.form",
        string="Consent",
        help="Patient consent record for the imaging procedure.",
    )

    # -------------------------------------------------------------------------
    # Imaging Specification
    # -------------------------------------------------------------------------
    imaging_type_id = fields.Many2one(
        "clinical.imaging.type",
        string="Imaging Type",
        required=True,
        help="Type of imaging (e.g., X-Ray, CT, MRI, Ultrasound).",
        tracking=True,
    )
    device_id = fields.Many2one(
        "clinical.imaging.device",
        string="Imaging Device",
        help="Imaging device used for acquisition.",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Billable Service",
        domain=[("type", "=", "service")],
        help="Service product used for pricing and invoicing.",
    )
    priority = fields.Selection(
        [
            ("0", "Normal"),
            ("1", "High"),
            ("2", "Urgent"),
            ("3", "Emergency"),
        ],
        string="Priority",
        default="0",
        help="Clinical priority to schedule and perform the imaging.",
        tracking=True,
    )

    # DICOM basics (high-level; detailed metadata lives in study/series/image models)
    dicom_study_uid = fields.Char(
        string="DICOM Study UID",
        help="DICOM Study Instance UID, if available from RIS/PACS.",
        copy=False,
        index=True,
    )
    dicom_accession_number = fields.Char(
        string="Accession Number",
        help="Accession Number assigned by RIS/PACS (if integrated).",
        copy=False,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Dates & SLA
    # -------------------------------------------------------------------------
    request_datetime = fields.Datetime(
        string="Requested At",
        default=fields.Datetime.now,
        required=True,
        help="Datetime when the imaging was requested.",
        tracking=True,
    )
    scheduled_datetime = fields.Datetime(
        string="Scheduled At",
        help="Planned datetime to perform the imaging.",
        tracking=True,
    )
    performed_datetime = fields.Datetime(
        string="Performed At",
        help="Datetime when the imaging acquisition was completed.",
        tracking=True,
    )
    reviewed_datetime = fields.Datetime(
        string="Reviewed At",
        help="Datetime when the imaging was reviewed by the doctor.",
        tracking=True,
    )
    expected_done_datetime = fields.Datetime(
        string="Expected Completion",
        help="Expected completion time used for SLA tracking and reminders.",
    )
    duration_minutes = fields.Integer(
        string="Duration (min)",
        help="Actual duration in minutes for the acquisition.",
    )
    is_overdue = fields.Boolean(
        string="Overdue",
        compute="_compute_is_overdue",
        help="Checked when the record missed its expected completion or review time.",
        store=True,
    )

    # -------------------------------------------------------------------------
    # Clinical Content
    # -------------------------------------------------------------------------
    clinical_indication = fields.Text(
        string="Clinical Indication",
        help="Reason for imaging; the clinical question to be answered.",
    )
    notes = fields.Text(
        string="Internal Notes",
        help="Internal notes for staff.",
    )
    findings_summary = fields.Text(
        string="Findings (Summary)",
        help="Brief summary of key findings; the full report is kept in the report model.",
        tracking=True,
    )
    recommendations = fields.Text(
        string="Recommendations",
        help="Clinical recommendations based on the findings.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Files & Attachments
    # -------------------------------------------------------------------------
    main_file = fields.Binary(
        string="Primary Image/File",
        attachment=True,
        help="Primary representative file (image/PDF). Full image sets are stored "
             "in child models (study/series/image) or as attachments.",
    )
    main_filename = fields.Char(
        string="File Name",
        help="Filename of the primary file."
    )
    attachment_count = fields.Integer(
        string="Attachment Count",
        compute="_compute_attachment_count",
        help="Number of attachments linked to this record.",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Billing (optional but common)
    # -------------------------------------------------------------------------
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id.id,
    )
    quantity = fields.Float(
        string="Quantity",
        default=1.0,
        help="Quantity for billing; typically 1.0 for a single imaging service.",
    )
    price_unit = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        help="Unit price for billing; prefilled from product if available.",
    )
    price_subtotal = fields.Monetary(
        string="Subtotal",
        currency_field="currency_id",
        compute="_compute_price_subtotal",
        store=True,
        help="Computed as Quantity * Unit Price.",
    )
    is_billable = fields.Boolean(
        string="Billable",
        default=True,
        help="If checked, this imaging will be included in patient billing.",
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        domain=[("move_type", "in", ["out_invoice", "out_refund"])],
        help="Linked invoice if this imaging has been billed.",
        tracking=True,
    )
    billing_state = fields.Selection(
        [
            ("no", "Not Billed"),
            ("draft", "In Draft Invoice"),
            ("posted", "Billed"),
            ("refund", "Refunded"),
        ],
        string="Billing Status",
        compute="_compute_billing_state",
        store=True,
        help="Derived from the linked invoice.",
    )

    # -------------------------------------------------------------------------
    # Privacy & Portal
    # -------------------------------------------------------------------------
    portal_published = fields.Boolean(
        string="Visible on Portal",
        help="If checked, the patient can view this imaging in the portal (subject to access rules).",
        tracking=True,
    )
    privacy_level = fields.Selection(
        [
            ("normal", "Normal"),
            ("restricted", "Restricted"),
            ("high", "Highly Restricted"),
        ],
        string="Privacy Level",
        default="normal",
        help="Controls staff and portal accessibility level.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # State Machine
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("requested", "Requested"),
            ("scheduled", "Scheduled"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("reviewed", "Reviewed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
        help="Lifecycle status of the imaging record.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("quantity", "price_unit", "currency_id")
    def _compute_price_subtotal(self):
        for rec in self:
            rec.price_subtotal = (rec.quantity or 0.0) * (rec.price_unit or 0.0)

    # @api.depends("id")
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    @api.depends("expected_done_datetime", "reviewed_datetime", "state")
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for rec in self:
            overdue = False
            # overdue if expected done has passed and not yet completed/reviewed
            if rec.state in ("requested", "scheduled", "in_progress", "completed"):
                if rec.expected_done_datetime and now > rec.expected_done_datetime:
                    # If already reviewed, not overdue.
                    if rec.state != "reviewed":
                        overdue = True
            rec.is_overdue = overdue

    @api.depends("invoice_id.state", "invoice_id.move_type")
    def _compute_billing_state(self):
        for rec in self:
            if not rec.invoice_id:
                rec.billing_state = "no"
            else:
                move = rec.invoice_id
                if move.state == "draft":
                    rec.billing_state = "draft"
                elif move.state == "posted" and move.move_type == "out_invoice":
                    rec.billing_state = "posted"
                elif move.state == "posted" and move.move_type == "out_refund":
                    rec.billing_state = "refund"
                else:
                    rec.billing_state = "no"

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("imaging_type_id")
    def _onchange_imaging_type_id(self):
        """Prefill product and duration from imaging type defaults."""
        for rec in self:
            if rec.imaging_type_id:
                if rec.imaging_type_id.default_product_id and not rec.product_id:
                    rec.product_id = rec.imaging_type_id.default_product_id.id
                if rec.imaging_type_id.default_duration_minutes and not rec.duration_minutes:
                    rec.duration_minutes = rec.imaging_type_id.default_duration_minutes

    @api.onchange("product_id")
    def _onchange_product_id_set_price(self):
        for rec in self:
            if rec.product_id and (not rec.price_unit or rec.price_unit == 0.0):
                rec.price_unit = rec.product_id.lst_price

    @api.onchange("appointment_id")
    def _onchange_appointment_id(self):
        """If linked to an appointment, align the schedule if empty."""
        for rec in self:
            appt = rec.appointment_id
            if appt and not rec.scheduled_datetime:
                # Expect appointment to have start datetime field 'start_datetime'
                start_dt = getattr(appt, "start_datetime", False)
                if start_dt:
                    rec.scheduled_datetime = start_dt

    @api.onchange("scheduled_datetime", "duration_minutes")
    def _onchange_schedule_duration(self):
        """Estimate expected completion when scheduled and duration known."""
        for rec in self:
            if rec.scheduled_datetime and rec.duration_minutes:
                rec.expected_done_datetime = fields.Datetime.add(
                    rec.scheduled_datetime, minutes=int(rec.duration_minutes)
                )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("performed_datetime", "scheduled_datetime")
    def _check_performed_after_scheduled(self):
        for rec in self:
            if rec.performed_datetime and rec.scheduled_datetime and rec.performed_datetime < rec.scheduled_datetime:
                raise ValidationError(_("‘Performed At’ must be on or after ‘Scheduled At’."))
    @api.constrains("reviewed_datetime", "performed_datetime")
    def _check_review_after_perform(self):
        for rec in self:
            if rec.reviewed_datetime and rec.performed_datetime and rec.reviewed_datetime < rec.performed_datetime:
                raise ValidationError(_("‘Reviewed At’ must be on or after ‘Performed At’."))
    @api.constrains("invoice_id", "is_billable")
    def _check_invoice_when_billable(self):
        for rec in self:
            if not rec.is_billable and rec.invoice_id:
                raise ValidationError(_("Non-billable imaging should not have an invoice linked."))

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging") or _("New")
        records = super().create(vals_list)
        # Auto-subscribe doctor/technician to chatter
        for rec in records:
            partner_ids = []
            if rec.doctor_id and rec.doctor_id.work_contact_id:
                partner_ids.append(rec.doctor_id.work_contact_id.id)
            if rec.technician_id and rec.technician_id.work_contact_id:
                partner_ids.append(rec.technician_id.work_contact_id.id)
            if partner_ids:
                rec.message_subscribe(partner_ids=list(set(partner_ids)))
        return records

    def write(self, vals):
        # Prevent modifying company after creation
        if "company_id" in vals:
            for rec in self:
                if rec.invoice_id:
                    raise UserError(_("You cannot change the Company once invoiced."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.invoice_id and rec.invoice_id.state == "posted":
                raise UserError(_("You cannot delete an imaging record that has a posted invoice."))
        return super().unlink()

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("state", "draft")
        default.setdefault("invoice_id", False)
        default.setdefault("reviewed_datetime", False)
        default.setdefault("performed_datetime", False)
        return super().copy(default)

    # -------------------------------------------------------------------------
    # ACTIONS / STATE TRANSITIONS
    # -------------------------------------------------------------------------
    def action_request(self):
        for rec in self:
            if rec.state not in ("draft", "cancelled"):
                raise UserError(_("Only Draft/Cancelled records can be moved to Requested."))
            rec.state = "requested"
            rec.message_post(body=_("Imaging has been requested."))

    def action_schedule(self):
        for rec in self:
            if rec.state not in ("requested", "draft"):
                raise UserError(_("Only Draft/Requested records can be Scheduled."))
            if not rec.scheduled_datetime:
                raise UserError(_("Please set ‘Scheduled At’ before scheduling."))
            rec.state = "scheduled"
            rec.message_post(body=_("Imaging has been scheduled."))

    def action_start(self):
        for rec in self:
            if rec.state not in ("scheduled", "requested"):
                raise UserError(_("Only Scheduled/Requested records can be set In Progress."))
            rec.state = "in_progress"
            rec.message_post(body=_("Imaging acquisition started."))

    def action_complete(self):
        Activity = self.env["mail.activity"]
        for rec in self:
            if rec.state not in ("in_progress", "scheduled"):
                raise UserError(_("Only In Progress/Scheduled records can be completed."))
            if not rec.performed_datetime:
                rec.performed_datetime = fields.Datetime.now()
            rec.state = "completed"
            rec.message_post(body=_("Imaging acquisition completed."))
            # Schedule a Review activity for the doctor
            if rec.doctor_id and rec.doctor_id.user_id:
                Activity.create({
                    "res_model_id": self.env["ir.model"]._get_id(self._name),
                    "res_id": rec.id,
                    "user_id": rec.doctor_id.user_id.id,
                    "summary": _("Review Imaging"),
                    "note": _("Please review the imaging findings and add recommendations."),
                    "activity_type_id": self.env.ref("mail.mail_activity_data_todo").id,
                    "date_deadline": fields.Date.today(),
                })

    def action_review(self):
        for rec in self:
            if rec.state != "completed":
                raise UserError(_("Only Completed records can be Reviewed."))
            if not rec.findings_summary and not rec.recommendations:
                raise UserError(_("Add findings/recommendations before marking as Reviewed."))
            if not rec.reviewed_datetime:
                rec.reviewed_datetime = fields.Datetime.now()
            rec.state = "reviewed"
            rec.message_post(body=_("Imaging has been reviewed by the doctor."))

    def action_cancel(self):
        for rec in self:
            if rec.state == "reviewed" and rec.invoice_id and rec.invoice_id.state == "posted":
                raise UserError(_("Reviewed & billed records cannot be cancelled. Please handle billing first."))
            rec.state = "cancelled"
            rec.message_post(body=_("Imaging record has been cancelled."))

    # -------------------------------------------------------------------------
    # BILLING INTEGRATION
    # -------------------------------------------------------------------------
    def _get_invoice_partner(self):
        self.ensure_one()
        if not self.patient_id:
            raise UserError(_("Patient is required for billing."))
        return self.patient_id.commercial_partner_id

    def _get_invoice_description(self):
        self.ensure_one()
        parts = [_("Imaging")]
        if self.name:
            parts.append(self.name)
        if self.imaging_type_id:
            parts.append("[%s]" % self.imaging_type_id.display_name)
        if self.patient_id:
            parts.append("- %s" % self.patient_id.display_name)
        return " ".join(parts)

    def _prepare_invoice_vals(self):
        self.ensure_one()
        partner = self._get_invoice_partner()
        return {
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "invoice_origin": self.name,
            "invoice_user_id": self.env.user.id,
            "invoice_date": fields.Date.context_today(self),
            "currency_id": self.currency_id.id or self.env.company.currency_id.id,
            "invoice_line_ids": [(0, 0, self._prepare_invoice_line_vals())],
            "invoice_payment_ref": self.name,
            "invoice_payment_term_id": partner.property_payment_term_id.id or False,
            "invoice_incoterm_id": False,
        }

    def _prepare_invoice_line_vals(self):
        self.ensure_one()
        if not self.product_id:
            raise UserError(_("Please set a Billable Service (product) before creating the invoice."))
        name = self._get_invoice_description()
        # Taxes from product, mapped by fiscal position if set on partner
        partner = self._get_invoice_partner()
        fpos = partner.property_account_position_id
        taxes = self.product_id.taxes_id
        if fpos:
            taxes = fpos.map_tax(taxes, partner)
        return {
            "name": name,
            "product_id": self.product_id.id,
            "quantity": self.quantity or 1.0,
            "price_unit": self.price_unit or self.product_id.lst_price,
            "currency_id": self.currency_id.id or self.env.company.currency_id.id,
            "tax_ids": [(6, 0, taxes.ids)],
        }

    def action_create_invoice(self):
        """Create a draft invoice if none exists."""
        for rec in self:
            if not rec.is_billable:
                raise UserError(_("This imaging is marked as not billable."))
            if rec.invoice_id:
                raise UserError(_("An invoice has already been linked to this imaging."))
            vals = rec._prepare_invoice_vals()
            move = self.env["account.move"].create(vals)
            rec.invoice_id = move.id
            rec.message_post(body=_("Draft invoice created: %s") % move.display_name)
        return self.action_open_invoice()

    def action_open_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No invoice linked to this imaging."))
        return {
            "name": _("Invoice"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.invoice_id.id,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # QUICK NAVIGATION / HELPERS
    # -------------------------------------------------------------------------
    def action_view_attachments(self):
        self.ensure_one()
        return {
            "name": _("Attachments"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    def action_open_appointment(self):
        self.ensure_one()
        if not self.appointment_id:
            raise UserError(_("No appointment is linked."))
        return {
            "name": _("Appointment"),
            "type": "ir.actions.act_window",
            "res_model": self.appointment_id._name,
            "view_mode": "form",
            "res_id": self.appointment_id.id,
            "target": "current",
        }

    def action_open_encounter(self):
        self.ensure_one()
        if not self.encounter_id:
            raise UserError(_("No clinical encounter is linked."))
        return {
            "name": _("Clinical Encounter"),
            "type": "ir.actions.act_window",
            "res_model": self.encounter_id._name,
            "view_mode": "form",
            "res_id": self.encounter_id.id,
            "target": "current",
        }

    def action_toggle_portal(self):
        for rec in self:
            rec.portal_published = not rec.portal_published

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        result = []
        for rec in self:
            display = rec.name or _("Imaging")
            if rec.patient_id:
                display = f"{display} - {rec.patient_id.display_name}"
            if rec.imaging_type_id:
                display = f"{display} [{rec.imaging_type_id.display_name}]"
            result.append((rec.id, display))
        return result

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _name_company_uniq = models.Constraint(
        'unique(name, company_id)',
        'Imaging Number must be unique per company.',
    )
    _dicom_study_uid_company_uniq = models.Constraint(
        'unique(dicom_study_uid, company_id)',
        'DICOM Study UID must be unique per company.',
    )


# =============================================================================
# Imaging Type (basic master data)
# =============================================================================
class ClinicalImagingType(models.Model):
    _name = "clinical.imaging.type"
    _description = "Clinical Imaging Type"
    _order = "sequence, name"

    name = fields.Char(string="Name", required=True, help="Display name for the imaging type.")
    code = fields.Char(string="Code", help="Short code (e.g., XR, CT, MR, US).")
    sequence = fields.Integer(string="Sequence", default=10, help="Ordering helper.")
    default_product_id = fields.Many2one(
        "product.product",
        string="Default Service",
        domain=[("type", "=", "service")],
        help="Default billable service to prefill on imaging records."
    )
    default_duration_minutes = fields.Integer(
        string="Default Duration (min)",
        help="Typical duration in minutes for this imaging type."
    )
    description = fields.Text(string="Description", help="Notes about modality, protocol, precautions, etc.")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Imaging Type code must be unique per company.',
    )


# =============================================================================
# Imaging Device (equipment master data)
# =============================================================================
class ClinicalImagingDevice(models.Model):
    _name = "clinical.imaging.device"
    _description = "Clinical Imaging Device"
    _order = "name"

    name = fields.Char(string="Device Name", required=True)
    manufacturer = fields.Char(string="Manufacturer")
    model_name = fields.Char(string="Model")
    serial_number = fields.Char(string="Serial Number")
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
        help="Primary modality of the device."
    )
    location = fields.Char(string="Location", help="Physical room/location of the device.")
    vendor_contact_id = fields.Many2one("res.partner", string="Vendor", help="Vendor or maintenance provider.")
    last_maintenance_date = fields.Date(string="Last Maintenance")
    next_maintenance_date = fields.Date(string="Next Maintenance")
    maintenance_interval_days = fields.Integer(
        string="Maintenance Interval (days)",
        default=180,
        help="Interval between preventive maintenance schedules."
    )
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    @api.onchange("last_maintenance_date", "maintenance_interval_days")
    def _onchange_maintenance_dates(self):
        for rec in self:
            if rec.last_maintenance_date and rec.maintenance_interval_days:
                rec.next_maintenance_date = fields.Date.add(
                    rec.last_maintenance_date, days=int(rec.maintenance_interval_days)
                )

    _serial_company_unique = models.Constraint(
        'unique(serial_number, company_id)',
        'Serial number must be unique per company.',
    )


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# TAGS - For classifying imaging types (e.g., "Musculoskeletal", "Cardiac")
# =============================================================================
class ClinicalImagingTypeTag(models.Model):
    _name = "clinical.imaging.type.tag"
    _description = "Clinical Imaging Type Tag"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(string="Tag Name", required=True, translate=False)
    color = fields.Integer(string="Color Index", help="Color index for kanban/list chips.")
    description = fields.Char(string="Description")
    company_id = fields.Many2one("res.company", string="Company",
                                 default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Imaging Type Tag must be unique per company.',
    )


# =============================================================================
# MASTER - Clinical Imaging Type
# =============================================================================
class ClinicalImagingType(models.Model):
    """
    Master data for clinical imaging types (XR/CT/MR/US, etc.).
    Drives default billing, scheduling, device preference, consent, and reporting.
    """
    _name = "clinical.imaging.type"
    _description = "Clinical Imaging Type"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Name", required=True, tracking=True,
        help="Display name of the imaging type (e.g., 'Chest X-Ray PA', 'Brain MRI with Contrast')."
    )
    code = fields.Char(
        string="Code", tracking=True, index=True,
        help="Short code for the imaging type (e.g., XR-CH-PA, CT-ABD, MR-BRAIN-CE)."
    )
    sequence = fields.Integer(string="Sequence", default=10,
                              help="Ordering helper in lists and menus.")
    company_id = fields.Many2one(
        "res.company", string="Company", required=True,
        default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)

    # -------------------------------------------------------------------------
    # Classification
    # -------------------------------------------------------------------------
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
        string="Modality", required=True, tracking=True,
        help="Primary modality category for this imaging type."
    )
    category = fields.Selection(
        [
            ("diagnostic", "Diagnostic"),
            ("interventional", "Interventional"),
            ("screening", "Screening"),
            ("therapy", "Therapeutic/Procedure Guidance"),
        ],
        string="Category", default="diagnostic", tracking=True,
        help="Clinical intent category for this imaging type."
    )
    tag_ids = fields.Many2many(
        "clinical.imaging.type.tag",
        "clinical_imaging_type_tag_rel",
        "imaging_type_id", "tag_id",
        string="Tags",
        help="Optional tags to classify and search imaging types."
    )
    description = fields.Text(string="Description",
                              help="Additional notes about indication, protocol variants, caveats.")

    # -------------------------------------------------------------------------
    # Billing Defaults (integration with accounting/product)
    # -------------------------------------------------------------------------
    default_product_id = fields.Many2one(
        "product.product",
        string="Default Billable Service",
        domain=[("type", "=", "service")],
        help="Default service product used when creating requests or imaging records."
    )
    default_price_unit = fields.Monetary(
        string="Default Unit Price",
        currency_field="currency_id",
        help="Suggested price if no product is selected; falls back to product list price."
    )
    currency_id = fields.Many2one(
        "res.currency", string="Currency",
        default=lambda self: self.env.company.currency_id.id
    )
    default_tax_ids = fields.Many2many(
        "account.tax",
        "clinical_imaging_type_tax_rel",
        "imaging_type_id", "tax_id",
        string="Default Taxes",
        help="Default taxes; will be mapped by fiscal position on the patient."
    )
    is_billable = fields.Boolean(
        string="Billable by Default", default=True,
        help="If checked, generated imaging is billable by default."
    )

    # -------------------------------------------------------------------------
    # Scheduling Defaults
    # -------------------------------------------------------------------------
    default_duration_minutes = fields.Integer(
        string="Default Duration (min)", tracking=True,
        help="Typical duration to perform this imaging; used for scheduling/SLA."
    )
    default_device_id = fields.Many2one(
        "clinical.imaging.device",
        string="Preferred Device",
        help="Default/primary device to allocate when available."
    )
    device_ids = fields.Many2many(
        "clinical.imaging.device",
        "clinical_imaging_type_device_rel",
        "imaging_type_id", "device_id",
        string="Allowed Devices",
        help="List of devices considered suitable for this imaging type."
    )

    # -------------------------------------------------------------------------
    # Consent & Safety
    # -------------------------------------------------------------------------
    require_consent = fields.Boolean(
        string="Consent Required", default=False,
        help="If checked, a patient consent is required before acquisition."
    )
    consent_note = fields.Text(
        string="Consent Note",
        help="Instructions/policy notes for consent (template mapping handled by consent module)."
    )
    safety_risk = fields.Selection(
        [
            ("none", "None"),
            ("low", "Low"),
            ("moderate", "Moderate"),
            ("high", "High"),
        ],
        string="Safety Risk Level", default="low", tracking=True,
        help="Generalized risk for triage and scheduling allocation."
    )
    require_pregnancy_check = fields.Boolean(
        string="Pregnancy Check Required", default=False,
        help="If checked, pregnancy status must be verified per policy before acquisition."
    )
    require_creatinine_check = fields.Boolean(
        string="Creatinine/eGFR Required", default=False,
        help="If checked, recent renal function labs required (contrast or specific modalities)."
    )
    creatinine_max_value = fields.Float(
        string="Max Creatinine (mg/dL)",
        help="If set, creatinine must be ≤ this value; used for validation prompts."
    )

    # -------------------------------------------------------------------------
    # Contrast / Medication Policies
    # -------------------------------------------------------------------------
    contrast_required = fields.Boolean(
        string="Contrast Required", default=False,
        help="If checked, contrast administration is required by default."
    )
    contrast_agent_product_id = fields.Many2one(
        "product.product", string="Contrast Agent",
        domain=[("type", "in", ["consu"])],
        help="Default contrast agent product (stockable or consumable)."
    )
    contrast_dose_mg_per_kg = fields.Float(
        string="Contrast Dose (mg/kg)",
        help="Suggested dose per kg body weight; final dose calculated at acquisition."
    )
    sedation_required = fields.Boolean(
        string="Sedation Required", default=False,
        help="If checked, sedation/anxiolysis is required by default (e.g., pediatric MRI)."
    )
    fasting_hours = fields.Integer(
        string="Fasting Hours",
        help="Recommended fasting hours prior to the procedure (if applicable)."
    )

    # -------------------------------------------------------------------------
    # Reporting Defaults (optional)
    # -------------------------------------------------------------------------
    report_template_id = fields.Many2one(
        "clinical.imaging.report.template",
        string="Default Report Template",
        help="Optional default report template for results of this imaging type."
    )

    # -------------------------------------------------------------------------
    # Statistics / Helpers
    # -------------------------------------------------------------------------
    protocol_step_count = fields.Integer(
        string="Protocol Steps",
        compute="_compute_counts", store=False
    )
    prep_count = fields.Integer(
        string="Preparation Items",
        compute="_compute_counts", store=False
    )
    contra_count = fields.Integer(
        string="Contraindications",
        compute="_compute_counts", store=False
    )
    device_count = fields.Integer(
        string="Devices",
        compute="_compute_counts", store=False
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_counts(self):
        for rec in self:
            rec.protocol_step_count = self.env["clinical.imaging.protocol"].search_count([("imaging_type_id", "=", rec.id)])
            rec.prep_count = self.env["clinical.imaging.type.prep"].search_count([("imaging_type_id", "=", rec.id)])
            rec.contra_count = self.env["clinical.imaging.type.contra"].search_count([("imaging_type_id", "=", rec.id)])
            rec.device_count = len(rec.device_ids)

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("default_product_id")
    def _onchange_default_product_id(self):
        for rec in self:
            if rec.default_product_id:
                if not rec.default_price_unit or rec.default_price_unit == 0.0:
                    rec.default_price_unit = rec.default_product_id.lst_price
                # Suggest taxes from product
                taxes = rec.default_product_id.taxes_id
                rec.default_tax_ids = [(6, 0, taxes.ids)] if taxes else [(6, 0, [])]

    @api.onchange("modality", "default_device_id")
    def _onchange_device_modality_guard(self):
        """
        Soft guard: if preferred device has different modality, warn user.
        Hard checks are enforced in constraints.
        """
        for rec in self:
            if rec.modality and rec.default_device_id and rec.default_device_id.modality and \
               rec.default_device_id.modality != rec.modality:
                return {
                    "warning": {
                        "title": _("Modality Mismatch"),
                        "message": _(
                            "Preferred Device modality (%s) differs from Imaging Type modality (%s). "
                            "Please review your selection."
                        ) % (rec.default_device_id.modality, rec.modality)
                    }
                }

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("code")
    def _check_code_upper(self):
        for rec in self:
            if rec.code and rec.code.strip() != rec.code.strip().upper():
                # Normalize silently instead of blocking
                rec.code = rec.code.strip().upper()

    @api.constrains("fasting_hours")
    def _check_fasting_non_negative(self):
        for rec in self:
            if rec.fasting_hours is not None and rec.fasting_hours < 0:
                raise ValidationError(_("Fasting Hours must be greater than or equal to zero."))

    @api.constrains("contrast_dose_mg_per_kg")
    def _check_contrast_dose_positive(self):
        for rec in self:
            if rec.contrast_required and (rec.contrast_dose_mg_per_kg or 0.0) <= 0.0:
                raise ValidationError(_("Contrast dose (mg/kg) must be positive when contrast is required."))

    @api.constrains("default_device_id", "modality")
    def _check_device_modality(self):
        for rec in self:
            if rec.default_device_id and rec.default_device_id.modality and rec.modality:
                if rec.default_device_id.modality != rec.modality:
                    raise ValidationError(_("Preferred Device modality must match Imaging Type modality."))

    @api.constrains("require_creatinine_check", "creatinine_max_value")
    def _check_creatinine_threshold(self):
        for rec in self:
            if rec.require_creatinine_check and (rec.creatinine_max_value or 0.0) <= 0.0:
                raise ValidationError(_("Max Creatinine must be set to a positive value when renal check is required."))

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            parts = [rec.name]
            if rec.code:
                parts.append("[%s]" % rec.code)
            if rec.modality:
                parts.append("(%s)" % rec.modality)
            res.append((rec.id, " ".join(parts)))
        return res

    def action_open_devices(self):
        self.ensure_one()
        return {
            "name": _("Allowed Devices"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.device",
            "view_mode": "list,form",
            "domain": [("id", "in", self.device_ids.ids)],
            "target": "current",
        }

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Imaging Type code must be unique per company.',
    )


# =============================================================================
# PROTOCOL - Step-by-step acquisition guide per imaging type
# =============================================================================
class ClinicalImagingProtocol(models.Model):
    _name = "clinical.imaging.protocol"
    _description = "Clinical Imaging Protocol"
    _order = "imaging_type_id, sequence, id"
    _check_company_auto = True

    imaging_type_id = fields.Many2one(
        "clinical.imaging.type", string="Imaging Type",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="imaging_type_id.company_id", store=True, readonly=True
    )
    sequence = fields.Integer(string="Sequence", default=10)
    title = fields.Char(string="Step Title", required=True,
                        help="Short title of the protocol step (e.g., 'Positioning', 'Scout/Localizer').")
    instruction = fields.Text(
        string="Detailed Instruction", required=True,
        help="Detailed instructions for the technician/operator."
    )
    expected_duration_minutes = fields.Integer(
        string="Expected Duration (min)",
        help="Expected duration for this specific step."
    )
    requires_contrast = fields.Boolean(
        string="Requires Contrast", default=False,
        help="Check if this step includes contrast administration."
    )
    requires_sedation = fields.Boolean(
        string="Requires Sedation", default=False,
        help="Check if this step requires sedation or anxiolysis."
    )
    note = fields.Char(string="Notes")

    @api.constrains("expected_duration_minutes")
    def _check_step_duration_non_negative(self):
        for rec in self:
            if rec.expected_duration_minutes is not None and rec.expected_duration_minutes < 0:
                raise ValidationError(_("Expected duration must be non-negative."))


# =============================================================================
# PREPARATION - Pre-procedure preparation items per imaging type
# =============================================================================
class ClinicalImagingTypePrep(models.Model):
    _name = "clinical.imaging.type.prep"
    _description = "Clinical Imaging Type Preparation"
    _order = "imaging_type_id, sequence, id"
    _check_company_auto = True

    imaging_type_id = fields.Many2one(
        "clinical.imaging.type", string="Imaging Type",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="imaging_type_id.company_id", store=True, readonly=True
    )
    sequence = fields.Integer(string="Sequence", default=10)
    title = fields.Char(string="Preparation Title", required=True,
                        help="Short title (e.g., 'Fasting', 'Remove metallic objects').")
    instruction = fields.Text(
        string="Preparation Instruction", required=True,
        help="Plain-language instruction for patients or staff."
    )
    responsible = fields.Selection(
        [
            ("patient", "Patient"),
            ("staff", "Staff"),
            ("doctor", "Doctor"),
        ],
        string="Responsible", default="patient",
        help="Who is responsible to perform/ensure this preparation."
    )
    min_hours_before = fields.Float(
        string="Min Hours Before",
        help="Minimum hours before procedure when this preparation must be completed."
    )
    note = fields.Char(string="Notes")

    @api.constrains("min_hours_before")
    def _check_min_hours_before_non_negative(self):
        for rec in self:
            if rec.min_hours_before is not None and rec.min_hours_before < 0.0:
                raise ValidationError(_("Minimal hours before must be non-negative."))


# =============================================================================
# CONTRAINDICATIONS - Safety checklist per imaging type
# =============================================================================
class ClinicalImagingTypeContra(models.Model):
    _name = "clinical.imaging.type.contra"
    _description = "Clinical Imaging Type Contraindication"
    _order = "imaging_type_id, severity desc, name"
    _check_company_auto = True

    imaging_type_id = fields.Many2one(
        "clinical.imaging.type", string="Imaging Type",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="imaging_type_id.company_id", store=True, readonly=True
    )
    name = fields.Char(
        string="Contraindication", required=True,
        help="Short title (e.g., 'Pacemaker', 'Severe renal impairment', 'Pregnancy')."
    )
    severity = fields.Selection(
        [
            ("info", "Info / Caution"),
            ("relative", "Relative"),
            ("absolute", "Absolute"),
        ],
        string="Severity", default="relative",
        help="Severity level for this contraindication."
    )
    guidance = fields.Text(
        string="Guidance",
        help="Guidance on how to proceed (e.g., 'Use non-MR conditional device', 'Delay until postpartum')."
    )
    require_doctor_approval = fields.Boolean(
        string="Requires Doctor Approval", default=False,
        help="If checked, explicit doctor approval is required to proceed."
    )
    require_lab_check = fields.Boolean(
        string="Requires Lab Check", default=False,
        help="If checked, additional lab verification is required before proceeding."
    )


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import re

# =============================================================================
# Clinical Imaging Study
# =============================================================================
class ClinicalImagingStudy(models.Model):
    """
    Represents a DICOM Study (collection of one or more Series) acquired
    for an Imaging record (clinical.imaging).

    Design notes:
    - One Imaging record MAY have multiple Studies (multi-modality or repeat).
    - Each Study groups Series and Images, stores key DICOM attributes,
      and tracks PACS/RIS integration metadata.
    - This model does not duplicate the medical report; see clinical.imaging.result.
    """
    _name = "clinical.imaging.study"
    _description = "Clinical Imaging Study"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "study_datetime desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Study Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        help="Unique identifier generated from sequence at creation time.",
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive this study from regular views.",
    )

    # -------------------------------------------------------------------------
    # Core Links & Context
    # -------------------------------------------------------------------------
    imaging_id = fields.Many2one(
        "clinical.imaging",
        string="Imaging",
        required=True,
        ondelete="cascade",
        index=True,
        help="The parent Imaging record that this study belongs to.",
        tracking=True,
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="imaging_id.patient_id",
        store=True,
        readonly=True,
        help="Patient (readonly; propagated from Imaging).",
    )
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        related="imaging_id.appointment_id",
        store=True, readonly=True,
    )
    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     related="imaging_id.encounter_id",
    #     store=True, readonly=True,
    # )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="imaging_id.treatment_id",
        store=True, readonly=True,
    )
    procedure_session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Procedure Session",
        related="imaging_id.procedure_session_id",
        store=True, readonly=True,
    )

    # -------------------------------------------------------------------------
    # Study Descriptors (DICOM & Clinical)
    # -------------------------------------------------------------------------
    study_datetime = fields.Datetime(
        string="Study Datetime",
        default=fields.Datetime.now,
        help="Datetime the study acquisition was started (DICOM StudyDate/StudyTime).",
        tracking=True,
    )
    study_description = fields.Char(
        string="Study Description",
        help="DICOM Study Description or locally curated summary.",
        tracking=True,
    )
    body_part = fields.Char(
        string="Body Part",
        help="Body part examined (free text or as per DICOM BodyPartExamined).",
    )
    laterality = fields.Selection(
        [
            ("left", "Left"),
            ("right", "Right"),
            ("bilateral", "Bilateral"),
            ("unknown", "Unknown"),
        ],
        string="Laterality",
        default="unknown",
        help="Laterality (if applicable).",
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
        help="Primary modality for this study. Defaults from Imaging Type if available.",
        tracking=True,
    )
    referring_doctor_id = fields.Many2one(
        "hr.employee",
        string="Referring Doctor",
        domain=[("is_doctor", "=", True)],
        help="Referring physician.",
    )
    reading_radiologist_id = fields.Many2one(
        "hr.employee",
        string="Reading Radiologist",
        domain=[("is_doctor", "=", True)],
        help="Radiologist responsible for reading this study.",
        tracking=True,
    )

    # Contrast / Sedation actually used in this STUDY (not just 'type default')
    contrast_used = fields.Boolean(
        string="Contrast Used",
        help="Checked if contrast was administered during this study.",
    )
    contrast_agent_product_id = fields.Many2one(
        "product.product",
        string="Contrast Agent",
        domain=[("type", "in", ["consu"])],
        help="Actual contrast agent used.",
    )
    contrast_volume_ml = fields.Float(
        string="Contrast Volume (mL)",
        help="Volume of contrast administered in milliliters.",
    )
    sedation_used = fields.Boolean(
        string="Sedation Used",
        help="Checked if sedation/anxiolysis was used.",
    )
    sedation_agent_product_id = fields.Many2one(
        "product.product",
        string="Sedation Agent",
        domain=[("type", "in", ["consu"])],
        help="Sedation/anxiolysis agent used, if any.",
    )

    # -------------------------------------------------------------------------
    # Device & Acquisition
    # -------------------------------------------------------------------------
    device_id = fields.Many2one(
        "clinical.imaging.device",
        string="Imaging Device",
        help="Device used to acquire this study.",
        tracking=True,
    )
    manufacturer = fields.Char(
        string="Manufacturer",
        help="DICOM Manufacturer (from device) if known.",
    )
    station_name = fields.Char(
        string="Station Name",
        help="DICOM StationName (acquisition console).",
    )

    # -------------------------------------------------------------------------
    # DICOM Identifiers
    # -------------------------------------------------------------------------
    dicom_study_uid = fields.Char(
        string="DICOM Study Instance UID",
        copy=False,
        index=True,
        help="Globally unique DICOM Study Instance UID.",
    )
    dicom_accession_number = fields.Char(
        string="Accession Number",
        copy=False,
        index=True,
        help="Accession Number assigned by RIS/PACS for the study.",
    )

    # -------------------------------------------------------------------------
    # Series & Images (linked models defined in other files)
    # -------------------------------------------------------------------------
    series_ids = fields.One2many(
        "clinical.imaging.series",
        "study_id",
        string="Series",
        help="List of series belonging to this study.",
        copy=True,
    )
    series_count = fields.Integer(
        string="Series Count",
        compute="_compute_counts",
        store=False,
    )
    image_count = fields.Integer(
        string="Image Count",
        compute="_compute_counts",
        store=False,
        help="Total images across all series in this study.",
    )

    # -------------------------------------------------------------------------
    # Files & Attachments (optional)
    # -------------------------------------------------------------------------
    primary_preview = fields.Binary(
        string="Primary Preview",
        attachment=True,
        help="Representative image (e.g., thumbnail) for quick preview.",
    )
    dicom_bundle = fields.Binary(
        string="DICOM Export (ZIP)",
        attachment=True,
        help="Optional ZIP export of DICOM instances for this study.",
    )
    dicom_bundle_filename = fields.Char(string="DICOM Export File Name")
    attachment_count = fields.Integer(
        string="Attachment Count",
        compute="_compute_attachment_count",
        store=False,
    )

    # -------------------------------------------------------------------------
    # PACS / Viewer Integration
    # -------------------------------------------------------------------------
    pacs_status = fields.Selection(
        [
            ("none", "None"),
            ("to_send", "Pending Send"),
            ("sent", "Sent"),
            ("received", "Received"),
            ("error", "Error"),
        ],
        string="PACS Status",
        default="none",
        help="Status for PACS/RIS integration workflows.",
        tracking=True,
    )
    pacs_viewer_url = fields.Char(
        string="Viewer URL",
        help="Link to an external viewer (PACS/VNA/Web viewer) for this study.",
    )
    pacs_message_last = fields.Text(
        string="Last PACS Message",
        help="Last message or error returned by PACS/RIS integration.",
    )

    # -------------------------------------------------------------------------
    # Notes & Audit
    # -------------------------------------------------------------------------
    notes = fields.Text(
        string="Internal Notes",
        help="Internal notes about this study.",
    )

    # -------------------------------------------------------------------------
    # State Machine
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("acquired", "Acquired"),
            ("verified", "Verified"),
            ("archived", "Archived"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
        help="Lifecycle status of the study.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_counts(self):
        Image = self.env["clinical.imaging.image"]
        for rec in self:
            rec.series_count = len(rec.series_ids)
            # Count images by study via series
            if rec.series_ids:
                rec.image_count = Image.search_count([("series_id", "in", rec.series_ids.ids)])
            else:
                rec.image_count = 0

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("imaging_id")
    def _onchange_imaging_id_defaults(self):
        for rec in self:
            if not rec.imaging_id:
                continue
            # Default modality from imaging type
            if not rec.modality and rec.imaging_id.imaging_type_id and rec.imaging_id.imaging_type_id.modality:
                rec.modality = rec.imaging_id.imaging_type_id.modality
            # Default device/manufacturer/station from imaging device
            if rec.imaging_id.device_id and not rec.device_id:
                rec.device_id = rec.imaging_id.device_id.id
                if rec.imaging_id.device_id.manufacturer:
                    rec.manufacturer = rec.imaging_id.device_id.manufacturer
                if rec.imaging_id.device_id.location and not rec.station_name:
                    rec.station_name = rec.imaging_id.device_id.location
            # Default doctors
            if rec.imaging_id.doctor_id and not rec.referring_doctor_id:
                rec.referring_doctor_id = rec.imaging_id.doctor_id.id
            # reading radiologist may be different; leave blank unless same
            # Copy accession from imaging if present
            if rec.imaging_id.dicom_accession_number and not rec.dicom_accession_number:
                rec.dicom_accession_number = rec.imaging_id.dicom_accession_number
            # Copy study UID to imaging if imaging lacks it
            if rec.dicom_study_uid and not rec.imaging_id.dicom_study_uid:
                rec.imaging_id.dicom_study_uid = rec.dicom_study_uid

    @api.onchange("device_id")
    def _onchange_device_id(self):
        for rec in self:
            if rec.device_id and rec.device_id.manufacturer and not rec.manufacturer:
                rec.manufacturer = rec.device_id.manufacturer
            # If device modality differs, warn
            if rec.device_id and rec.modality and rec.device_id.modality and rec.device_id.modality != rec.modality:
                return {
                    "warning": {
                        "title": _("Modality Mismatch"),
                        "message": _(
                            "Device modality (%s) differs from Study modality (%s). "
                            "Please review your selection."
                        ) % (rec.device_id.modality, rec.modality)
                    }
                }

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("dicom_study_uid")
    def _check_dicom_uid_format(self):
        """
        Soft validation that Study Instance UID looks like a DICOM UID:
        digits and dots, starts with digit, no consecutive dots.
        """
        uid_re = re.compile(r"^[0-9](?:[0-9]*\.?)*[0-9]?$")
        for rec in self:
            if rec.dicom_study_uid:
                uid = rec.dicom_study_uid.strip()
                if ".." in uid or not uid_re.match(uid):
                    raise ValidationError(_("DICOM Study Instance UID appears invalid."))

    @api.constrains("reading_radiologist_id", "state")
    def _check_verify_requirements(self):
        for rec in self:
            if rec.state in ("verified",) and not rec.reading_radiologist_id:
                raise ValidationError(_("Reading Radiologist is required when Study is Verified."))

    @api.constrains("modality", "device_id")
    def _check_device_modality_match(self):
        for rec in self:
            if rec.device_id and rec.modality and rec.device_id.modality and rec.device_id.modality != rec.modality:
                raise ValidationError(_("Device modality must match Study modality."))

    # Unique constraints
    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Study Number must be unique per company.',
    )
    _study_uid_company_unique = models.Constraint(
        'unique(dicom_study_uid, company_id)',
        'DICOM Study UID must be unique per company.',
    )

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging.study") or _("New")
        records = super().create(vals_list)
        # Post-create: propagate first study UID to Imaging (if empty)
        for rec in records:
            if rec.dicom_study_uid and rec.imaging_id and not rec.imaging_id.dicom_study_uid:
                rec.imaging_id.sudo().write({"dicom_study_uid": rec.dicom_study_uid})
        return records

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("dicom_study_uid", False)
        default.setdefault("pacs_status", "none")
        default.setdefault("pacs_viewer_url", False)
        return super().copy(default)

    def unlink(self):
        for rec in self:
            if rec.state == "verified":
                raise UserError(_("You cannot delete a Verified study. Consider Archiving instead."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # ACTIONS / WORKFLOW
    # -------------------------------------------------------------------------
    def action_mark_acquired(self):
        for rec in self:
            if rec.state not in ("draft",):
                raise UserError(_("Only Draft studies can be marked as Acquired."))
            if not rec.study_datetime:
                rec.study_datetime = fields.Datetime.now()
            rec.state = "acquired"
            rec.message_post(body=_("Study marked as Acquired."))

    def action_verify(self):
        for rec in self:
            if rec.state not in ("acquired",):
                raise UserError(_("Only Acquired studies can be Verified."))
            if not rec.reading_radiologist_id:
                raise UserError(_("Please set Reading Radiologist before verifying."))
            rec.state = "verified"
            rec.message_post(body=_("Study verified by %s.") % (rec.reading_radiologist_id.name or _("Radiologist")))
            # Optional: notify Imaging that a study is verified
            if rec.imaging_id and rec.imaging_id.state in ("completed",):
                # nothing to change on imaging; leave to result workflow
                pass

    def action_archive(self):
        for rec in self:
            if rec.state not in ("verified", "cancelled"):
                raise UserError(_("Only Verified or Cancelled studies can be archived."))
            rec.state = "archived"
            rec.active = False
            rec.message_post(body=_("Study archived."))

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state == "verified":
                raise UserError(_("Verified studies cannot be cancelled. Archive instead."))
            rec.state = "cancelled"
            if reason:
                rec.message_post(body=_("Study cancelled. Reason: %s") % reason)
            else:
                rec.message_post(body=_("Study cancelled."))

    # PACS / Viewer helpers
    def action_send_to_pacs(self):
        """
        Placeholder for integration hooks (connector module).
        Change pacs_status and store message.
        """
        for rec in self:
            rec.pacs_status = "to_send"
            rec.pacs_message_last = _("Queued for PACS transmission.")
            rec.message_post(body=_("Study queued for PACS transmission."))

    def action_mark_sent(self, message=None):
        for rec in self:
            rec.pacs_status = "sent"
            if message:
                rec.pacs_message_last = message
            rec.message_post(body=_("Study marked as Sent to PACS."))

    def action_mark_received(self, viewer_url=None, message=None):
        for rec in self:
            rec.pacs_status = "received"
            if viewer_url:
                rec.pacs_viewer_url = viewer_url
            if message:
                rec.pacs_message_last = message
            rec.message_post(body=_("Study acknowledged by PACS."))

    def action_mark_pacs_error(self, message):
        for rec in self:
            rec.pacs_status = "error"
            rec.pacs_message_last = message or _("Unknown PACS error.")
            rec.message_post(body=_("PACS error: %s") % (message or ""))

    # Navigation
    def action_open_series(self):
        self.ensure_one()
        return {
            "name": _("Series"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.series",
            "view_mode": "list,form,kanban",
            "domain": [("study_id", "=", self.id)],
            "target": "current",
            "context": {"default_study_id": self.id},
        }

    def action_open_images(self):
        self.ensure_one()
        return {
            "name": _("Images"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.image",
            "view_mode": "list,form,kanban",
            "domain": [("series_id.study_id", "=", self.id)],
            "target": "current",
        }

    def action_view_attachments(self):
        self.ensure_one()
        return {
            "name": _("Attachments"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }


# =============================================================================
# Study Notes (lightweight threaded items per Study)
# =============================================================================
class ClinicalImagingStudyNote(models.Model):
    _name = "clinical.imaging.study.note"
    _description = "Clinical Imaging Study Note"
    _order = "create_date desc, id desc"
    _check_company_auto = True

    study_id = fields.Many2one(
        "clinical.imaging.study",
        string="Study",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="study_id.company_id",
        store=True,
        readonly=True,
    )
    author_id = fields.Many2one(
        "res.users",
        string="Author",
        default=lambda self: self.env.user,
        required=True,
    )
    note = fields.Text(
        string="Note",
        required=True,
        help="Plain text note about this study (non-diagnostic).",
    )
    tag = fields.Selection(
        [
            ("general", "General"),
            ("safety", "Safety"),
            ("prep", "Preparation"),
            ("tech", "Technical"),
        ],
        string="Tag",
        default="general",
        help="Category tag for this note.",
    )

class ClinicalImagingDeviceStudy(models.Model):
    _inherit = "clinical.imaging.device"
        
    imaging_count = fields.Integer(
        string="Imaging Count", compute="_compute_imaging_stats", store=False,
        help="Number of imaging records acquired using this device."
    )
    
    def _compute_imaging_stats(self):
        Imaging = self.env["clinical.imaging"]
        for rec in self:
            rec.imaging_count = Imaging.search_count([("device_id", "=", rec.id)])

    def _compute_imaging_stats(self):
        Imaging = self.env["clinical.imaging"]
        for rec in self:
            rec.imaging_count = Imaging.search_count([("device_id", "=", rec.id)])


    def action_open_imaging(self):
        self.ensure_one()
        return {
            "name": _("Imaging Records"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging",
            "view_mode": "list,form,kanban,calendar",
            "domain": [("device_id", "=", self.id)],
            "target": "current",
            "context": {"search_default_groupby_patient": 1},
        }


# =============================================================================
# Soft links on Imaging to navigate to Studies
# =============================================================================
class ClinicalImaging(models.Model):
    _inherit = "clinical.imaging"

    study_ids = fields.One2many(
        "clinical.imaging.study",
        "imaging_id",
        string="Studies",
        help="DICOM studies acquired for this imaging.",
    )
    study_count = fields.Integer(
        string="Study Count",
        compute="_compute_study_count",
        store=False,
    )

    device_downtime_count = fields.Integer(
        string="Downtimes", compute="_compute_device_log_counts", store=False
    )
    device_calibration_count = fields.Integer(
        string="Calibrations/QC", compute="_compute_device_log_counts", store=False
    )

    def _compute_device_log_counts(self):
        Downtime = self.env["clinical.imaging.device.downtime"]
        Calib = self.env["clinical.imaging.device.calibration"]
        for rec in self:
            if rec.device_id:
                rec.device_downtime_count = Downtime.search_count([("device_id", "=", rec.device_id.id)])
                rec.device_calibration_count = Calib.search_count([("device_id", "=", rec.device_id.id)])
            else:
                rec.device_downtime_count = 0
                rec.device_calibration_count = 0

    def action_open_device_downtime(self):
        self.ensure_one()
        if not self.device_id:
            raise UserError(_("No device is linked to this imaging."))
        return {
            "name": _("Downtime Logs"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.device.downtime",
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.device_id.id)],
            "target": "current",
        }

    def action_open_device_calibration(self):
        self.ensure_one()
        if not self.device_id:
            raise UserError(_("No device is linked to this imaging."))
        return {
            "name": _("Calibration / QC Logs"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.device.calibration",
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.device_id.id)],
            "target": "current",
        }

    def _compute_study_count(self):
        for rec in self:
            rec.study_count = len(rec.study_ids)

    def action_open_studies(self):
        self.ensure_one()
        return {
            "name": _("Studies"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.study",
            "view_mode": "list,form,kanban",
            "domain": [("imaging_id", "=", self.id)],
            "target": "current",
            "context": {"default_imaging_id": self.id},
        }

    def action_create_study(self):
        """
        Convenience action to create a blank Study from the Imaging form.
        """
        self.ensure_one()
        study = self.env["clinical.imaging.study"].create({
            "imaging_id": self.id,
            "company_id": self.company_id.id,
            "modality": (self.imaging_type_id and self.imaging_type_id.modality) or False,
            "device_id": self.device_id.id if self.device_id else False,
            "dicom_accession_number": self.dicom_accession_number or False,
        })
        return {
            "name": _("Study"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.study",
            "view_mode": "form",
            "res_id": study.id,
            "target": "current",
        }

# \\\ PINDAHAN DARI File: clinical_imaging_device.py ///
# /// Digabungkan DIATAS \\\
# class ClinicalImaging(models.Model):
#     _inherit = "clinical.imaging"

    # device_downtime_count = fields.Integer(
    #     string="Downtimes", compute="_compute_device_log_counts", store=False
    # )
    # device_calibration_count = fields.Integer(
    #     string="Calibrations/QC", compute="_compute_device_log_counts", store=False
    # )

    # def _compute_device_log_counts(self):
    #     Downtime = self.env["clinical.imaging.device.downtime"]
    #     Calib = self.env["clinical.imaging.device.calibration"]
    #     for rec in self:
    #         if rec.device_id:
    #             rec.device_downtime_count = Downtime.search_count([("device_id", "=", rec.device_id.id)])
    #             rec.device_calibration_count = Calib.search_count([("device_id", "=", rec.device_id.id)])
    #         else:
    #             rec.device_downtime_count = 0
    #             rec.device_calibration_count = 0

    # def action_open_device_downtime(self):
    #     self.ensure_one()
    #     if not self.device_id:
    #         raise UserError(_("No device is linked to this imaging."))
    #     return {
    #         "name": _("Downtime Logs"),
    #         "type": "ir.actions.act_window",
    #         "res_model": "clinical.imaging.device.downtime",
    #         "view_mode": "list,form",
    #         "domain": [("device_id", "=", self.device_id.id)],
    #         "target": "current",
    #     }

    # def action_open_device_calibration(self):
    #     self.ensure_one()
    #     if not self.device_id:
    #         raise UserError(_("No device is linked to this imaging."))
    #     return {
    #         "name": _("Calibration / QC Logs"),
    #         "type": "ir.actions.act_window",
    #         "res_model": "clinical.imaging.device.calibration",
    #         "view_mode": "list,form",
    #         "domain": [("device_id", "=", self.device_id.id)],
    #         "target": "current",
    #     }


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import re


# =============================================================================
# Clinical Imaging Series
# =============================================================================
class ClinicalImagingSeries(models.Model):
    """
    Represents a DICOM Series inside a Study.
    A Series groups a coherent acquisition set (e.g., 'AX T2', 'Arterial Phase').
    """
    _name = "clinical.imaging.series"
    _description = "Clinical Imaging Series"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "series_datetime desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Series Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
        tracking=True,
        help="Unique identifier generated from sequence at creation time."
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive the series from regular views.",
    )

    # -------------------------------------------------------------------------
    # Core Links & Context
    # -------------------------------------------------------------------------
    study_id = fields.Many2one(
        "clinical.imaging.study",
        string="Study",
        required=True,
        ondelete="cascade",
        index=True,
        help="Parent Study that this series belongs to.",
        tracking=True,
    )
    imaging_id = fields.Many2one(
        "clinical.imaging",
        string="Imaging",
        related="study_id.imaging_id",
        store=True,
        readonly=True,
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="study_id.patient_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Series Descriptors (DICOM & Clinical)
    # -------------------------------------------------------------------------
    series_datetime = fields.Datetime(
        string="Series Datetime",
        default=fields.Datetime.now,
        help="Datetime when this series acquisition started (DICOM SeriesTime).",
        tracking=True,
    )
    series_description = fields.Char(
        string="Series Description",
        help="DICOM Series Description or locally curated title (e.g., 'AX T2 FS').",
        tracking=True,
    )
    sequence_name = fields.Char(
        string="Sequence Name",
        help="Scanner sequence name (e.g., 'SE_T2', 'GRE', vendor-specific).",
    )
    body_part = fields.Char(
        string="Body Part",
        help="Anatomical body part examined (e.g., 'Chest', 'L-Spine').",
    )
    laterality = fields.Selection(
        [
            ("left", "Left"),
            ("right", "Right"),
            ("bilateral", "Bilateral"),
            ("midline", "Midline"),
            ("unknown", "Unknown"),
        ],
        string="Laterality",
        default="unknown",
        help="Laterality for this series, if applicable.",
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
        help="Series modality. Defaults from Study modality.",
        tracking=True,
    )
    plane = fields.Selection(
        [
            ("axial", "Axial"),
            ("coronal", "Coronal"),
            ("sagittal", "Sagittal"),
            ("oblique", "Oblique"),
            ("3d", "3D/Volume"),
            ("unknown", "Unknown"),
        ],
        string="Imaging Plane",
        default="unknown",
        help="Primary acquisition plane for the series.",
    )
    patient_position = fields.Selection(
        [
            ("HFS", "Head First Supine"),
            ("HFP", "Head First Prone"),
            ("HFDR", "Head First Decubitus Right"),
            ("HFDL", "Head First Decubitus Left"),
            ("FFS", "Feet First Supine"),
            ("FFP", "Feet First Prone"),
            ("FFDR", "Feet First Decubitus Right"),
            ("FFDL", "Feet First Decubitus Left"),
            ("SITTING", "Sitting"),
            ("STANDING", "Standing"),
            ("UNKNOWN", "Unknown"),
        ],
        string="Patient Position",
        help="Patient position during acquisition (if available).",
    )

    # Contrast phase & scheduling context
    contrast_phase = fields.Selection(
        [
            ("none", "None"),
            ("arterial", "Arterial"),
            ("venous", "Venous/Portal"),
            ("delayed", "Delayed"),
            ("precontrast", "Pre-Contrast"),
            ("postcontrast", "Post-Contrast"),
            ("dynamic", "Dynamic / Perfusion"),
            ("other", "Other"),
        ],
        string="Contrast Phase",
        default="none",
        help="Contrast phase captured by this series (if applicable).",
    )
    protocol_step_id = fields.Many2one(
        "clinical.imaging.protocol",
        string="Protocol Step",
        help="Protocol step reference linked to this series (if tracked).",
    )

    # -------------------------------------------------------------------------
    # Device & Acquisition Parameters
    # -------------------------------------------------------------------------
    device_id = fields.Many2one(
        "clinical.imaging.device",
        string="Imaging Device",
        help="Device used to acquire this series.",
        tracking=True,
    )
    manufacturer = fields.Char(string="Manufacturer", help="Device manufacturer (from DICOM).")
    station_name = fields.Char(string="Station Name", help="Acquisition console name (DICOM).")

    # Generic geometry & sampling
    slice_thickness_mm = fields.Float(
        string="Slice Thickness (mm)",
        help="Nominal slice thickness in millimeters."
    )
    spacing_mm = fields.Float(
        string="Spacing (mm)",
        help="Spacing between slices or pixels (average), in millimeters."
    )
    matrix = fields.Char(
        string="Matrix",
        help="Acquisition matrix (e.g., '512x512', '256x320')."
    )
    fov_mm = fields.Char(
        string="Field of View (mm)",
        help="Field of View (e.g., '360x360')."
    )

    # Modality-specific knobs (optional)
    # CT / XR dose & exposure
    kvp = fields.Float(string="kVp", help="Peak kilovoltage.")
    ma = fields.Float(string="mA", help="Tube current (mA).")
    exposure_time_ms = fields.Float(string="Exposure Time (ms)")
    ctdi_vol_mgy = fields.Float(string="CTDIvol (mGy)")
    dlp_mgy_cm = fields.Float(string="DLP (mGy·cm)")
    dap_gy_cm2 = fields.Float(string="DAP (Gy·cm²)")
    fluoro_time_min = fields.Float(string="Fluoroscopy Time (min)")

    # MRI
    tr_ms = fields.Float(string="TR (ms)")
    te_ms = fields.Float(string="TE (ms)")
    ti_ms = fields.Float(string="TI (ms)")
    flip_angle_deg = fields.Float(string="Flip Angle (°)")
    bandwidth_hz = fields.Float(string="Bandwidth (Hz)")
    field_strength_t = fields.Float(string="Field Strength (T)")

    # Ultrasound
    probe = fields.Char(string="Probe", help="Transducer/probe type (e.g., 'C5-2').")
    frequency_mhz = fields.Float(string="Frequency (MHz)")

    # Nuclear Medicine (optional)
    radiotracer = fields.Char(string="Radiotracer")
    tracer_dose_mbq = fields.Float(string="Tracer Dose (MBq)")

    # -------------------------------------------------------------------------
    # DICOM Identifiers
    # -------------------------------------------------------------------------
    dicom_series_uid = fields.Char(
        string="DICOM Series Instance UID",
        copy=False,
        index=True,
        help="Globally unique DICOM Series Instance UID."
    )
    series_number = fields.Integer(
        string="Series Number (DICOM)",
        help="DICOM SeriesNumber integer."
    )
    instance_count = fields.Integer(
        string="Instance Count",
        compute="_compute_counts",
        store=False,
        help="Number of instances/images in this series."
    )

    # -------------------------------------------------------------------------
    # Images (child model defined in clinical_imaging_image.py)
    # -------------------------------------------------------------------------
    image_ids = fields.One2many(
        "clinical.imaging.image",
        "series_id",
        string="Images",
        help="Image instances belonging to this series.",
        copy=True,
    )

    # -------------------------------------------------------------------------
    # Files & Attachments
    # -------------------------------------------------------------------------
    key_image = fields.Binary(
        string="Key Image",
        attachment=True,
        help="Representative image/thumbnail for the series."
    )
    key_image_filename = fields.Char(string="Key Image Name")
    attachment_count = fields.Integer(
        string="Attachment Count",
        compute="_compute_attachment_count",
        store=False,
    )

    # -------------------------------------------------------------------------
    # PACS / Viewer Integration
    # -------------------------------------------------------------------------
    pacs_status = fields.Selection(
        [
            ("none", "None"),
            ("to_send", "Pending Send"),
            ("sent", "Sent"),
            ("received", "Received"),
            ("error", "Error"),
        ],
        string="PACS Status",
        default="none",
        help="Status of PACS/RIS transfer for this series.",
        tracking=True,
    )
    pacs_viewer_url = fields.Char(
        string="Viewer URL",
        help="Link to an external viewer at Series level (optional)."
    )
    pacs_message_last = fields.Text(
        string="Last PACS Message",
        help="Last integration message or error for this series."
    )

    # -------------------------------------------------------------------------
    # Quality & Audit
    # -------------------------------------------------------------------------
    quality_score = fields.Selection(
        [
            ("0", "0 - Uninterpretable"),
            ("1", "1 - Poor"),
            ("2", "2 - Fair"),
            ("3", "3 - Good"),
            ("4", "4 - Very Good"),
            ("5", "5 - Excellent"),
        ],
        string="Image Quality",
        default="3",
        tracking=True,
        help="Subjective image quality score for QA."
    )
    quality_notes = fields.Text(
        string="Quality Notes",
        help="Artifacts, motion, positioning, or other quality observations."
    )
    notes = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # State Machine
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("acquired", "Acquired"),
            ("processed", "Processed"),
            ("archived", "Archived"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        index=True,
        tracking=True,
        help="Lifecycle status of the series.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_counts(self):
        Image = self.env["clinical.imaging.image"]
        for rec in self:
            rec.instance_count = Image.search_count([("series_id", "=", rec.id)])

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("study_id")
    def _onchange_study_defaults(self):
        for rec in self:
            if not rec.study_id:
                continue
            # Default modality and device from Study
            if not rec.modality and rec.study_id.modality:
                rec.modality = rec.study_id.modality
            if rec.study_id.device_id and not rec.device_id:
                rec.device_id = rec.study_id.device_id.id
                if rec.study_id.device_id.manufacturer and not rec.manufacturer:
                    rec.manufacturer = rec.study_id.device_id.manufacturer
            # Default contrast phase None if study not using contrast
            # (left as-is; some series in non-contrast studies may still be marked)

    @api.onchange("device_id")
    def _onchange_device(self):
        for rec in self:
            if rec.device_id and not rec.manufacturer:
                rec.manufacturer = rec.device_id.manufacturer
            # Soft warning if modality mismatch
            if rec.device_id and rec.modality and rec.device_id.modality and rec.device_id.modality != rec.modality:
                return {
                    "warning": {
                        "title": _("Modality Mismatch"),
                        "message": _(
                            "Device modality (%s) differs from Series modality (%s). "
                            "Please review your selection."
                        ) % (rec.device_id.modality, rec.modality)
                    }
                }

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("dicom_series_uid")
    def _check_dicom_series_uid_format(self):
        """
        Basic DICOM UID shape: digits and dots, starts with a digit, no '..'
        """
        uid_re = re.compile(r"^[0-9](?:[0-9]*\.?)*[0-9]?$")
        for rec in self:
            if rec.dicom_series_uid:
                uid = rec.dicom_series_uid.strip()
                if ".." in uid or not uid_re.match(uid):
                    raise ValidationError(_("DICOM Series Instance UID appears invalid."))

    @api.constrains("modality", "device_id")
    def _check_device_modality(self):
        for rec in self:
            if rec.device_id and rec.modality and rec.device_id.modality and rec.device_id.modality != rec.modality:
                raise ValidationError(_("Device modality must match Series modality."))

    @api.constrains("ctdi_vol_mgy", "dlp_mgy_cm", "dap_gy_cm2", "fluoro_time_min",
                    "kvp", "ma", "exposure_time_ms", "tr_ms", "te_ms", "ti_ms",
                    "flip_angle_deg", "bandwidth_hz", "field_strength_t",
                    "slice_thickness_mm", "spacing_mm", "frequency_mhz", "tracer_dose_mbq")
    def _check_non_negative_params(self):
        for rec in self:
            for field_name in [
                "ctdi_vol_mgy", "dlp_mgy_cm", "dap_gy_cm2", "fluoro_time_min",
                "kvp", "ma", "exposure_time_ms", "tr_ms", "te_ms", "ti_ms",
                "flip_angle_deg", "bandwidth_hz", "field_strength_t",
                "slice_thickness_mm", "spacing_mm", "frequency_mhz", "tracer_dose_mbq"
            ]:
                val = getattr(rec, field_name)
                if val is not None and val < 0:
                    raise ValidationError(_("%s cannot be negative.") % field_name)

    @api.constrains("quality_score")
    def _check_quality_score(self):
        for rec in self:
            if rec.quality_score and rec.quality_score not in ("0", "1", "2", "3", "4", "5"):
                raise ValidationError(_("Invalid Image Quality score."))

    # Unique constraints
    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Series Number must be unique per company.',
    )
    _series_uid_company_unique = models.Constraint(
        'unique(dicom_series_uid, company_id)',
        'DICOM Series UID must be unique per company.',
    )

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging.series") or _("New")
            # default modality from study if missing
            if not vals.get("modality") and vals.get("study_id"):
                study = self.env["clinical.imaging.study"].browse(vals["study_id"])
                if study and study.modality:
                    vals["modality"] = study.modality
        records = super().create(vals_list)
        return records

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("dicom_series_uid", False)
        default.setdefault("pacs_status", "none")
        default.setdefault("pacs_viewer_url", False)
        return super().copy(default)

    def unlink(self):
        for rec in self:
            if rec.state in ("processed",):
                raise UserError(_("Processed series cannot be deleted. Archive instead."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # ACTIONS / WORKFLOW
    # -------------------------------------------------------------------------
    def action_mark_acquired(self):
        for rec in self:
            if rec.state not in ("draft",):
                raise UserError(_("Only Draft series can be marked as Acquired."))
            if not rec.series_datetime:
                rec.series_datetime = fields.Datetime.now()
            rec.state = "acquired"
            rec.message_post(body=_("Series marked as Acquired."))

    def action_mark_processed(self):
        for rec in self:
            if rec.state not in ("acquired",):
                raise UserError(_("Only Acquired series can be marked as Processed."))
            rec.state = "processed"
            rec.message_post(body=_("Series marked as Processed."))

    def action_archive(self):
        for rec in self:
            if rec.state not in ("processed", "cancelled"):
                raise UserError(_("Only Processed or Cancelled series can be archived."))
            rec.active = False
            rec.state = "archived"
            rec.message_post(body=_("Series archived."))

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state == "processed":
                raise UserError(_("Processed series cannot be cancelled. Archive instead."))
            rec.state = "cancelled"
            if reason:
                rec.message_post(body=_("Series cancelled. Reason: %s") % reason)
            else:
                rec.message_post(body=_("Series cancelled."))

    # PACS helpers
    def action_send_to_pacs(self):
        for rec in self:
            rec.pacs_status = "to_send"
            rec.pacs_message_last = _("Queued for PACS transmission.")
            rec.message_post(body=_("Series queued for PACS transmission."))

    def action_mark_sent(self, message=None):
        for rec in self:
            rec.pacs_status = "sent"
            if message:
                rec.pacs_message_last = message
            rec.message_post(body=_("Series marked as Sent to PACS."))

    def action_mark_received(self, viewer_url=None, message=None):
        for rec in self:
            rec.pacs_status = "received"
            if viewer_url:
                rec.pacs_viewer_url = viewer_url
            if message:
                rec.pacs_message_last = message
            rec.message_post(body=_("Series acknowledged by PACS."))

    def action_mark_pacs_error(self, message):
        for rec in self:
            rec.pacs_status = "error"
            rec.pacs_message_last = message or _("Unknown PACS error.")
            rec.message_post(body=_("PACS error on Series: %s") % (message or ""))

    # Navigation
    def action_open_images(self):
        self.ensure_one()
        return {
            "name": _("Images"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.image",
            "view_mode": "list,form,kanban",
            "domain": [("series_id", "=", self.id)],
            "target": "current",
            "context": {"default_series_id": self.id},
        }

    def action_view_attachments(self):
        self.ensure_one()
        return {
            "name": _("Attachments"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    # Display
    def name_get(self):
        res = []
        for rec in self:
            parts = [rec.name]
            if rec.series_description:
                parts.append(rec.series_description)
            if rec.study_id:
                parts.append(f"({rec.study_id.name})")
            res.append((rec.id, " - ".join([p for p in parts if p])))
        return res


# =============================================================================
# Generic key-value parameters attached to a Series (optional)
# =============================================================================
class ClinicalImagingSeriesParam(models.Model):
    _name = "clinical.imaging.series.param"
    _description = "Imaging Series Parameter"
    _order = "series_id, sequence, id"
    _check_company_auto = True

    series_id = fields.Many2one(
        "clinical.imaging.series",
        string="Series",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="series_id.company_id",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)
    key = fields.Char(string="Key", required=True, help="Parameter key (e.g., 'EchoTrainLength').")
    value = fields.Char(string="Value", help="Parameter value (string).")
    unit = fields.Char(string="Unit", help="Optional unit (e.g., 'ms', 'mm').")
    note = fields.Char(string="Notes")


# =============================================================================
# Per-Series Dose / Exposure (optional, complementary to Result-level dose)
# =============================================================================
class ClinicalImagingSeriesDose(models.Model):
    _name = "clinical.imaging.series.dose"
    _description = "Imaging Series Dose/Exposure"
    _order = "series_id, sequence, id"
    _check_company_auto = True

    series_id = fields.Many2one(
        "clinical.imaging.series",
        string="Series",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="series_id.company_id",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)
    metric = fields.Selection(
        [
            ("ctdi_vol", "CTDIvol (mGy)"),
            ("dlp", "DLP (mGy·cm)"),
            ("dap", "Dose Area Product (Gy·cm²)"),
            ("fluoro_time", "Fluoroscopy Time (min)"),
            ("exposure", "Exposure (mAs/kVp)"),
            ("other", "Other"),
        ],
        string="Metric",
        required=True,
        help="Dose/exposure metric type.",
    )
    value = fields.Float(string="Value", required=True)
    unit = fields.Char(string="Unit", help="Unit override if 'Other' metric or custom unit.")
    note = fields.Char(string="Notes")

    @api.constrains("value")
    def _check_value_non_negative(self):
        for rec in self:
            if rec.value is not None and rec.value < 0.0:
                raise ValidationError(_("Dose/Exposure value must be non-negative."))


# =============================================================================
# Soft links on Study to navigate/open Series
# =============================================================================
class ClinicalImagingStudy(models.Model):
    _inherit = "clinical.imaging.study"

    def action_create_series(self):
        """
        Convenience action to create a blank Series from the Study form.
        """
        self.ensure_one()
        series = self.env["clinical.imaging.series"].create({
            "study_id": self.id,
            "company_id": self.company_id.id,
            "modality": self.modality or False,
            "device_id": self.device_id.id if getattr(self, "device_id", False) else False,
        })
        return {
            "name": _("Series"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.series",
            "view_mode": "form",
            "res_id": series.id,
            "target": "current",
        }


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# Clinical Imaging Result (header)
# =============================================================================
class ClinicalImagingResult(models.Model):
    """
    Structured result/report for a clinical imaging record.

    Key goals:
    - Support draft → preliminary → final (signed) → amended lifecycles.
    - Keep strong links to the core imaging record and patient context.
    - Allow structured content (technique, findings, impression, recommendations).
    - Store quality/dose info and reference key images.
    - Integrate with Portal, Activities, Billing (indirect via imaging), and QWeb reports.
    """
    _name = "clinical.imaging.result"
    _description = "Clinical Imaging Result"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "create_date desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Result Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        help="Unique identifier generated from sequence when created.",
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, the result is archived from regular views.",
    )

    # -------------------------------------------------------------------------
    # Core Links
    # -------------------------------------------------------------------------
    imaging_id = fields.Many2one(
        "clinical.imaging",
        string="Imaging",
        required=True,
        ondelete="cascade",
        index=True,
        help="The imaging record that this result/report belongs to.",
        tracking=True,
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="imaging_id.patient_id",
        store=True,
        readonly=True,
        help="Patient (readonly, propagated from the imaging record).",
    )
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        related="imaging_id.appointment_id",
        store=True,
        readonly=True,
        help="Appointment context (readonly, from imaging).",
    )
    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     related="imaging_id.encounter_id",
    #     store=True,
    #     readonly=True,
    #     help="Encounter context (readonly, from imaging).",
    # )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="imaging_id.treatment_id",
        store=True,
        readonly=True,
        help="Treatment plan context (readonly, from imaging).",
    )
    procedure_session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Procedure Session",
        related="imaging_id.procedure_session_id",
        store=True,
        readonly=True,
        help="Procedure session context (readonly, from imaging).",
    )
    prescription_order_id = fields.Many2one(
        "clinic.prescription.order",
        string="Prescription/Order (eMAR)",
        related="imaging_id.prescription_order_id",
        store=True,
        readonly=True,
        help="Prescription/order context (readonly, from imaging).",
    )
    consent_id = fields.Many2one(
        "clinic.consent.form",
        string="Consent",
        related="imaging_id.consent_id",
        store=True,
        readonly=True,
        help="Consent record (readonly, from imaging).",
    )

    # -------------------------------------------------------------------------
    # Authors & Sign-off
    # -------------------------------------------------------------------------
    author_doctor_id = fields.Many2one(
        "hr.employee",
        string="Authoring Doctor",
        domain=[("is_doctor", "=", True)],
        help="Doctor (e.g., radiologist) who authored this result.",
        tracking=True,
    )
    co_signer_id = fields.Many2one(
        "hr.employee",
        string="Co-signer",
        domain=[("is_doctor", "=", True)],
        help="Optional co-signer doctor if double sign-off is required.",
        tracking=True,
    )
    signed_datetime = fields.Datetime(
        string="Signed At",
        help="Datetime when the result was finalized and signed.",
        tracking=True,
    )
    amended_datetime = fields.Datetime(
        string="Amended At",
        help="Datetime when an addendum/amendment was recorded.",
        tracking=True,
    )
    version = fields.Integer(
        string="Version",
        default=1,
        help="Monotonic version number: 1 for first final, increments on amendments.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Result Lifecycle
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("preliminary", "Preliminary"),
            ("final", "Final (Signed)"),
            ("amended", "Amended"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
        help="Lifecycle status of the imaging result.",
    )
    result_datetime = fields.Datetime(
        string="Result Datetime",
        default=fields.Datetime.now,
        help="Datetime when the result content was completed.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Structured Content
    # -------------------------------------------------------------------------
    technique = fields.Text(
        string="Technique / Protocol",
        help="Acquisition technique and protocol details.",
        tracking=True,
    )
    comparison = fields.Text(
        string="Comparison",
        help="Comparison to prior studies (dates, modalities, findings).",
        tracking=True,
    )
    findings = fields.Text(
        string="Findings",
        help="Detailed findings and observations.",
        tracking=True,
    )
    impression = fields.Text(
        string="Impression",
        help="Concise diagnostic impression / conclusion.",
        tracking=True,
    )
    recommendations = fields.Text(
        string="Recommendations",
        help="Clinical recommendations or next steps.",
        tracking=True,
    )

    # External structured links (defined in other files)
    finding_ids = fields.Many2many(
        "clinical.imaging.finding",
        "clinical_imaging_result_finding_rel",
        "result_id",
        "finding_id",
        string="Structured Findings",
        help="Linked structured findings (lesions, measurements, categorizations).",
    )
    finding_count = fields.Integer(
        string="Finding Count",
        compute="_compute_finding_count",
        store=False,
    )

    # Key Images (optional; defined in clinical_imaging_image.py)
    key_image_ids = fields.Many2many(
        "clinical.imaging.image",
        "clinical_imaging_result_key_image_rel",
        "result_id",
        "image_id",
        string="Key Images",
        help="Representative images bookmarked for this result.",
    )
    key_image_count = fields.Integer(
        string="Key Image Count",
        compute="_compute_key_image_count",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Quality & Dose
    # -------------------------------------------------------------------------
    quality_score = fields.Selection(
        [
            ("0", "0 - Uninterpretable"),
            ("1", "1 - Poor"),
            ("2", "2 - Fair"),
            ("3", "3 - Good"),
            ("4", "4 - Very Good"),
            ("5", "5 - Excellent"),
        ],
        string="Image Quality",
        default="3",
        help="Subjective image quality score for audit and QA.",
        tracking=True,
    )
    quality_notes = fields.Text(
        string="Quality Notes",
        help="Notes about artifacts, positioning, motion, or other quality issues.",
    )
    dose_line_ids = fields.One2many(
        "clinical.imaging.result.dose",
        "result_id",
        string="Dose / Exposure Lines",
        help="Radiation or exposure metrics (e.g., CTDIvol, DLP, DAP, Fluoro Time).",
        copy=True,
    )

    # -------------------------------------------------------------------------
    # Files & Output
    # -------------------------------------------------------------------------
    report_file = fields.Binary(
        string="Rendered Report (PDF)",
        attachment=True,
        help="Optional stored PDF of the rendered report for archival or external sharing.",
    )
    report_filename = fields.Char(
        string="Report File Name",
        help="Filename for the rendered report (PDF).",
    )
    dicom_bundle = fields.Binary(
        string="DICOM Bundle (ZIP)",
        attachment=True,
        help="Optional ZIP archive of related DICOM exports or secondary captures.",
    )
    dicom_bundle_filename = fields.Char(
        string="DICOM Bundle Name",
        help="Filename for the DICOM bundle ZIP.",
    )
    attachment_count = fields.Integer(
        string="Attachment Count",
        compute="_compute_attachment_count",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Portal & Privacy
    # -------------------------------------------------------------------------
    portal_published = fields.Boolean(
        string="Visible on Portal",
        help="If checked, the patient can view this result on the portal (subject to rules).",
        tracking=True,
    )
    privacy_level = fields.Selection(
        [
            ("normal", "Normal"),
            ("restricted", "Restricted"),
            ("high", "Highly Restricted"),
        ],
        string="Privacy Level",
        default="normal",
        help="Controls how widely accessible the result is to staff and on the portal.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Report Template (optional integration with clinical_imaging_report.py)
    # -------------------------------------------------------------------------
    report_template_id = fields.Many2one(
        "clinical.imaging.report.template",
        string="Report Template",
        help="Optional template to render this result.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    def _compute_finding_count(self):
        for rec in self:
            rec.finding_count = len(rec.finding_ids)

    def _compute_key_image_count(self):
        for rec in self:
            rec.key_image_count = len(rec.key_image_ids)

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("imaging_id")
    def _onchange_imaging_id_defaults(self):
        """Prefill author from imaging's responsible doctor and propagate patient."""
        for rec in self:
            if rec.imaging_id and not rec.author_doctor_id:
                if rec.imaging_id.doctor_id:
                    rec.author_doctor_id = rec.imaging_id.doctor_id.id

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("patient_id", "imaging_id")
    def _check_patient_matches_imaging(self):
        for rec in self:
            if rec.imaging_id and rec.patient_id and rec.imaging_id.patient_id != rec.patient_id:
                raise ValidationError(_("Patient on Result must match the Imaging's patient."))

    @api.constrains("state", "impression", "author_doctor_id")
    def _check_required_on_finalize(self):
        for rec in self:
            if rec.state in ("final", "amended"):
                if not rec.impression and not rec.findings:
                    raise ValidationError(_("Please fill at least Findings or Impression before finalizing."))
                if not rec.author_doctor_id:
                    raise ValidationError(_("Authoring Doctor is required for final/amended results."))

    @api.constrains("quality_score")
    def _check_quality_score_range(self):
        for rec in self:
            if rec.quality_score and rec.quality_score not in ("0", "1", "2", "3", "4", "5"):
                raise ValidationError(_("Invalid Image Quality score."))

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging.result") or _("New")
        records = super().create(vals_list)
        # Auto-subscribe author/co-signer to chatter
        for rec in records:
            partner_ids = []
            for emp in (rec.author_doctor_id, rec.co_signer_id):
                if emp and emp.work_contact_id:
                    partner_ids.append(emp.work_contact_id.id)
            if partner_ids:
                rec.message_subscribe(partner_ids=list(set(partner_ids)))
        return records

    def write(self, vals):
        # Prevent company change after creation
        if "company_id" in vals:
            for rec in self:
                if rec.company_id.id != vals["company_id"]:
                    raise UserError(_("You cannot change Company on a result."))
        return super().write(vals)

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("state", "draft")
        default.setdefault("version", 1)
        default.setdefault("signed_datetime", False)
        default.setdefault("amended_datetime", False)
        default.setdefault("portal_published", False)
        return super().copy(default)

    # -------------------------------------------------------------------------
    # ACTIONS / WORKFLOW
    # -------------------------------------------------------------------------
    def action_set_preliminary(self):
        for rec in self:
            if rec.state not in ("draft",):
                raise UserError(_("Only Draft results can be set to Preliminary."))
            rec.state = "preliminary"
            rec.message_post(body=_("Result set to Preliminary."))

    def action_finalize_and_sign(self):
        for rec in self:
            if rec.state not in ("draft", "preliminary"):
                raise UserError(_("Only Draft/Preliminary results can be finalized."))
            if not rec.author_doctor_id:
                raise UserError(_("Please set the Authoring Doctor before finalizing."))
            if not rec.impression and not rec.findings:
                raise UserError(_("Please provide Findings or Impression before finalizing."))
            if not rec.signed_datetime:
                rec.signed_datetime = fields.Datetime.now()
            rec.state = "final"
            rec.version = max(1, rec.version or 1)
            rec.message_post(body=_("Result finalized and signed."))

    def action_amend(self, addendum_text=None):
        for rec in self:
            if rec.state not in ("final", "amended"):
                raise UserError(_("Only Final/Amended results can be amended again."))
            rec.state = "amended"
            rec.version = (rec.version or 1) + 1
            rec.amended_datetime = fields.Datetime.now()
            body = _("Result amended. Version: %s") % rec.version
            if addendum_text:
                # Append the addendum text to recommendations by default
                rec.recommendations = (rec.recommendations or "") + ("\n" if rec.recommendations else "") + addendum_text
                body += " " + _("Addendum added.")
            rec.message_post(body=body)

    def action_cancel(self):
        for rec in self:
            if rec.state == "final" and rec.imaging_id and rec.imaging_id.invoice_id and rec.imaging_id.invoice_id.state == "posted":
                raise UserError(_("Final results linked to billed imaging cannot be cancelled."))
            rec.state = "cancelled"
            rec.message_post(body=_("Result cancelled."))

    def action_toggle_portal(self):
        for rec in self:
            rec.portal_published = not rec.portal_published

    # -------------------------------------------------------------------------
    # REPORTING
    # -------------------------------------------------------------------------
    def action_print_report(self):
        """
        Render the QWeb PDF. Requires report/action XML IDs:
          - clinic_imaging.report_clinical_imaging_result (ir.actions.report)
        """
        self.ensure_one()
        report = self.env.ref("clinic_imaging.report_clinical_imaging_result", raise_if_not_found=False)
        if not report:
            raise UserError(_("Report action 'clinic_imaging.report_clinical_imaging_result' not found."))
        return report.report_action(self)

    def action_send_result_email(self):
        """
        Send the result via email using a Mail Template, if configured:
          - clinic_imaging.mail_template_clinical_imaging_result
        """
        self.ensure_one()
        template = self.env.ref("clinic_imaging.mail_template_clinical_imaging_result", raise_if_not_found=False)
        if not template:
            raise UserError(_("Mail template 'clinic_imaging.mail_template_clinical_imaging_result' not found."))
        return template.send_mail(self.id, force_send=True)

    # -------------------------------------------------------------------------
    # NAVIGATION
    # -------------------------------------------------------------------------
    def action_view_attachments(self):
        self.ensure_one()
        return {
            "name": _("Attachments"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    def name_get(self):
        result = []
        for rec in self:
            display = rec.name or _("Result")
            if rec.imaging_id:
                display = f"{display} - {rec.imaging_id.name}"
            if rec.patient_id:
                display = f"{display} - {rec.patient_id.display_name}"
            if rec.state:
                display = f"{display} [{rec.state}]"
            result.append((rec.id, display))
        return result

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Result Number must be unique per company.',
    )


# =============================================================================
# Dose / Exposure lines (child)
# =============================================================================
class ClinicalImagingResultDose(models.Model):
    """
    Radiation/exposure metrics captured for the result.
    Not all modalities use all fields (e.g., CT uses CTDIvol/DLP).
    """
    _name = "clinical.imaging.result.dose"
    _description = "Clinical Imaging Result Dose/Exposure"
    _order = "sequence, id"

    result_id = fields.Many2one(
        "clinical.imaging.result",
        string="Result",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)

    metric = fields.Selection(
        [
            ("ctdi_vol", "CTDIvol (mGy)"),
            ("dlp", "DLP (mGy·cm)"),
            ("dap", "Dose Area Product (Gy·cm²)"),
            ("fluoro_time", "Fluoroscopy Time (min)"),
            ("exposure", "Exposure (mAs/kVp)"),
            ("other", "Other"),
        ],
        string="Metric",
        required=True,
        help="Dose/exposure metric type.",
    )
    value = fields.Float(
        string="Value",
        required=True,
        help="Numeric value for the metric.",
    )
    unit = fields.Char(
        string="Unit",
        help="Unit override if 'Other' metric or custom unit.",
    )
    series_ref = fields.Char(
        string="Series Reference",
        help="Optional series identifier/reference within the study.",
    )
    note = fields.Char(
        string="Notes",
        help="Optional short note/remark for this metric.",
    )

    @api.constrains("value")
    def _check_value_non_negative(self):
        for rec in self:
            if rec.value is not None and rec.value < 0.0:
                raise ValidationError(_("Dose/Exposure value must be non-negative."))


# =============================================================================
# Optional: Measurements table (child)
# =============================================================================
class ClinicalImagingResultMeasure(models.Model):
    """
    Generic measurement rows (e.g., lesion sizes, organ dimensions, indices).
    For specialized measurements, consider dedicated models in future expansions.
    """
    _name = "clinical.imaging.result.measure"
    _description = "Clinical Imaging Result Measurement"
    _order = "sequence, id"

    result_id = fields.Many2one(
        "clinical.imaging.result",
        string="Result",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)

    name = fields.Char(
        string="Measurement Name",
        required=True,
        help="Short title for the measurement (e.g., 'Lesion A long-axis').",
    )
    region = fields.Char(
        string="Region",
        help="Anatomical region or description (e.g., 'Right lobe liver').",
    )
    method = fields.Char(
        string="Method",
        help="Measurement method/protocol (e.g., 'RECIST 1.1', 'Axial plane').",
    )
    value = fields.Float(
        string="Value",
        help="Measured value (numeric).",
    )
    unit = fields.Char(
        string="Unit",
        help="Unit of the measured value (e.g., 'mm', 'cm', 'HU').",
    )
    note = fields.Char(
        string="Notes",
        help="Optional remark about the measurement.",
    )

    @api.constrains("value")
    def _check_value_not_nan(self):
        for rec in self:
            # No NaN check needed explicitly in Odoo, but ensure not absurd.
            if rec.value is not None and rec.value < 0 and rec.unit in ("mm", "cm"):
                # Negative length is usually invalid; allow negatives for HU, etc.
                raise ValidationError(_("Length/size measurements should not be negative."))


# =============================================================================
# Hooks: keep imaging header aware of latest final result (optional convenience)
# =============================================================================
class ClinicalImaging(models.Model):
    _inherit = "clinical.imaging"

    latest_result_id = fields.Many2one(
        "clinical.imaging.result",
        string="Latest Result",
        compute="_compute_latest_result",
        store=False,
        help="Convenience link to the most recent final/amended result for quick access.",
    )
    result_count = fields.Integer(
        string="Result Count",
        compute="_compute_result_stats",
        store=False,
    )

    def _compute_result_stats(self):
        for rec in self:
            rec.result_count = self.env["clinical.imaging.result"].search_count([("imaging_id", "=", rec.id)])

    def _compute_latest_result(self):
        for rec in self:
            latest = self.env["clinical.imaging.result"].search(
                [("imaging_id", "=", rec.id), ("state", "in", ["final", "amended"])],
                order="signed_datetime desc, write_date desc, id desc",
                limit=1,
            )
            rec.latest_result_id = latest.id if latest else False

    def action_open_results(self):
        self.ensure_one()
        return {
            "name": _("Imaging Results"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.result",
            "view_mode": "list,form,kanban",
            "domain": [("imaging_id", "=", self.id)],
            "target": "current",
            "context": {"default_imaging_id": self.id},
        }


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# Clinical Imaging Request (header/master)
# =============================================================================
class ClinicalImagingRequest(models.Model):
    """
    Represents a physician's request/order for one or more imaging procedures.
    Each request comprises one or more lines (requested imaging types), and can
    generate one or multiple clinical.imaging records upon approval.

    Integration points (cross-module):
      - Patient (clinic_patient / res.partner with is_patient)
      - Doctor & Technician (clinic_doctor / hr.employee with flags)
      - Appointment (clinic_booking)
      - Encounter (clinic_encounter)
      - Treatment & Procedure Session (clinic_treatment / clinic_procedure)
      - eMAR / Prescription Order (clinic_prescription)
      - Consent (clinic_consent)
      - Billing (account / clinic_billing / clinic_finance / clinic_accounting)
      - Membership / Coverage (clinic_membership)
      - Portal publishing (clinic_portal)
    """
    _name = "clinical.imaging.request"
    _description = "Clinical Imaging Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "request_datetime desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Request Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        help="Unique identifier generated from sequence at creation time.",
        tracking=True,
        index=True,
    )
    plan_id = fields.Many2one(
        "clinic.treatment.imaging.plan",
        string="Originating Plan",
        index=True,
        ondelete="set null",
        help="If this request was generated from a treatment imaging plan, link it here.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, the request is archived from regular views.",
    )

    # -------------------------------------------------------------------------
    # Patient & Care Team
    # -------------------------------------------------------------------------
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        required=True,
        index=True,
        domain=[("is_company", "=", False), ("is_patient", "=", True)],
        help="Linked patient (res.partner) flagged with 'Is a Patient'.",
        tracking=True,
    )
    ordering_doctor_id = fields.Many2one(
        "hr.employee",
        string="Ordering Doctor",
        domain=[("is_doctor", "=", True)],
        help="Doctor who ordered this imaging request.",
        tracking=True,
    )
    responsible_doctor_id = fields.Many2one(
        "hr.employee",
        string="Responsible Doctor",
        domain=[("is_doctor", "=", True)],
        help="Doctor in charge for review/approval (radiologist or assigned MD).",
        tracking=True,
    )
    technician_id = fields.Many2one(
        "hr.employee",
        string="Preferred Technician",
        domain=[("is_imaging_technician", "=", True)],
        help="Preferred technician to perform imaging (optional).",
        tracking=True,
    )
    # membership_id = fields.Many2one(
    #     "clinic.membership",
    #     string="Membership",
    #     help="Membership used for benefits/coverage for this request (if any).",
    #     tracking=True,
    # )

    # -------------------------------------------------------------------------
    # Clinical Context (cross-module references)
    # -------------------------------------------------------------------------
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        help="Appointment related to this request (if scheduled via booking).",
    )
    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     help="Encounter during which the imaging is requested.",
    # )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        help="Treatment plan associated with this request.",
    )
    procedure_session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Procedure Session",
        help="Related procedure/treatment session, if applicable.",
    )
    prescription_order_id = fields.Many2one(
        "clinic.prescription.order",
        string="Prescription/Order (eMAR)",
        help="eMAR/Prescription record authorizing this request.",
    )
    consent_id = fields.Many2one(
        "clinic.consent.form",
        string="Consent",
        help="Patient consent record linked to this request.",
    )

    # -------------------------------------------------------------------------
    # Request Details
    # -------------------------------------------------------------------------
    request_datetime = fields.Datetime(
        string="Requested At",
        required=True,
        default=fields.Datetime.now,
        help="Datetime when the request was created.",
        tracking=True,
    )
    desired_datetime = fields.Datetime(
        string="Desired Date/Time",
        help="Preferred datetime to schedule imaging.",
        tracking=True,
    )
    expiry_date = fields.Date(
        string="Order Expiry Date",
        help="Date after which the request/order is considered expired.",
        tracking=True,
    )
    priority = fields.Selection(
        [
            ("0", "Normal"),
            ("1", "High"),
            ("2", "Urgent"),
            ("3", "Emergency"),
        ],
        string="Priority",
        default="0",
        help="Clinical urgency of this request.",
        tracking=True,
    )
    clinical_indication = fields.Text(
        string="Clinical Indication",
        help="Reason for imaging; the clinical question to be answered.",
        tracking=True,
    )
    notes = fields.Text(
        string="Internal Notes",
        help="Additional notes for staff.",
    )

    # -------------------------------------------------------------------------
    # Lines & Imaging linkage
    # -------------------------------------------------------------------------
    line_ids = fields.One2many(
        "clinical.imaging.request.line",
        "request_id",
        string="Requested Procedures",
        help="One or more requested imaging procedures.",
        copy=True,
    )
    created_imaging_ids = fields.Many2many(
        "clinical.imaging",
        "clinical_imaging_request_rel",
        "request_id",
        "imaging_id",
        string="Created Imaging Records",
        help="Imaging records generated from this request.",
        copy=False,
    )
    line_count = fields.Integer(
        string="Line Count",
        compute="_compute_counts",
        store=False,
    )
    created_imaging_count = fields.Integer(
        string="Created Imaging Count",
        compute="_compute_counts",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Billing & Currency
    # -------------------------------------------------------------------------
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )
    fiscal_position_id = fields.Many2one(
        "account.fiscal.position",
        string="Fiscal Position",
        help="Fiscal position used to map taxes based on the patient/partner.",
    )
    amount_untaxed = fields.Monetary(
        string="Untaxed Amount",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Sum of line subtotals without taxes.",
    )
    amount_tax = fields.Monetary(
        string="Taxes",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Total tax amount from all lines.",
    )
    amount_total = fields.Monetary(
        string="Total",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Grand total including taxes.",
    )
    is_billable = fields.Boolean(
        string="Billable",
        default=True,
        help="If checked, this request is billable and can generate a draft invoice.",
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        domain=[("move_type", "in", ["out_invoice", "out_refund"])],
        help="Linked invoice if the request has been billed.",
        tracking=True,
    )
    billing_state = fields.Selection(
        [
            ("no", "Not Billed"),
            ("draft", "In Draft Invoice"),
            ("posted", "Billed"),
            ("refund", "Refunded"),
        ],
        string="Billing Status",
        compute="_compute_billing_state",
        store=True,
        help="Derived from the linked invoice state.",
    )

    # -------------------------------------------------------------------------
    # Portal & Attachments
    # -------------------------------------------------------------------------
    portal_published = fields.Boolean(
        string="Visible on Portal",
        help="If checked, the patient can view this request via the portal (subject to rules).",
        tracking=True,
    )
    attachment_count = fields.Integer(
        string="Attachment Count",
        compute="_compute_attachment_count",
        store=False,
    )

    # -------------------------------------------------------------------------
    # State Machine
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("in_progress", "In Progress"),
            ("imaging_created", "Imaging Created"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
            ("done", "Done"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
        help="Lifecycle status of the imaging request.",
    )
    is_overdue = fields.Boolean(
        string="Overdue",
        compute="_compute_is_overdue",
        store=True,
        help="Checked when desired/expiry SLA is missed and the request is still open.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("line_ids.price_subtotal", "line_ids.price_tax")
    def _compute_amounts(self):
        for rec in self:
            untaxed = sum(rec.line_ids.mapped("price_subtotal"))
            tax = sum(rec.line_ids.mapped("price_tax"))
            rec.amount_untaxed = untaxed
            rec.amount_tax = tax
            rec.amount_total = untaxed + tax

    @api.depends("invoice_id.state", "invoice_id.move_type")
    def _compute_billing_state(self):
        for rec in self:
            if not rec.invoice_id:
                rec.billing_state = "no"
            else:
                move = rec.invoice_id
                if move.state == "draft":
                    rec.billing_state = "draft"
                elif move.state == "posted" and move.move_type == "out_invoice":
                    rec.billing_state = "posted"
                elif move.state == "posted" and move.move_type == "out_refund":
                    rec.billing_state = "refund"
                else:
                    rec.billing_state = "no"

    @api.depends("desired_datetime", "expiry_date", "state")
    def _compute_is_overdue(self):
        now_dt = fields.Datetime.now()
        today = fields.Date.context_today(self)
        for rec in self:
            overdue = False
            if rec.state in ("submitted", "approved", "in_progress"):
                if rec.desired_datetime and now_dt > rec.desired_datetime:
                    overdue = True
                if rec.expiry_date and today > rec.expiry_date:
                    overdue = True
            rec.is_overdue = overdue

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    def _compute_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.created_imaging_count = len(rec.created_imaging_ids)

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        """Set fiscal position from patient and suggest membership if available."""
        for rec in self:
            partner = rec.patient_id and rec.patient_id.commercial_partner_id or False
            if partner:
                rec.fiscal_position_id = partner.property_account_position_id
            # Membership suggestion hook (if patient has default membership logic)
            # Keep non-destructive (do not override if already set)
            if not rec.membership_id and getattr(rec.patient_id, "default_membership_id", False):
                rec.membership_id = rec.patient_id.default_membership_id.id

    @api.onchange("appointment_id")
    def _onchange_appointment_id(self):
        for rec in self:
            if rec.appointment_id and not rec.desired_datetime:
                start_dt = getattr(rec.appointment_id, "start_datetime", False)
                if start_dt:
                    rec.desired_datetime = start_dt

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("line_ids")
    def _check_has_lines(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_("Please add at least one request line."))

    @api.constrains("expiry_date", "request_datetime")
    def _check_expiry_not_before_request(self):
        for rec in self:
            if rec.expiry_date and rec.request_datetime:
                if fields.Date.to_date(rec.expiry_date) < fields.Date.to_date(rec.request_datetime):
                    raise ValidationError(_("Order Expiry Date cannot be earlier than Requested At."))

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging.request") or _("New")
        records = super().create(vals_list)
        # Auto-subscribe ordering/responsible doctors to chatter
        for rec in records:
            partner_ids = []
            if rec.ordering_doctor_id and rec.ordering_doctor_id.work_contact_id:
                partner_ids.append(rec.ordering_doctor_id.work_contact_id.id)
            if rec.responsible_doctor_id and rec.responsible_doctor_id.work_contact_id:
                partner_ids.append(rec.responsible_doctor_id.work_contact_id.id)
            if partner_ids:
                rec.message_subscribe(partner_ids=list(set(partner_ids)))
        return records

    def write(self, vals):
        # Prevent company changes after creation if invoiced
        if "company_id" in vals:
            for rec in self:
                if rec.invoice_id:
                    raise UserError(_("You cannot change the Company once an invoice is linked."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.invoice_id and rec.invoice_id.state == "posted":
                raise UserError(_("You cannot delete a request that has a posted invoice."))
        return super().unlink()

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("state", "draft")
        default.setdefault("invoice_id", False)
        default.setdefault("created_imaging_ids", False)
        return super().copy(default)

    # -------------------------------------------------------------------------
    # ACTIONS / WORKFLOW
    # -------------------------------------------------------------------------
    def action_submit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only Draft requests can be submitted."))
            rec.state = "submitted"
            rec.message_post(body=_("Imaging request has been submitted."))

    def action_approve(self):
        for rec in self:
            if rec.state not in ("submitted",):
                raise UserError(_("Only Submitted requests can be approved."))
            if not rec.responsible_doctor_id:
                raise UserError(_("Please set a Responsible Doctor before approval."))
            rec.state = "approved"
            rec.message_post(body=_("Imaging request has been approved by the doctor."))

    def action_reject(self, reason=None):
        for rec in self:
            if rec.state not in ("submitted", "approved"):
                raise UserError(_("Only Submitted/Approved requests can be rejected."))
            rec.state = "rejected"
            body = _("Imaging request has been rejected.")
            if reason:
                body += " " + _("Reason: %s") % reason
            rec.message_post(body=body)

    def action_cancel(self):
        for rec in self:
            if rec.state in ("done",):
                raise UserError(_("Completed requests cannot be cancelled."))
            rec.state = "cancelled"
            rec.message_post(body=_("Imaging request has been cancelled."))

    def action_set_in_progress(self):
        for rec in self:
            if rec.state not in ("approved",):
                raise UserError(_("Only Approved requests can be set In Progress."))
            rec.state = "in_progress"
            rec.message_post(body=_("Imaging request is now In Progress."))

    def action_create_imaging(self):
        """
        Generate one or multiple 'clinical.imaging' records from approved requests.
        Typically creates one imaging per line (and per quantity if >1).
        """
        Imaging = self.env["clinical.imaging"]
        created_map = {}
        for rec in self:
            if rec.state not in ("approved", "in_progress", "submitted"):
                raise UserError(_("Only Submitted/Approved/In Progress requests can create imaging records."))
            if not rec.patient_id:
                raise UserError(_("Patient is required to create imaging records."))

            imaging_records = self.env["clinical.imaging"]
            for line in rec.line_ids:
                if not line.imaging_type_id:
                    raise UserError(_("Each line must have an Imaging Type."))
                qty = max(1, int(line.quantity or 1))
                for _i in range(qty):
                    vals = {
                        "company_id": rec.company_id.id,
                        "patient_id": rec.patient_id.id,
                        "doctor_id": rec.responsible_doctor_id.id if rec.responsible_doctor_id else False,
                        "technician_id": rec.technician_id.id if rec.technician_id else False,
                        "membership_id": rec.membership_id.id if rec.membership_id else False,
                        "appointment_id": rec.appointment_id.id if rec.appointment_id else False,
                        "encounter_id": rec.encounter_id.id if rec.encounter_id else False,
                        "treatment_id": rec.treatment_id.id if rec.treatment_id else False,
                        "procedure_session_id": rec.procedure_session_id.id if rec.procedure_session_id else False,
                        "prescription_order_id": rec.prescription_order_id.id if rec.prescription_order_id else False,
                        "consent_id": rec.consent_id.id if rec.consent_id else False,
                        "imaging_type_id": line.imaging_type_id.id,
                        "device_id": line.device_id.id if line.device_id else False,
                        "product_id": line.product_id.id if line.product_id else False,
                        "priority": rec.priority,
                        "request_datetime": rec.request_datetime,
                        "scheduled_datetime": rec.desired_datetime or False,
                        "clinical_indication": rec.clinical_indication,
                        "notes": line.notes or rec.notes,
                        "quantity": 1.0,
                        "price_unit": line.price_unit or (line.product_id and line.product_id.lst_price) or 0.0,
                        "currency_id": rec.currency_id.id,
                        "portal_published": False,
                    }
                    new_imaging = Imaging.create(vals)
                    imaging_records |= new_imaging
                    # Link back to request line
                    line.imaging_ids = [(4, new_imaging.id)]
            if imaging_records:
                # link at header level
                rec.created_imaging_ids = [(6, 0, imaging_records.ids)]
                rec.state = "imaging_created"
                rec.message_post(body=_("Created %s imaging record(s).") % len(imaging_records))
            created_map[rec.id] = imaging_records.ids
        # Return an action to show all created imaging for the last request if single
        if len(self) == 1 and self.created_imaging_ids:
            return self.action_open_created_imaging()
        return created_map

    def action_open_created_imaging(self):
        self.ensure_one()
        return {
            "name": _("Created Imaging"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging",
            "view_mode": "list,form,kanban,calendar",
            "domain": [("id", "in", self.created_imaging_ids.ids)],
            "target": "current",
        }

    def action_mark_done(self):
        for rec in self:
            if rec.state not in ("imaging_created", "in_progress", "approved"):
                raise UserError(_("Only Approved/In Progress/Imaging Created requests can be marked Done."))
            rec.state = "done"
            rec.message_post(body=_("Imaging request is marked as Done."))

    # -------------------------------------------------------------------------
    # BILLING INTEGRATION (optional)
    # -------------------------------------------------------------------------
    def _get_invoice_partner(self):
        self.ensure_one()
        if not self.patient_id:
            raise UserError(_("Patient is required for billing."))
        return self.patient_id.commercial_partner_id

    def _prepare_invoice_vals(self):
        self.ensure_one()
        partner = self._get_invoice_partner()
        return {
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "invoice_origin": self.name,
            "invoice_user_id": self.env.user.id,
            "invoice_date": fields.Date.context_today(self),
            "currency_id": self.currency_id.id,
            "invoice_line_ids": [(0, 0, line._prepare_invoice_line_vals(self)) for line in self.line_ids],
            "invoice_payment_ref": self.name,
            "invoice_payment_term_id": partner.property_payment_term_id.id or False,
        }

    def action_create_invoice(self):
        for rec in self:
            if not rec.is_billable:
                raise UserError(_("This request is marked as not billable."))
            if rec.invoice_id:
                raise UserError(_("An invoice has already been linked to this request."))
            if not rec.line_ids:
                raise UserError(_("Please add at least one request line to bill."))
            move = self.env["account.move"].create(rec._prepare_invoice_vals())
            rec.invoice_id = move.id
            rec.message_post(body=_("Draft invoice created: %s") % move.display_name)
        return self.action_open_invoice()

    def action_open_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No invoice linked to this request."))
        return {
            "name": _("Invoice"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.invoice_id.id,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # PORTAL / NAVIGATION HELPERS
    # -------------------------------------------------------------------------
    def action_view_attachments(self):
        self.ensure_one()
        return {
            "name": _("Attachments"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    def action_toggle_portal(self):
        for rec in self:
            rec.portal_published = not rec.portal_published

    def name_get(self):
        result = []
        for rec in self:
            display = rec.name or _("Request")
            if rec.patient_id:
                display = f"{display} - {rec.patient_id.display_name}"
            result.append((rec.id, display))
        return result

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Request Number must be unique per company.',
    )


# =============================================================================
# Clinical Imaging Request Line (detail)
# =============================================================================
class ClinicalImagingRequestLine(models.Model):
    """
    A single requested imaging procedure within a request.
    Each line may generate one or more clinical.imaging records (per quantity).
    """
    _name = "clinical.imaging.request.line"
    _description = "Clinical Imaging Request Line"
    _order = "sequence, id"

    # Header relation
    request_id = fields.Many2one(
        "clinical.imaging.request",
        string="Request",
        required=True,
        ondelete="cascade",
        index=True,
    )

    sequence = fields.Integer(string="Sequence", default=10)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="request_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="request_id.currency_id",
        store=True,
        readonly=True,
    )

    # Imaging specification
    imaging_type_id = fields.Many2one(
        "clinical.imaging.type",
        string="Imaging Type",
        required=True,
        help="Imaging type to be performed for this line (e.g., X-Ray, CT, MRI).",
    )
    device_id = fields.Many2one(
        "clinical.imaging.device",
        string="Preferred Device",
        help="Preferred device to perform this imaging (optional).",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Billable Service",
        domain=[("type", "=", "service")],
        help="Service product used for pricing/invoicing this line.",
    )
    quantity = fields.Float(
        string="Quantity",
        default=1.0,
        help="Number of times this imaging is requested for this line.",
    )
    duration_minutes = fields.Integer(
        string="Expected Duration (min)",
        help="Expected duration for this imaging; used for scheduling.",
    )
    priority = fields.Selection(
        [
            ("0", "Normal"),
            ("1", "High"),
            ("2", "Urgent"),
            ("3", "Emergency"),
        ],
        string="Priority",
        default="0",
        help="Line-level priority (defaults to request's priority if unset).",
    )
    notes = fields.Text(
        string="Line Notes",
        help="Additional notes specific to this line.",
    )

    # Billing & Taxes
    price_unit = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        help="Unit price for billing; prefilled from product or imaging type default service.",
    )
    tax_ids = fields.Many2many(
        "account.tax",
        "clinical_imaging_request_line_tax_rel",
        "line_id",
        "tax_id",
        string="Taxes",
        help="Taxes applicable to this line.",
    )

    # Totals
    price_subtotal = fields.Monetary(
        string="Subtotal",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Subtotal without taxes for this line.",
    )
    price_tax = fields.Monetary(
        string="Tax",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Tax amount for this line.",
    )
    price_total = fields.Monetary(
        string="Total",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Total including taxes for this line.",
    )

    # Link to created imaging (one line may produce many imaging records)
    imaging_ids = fields.Many2many(
        "clinical.imaging",
        "clinical_imaging_request_line_rel",
        "line_id",
        "imaging_id",
        string="Imaging Records",
        help="Imaging records created from this line.",
        copy=False,
    )
    imaging_count = fields.Integer(
        string="Imaging Count",
        compute="_compute_imaging_count",
        store=False,
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("quantity", "price_unit", "tax_ids", "request_id.fiscal_position_id")
    def _compute_amounts(self):
        for line in self:
            qty = line.quantity or 0.0
            price_unit = line.price_unit or 0.0
            currency = line.currency_id or line.request_id.currency_id
            partner = line.request_id.patient_id and line.request_id.patient_id.commercial_partner_id or False
            fpos = line.request_id.fiscal_position_id or (partner and partner.property_account_position_id) or False

            taxes = line.tax_ids
            if fpos:
                taxes = fpos.map_tax(taxes, partner)
            res = taxes.compute_all(
                price_unit,
                currency=currency,
                quantity=qty,
                product=line.product_id,
                partner=partner,
            ) if taxes else {
                "total_excluded": price_unit * qty,
                "total_included": price_unit * qty,
                "taxes": [],
            }
            line.price_subtotal = currency.round(res["total_excluded"]) if currency else res["total_excluded"]
            line.price_total = currency.round(res["total_included"]) if currency else res["total_included"]
            # Derive tax amount
            line.price_tax = line.price_total - line.price_subtotal

    def _compute_imaging_count(self):
        for line in self:
            line.imaging_count = len(line.imaging_ids)

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("imaging_type_id")
    def _onchange_imaging_type_id(self):
        for line in self:
            if line.imaging_type_id:
                # Prefill product and duration from imaging type defaults
                if line.imaging_type_id.default_product_id and not line.product_id:
                    line.product_id = line.imaging_type_id.default_product_id.id
                if line.imaging_type_id.default_duration_minutes and not line.duration_minutes:
                    line.duration_minutes = line.imaging_type_id.default_duration_minutes

    @api.onchange("product_id")
    def _onchange_product_id_set_price_and_taxes(self):
        for line in self:
            if line.product_id:
                # Set price if empty
                if not line.price_unit or line.price_unit == 0.0:
                    line.price_unit = line.product_id.lst_price
                # Map taxes from product
                taxes = line.product_id.taxes_id
                partner = line.request_id.patient_id and line.request_id.patient_id.commercial_partner_id or False
                fpos = line.request_id.fiscal_position_id or (partner and partner.property_account_position_id) or False
                if fpos:
                    taxes = fpos.map_tax(taxes, partner)
                line.tax_ids = [(6, 0, taxes.ids)]

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("quantity")
    def _check_quantity_positive(self):
        for line in self:
            if (line.quantity or 0.0) <= 0.0:
                raise ValidationError(_("Quantity must be greater than zero."))

    # -------------------------------------------------------------------------
    # INVOICE LINE PREPARATION
    # -------------------------------------------------------------------------
    def _prepare_invoice_line_vals(self, request):
        self.ensure_one()
        if not self.product_id:
            raise UserError(_("Please set a Billable Service (product) on each line before invoicing."))
        partner = request._get_invoice_partner()
        # Ensure taxes mapped with fiscal position
        taxes = self.tax_ids
        if request.fiscal_position_id:
            taxes = request.fiscal_position_id.map_tax(taxes, partner)
        name_parts = [
            _("Imaging Request"),
            request.name or "",
            ("[%s]" % self.imaging_type_id.display_name) if self.imaging_type_id else "",
            ("- %s" % request.patient_id.display_name) if request.patient_id else "",
        ]
        return {
            "name": " ".join([p for p in name_parts if p]),
            "product_id": self.product_id.id,
            "quantity": self.quantity or 1.0,
            "price_unit": self.price_unit or self.product_id.lst_price,
            "currency_id": request.currency_id.id,
            "tax_ids": [(6, 0, taxes.ids)],
        }

    # -------------------------------------------------------------------------
    # NAVIGATION
    # -------------------------------------------------------------------------
    def action_open_imaging(self):
        self.ensure_one()
        return {
            "name": _("Imaging Records"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging",
            "view_mode": "list,form,kanban,calendar",
            "domain": [("id", "in", self.imaging_ids.ids)],
            "target": "current",
        }


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.safe_eval import safe_eval
from datetime import date, datetime
import re


# =============================================================================
# Report Template (Master)
# =============================================================================
class ClinicalImagingReportTemplate(models.Model):
    _name = "clinical.imaging.report.template"
    _description = "Clinical Imaging Report Template"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(string="Template Name", required=True, tracking=True)
    code = fields.Char(string="Code", index=True, tracking=True,
                       help="Short unique code for referencing this template (e.g., 'XR_CHEST_STD').")
    sequence = fields.Integer(string="Sequence", default=10)
    company_id = fields.Many2one("res.company", string="Company", required=True,
                                 default=lambda s: s.env.company)
    active = fields.Boolean(default=True)

    # -------------------------------------------------------------------------
    # Applicability / Scoping
    # -------------------------------------------------------------------------
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
        help="If set, this template is recommended for the selected modality.",
        tracking=True,
    )
    imaging_type_ids = fields.Many2many(
        "clinical.imaging.type",
        "clinical_imaging_report_template_type_rel",
        "template_id", "type_id",
        string="Imaging Types",
        help="Restrict usage to selected imaging types (leave empty for all).",
    )
    default_language = fields.Selection(
        lambda self: self.env['res.lang'].get_installed(),
        string="Default Language",
        help="Default language used when rendering this template.",
    )
    is_default_company = fields.Boolean(
        string="Company Default",
        help="If checked, acts as the fallback template for the company "
             "when result/imaging type does not specify one.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Layout & Components
    # -------------------------------------------------------------------------
    paperformat_id = fields.Many2one(
        "report.paperformat", string="Paper Format",
        help="Optional paper format override (otherwise report default is used).",
    )
    include_findings = fields.Boolean(string="Include Findings", default=True)
    include_key_images = fields.Boolean(string="Include Key Images", default=True)
    include_measurements = fields.Boolean(string="Include Measurements", default=True)
    show_author_signature = fields.Boolean(string="Show Author Signature", default=True)
    show_cosigner_signature = fields.Boolean(string="Show Co-signer Signature", default=False)

    header_html = fields.Html(
        string="Header (HTML)",
        sanitize=False,
        help="HTML fragment for the report header. Supports ${placeholders}.",
    )
    body_html = fields.Html(
        string="Body (HTML)",
        sanitize=False,
        help="Main body HTML. You can include ${placeholders} and sections below.",
    )
    footer_html = fields.Html(
        string="Footer (HTML)",
        sanitize=False,
        help="HTML fragment for the report footer. Supports ${placeholders}.",
    )

    section_ids = fields.One2many(
        "clinical.imaging.report.template.section", "template_id",
        string="Sections", copy=True
    )
    variable_ids = fields.One2many(
        "clinical.imaging.report.template.variable", "template_id",
        string="Variables", copy=True
    )
    asset_ids = fields.One2many(
        "clinical.imaging.report.template.asset", "template_id",
        string="Assets (CSS)", copy=True
    )

    # -------------------------------------------------------------------------
    # Versioning & Audit
    # -------------------------------------------------------------------------
    version = fields.Integer(string="Version", default=1, tracking=True)
    locked = fields.Boolean(
        string="Locked",
        help="Locked templates cannot be edited (use 'Duplicate' to create a new version).",
        tracking=True,
    )
    notes = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # COMPUTES / HELPERS
    # -------------------------------------------------------------------------
    section_count = fields.Integer(string="Section Count", compute="_compute_counts", store=False)
    variable_count = fields.Integer(string="Variable Count", compute="_compute_counts", store=False)

    def _compute_counts(self):
        for rec in self:
            rec.section_count = len(rec.section_ids)
            rec.variable_count = len(rec.variable_ids)

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("code")
    def _check_code_upper(self):
        for rec in self:
            if rec.code and rec.code.strip() != rec.code.strip().upper():
                rec.code = rec.code.strip().upper()

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Template Code must be unique per company.',
    )

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    def write(self, vals):
        if any(field in vals for field in ["name", "code", "modality", "imaging_type_ids",
                                           "header_html", "body_html", "footer_html"]) and any(self.mapped("locked")):
            raise UserError(_("Locked templates cannot be edited. Duplicate to create a new version."))
        return super().write(vals)

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("%s (Copy)") % (self.name or "Template"))
        default.setdefault("version", (self.version or 1) + 1)
        default.setdefault("locked", False)
        default.setdefault("is_default_company", False)
        return super().copy(default)

    # -------------------------------------------------------------------------
    # Rendering Pipeline (for preview / portal)
    # -------------------------------------------------------------------------
    PLACEHOLDER_RE = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_\.]*)\}")

    def _ctx_get(self, ctx, dotted_key):
        """Get dot.notation value from dict-like context."""
        cur = ctx
        for part in dotted_key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return ""
        return cur if cur is not None else ""

    def _replace_placeholders(self, html, ctx):
        if not html:
            return ""
        def repl(match):
            key = match.group(1)
            val = self._ctx_get(ctx, key)
            return str(val) if val is not None else ""
        return self.PLACEHOLDER_RE.sub(repl, html)

    def _build_base_context(self, result):
        """Build a base dict used to render placeholders."""
        patient = result.patient_id
        imaging = result.imaging_id
        studies = imaging.study_ids if imaging else self.env["clinical.imaging.study"]
        latest_study = studies[:1]
        appt = result.appointment_id
        enc = result.encounter_id

        # age in years (approx)
        age_years = ""
        if patient and patient.birthdate_date:
            today = date.today()
            bd = patient.birthdate_date
            age_years = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))

        # findings for convenience
        findings = []
        for f in result.finding_ids:
            findings.append({
                "title": f.display_name,
                "category": f.category or "",
                "severity": f.severity or "",
                "trend": f.trend or "",
                "body_region": f.body_region or "",
                "organ": f.organ or "",
                "segment": f.organ_segment or "",
                "side": f.side or "",
                "long_axis_mm": f.long_axis_mm or "",
                "short_axis_mm": f.short_axis_mm or "",
                "desc": f.description or "",
            })

        ctx = {
            # entities
            "company_name": result.company_id.name or "",
            "patient_name": patient.display_name if patient else "",
            "patient_code": patient.ref or "",
            "patient_dob": patient.birthdate_date and fields.Date.to_string(patient.birthdate_date) or "",
            "patient_age_years": age_years,
            "patient_phone": patient.phone or "",
            "patient_email": patient.email or "",
            "patient_gender": (patient.gender if hasattr(patient, "gender") else "") or "",
            "imaging_number": imaging.name if imaging else "",
            "imaging_type": imaging.imaging_type_id.name if imaging and imaging.imaging_type_id else "",
            "modality": imaging.imaging_type_id.modality if imaging and imaging.imaging_type_id else "",
            "device_name": imaging.device_id.name if imaging and imaging.device_id else "",
            "study_date": latest_study.study_datetime and fields.Datetime.to_string(latest_study.study_datetime) or "",
            "result_number": result.name,
            "result_datetime": result.signed_datetime and fields.Datetime.to_string(result.signed_datetime)
                               or (result.result_datetime and fields.Datetime.to_string(result.result_datetime)) or "",
            "doctor_name": result.author_doctor_id.name if result.author_doctor_id else "",
            "cosigner_name": result.co_signer_id.name if result.co_signer_id else "",
            "appointment_number": appt and appt.name or "",
            "encounter_number": enc and enc.name or "",
            # structured content
            "technique": result.technique or "",
            "comparison": result.comparison or "",
            "findings_text": result.findings or "",
            "impression": result.impression or "",
            "recommendations": result.recommendations or "",
            "findings": findings,
            # counts
            "finding_count": len(result.finding_ids),
            "key_image_count": len(result.key_image_ids),
            # misc
            "today": fields.Datetime.to_string(fields.Datetime.now()),
        }
        return ctx

    def _eval_variables(self, ctx):
        """Evaluate template-level variables with safe_eval."""
        local_ctx = {"ctx": ctx}
        # Do NOT expose env or records to safe_eval
        for var in self.variable_ids:
            try:
                value = safe_eval(var.expr or "None", local_ctx, nocopy=True)
            except Exception as e:
                value = _("(error: %s)") % str(e)
            ctx[var.code] = value
        return ctx

    def _render_sections(self, ctx):
        """Render sections to a single HTML string (ordered by sequence)."""
        parts = []
        for sec in self.section_ids.sorted(key=lambda s: (s.sequence, s.id)):
            if not sec.active:
                continue
            if sec.condition_expr:
                try:
                    if not safe_eval(sec.condition_expr, {"ctx": ctx}, nocopy=True):
                        continue
                except Exception:
                    # If condition fails, skip section silently (do not break report)
                    continue
            title_html = f"<h3>{sec.title}</h3>" if sec.title else ""
            body_html = self._replace_placeholders(sec.body_html or "", ctx)
            parts.append(f'<div class="cim-section cim-sec-{sec.code or sec.id}">{title_html}{body_html}</div>')
        return "\n".join(parts)

    def render_html_from_template(self, result):
        """
        Build a complete HTML string by combining header/body/footer with
        placeholder replacement and conditional sections.
        """
        if not result or result._name != "clinical.imaging.result":
            raise UserError(_("Rendering requires a 'clinical.imaging.result' record."))

        ctx = self._build_base_context(result)
        ctx = self._eval_variables(ctx)

        # default 'sections' placeholder for body_html
        sections_html = self._render_sections(ctx)
        ctx["sections"] = sections_html

        header = self._replace_placeholders(self.header_html or "", ctx)
        body = self._replace_placeholders(self.body_html or "", ctx)
        footer = self._replace_placeholders(self.footer_html or "", ctx)

        # Append CSS assets
        css_blocks = [a.css or "" for a in self.asset_ids if a.active]
        css_bundle = "\n".join(css_blocks)
        css_wrap = f"<style>{css_bundle}</style>" if css_bundle else ""

        # Final HTML
        html = f"""
        <div class="cim-report">
          {css_wrap}
          <div class="cim-header">{header}</div>
          <div class="cim-body">{body}</div>
          <div class="cim-footer">{footer}</div>
        </div>
        """
        return html

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_preview_with_result(self, result_id=None):
        """
        Preview this template with a selected Result in the standard PDF report.
        Requires the report action:
          - clinic_imaging.report_clinical_imaging_result
        The actual QWeb will read result.report_template_id or context override below.
        """
        self.ensure_one()
        if not result_id:
            raise UserError(_("Please provide a Clinical Imaging Result to preview with this template."))
        result = self.env["clinical.imaging.result"].browse(result_id).exists()
        if not result:
            raise UserError(_("The provided Result was not found."))
        # temporarily force template via context so QWeb can use it
        action = self.env.ref("clinic_imaging.report_clinical_imaging_result", raise_if_not_found=False)
        if not action:
            raise UserError(_("Report action 'clinic_imaging.report_clinical_imaging_result' not found."))
        ctx = dict(self.env.context or {})
        ctx["force_report_template_id"] = self.id
        return action.with_context(ctx).report_action(result)


# =============================================================================
# Report Template Sections
# =============================================================================
class ClinicalImagingReportTemplateSection(models.Model):
    _name = "clinical.imaging.report.template.section"
    _description = "Imaging Report Template Section"
    _order = "template_id, sequence, id"
    _check_company_auto = True

    template_id = fields.Many2one(
        "clinical.imaging.report.template", string="Template",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="template_id.company_id", store=True, readonly=True
    )

    active = fields.Boolean(default=True)
    sequence = fields.Integer(string="Sequence", default=10)
    code = fields.Char(string="Code", help="Short code used for CSS hooks or references.")
    title = fields.Char(string="Title", help="Optional section title (e.g., 'Technique', 'Findings').")
    body_html = fields.Html(
        string="Body (HTML)", sanitize=False,
        help="HTML with ${placeholders}. Example: '<p>${technique}</p>'."
    )
    condition_expr = fields.Char(
        string="Condition (safe_eval)",
        help="Python expression evaluated with 'ctx' dict. If True, the section is shown. "
             "Example: 'ctx.get(\"finding_count\",0) > 0'."
    )

    @api.constrains("condition_expr")
    def _check_condition_expr(self):
        # Try a dry-run with empty ctx to catch syntax errors early.
        for rec in self:
            if rec.condition_expr:
                try:
                    safe_eval(rec.condition_expr, {"ctx": {}}, nocopy=True)
                except Exception as e:
                    raise ValidationError(_("Invalid condition expression: %s") % str(e))


# =============================================================================
# Report Template Variables
# =============================================================================
class ClinicalImagingReportTemplateVariable(models.Model):
    _name = "clinical.imaging.report.template.variable"
    _description = "Imaging Report Template Variable"
    _order = "template_id, sequence, id"
    _check_company_auto = True

    template_id = fields.Many2one(
        "clinical.imaging.report.template", string="Template",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="template_id.company_id", store=True, readonly=True
    )

    sequence = fields.Integer(string="Sequence", default=10)
    code = fields.Char(
        string="Variable Code", required=True,
        help="Name used as ${code} in placeholders."
    )
    expr = fields.Text(
        string="Expression (safe_eval)", required=True,
        help="Python expression evaluated with 'ctx' dict. "
             "Result will be injected into placeholders as ${code}. "
             "Example: 'f\"Age: {ctx.get('patient_age_years','')} years\"'"
    )
    description = fields.Char(string="Description")
    active = fields.Boolean(default=True)

    _code_template_unique = models.Constraint(
        'unique(code, template_id)',
        'Variable Code must be unique per template.',
    )


# =============================================================================
# Report Template Assets (CSS)
# =============================================================================
class ClinicalImagingReportTemplateAsset(models.Model):
    _name = "clinical.imaging.report.template.asset"
    _description = "Imaging Report Template Asset"
    _order = "template_id, sequence, id"
    _check_company_auto = True

    template_id = fields.Many2one(
        "clinical.imaging.report.template", string="Template",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="template_id.company_id", store=True, readonly=True
    )

    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Asset Name", required=True)
    css = fields.Text(string="CSS", help="Raw CSS to include inside <style>...</style>.")
    active = fields.Boolean(default=True)


# =============================================================================
# Extensions on Result: defaulting & rendering helpers
# =============================================================================
# class ClinicalImagingResult(models.Model):
#     _inherit = "clinical.imaging.result"

#     report_template_id = fields.Many2one(
#         "clinical.imaging.report.template",
#         string="Report Template",
#         help="Template used to render this result. "
#              "Defaults from Imaging Type or company default.",
#     )

#     @api.onchange("imaging_id")
#     def _onchange_imaging_set_default_template(self):
#         for rec in self:
#             if rec.report_template_id:
#                 continue
#             tmpl = rec._get_default_report_template()
#             if tmpl:
#                 rec.report_template_id = tmpl.id

#     def _get_default_report_template(self):
#         """Resolve default template by priority:
#            1) Imaging Type's default report_template_id (if set in type)
#            2) Company default template (is_default_company)
#            3) Any template filtered by modality
#         """
#         self.ensure_one()
#         imaging = self.imaging_id
#         # from type
#         if imaging and imaging.imaging_type_id and imaging.imaging_type_id.report_template_id:
#             return imaging.imaging_type_id.report_template_id
#         # company default
#         tmpl = self.env["clinical.imaging.report.template"].search([
#             ("company_id", "=", self.company_id.id),
#             ("is_default_company", "=", True),
#             ("active", "=", True),
#         ], limit=1, order="sequence, id")
#         if tmpl:
#             return tmpl
#         # modality match
#         modality = imaging.imaging_type_id.modality if imaging and imaging.imaging_type_id else False
#         if modality:
#             tmpl = self.env["clinical.imaging.report.template"].search([
#                 ("company_id", "=", self.company_id.id),
#                 ("modality", "=", modality),
#                 ("active", "=", True),
#             ], limit=1, order="sequence, id")
#             if tmpl:
#                 return tmpl
#         # fallback any active
#         return self.env["clinical.imaging.report.template"].search([
#             ("company_id", "=", self.company_id.id),
#             ("active", "=", True),
#         ], limit=1, order="sequence, id")

#     def action_preview_current_template(self):
#         """Preview currently selected template using standard PDF report."""
#         self.ensure_one()
#         if not self.report_template_id:
#             tmpl = self._get_default_report_template()
#             if tmpl:
#                 self.report_template_id = tmpl.id
#         report = self.env.ref("clinic_imaging.report_clinical_imaging_result", raise_if_not_found=False)
#         if not report:
#             raise UserError(_("Report action 'clinic_imaging.report_clinical_imaging_result' not found."))
#         return report.report_action(self)

#     # Expose HTML (useful for portal/wizard)
#     def get_rendered_html(self):
#         """Return the HTML string produced by the selected template."""
#         self.ensure_one()
#         tmpl = self.report_template_id or self._get_default_report_template()
#         if not tmpl:
#             raise UserError(_("No report template available for rendering."))
#         return tmpl.render_html_from_template(self)


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
from collections import defaultdict
import math


# =============================================================================
# Helpers (mixins / utilities)
# =============================================================================
class _KPIHelpersMixin(models.AbstractModel):
    _name = "clinical.imaging.kpi.helpers.mixin"
    _description = "Imaging KPI Helpers Mixin"

    # ---------- generic helpers ----------
    def _has_model(self, model_name):
        return model_name in self.env

    def _has_field(self, model_name, field_name):
        try:
            return field_name in self.env[model_name]._fields
        except Exception:
            return False

    def _dt_in_range(self, dt, start, end):
        if not dt:
            return False
        return (dt >= start) and (dt <= end)

    def _hours_between(self, dt_start, dt_end):
        if not dt_start or not dt_end:
            return 0.0
        delta = fields.Datetime.to_datetime(dt_end) - fields.Datetime.to_datetime(dt_start)
        return max(0.0, round(delta.total_seconds() / 3600.0, 4))

    def _avg(self, values):
        vals = [v for v in values if isinstance(v, (int, float))]
        return (sum(vals) / len(vals)) if vals else 0.0

    def _sum(self, values):
        vals = [v for v in values if isinstance(v, (int, float))]
        return sum(vals) if vals else 0.0

    def _safe_search(self, model, domain, fields_list=None, limit=0, order=None):
        """Search + read raw dict list safely."""
        recs = self.env[model].sudo().search(domain, limit=limit, order=order)
        if fields_list:
            return recs.read(fields_list)
        return recs

    def _overlap_hours(self, start_a, end_a, start_b, end_b):
        """Duration (hours) overlapping between [a] and [b]."""
        if not start_a or not end_a or not start_b or not end_b:
            return 0.0
        a1 = fields.Datetime.to_datetime(start_a)
        a2 = fields.Datetime.to_datetime(end_a)
        b1 = fields.Datetime.to_datetime(start_b)
        b2 = fields.Datetime.to_datetime(end_b)
        if a2 <= b1 or a1 >= b2:
            return 0.0
        s = max(a1, b1)
        e = min(a2, b2)
        if e <= s:
            return 0.0
        return (e - s).total_seconds() / 3600.0


# =============================================================================
# KPI Snapshot (periodic aggregation)
# =============================================================================
class ClinicalImagingKpiSnapshot(models.Model, _KPIHelpersMixin):
    _name = "clinical.imaging.kpi.snapshot"
    _description = "Clinical Imaging KPI Snapshot"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Period
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Name", required=True, copy=False,
        default=lambda s: _("New"),
        help="Display name for this KPI snapshot (auto-filled on compute).",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company", string="Company", required=True,
        default=lambda s: s.env.company, index=True
    )
    period = fields.Selection(
        [
            ("day", "Day"),
            ("week", "Week"),
            ("month", "Month"),
            ("custom", "Custom"),
        ],
        string="Period", default="day", required=True, tracking=True
    )
    date_start = fields.Datetime(string="Start Datetime", required=True, tracking=True)
    date_end = fields.Datetime(string="End Datetime", required=True, tracking=True)

    active = fields.Boolean(default=True)
    notes = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # Volume / Workflow counts
    # -------------------------------------------------------------------------
    request_count = fields.Integer(string="Requests", help="Imaging requests created within the period.")
    request_cancelled = fields.Integer(string="Requests Cancelled")
    imaging_count = fields.Integer(string="Imaging Records", help="Imaging records involved in the period.")
    study_count = fields.Integer(string="Studies Acquired", help="DICOM studies acquired in the period.")
    series_count = fields.Integer(string="Series Acquired", help="Series created in the period.")
    image_count = fields.Integer(string="Images Instances", help="DICOM instances or rendered images in the period.")
    result_created = fields.Integer(string="Results Created")
    result_final = fields.Integer(string="Results Finalized")
    backlog_open_requests = fields.Integer(string="Backlog: Open Requests", help="Requests not completed/cancelled at period end.")
    backlog_pending_reports = fields.Integer(string="Backlog: Pending Reports", help="Results not yet final at period end.")

    # -------------------------------------------------------------------------
    # Turn-Around-Time (hours)
    # -------------------------------------------------------------------------
    tat_order_to_acq_avg_h = fields.Float(string="Avg TAT Order→Acquisition (h)")
    tat_acq_to_sign_avg_h = fields.Float(string="Avg TAT Acquisition→Sign (h)")
    tat_total_order_to_sign_avg_h = fields.Float(string="Avg TAT Order→Sign (h)")

    # -------------------------------------------------------------------------
    # Device & QC
    # -------------------------------------------------------------------------
    device_count = fields.Integer(string="Devices Tracked")
    device_downtime_h = fields.Float(string="Total Downtime (h) in Period")
    device_uptime_ratio = fields.Float(
        string="Uptime Ratio (period)", help="Approx uptime ratio across devices in this period (0..1)."
    )
    device_qc_due = fields.Integer(string="QC Due", help="Devices with QC due within the period.")
    device_qc_overdue = fields.Integer(string="QC Overdue at End")

    # -------------------------------------------------------------------------
    # Dose / Exposure (aggregates from Series)
    # -------------------------------------------------------------------------
    avg_ctdi_vol_mgy = fields.Float(string="Avg CTDIvol (mGy)")
    avg_dlp_mgy_cm = fields.Float(string="Avg DLP (mGy·cm)")
    total_dap_gy_cm2 = fields.Float(string="Total DAP (Gy·cm²)")
    total_fluoro_time_min = fields.Float(string="Total Fluoro Time (min)")

    # -------------------------------------------------------------------------
    # Billing (optional, safe if linked)
    # -------------------------------------------------------------------------
    currency_id = fields.Many2one(
        "res.currency", string="Currency",
        default=lambda s: s.env.company.currency_id.id
    )
    invoice_count = fields.Integer(string="Invoices (Imaging)")
    invoice_amount_total = fields.Monetary(string="Total Invoiced")
    avg_days_to_invoice = fields.Float(string="Avg Days to Invoice")

    # -------------------------------------------------------------------------
    # Lines (modality / device / radiologist)
    # -------------------------------------------------------------------------
    modality_line_ids = fields.One2many(
        "clinical.imaging.kpi.modality.line", "snapshot_id",
        string="Modality Lines", copy=True
    )
    device_line_ids = fields.One2many(
        "clinical.imaging.kpi.device.line", "snapshot_id",
        string="Device Lines", copy=True
    )
    radiologist_line_ids = fields.One2many(
        "clinical.imaging.kpi.radiologist.line", "snapshot_id",
        string="Radiologist Lines", copy=True
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_end <= rec.date_start:
                raise ValidationError(_("End Datetime must be after Start Datetime."))

    # -------------------------------------------------------------------------
    # Compute / Recompute
    # -------------------------------------------------------------------------
    def action_recompute(self):
        """Recompute all KPI fields and lines for this snapshot."""
        for snap in self:
            snap._compute_all_metrics()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            # auto-fill name then compute
            rec.name = rec._make_display_name()
            rec.action_recompute()
        return recs

    def write(self, vals):
        res = super().write(vals)
        # If period or dates change, recompute
        trigger = any(k in vals for k in ["date_start", "date_end", "period", "company_id"])
        if trigger:
            for rec in self:
                rec.name = rec._make_display_name()
                rec.action_recompute()
        return res

    def _make_display_name(self):
        self.ensure_one()
        start = fields.Datetime.to_string(self.date_start)
        end = fields.Datetime.to_string(self.date_end)
        return f"KPI {self.period.upper()} [{start} → {end}]"

    # ---------- core computation ----------
    def _compute_all_metrics(self):
        self.ensure_one()
        start = self.date_start
        end = self.date_end
        company = self.company_id

        # reset lines
        self.modality_line_ids.unlink()
        self.device_line_ids.unlink()
        self.radiologist_line_ids.unlink()

        # --- Requests ---
        self._compute_requests(company, start, end)

        # --- Studies/Series/Images volume ---
        self._compute_acquisition_volume(company, start, end)

        # --- Results & TAT ---
        self._compute_results_and_tat(company, start, end)

        # --- Devices & QC & Downtime ---
        self._compute_device_metrics(company, start, end)

        # --- Dose / Exposure from Series ---
        self._compute_dose_metrics(company, start, end)

        # --- Billing (if linked) ---
        self._compute_billing_metrics(company, start, end)

        # --- Lines: Modality/Device/Radiologist ---
        self._build_modality_lines(company, start, end)
        self._build_device_lines(company, start, end)
        self._build_radiologist_lines(company, start, end)

    # ------------------- Requests -------------------
    def _compute_requests(self, company, start, end):
        if not self._has_model("clinical.imaging.request"):
            self.request_count = 0
            self.request_cancelled = 0
            self.backlog_open_requests = 0
            return

        Req = self.env["clinical.imaging.request"].sudo().with_context(active_test=False)
        # assume 'request_datetime' if exists, else fallback to create_date
        dt_field = "request_datetime" if self._has_field("clinical.imaging.request", "request_datetime") else "create_date"
        state_field = "state" if self._has_field("clinical.imaging.request", "state") else None

        req_in_period = Req.search([
            ("company_id", "=", company.id),
            (dt_field, ">=", start),
            (dt_field, "<=", end),
        ])
        self.request_count = len(req_in_period)

        # cancellations in the period (state == cancelled with write_date in range OR cancel_datetime)
        if state_field:
            cancelled_domain = [("company_id", "=", company.id), (state_field, "in", ["cancelled", "canceled", "void"])]
            if self._has_field("clinical.imaging.request", "cancel_datetime"):
                cancelled_domain += [("cancel_datetime", ">=", start), ("cancel_datetime", "<=", end)]
            else:
                cancelled_domain += [("write_date", ">=", start), ("write_date", "<=", end)]
            self.request_cancelled = Req.search_count(cancelled_domain)
            # backlog at end: not finished/cancelled
            open_states = ["draft", "submitted", "approved", "scheduled", "in_progress"]
            backlog_domain = [("company_id", "=", company.id), (state_field, "in", open_states)]
            self.backlog_open_requests = Req.search_count(backlog_domain)
        else:
            self.request_cancelled = 0
            self.backlog_open_requests = 0

    # ------------------- Acquisition volume -------------------
    def _compute_acquisition_volume(self, company, start, end):
        # Studies
        if self._has_model("clinical.imaging.study"):
            Study = self.env["clinical.imaging.study"].sudo().with_context(active_test=False)
            study_recs = Study.search([
                ("company_id", "=", company.id),
                ("study_datetime", ">=", start),
                ("study_datetime", "<=", end),
            ])
            self.study_count = len(study_recs)
        else:
            study_recs = self.env["clinical.imaging.study"]  # empty
            self.study_count = 0

        # Series
        if self._has_model("clinical.imaging.series"):
            Series = self.env["clinical.imaging.series"].sudo().with_context(active_test=False)
            series_recs = Series.search([
                ("company_id", "=", company.id),
                ("series_datetime", ">=", start),
                ("series_datetime", "<=", end),
            ])
            self.series_count = len(series_recs)
        else:
            series_recs = self.env["clinical.imaging.series"]
            self.series_count = 0

        # Images
        if self._has_model("clinical.imaging.image"):
            Image = self.env["clinical.imaging.image"].sudo().with_context(active_test=False)
            # use acquisition_datetime if present else create_date
            dt_field = "acquisition_datetime" if self._has_field("clinical.imaging.image", "acquisition_datetime") else "create_date"
            image_recs = Image.search([
                ("company_id", "=", company.id),
                (dt_field, ">=", start),
                (dt_field, "<=", end),
            ])
            self.image_count = len(image_recs)
        else:
            image_recs = self.env["clinical.imaging.image"]
            self.image_count = 0

        # Imaging (parent) approximate involvement count: distinct imaging_id from studies
        imaging_ids = set()
        if study_recs:
            imaging_ids.update(study_recs.mapped("imaging_id").ids)
        elif series_recs:
            imaging_ids.update(series_recs.mapped("imaging_id").ids)
        self.imaging_count = len(imaging_ids)

    # ------------------- Results & TAT -------------------
    def _compute_results_and_tat(self, company, start, end):
        if not self._has_model("clinical.imaging.result"):
            self.result_created = 0
            self.result_final = 0
            self.backlog_pending_reports = 0
            self.tat_order_to_acq_avg_h = 0.0
            self.tat_acq_to_sign_avg_h = 0.0
            self.tat_total_order_to_sign_avg_h = 0.0
            return

        Result = self.env["clinical.imaging.result"].sudo().with_context(active_test=False)

        # create count in period (using create_date)
        created_cnt = Result.search_count([
            ("company_id", "=", company.id),
            ("create_date", ">=", start),
            ("create_date", "<=", end),
        ])
        self.result_created = created_cnt

        # finalized in period: states final/amended and signed_datetime in range
        state_field = "state" if self._has_field("clinical.imaging.result", "state") else None
        signed_field = "signed_datetime" if self._has_field("clinical.imaging.result", "signed_datetime") else None
        if state_field and signed_field:
            final_states = ["final", "amended"]
            final_cnt = Result.search_count([
                ("company_id", "=", company.id),
                (state_field, "in", final_states),
                (signed_field, ">=", start),
                (signed_field, "<=", end),
            ])
            self.result_final = final_cnt
            # backlog: not final at end
            pending_states = ["draft", "in_review", "preliminary", "verified", "approved"]
            self.backlog_pending_reports = Result.search_count([
                ("company_id", "=", company.id),
                (state_field, "in", pending_states),
            ])
        else:
            self.result_final = 0
            self.backlog_pending_reports = 0

        # TATs: Order→Acquisition, Acquisition→Sign, Total
        # Derive events:
        # - order: from clinical.imaging.request.request_datetime (fallback: create_date)
        # - acquisition: earliest study_datetime per imaging within period
        # - sign: result.signed_datetime
        order_times = {}
        if self._has_model("clinical.imaging.request"):
            Req = self.env["clinical.imaging.request"].sudo()
            dt_field = "request_datetime" if self._has_field("clinical.imaging.request", "request_datetime") else "create_date"
            reqs = Req.search([("company_id", "=", company.id), (dt_field, "!=", False)], limit=0)
            for r in reqs:
                key = r.imaging_id.id if self._has_field("clinical.imaging.request", "imaging_id") else (r.id,)
                order_times[key] = getattr(r, dt_field)

        # acquisition: earliest study per imaging within global index (not only in-period, to allow cross-period TAT)
        acq_times = {}
        if self._has_model("clinical.imaging.study"):
            Study = self.env["clinical.imaging.study"].sudo()
            st = Study.search([("company_id", "=", company.id), ("study_datetime", "!=", False)], limit=0, order="study_datetime asc")
            for s in st:
                img_id = s.imaging_id.id
                if img_id and img_id not in acq_times:
                    acq_times[img_id] = s.study_datetime

        # sign times for results within the period (to stabilize sample)
        sign_times = {}
        signed_results = Result.search([
            ("company_id", "=", company.id),
            ("signed_datetime", ">=", start),
            ("signed_datetime", "<=", end),
            ("signed_datetime", "!=", False),
        ], order="signed_datetime asc")
        for rs in signed_results:
            sign_times[rs.imaging_id.id if rs.imaging_id else rs.id] = rs.signed_datetime

        # compute arrays
        arr_order_acq = []
        arr_acq_sign = []
        arr_order_sign = []
        for key, sign_dt in sign_times.items():
            # key is imaging_id
            order_dt = order_times.get(key) if isinstance(key, int) else None
            acq_dt = acq_times.get(key)
            if order_dt and acq_dt:
                arr_order_acq.append(self._hours_between(order_dt, acq_dt))
                arr_order_sign.append(self._hours_between(order_dt, sign_dt))
            if acq_dt:
                arr_acq_sign.append(self._hours_between(acq_dt, sign_dt))

        self.tat_order_to_acq_avg_h = round(self._avg(arr_order_acq), 2) if arr_order_acq else 0.0
        self.tat_acq_to_sign_avg_h = round(self._avg(arr_acq_sign), 2) if arr_acq_sign else 0.0
        self.tat_total_order_to_sign_avg_h = round(self._avg(arr_order_sign), 2) if arr_order_sign else 0.0

    # ------------------- Devices & QC -------------------
    def _compute_device_metrics(self, company, start, end):
        if not self._has_model("clinical.imaging.device"):
            self.device_count = 0
            self.device_downtime_h = 0.0
            self.device_uptime_ratio = 1.0
            self.device_qc_due = 0
            self.device_qc_overdue = 0
            return

        Device = self.env["clinical.imaging.device"].sudo().with_context(active_test=False)
        devices = Device.search([("company_id", "=", company.id)], limit=0)
        self.device_count = len(devices)

        # Downtime in period
        downtime_h = 0.0
        qc_due = 0
        qc_over = 0

        # Device downtime model
        if self._has_model("clinical.imaging.device.downtime"):
            Downtime = self.env["clinical.imaging.device.downtime"].sudo()
            for d in devices:
                dts = Downtime.search([("device_id", "=", d.id), ("state", "=", "closed")])
                for row in dts:
                    dur = self._overlap_hours(row.start_datetime, row.end_datetime or fields.Datetime.now(), start, end)
                    downtime_h += dur

        # QC due / overdue within or at end of period
        if self._has_field("clinical.imaging.device", "next_qc_date"):
            for d in devices:
                if d.next_qc_date:
                    # due if next_qc_date is within [start, end]
                    if d.next_qc_date >= fields.Date.to_date(start) and d.next_qc_date <= fields.Date.to_date(end):
                        qc_due += 1
                    # overdue at the end
                    if d.next_qc_date < fields.Date.to_date(end):
                        qc_over += 1

        self.device_downtime_h = round(downtime_h, 2)
        period_hours = max(1.0, (fields.Datetime.to_datetime(end) - fields.Datetime.to_datetime(start)).total_seconds() / 3600.0)
        # uptime ratio = 1 - (downtime / (period_hours * device_count))
        denom = period_hours * max(1, self.device_count)
        uptime_ratio = 1.0 - (downtime_h / denom)
        self.device_uptime_ratio = round(max(0.0, min(1.0, uptime_ratio)), 3)
        self.device_qc_due = qc_due
        self.device_qc_overdue = qc_over

    # ------------------- Dose / Exposure (Series) -------------------
    def _compute_dose_metrics(self, company, start, end):
        if not self._has_model("clinical.imaging.series"):
            self.avg_ctdi_vol_mgy = 0.0
            self.avg_dlp_mgy_cm = 0.0
            self.total_dap_gy_cm2 = 0.0
            self.total_fluoro_time_min = 0.0
            return

        Series = self.env["clinical.imaging.series"].sudo()
        series = Series.search([
            ("company_id", "=", company.id),
            ("series_datetime", ">=", start),
            ("series_datetime", "<=", end),
        ], limit=0)

        ctdi_vals = []
        dlp_vals = []
        dap_vals = []
        fl_time_vals = []

        for s in series:
            if s.ctdi_vol_mgy is not None and s.ctdi_vol_mgy >= 0:
                ctdi_vals.append(s.ctdi_vol_mgy)
            if s.dlp_mgy_cm is not None and s.dlp_mgy_cm >= 0:
                dlp_vals.append(s.dlp_mgy_cm)
            if s.dap_gy_cm2 is not None and s.dap_gy_cm2 >= 0:
                dap_vals.append(s.dap_gy_cm2)
            if s.fluoro_time_min is not None and s.fluoro_time_min >= 0:
                fl_time_vals.append(s.fluoro_time_min)

        self.avg_ctdi_vol_mgy = round(self._avg(ctdi_vals), 2) if ctdi_vals else 0.0
        self.avg_dlp_mgy_cm = round(self._avg(dlp_vals), 2) if dlp_vals else 0.0
        self.total_dap_gy_cm2 = round(self._sum(dap_vals), 2) if dap_vals else 0.0
        self.total_fluoro_time_min = round(self._sum(fl_time_vals), 2) if fl_time_vals else 0.0

    # ------------------- Billing (optional) -------------------
    def _compute_billing_metrics(self, company, start, end):
        # This block is safe: if account.move or linking fields are absent, return zeros.
        self.invoice_count = 0
        self.invoice_amount_total = 0.0
        self.avg_days_to_invoice = 0.0

        if not self._has_model("account.move"):
            return

        Move = self.env["account.move"].sudo()
        # We try to detect a link field from imaging to invoice
        link_field = None
        for fname in ["clinical_imaging_id", "clinic_imaging_id", "imaging_id"]:
            if self._has_field("account.move", fname):
                link_field = fname
                break

        domain = [("company_id", "=", company.id), ("move_type", "in", ["out_invoice", "out_refund"]),
                  ("state", "=", "posted"), ("invoice_date", ">=", fields.Date.to_date(start)),
                  ("invoice_date", "<=", fields.Date.to_date(end))]
        if link_field:
            # keep only invoices that reference imaging records
            domain.append((link_field, "!=", False))
        moves = Move.search(domain, limit=0)

        self.invoice_count = len(moves)
        self.invoice_amount_total = sum(m.amount_total_signed for m in moves)

        # Avg days from acquisition to invoice (if we can find an imaging & earliest study)
        if link_field and self._has_model("clinical.imaging.study"):
            Study = self.env["clinical.imaging.study"].sudo()
            deltas = []
            for mv in moves:
                img = getattr(mv, link_field, False)
                if not img:
                    continue
                # earliest study
                studies = Study.search([("imaging_id", "=", img.id)], limit=1, order="study_datetime asc")
                if studies and mv.invoice_date:
                    dt_acq = fields.Datetime.to_datetime(studies.study_datetime)
                    dt_inv = datetime.combine(mv.invoice_date, datetime.min.time())
                    delta_days = max(0.0, (dt_inv - dt_acq).total_seconds() / 86400.0)
                    deltas.append(delta_days)
            self.avg_days_to_invoice = round(self._avg(deltas), 2) if deltas else 0.0

    # ------------------- Modality Lines -------------------
    def _build_modality_lines(self, company, start, end):
        if not self._has_model("clinical.imaging.study"):
            return
        Study = self.env["clinical.imaging.study"].sudo()
        Result = self.env["clinical.imaging.result"].sudo() if self._has_model("clinical.imaging.result") else None

        # group studies per modality
        studies = Study.search([
            ("company_id", "=", company.id),
            ("study_datetime", ">=", start),
            ("study_datetime", "<=", end),
        ], limit=0)
        grp = defaultdict(list)
        for st in studies:
            grp[st.modality or "OT"].append(st)

        for modality, items in grp.items():
            count_study = len(items)
            # final results linked to these imaging
            final_cnt = 0
            tat_h = []
            if Result:
                for st in items:
                    res = Result.search([
                        ("imaging_id", "=", st.imaging_id.id),
                        ("state", "in", ["final", "amended"]),
                        ("signed_datetime", ">=", start),
                        ("signed_datetime", "<=", end),
                    ], limit=1, order="signed_datetime desc")
                    if res:
                        final_cnt += 1
                        tat_h.append(self._hours_between(st.study_datetime, res.signed_datetime))
            self.env["clinical.imaging.kpi.modality.line"].create({
                "snapshot_id": self.id,
                "modality": modality,
                "study_count": count_study,
                "result_final_count": final_cnt,
                "tat_acq_to_sign_avg_h": round(self._avg(tat_h), 2) if tat_h else 0.0,
            })

    # ------------------- Device Lines -------------------
    def _build_device_lines(self, company, start, end):
        if not self._has_model("clinical.imaging.device"):
            return
        Device = self.env["clinical.imaging.device"].sudo()
        Study = self.env["clinical.imaging.study"].sudo() if self._has_model("clinical.imaging.study") else None
        Downtime = self.env["clinical.imaging.device.downtime"].sudo() if self._has_model("clinical.imaging.device.downtime") else None

        devices = Device.search([("company_id", "=", company.id)], limit=0)
        for d in devices:
            study_cnt = 0
            if Study:
                study_cnt = Study.search_count([
                    ("device_id", "=", d.id),
                    ("study_datetime", ">=", start),
                    ("study_datetime", "<=", end),
                ])
            # downtime hours overlap in period
            dt_h = 0.0
            if Downtime:
                dts = Downtime.search([("device_id", "=", d.id), ("state", "=", "closed")])
                for row in dts:
                    dt_h += self._overlap_hours(row.start_datetime, row.end_datetime or fields.Datetime.now(), start, end)
            # utilization naive: studies per hour capacity (throughput * hours)
            hours = max(1.0, (fields.Datetime.to_datetime(end) - fields.Datetime.to_datetime(start)).total_seconds() / 3600.0)
            capacity = (d.throughput_per_hour or 0.0) * hours
            utilization = (study_cnt / capacity) if capacity > 0 else 0.0
            self.env["clinical.imaging.kpi.device.line"].create({
                "snapshot_id": self.id,
                "device_id": d.id,
                "modality": d.modality,
                "study_count": study_cnt,
                "downtime_h": round(dt_h, 2),
                "utilization_ratio": round(max(0.0, min(1.0, utilization)), 3),
                "qc_status": getattr(d, "qc_status", False) or "ok",
            })

    # ------------------- Radiologist Lines -------------------
    def _build_radiologist_lines(self, company, start, end):
        if not self._has_model("clinical.imaging.result"):
            return
        Result = self.env["clinical.imaging.result"].sudo()
        Study = self.env["clinical.imaging.study"].sudo() if self._has_model("clinical.imaging.study") else None

        # all results signed in period, grouped by author radiologist
        results = Result.search([
            ("company_id", "=", company.id),
            ("signed_datetime", ">=", start),
            ("signed_datetime", "<=", end),
            ("signed_datetime", "!=", False),
            ("author_doctor_id", "!=", False),
        ], limit=0)

        per_rad_counts = defaultdict(int)
        per_rad_tat = defaultdict(list)

        for res in results:
            per_rad_counts[res.author_doctor_id.id] += 1
            # TAT acquisition->sign: use earliest study for that imaging (if exists)
            tat_h = 0.0
            if Study and res.imaging_id:
                st = Study.search([("imaging_id", "=", res.imaging_id.id)], limit=1, order="study_datetime asc")
                if st:
                    tat_h = self._hours_between(st.study_datetime, res.signed_datetime)
            if tat_h:
                per_rad_tat[res.author_doctor_id.id].append(tat_h)

        for rad_id, cnt in per_rad_counts.items():
            self.env["clinical.imaging.kpi.radiologist.line"].create({
                "snapshot_id": self.id,
                "radiologist_id": rad_id,
                "result_signed": cnt,
                "tat_acq_to_sign_avg_h": round(self._avg(per_rad_tat.get(rad_id, [])), 2),
            })

    # -------------------------------------------------------------------------
    # Drill-down Actions
    # -------------------------------------------------------------------------
    def _action_window(self, name, res_model, domain, view_mode="list,form"):
        self.ensure_one()
        return {
            "name": name,
            "type": "ir.actions.act_window",
            "res_model": res_model,
            "view_mode": view_mode,
            "domain": domain,
            "target": "current",
            "context": {},
        }

    def action_open_results_finalized(self):
        self.ensure_one()
        if not self._has_model("clinical.imaging.result"):
            raise UserError(_("Imaging Result model is not available."))
        domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "in", ["final", "amended"]),
            ("signed_datetime", ">=", self.date_start),
            ("signed_datetime", "<=", self.date_end),
        ]
        return self._action_window(_("Finalized Results"), "clinical.imaging.result", domain)

    def action_open_studies(self):
        self.ensure_one()
        if not self._has_model("clinical.imaging.study"):
            raise UserError(_("Imaging Study model is not available."))
        domain = [
            ("company_id", "=", self.company_id.id),
            ("study_datetime", ">=", self.date_start),
            ("study_datetime", "<=", self.date_end),
        ]
        return self._action_window(_("Studies in Period"), "clinical.imaging.study", domain, view_mode="list,form,kanban")

    def action_open_series(self):
        self.ensure_one()
        if not self._has_model("clinical.imaging.series"):
            raise UserError(_("Imaging Series model is not available."))
        domain = [
            ("company_id", "=", self.company_id.id),
            ("series_datetime", ">=", self.date_start),
            ("series_datetime", "<=", self.date_end),
        ]
        return self._action_window(_("Series in Period"), "clinical.imaging.series", domain)

    def action_open_device_downtime(self):
        self.ensure_one()
        if not self._has_model("clinical.imaging.device.downtime"):
            raise UserError(_("Device Downtime model is not available."))
        domain = [
            ("device_id.company_id", "=", self.company_id.id),
            ("state", "=", "closed"),
            ("end_datetime", ">=", self.date_start),
            ("start_datetime", "<=", self.date_end),
        ]
        return self._action_window(_("Device Downtime (overlap period)"), "clinical.imaging.device.downtime", domain)


# =============================================================================
# Lines - Modality
# =============================================================================
class ClinicalImagingKpiModalityLine(models.Model):
    _name = "clinical.imaging.kpi.modality.line"
    _description = "Imaging KPI Modality Line"
    _order = "snapshot_id, modality"
    _check_company_auto = True

    snapshot_id = fields.Many2one(
        "clinical.imaging.kpi.snapshot", string="Snapshot",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="snapshot_id.company_id", store=True, readonly=True
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
        string="Modality", required=True
    )
    study_count = fields.Integer(string="Studies")
    result_final_count = fields.Integer(string="Finalized Results")
    tat_acq_to_sign_avg_h = fields.Float(string="Avg TAT Acq→Sign (h)")


# =============================================================================
# Lines - Device
# =============================================================================
class ClinicalImagingKpiDeviceLine(models.Model):
    _name = "clinical.imaging.kpi.device.line"
    _description = "Imaging KPI Device Line"
    _order = "snapshot_id, device_id"
    _check_company_auto = True

    snapshot_id = fields.Many2one(
        "clinical.imaging.kpi.snapshot", string="Snapshot",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="snapshot_id.company_id", store=True, readonly=True
    )
    device_id = fields.Many2one("clinical.imaging.device", string="Device", required=True)
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
    study_count = fields.Integer(string="Studies")
    downtime_h = fields.Float(string="Downtime (h)")
    utilization_ratio = fields.Float(string="Utilization Ratio (0..1)")
    qc_status = fields.Selection(
        [("ok", "OK"), ("due", "Due"), ("overdue", "Overdue")],
        string="QC Status"
    )


# =============================================================================
# Lines - Radiologist Productivity
# =============================================================================
class ClinicalImagingKpiRadiologistLine(models.Model):
    _name = "clinical.imaging.kpi.radiologist.line"
    _description = "Imaging KPI Radiologist Line"
    _order = "snapshot_id, result_signed desc"
    _check_company_auto = True

    snapshot_id = fields.Many2one(
        "clinical.imaging.kpi.snapshot", string="Snapshot",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="snapshot_id.company_id", store=True, readonly=True
    )
    radiologist_id = fields.Many2one(
        "hr.employee", string="Radiologist",
        domain=[("is_doctor", "=", True)]
    )
    result_signed = fields.Integer(string="Results Signed")
    tat_acq_to_sign_avg_h = fields.Float(string="Avg TAT Acq→Sign (h)")


# \\\ Pindahan DARI clinical_imaging_report ///
# =============================================================================
# Extensions on Result: defaulting & rendering helpers
# =============================================================================
class ClinicalImagingResult(models.Model):
    _inherit = "clinical.imaging.result"

    report_template_id = fields.Many2one(
        "clinical.imaging.report.template",
        string="Report Template",
        help="Template used to render this result. "
             "Defaults from Imaging Type or company default.",
    )

    @api.onchange("imaging_id")
    def _onchange_imaging_set_default_template(self):
        for rec in self:
            if rec.report_template_id:
                continue
            tmpl = rec._get_default_report_template()
            if tmpl:
                rec.report_template_id = tmpl.id
       
    def action_open_key_images(self):
        self.ensure_one()
        return {
            "name": _("Key Images"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.image",
            "view_mode": "list,form,kanban",
            "domain": [("id", "in", self.key_image_ids.ids)],
            "target": "current",
        }

    def action_open_findings(self):
        self.ensure_one()
        return {
            "name": _("Findings"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.finding",
            "view_mode": "list,form,kanban",
            "domain": [("id", "in", self.finding_ids.ids)],
            "target": "current",
        }

    def action_add_existing_finding(self):
        """Open a chooser to link existing findings for the same imaging."""
        self.ensure_one()
        return {
            "name": _("Add Existing Finding"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.finding",
            "view_mode": "list,form",
            "domain": [("imaging_id", "=", self.imaging_id.id)],
            "target": "current",
            "context": {"default_imaging_id": self.imaging_id.id},
        }

    def _get_default_report_template(self):
        """Resolve default template by priority:
           1) Imaging Type's default report_template_id (if set in type)
           2) Company default template (is_default_company)
           3) Any template filtered by modality
        """
        self.ensure_one()
        imaging = self.imaging_id
        # from type
        if imaging and imaging.imaging_type_id and imaging.imaging_type_id.report_template_id:
            return imaging.imaging_type_id.report_template_id
        # company default
        tmpl = self.env["clinical.imaging.report.template"].search([
            ("company_id", "=", self.company_id.id),
            ("is_default_company", "=", True),
            ("active", "=", True),
        ], limit=1, order="sequence, id")
        if tmpl:
            return tmpl
        # modality match
        modality = imaging.imaging_type_id.modality if imaging and imaging.imaging_type_id else False
        if modality:
            tmpl = self.env["clinical.imaging.report.template"].search([
                ("company_id", "=", self.company_id.id),
                ("modality", "=", modality),
                ("active", "=", True),
            ], limit=1, order="sequence, id")
            if tmpl:
                return tmpl
        # fallback any active
        return self.env["clinical.imaging.report.template"].search([
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
        ], limit=1, order="sequence, id")

    def action_preview_current_template(self):
        """Preview currently selected template using standard PDF report."""
        self.ensure_one()
        if not self.report_template_id:
            tmpl = self._get_default_report_template()
            if tmpl:
                self.report_template_id = tmpl.id
        report = self.env.ref("clinic_imaging.report_clinical_imaging_result", raise_if_not_found=False)
        if not report:
            raise UserError(_("Report action 'clinic_imaging.report_clinical_imaging_result' not found."))
        return report.report_action(self)

    # Expose HTML (useful for portal/wizard)
    def get_rendered_html(self):
        """Return the HTML string produced by the selected template."""
        self.ensure_one()
        tmpl = self.report_template_id or self._get_default_report_template()
        if not tmpl:
            raise UserError(_("No report template available for rendering."))
        return tmpl.render_html_from_template(self)

# =============================================================================
# Clinical Imaging Finding (structured lesion/observation)
# =============================================================================
class ClinicalImagingFindingKpi(models.Model):
    """
    Structured imaging finding (e.g., pulmonary nodule, hepatic lesion, fracture).
    Links to Imaging/Study/Series/Image for provenance, and to Result for reporting.

    Key features:
      - Standardized categorization (benign/suspicious), risk scores (BI-RADS, LI-RADS, PI-RADS, Lung-RADS)
      - Location & laterality, organ/segment
      - Size measurements (long/short axis) + optional detailed measure lines
      - Evolution/trend tracking vs prior (stable/increase/decrease/resolved)
      - Portal visibility with privacy levels
      - Many2many linkage to Results (bidirectional with clinical.imaging.result.finding_ids)
    """
    _inherit = "clinical.imaging.finding"

    result_ids = fields.Many2many(
        "clinical.imaging.result",
        "clinical_imaging_result_finding_rel",
        "finding_id",
        "result_id",
        string="Results",
        help="Results that include this finding.",
    )
    
    # Linking helpers
    def action_add_to_result(self, result_id=None):
        """
        Add this finding to a Result. If result_id not provided, use latest final/amended result.
        """
        Result = self.env["clinical.imaging.result"]
        for rec in self:
            target = False
            if result_id:
                target = Result.browse(result_id).exists()
            elif rec.imaging_id:
                target = Result.search(
                    [("imaging_id", "=", rec.imaging_id.id), ("state", "in", ["final", "amended"])],
                    order="signed_datetime desc, write_date desc, id desc",
                    limit=1,
                )
            if not target:
                raise UserError(_("No target Result found to link this finding."))
            rec.result_ids = [(4, target.id)]
            target.message_post(body=_("Finding %s linked to this Result.") % rec.display_name)


# =============================================================================
# Clinical Imaging Image (DICOM Instance / Rendered Image)
# =============================================================================
class ClinicalImagingImageKpi(models.Model):
    """
    Represents a single DICOM SOP Instance (or a rendered image file) inside a Series.
    Stores DICOM identifiers (SOP Instance UID, SOP Class UID), key pixel metadata,
    display parameters, and binary content (thumbnail/preview and/or original file).

    Integrations:
      - Patient, Appointment, Encounter, Treatment: propagated via Series -> Study -> Imaging.
      - Device/Room: indirect via Study/Series -> Device.
      - Result: images can be marked as key and linked from results.
      - Portal: optional publishing with privacy level.
      - PACS/Viewer: endpoint URL and status hooks.
    """
    _inherit = "clinical.imaging.image"
    
    def action_add_to_result(self, result_id=None):
        """
        Add this image to a Result's key images.
        Requires model 'clinical.imaging.result' to exist (same module).
        """
        Result = self.env["clinical.imaging.result"]
        for rec in self:
            # Find the latest final/amended result for the imaging if none provided
            dest = False
            if result_id:
                dest = Result.browse(result_id).exists()
            else:
                dest = Result.search(
                    [("imaging_id", "=", rec.imaging_id.id), ("state", "in", ["final", "amended"])],
                    order="signed_datetime desc, write_date desc, id desc",
                    limit=1,
                )
            if not dest:
                raise UserError(_("No target Result found to add this image."))
            dest.key_image_ids = [(4, rec.id)]
            rec.message_post(body=_("Image added to Result %s as key image.") % dest.display_name)

# =============================================================================
# Image Annotation (ROIs, measurements, comments)
# =============================================================================
class ClinicalImagingImageAnnotation(models.Model):
    """
    Stores structured annotations attached to an Image:
      - ROI geometry (point/line/rect/circle/polygon/polyline)
      - Optional measurement values and units
      - Optional linkage to a structured finding
    Geometry is stored as JSON (screen/pixel or patient space as provided by the viewer).
    """
    _inherit = "clinical.imaging.image.annotation"

    result_id = fields.Many2one(
        "clinical.imaging.result",
        string="Linked Result",
        help="Optional diagnostic result this annotation belongs to.",
    )

# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import re
import json


# =============================================================================
# Image Tag (classification)
# =============================================================================
class ClinicalImagingImageTag(models.Model):
    _name = "clinical.imaging.image.tag"
    _description = "Clinical Imaging Image Tag"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(string="Tag Name", required=True)
    color = fields.Integer(string="Color Index", help="Color index for kanban/list chips.")
    description = fields.Char(string="Description")
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Image Tag must be unique per company.',
    )


# =============================================================================
# Clinical Imaging Image (DICOM Instance / Rendered Image)
# =============================================================================
class ClinicalImagingImage(models.Model):
    """
    Represents a single DICOM SOP Instance (or a rendered image file) inside a Series.
    Stores DICOM identifiers (SOP Instance UID, SOP Class UID), key pixel metadata,
    display parameters, and binary content (thumbnail/preview and/or original file).

    Integrations:
      - Patient, Appointment, Encounter, Treatment: propagated via Series -> Study -> Imaging.
      - Device/Room: indirect via Study/Series -> Device.
      - Result: images can be marked as key and linked from results.
      - Portal: optional publishing with privacy level.
      - PACS/Viewer: endpoint URL and status hooks.
    """
    _name = "clinical.imaging.image"
    _description = "Clinical Imaging Image"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "instance_number asc, id asc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Image Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
        tracking=True,
        help="Unique identifier generated from sequence at creation time.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="series_id.study_id.company_id",
        store=True,
        readonly=True,
        help="Company derived from the parent Study.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive the image from regular views.",
    )

    # -------------------------------------------------------------------------
    # Core Links & Context (propagated)
    # -------------------------------------------------------------------------
    series_id = fields.Many2one(
        "clinical.imaging.series",
        string="Series",
        required=True,
        ondelete="cascade",
        index=True,
        help="Parent Series that this image belongs to.",
        tracking=True,
    )
    study_id = fields.Many2one(
        "clinical.imaging.study",
        string="Study",
        related="series_id.study_id",
        store=True,
        readonly=True,
    )
    imaging_id = fields.Many2one(
        "clinical.imaging",
        string="Imaging",
        related="study_id.imaging_id",
        store=True,
        readonly=True,
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="study_id.patient_id",
        store=True,
        readonly=True,
    )
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        related="imaging_id.appointment_id",
        store=True,
        readonly=True,
    )
    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     related="imaging_id.encounter_id",
    #     store=True,
    #     readonly=True,
    # )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="imaging_id.treatment_id",
        store=True,
        readonly=True,
    )
    procedure_session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Procedure Session",
        related="imaging_id.procedure_session_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # DICOM Identifiers & Ordering
    # -------------------------------------------------------------------------
    dicom_instance_uid = fields.Char(
        string="DICOM SOP Instance UID",
        copy=False,
        index=True,
        help="Globally unique DICOM SOP Instance UID.",
        tracking=True,
    )
    dicom_sop_class_uid = fields.Char(
        string="DICOM SOP Class UID",
        help="Indicates the SOP Class (e.g., CT Image Storage).",
    )
    instance_number = fields.Integer(
        string="Instance Number (DICOM)",
        help="DICOM InstanceNumber (ordering within the series).",
        index=True,
    )
    frame_count = fields.Integer(
        string="Frame Count",
        help="Number of frames if multi-frame (0/1 for single-frame).",
    )
    acquisition_datetime = fields.Datetime(
        string="Acquisition Datetime",
        help="Acquisition date/time of this image (DICOM AcquisitionDate/Time).",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Pixel / Geometry Metadata
    # -------------------------------------------------------------------------
    rows = fields.Integer(string="Rows", help="Number of rows (pixel height).")
    columns = fields.Integer(string="Columns", help="Number of columns (pixel width).")
    pixel_spacing_mm = fields.Char(
        string="Pixel Spacing (mm)",
        help="DICOM PixelSpacing as 'row_spacing\\column_spacing' or JSON array.",
    )
    slice_thickness_mm = fields.Float(string="Slice Thickness (mm)")
    slice_location_mm = fields.Float(string="Slice Location (mm)")
    image_position_patient = fields.Char(
        string="Image Position (Patient)",
        help="DICOM (x\\y\\z) position of the first pixel in mm.",
    )
    image_orientation_patient = fields.Char(
        string="Image Orientation (Patient)",
        help="DICOM orientation (6 values: row and column direction cosines).",
    )
    photometric_interpretation = fields.Selection(
        [
            ("MONOCHROME1", "MONOCHROME1"),
            ("MONOCHROME2", "MONOCHROME2"),
            ("RGB", "RGB"),
            ("YBR_FULL", "YBR_FULL"),
            ("PALETTE_COLOR", "PALETTE_COLOR"),
            ("HSV", "HSV"),
            ("LAB", "LAB"),
        ],
        string="Photometric Interpretation",
        help="DICOM Photometric Interpretation of the pixel data.",
    )
    bits_allocated = fields.Integer(string="Bits Allocated")
    bits_stored = fields.Integer(string="Bits Stored")
    high_bit = fields.Integer(string="High Bit")
    rescale_intercept = fields.Float(string="Rescale Intercept")
    rescale_slope = fields.Float(string="Rescale Slope")
    window_center = fields.Float(string="Window Center")
    window_width = fields.Float(string="Window Width")
    resolution = fields.Char(
        string="Resolution",
        compute="_compute_resolution",
        store=False,
        help="Convenience string 'WIDTH x HEIGHT'.",
    )

    # -------------------------------------------------------------------------
    # Files & Attachments
    # -------------------------------------------------------------------------
    file_thumbnail = fields.Binary(
        string="Thumbnail",
        attachment=True,
        help="Small preview thumbnail for fast listing.",
    )
    file_thumbnail_filename = fields.Char(string="Thumbnail File Name")
    file_image = fields.Binary(
        string="Rendered Image (e.g., JPEG/PNG)",
        attachment=True,
        help="Rendered image for quick viewing when original is DICOM.",
    )
    file_image_filename = fields.Char(string="Image File Name")
    file_dicom = fields.Binary(
        string="Original DICOM",
        attachment=True,
        help="Original DICOM instance file, if stored.",
    )
    file_dicom_filename = fields.Char(string="DICOM File Name")
    attachment_count = fields.Integer(
        string="Attachment Count",
        compute="_compute_attachment_count",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Quality & Flags
    # -------------------------------------------------------------------------
    is_key = fields.Boolean(
        string="Key Image",
        help="Mark as key/representative image for series/result.",
        tracking=True,
    )
    quality_score = fields.Selection(
        [
            ("0", "0 - Uninterpretable"),
            ("1", "1 - Poor"),
            ("2", "2 - Fair"),
            ("3", "3 - Good"),
            ("4", "4 - Very Good"),
            ("5", "5 - Excellent"),
        ],
        string="Image Quality",
        default="3",
        tracking=True,
    )
    quality_notes = fields.Text(string="Quality Notes")
    notes = fields.Text(string="Internal Notes")

    # Tags / labels
    tag_ids = fields.Many2many(
        "clinical.imaging.image.tag",
        "clinical_imaging_image_tag_rel",
        "image_id",
        "tag_id",
        string="Tags",
        help="Classification tags for this image.",
    )
    tag_count = fields.Integer(string="Tag Count", compute="_compute_tag_count", store=False)

    # Annotations (child model)
    annotation_ids = fields.One2many(
        "clinical.imaging.image.annotation",
        "image_id",
        string="Annotations",
        help="Structured annotations (ROIs, measurements, comments) for this image.",
        copy=True,
    )
    annotation_count = fields.Integer(
        string="Annotation Count",
        compute="_compute_annotation_count",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Portal & Privacy
    # -------------------------------------------------------------------------
    portal_published = fields.Boolean(
        string="Visible on Portal",
        help="If checked, the patient can view this image in the portal (subject to rules).",
        tracking=True,
    )
    privacy_level = fields.Selection(
        [
            ("normal", "Normal"),
            ("restricted", "Restricted"),
            ("high", "Highly Restricted"),
        ],
        string="Privacy Level",
        default="normal",
        help="Controls how widely accessible the image is to staff and on the portal.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # PACS / Viewer Integration
    # -------------------------------------------------------------------------
    pacs_status = fields.Selection(
        [
            ("none", "None"),
            ("to_send", "Pending Send"),
            ("sent", "Sent"),
            ("received", "Received"),
            ("error", "Error"),
        ],
        string="PACS Status",
        default="none",
        help="Status of PACS/VNA transfer for this image.",
        tracking=True,
    )
    pacs_viewer_url = fields.Char(
        string="Viewer URL",
        help="Link to an external PACS/Web viewer at image level (optional).",
    )
    pacs_message_last = fields.Text(
        string="Last PACS Message",
        help="Last integration message or error for this image.",
    )

    # -------------------------------------------------------------------------
    # State Machine
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("acquired", "Acquired"),
            ("processed", "Processed"),
            ("archived", "Archived"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        index=True,
        tracking=True,
        help="Lifecycle status of the image.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_resolution(self):
        for rec in self:
            if rec.columns and rec.rows:
                rec.resolution = f"{int(rec.columns)} x {int(rec.rows)}"
            else:
                rec.resolution = False

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    def _compute_tag_count(self):
        for rec in self:
            rec.tag_count = len(rec.tag_ids)

    def _compute_annotation_count(self):
        for rec in self:
            rec.annotation_count = len(rec.annotation_ids)

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("series_id")
    def _onchange_series_defaults(self):
        """Default ordering and timestamps from Series, if empty."""
        for rec in self:
            if not rec.series_id:
                continue
            if not rec.acquisition_datetime and rec.series_id.series_datetime:
                rec.acquisition_datetime = rec.series_id.series_datetime
            # Suggest next instance number
            if not rec.instance_number:
                existing = self.search_read(
                    [("series_id", "=", rec.series_id.id)],
                    fields=["instance_number"],
                    limit=0,
                )
                used = [e["instance_number"] or 0 for e in existing]
                next_no = (max(used) + 1) if used else 1
                rec.instance_number = next_no

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("dicom_instance_uid")
    def _check_dicom_instance_uid_format(self):
        """
        Basic DICOM UID shape: digits and dots, starts with digit, no double dots.
        """
        uid_re = re.compile(r"^[0-9](?:[0-9]*\.?)*[0-9]?$")
        for rec in self:
            if rec.dicom_instance_uid:
                uid = rec.dicom_instance_uid.strip()
                if ".." in uid or not uid_re.match(uid):
                    raise ValidationError(_("DICOM SOP Instance UID appears invalid."))

    @api.constrains("window_width")
    def _check_window_width_positive(self):
        for rec in self:
            if rec.window_width is not None and rec.window_width <= 0:
                raise ValidationError(_("Window Width must be positive when set."))

    @api.constrains("bits_stored", "bits_allocated", "high_bit")
    def _check_bits_relations(self):
        for rec in self:
            if rec.bits_stored and rec.bits_allocated and rec.bits_stored > rec.bits_allocated:
                raise ValidationError(_("Bits Stored cannot exceed Bits Allocated."))
            if rec.high_bit and rec.bits_stored and rec.high_bit != rec.bits_stored - 1:
                # Do not hard-block if vendor-specific, but prefer warning; keep as constraint for data quality
                raise ValidationError(_("High Bit should be Bits Stored - 1."))

    @api.constrains(
        "rows", "columns", "frame_count", "instance_number",
        "slice_thickness_mm", "slice_location_mm", "rescale_slope"
    )
    def _check_non_negative_numeric(self):
        for rec in self:
            for fname in ["rows", "columns", "frame_count", "instance_number"]:
                val = getattr(rec, fname)
                if val is not None and val < 0:
                    raise ValidationError(_("%s cannot be negative.") % fname)
            for fname in ["slice_thickness_mm", "slice_location_mm"]:
                # Slice location can be negative (position), so skip; only thickness must be non-negative
                pass
            if rec.slice_thickness_mm is not None and rec.slice_thickness_mm < 0:
                raise ValidationError(_("slice_thickness_mm cannot be negative."))
            # rescale_slope can be negative in some modalities; allow any real number

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Image Number must be unique per company.',
    )
    _sop_uid_company_unique = models.Constraint(
        'unique(dicom_instance_uid, company_id)',
        'DICOM SOP Instance UID must be unique per company.',
    )
    _series_instance_unique = models.Constraint(
        'unique(series_id, instance_number, company_id)',
        'Instance Number must be unique within a Series (per company).',
    )

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging.image") or _("New")
        records = super().create(vals_list)
        # If image is marked as key and Series has no key image, set it
        for rec in records:
            if rec.is_key and rec.series_id and not rec.series_id.key_image:
                rec.series_id.write({
                    "key_image": rec.file_image or rec.file_thumbnail or False,
                    "key_image_filename": rec.file_image_filename or rec.file_thumbnail_filename or False,
                })
        return records

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("dicom_instance_uid", False)
        default.setdefault("pacs_status", "none")
        default.setdefault("pacs_viewer_url", False)
        default.setdefault("is_key", False)
        return super().copy(default)

    def unlink(self):
        for rec in self:
            if rec.state in ("processed",):
                raise UserError(_("Processed images cannot be deleted. Archive instead."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # ACTIONS / WORKFLOW
    # -------------------------------------------------------------------------
    def action_mark_acquired(self):
        for rec in self:
            if rec.state not in ("draft",):
                raise UserError(_("Only Draft images can be marked as Acquired."))
            if not rec.acquisition_datetime:
                rec.acquisition_datetime = fields.Datetime.now()
            rec.state = "acquired"
            rec.message_post(body=_("Image marked as Acquired."))

    def action_mark_processed(self):
        for rec in self:
            if rec.state not in ("acquired",):
                raise UserError(_("Only Acquired images can be marked as Processed."))
            rec.state = "processed"
            rec.message_post(body=_("Image marked as Processed."))

    def action_archive(self):
        for rec in self:
            if rec.state not in ("processed", "cancelled"):
                raise UserError(_("Only Processed or Cancelled images can be archived."))
            rec.active = False
            rec.state = "archived"
            rec.message_post(body=_("Image archived."))

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state == "processed":
                raise UserError(_("Processed images cannot be cancelled. Archive instead."))
            rec.state = "cancelled"
            if reason:
                rec.message_post(body=_("Image cancelled. Reason: %s") % reason)
            else:
                rec.message_post(body=_("Image cancelled."))

    # PACS helpers
    def action_send_to_pacs(self):
        for rec in self:
            rec.pacs_status = "to_send"
            rec.pacs_message_last = _("Queued for PACS transmission.")
            rec.message_post(body=_("Image queued for PACS transmission."))

    def action_mark_sent(self, message=None):
        for rec in self:
            rec.pacs_status = "sent"
            if message:
                rec.pacs_message_last = message
            rec.message_post(body=_("Image marked as Sent to PACS."))

    def action_mark_received(self, viewer_url=None, message=None):
        for rec in self:
            rec.pacs_status = "received"
            if viewer_url:
                rec.pacs_viewer_url = viewer_url
            if message:
                rec.pacs_message_last = message
            rec.message_post(body=_("Image acknowledged by PACS."))

    def action_mark_pacs_error(self, message):
        for rec in self:
            rec.pacs_status = "error"
            rec.pacs_message_last = message or _("Unknown PACS error.")
            rec.message_post(body=_("PACS error on Image: %s") % (message or ""))

    # Portal / Attachments / Navigation
    def action_toggle_portal(self):
        for rec in self:
            rec.portal_published = not rec.portal_published

    def action_view_attachments(self):
        self.ensure_one()
        return {
            "name": _("Attachments"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    def action_set_as_key(self):
        for rec in self:
            rec.is_key = True
            if rec.series_id and not rec.series_id.key_image:
                rec.series_id.write({
                    "key_image": rec.file_image or rec.file_thumbnail or False,
                    "key_image_filename": rec.file_image_filename or rec.file_thumbnail_filename or False,
                })
            rec.message_post(body=_("Image flagged as Key."))

    # def action_add_to_result(self, result_id=None):
    #     """
    #     Add this image to a Result's key images.
    #     Requires model 'clinical.imaging.result' to exist (same module).
    #     """
    #     Result = self.env["clinical.imaging.result"]
    #     for rec in self:
    #         # Find the latest final/amended result for the imaging if none provided
    #         dest = False
    #         if result_id:
    #             dest = Result.browse(result_id).exists()
    #         else:
    #             dest = Result.search(
    #                 [("imaging_id", "=", rec.imaging_id.id), ("state", "in", ["final", "amended"])],
    #                 order="signed_datetime desc, write_date desc, id desc",
    #                 limit=1,
    #             )
    #         if not dest:
    #             raise UserError(_("No target Result found to add this image."))
    #         dest.key_image_ids = [(4, rec.id)]
    #         rec.message_post(body=_("Image added to Result %s as key image.") % dest.display_name)

    # Display
    def name_get(self):
        res = []
        for rec in self:
            parts = [rec.name]
            if rec.series_id:
                parts.append(rec.series_id.series_description or rec.series_id.name)
            if rec.study_id:
                parts.append(f"({rec.study_id.name})")
            res.append((rec.id, " - ".join([p for p in parts if p])))
        return res


# =============================================================================
# Image Annotation (ROIs, measurements, comments)
# =============================================================================
class ClinicalImagingImageAnnotation(models.Model):
    """
    Stores structured annotations attached to an Image:
      - ROI geometry (point/line/rect/circle/polygon/polyline)
      - Optional measurement values and units
      - Optional linkage to a structured finding
    Geometry is stored as JSON (screen/pixel or patient space as provided by the viewer).
    """
    _name = "clinical.imaging.image.annotation"
    _description = "Clinical Imaging Image Annotation"
    _order = "image_id, sequence, id"
    _check_company_auto = True

    image_id = fields.Many2one(
        "clinical.imaging.image",
        string="Image",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="image_id.company_id",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)
    type = fields.Selection(
        [
            ("point", "Point"),
            ("line", "Line"),
            ("rect", "Rectangle"),
            ("circle", "Circle"),
            ("polygon", "Polygon"),
            ("polyline", "Polyline"),
            ("text", "Text"),
            ("arrow", "Arrow"),
            ("other", "Other"),
        ],
        string="Annotation Type",
        required=True,
        default="point",
    )
    geometry_json = fields.Text(
        string="Geometry JSON",
        help="JSON payload describing ROI geometry (coordinates, radius, etc.).",
    )
    coord_space = fields.Selection(
        [
            ("pixel", "Pixel Space"),
            ("patient", "Patient Space (mm)"),
            ("world", "World / Scanner Space"),
        ],
        string="Coordinate Space",
        default="pixel",
        help="Coordinate space of the stored geometry.",
    )
    measurement_value = fields.Float(string="Measurement Value", help="Primary measurement value, if any.")
    unit = fields.Char(string="Unit", help="Unit for the measurement value (e.g., 'mm', 'cm²').")
    color = fields.Char(string="Color", help="Optional color (hex or named) for display.")
    comment = fields.Char(string="Comment", help="Short comment for this annotation.")

    # author_id = fields.Many2one("res.users", string="Author", default=lambda self: self.env.user, required=True)
    # result_id = fields.Many2one(
    #     "clinical.imaging.result",
    #     string="Linked Result",
    #     help="Optional diagnostic result this annotation belongs to.",
    # )
    finding_id = fields.Many2one(
        "clinical.imaging.finding",
        string="Linked Finding",
        help="Optional structured finding linked to this annotation.",
    )
    created_datetime = fields.Datetime(string="Created At", default=fields.Datetime.now)
    last_modified = fields.Datetime(string="Last Modified", readonly=True)

    @api.constrains("geometry_json")
    def _check_geometry_json(self):
        for rec in self:
            if rec.type not in ("text", "other") and not rec.geometry_json:
                raise ValidationError(_("Geometry JSON is required for non-text annotations."))
            if rec.geometry_json:
                try:
                    json.loads(rec.geometry_json)
                except Exception:
                    raise ValidationError(_("Geometry JSON is not valid JSON."))

    @api.constrains("measurement_value")
    def _check_measurement_non_negative_when_length_area(self):
        for rec in self:
            # If unit suggests a length/area, value must be non-negative
            if rec.unit and any(u in rec.unit.lower() for u in ["mm", "cm", "m", "px", "²", "2"]):
                if rec.measurement_value is not None and rec.measurement_value < 0:
                    raise ValidationError(_("Measurement value must be non-negative for length/area units."))

    def write(self, vals):
        vals["last_modified"] = fields.Datetime.now()
        return super().write(vals)

    # Navigation helper
    def action_open_image(self):
        self.ensure_one()
        return {
            "name": _("Image"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.image",
            "view_mode": "form",
            "res_id": self.image_id.id,
            "target": "current",
        }


# =============================================================================
# Soft links on Series/Result to navigate/open Images
# =============================================================================
class ClinicalImagingSeries(models.Model):
    _inherit = "clinical.imaging.series"

    def action_create_image(self):
        """
        Convenience action to create a blank Image from the Series form.
        """
        self.ensure_one()
        image = self.env["clinical.imaging.image"].create({
            "series_id": self.id,
        })
        return {
            "name": _("Image"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.image",
            "view_mode": "form",
            "res_id": image.id,
            "target": "current",
        }

# class ClinicalImagingResult(models.Model):
#     _inherit = "clinical.imaging.result"

#     def action_open_key_images(self):
#         self.ensure_one()
#         return {
#             "name": _("Key Images"),
#             "type": "ir.actions.act_window",
#             "res_model": "clinical.imaging.image",
#             "view_mode": "list,form,kanban",
#             "domain": [("id", "in", self.key_image_ids.ids)],
#             "target": "current",
#         }


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import re
import json


# =============================================================================
# Tags for Findings (classification)
# =============================================================================
class ClinicalImagingFindingTag(models.Model):
    _name = "clinical.imaging.finding.tag"
    _description = "Clinical Imaging Finding Tag"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(string="Tag Name", required=True)
    color = fields.Integer(string="Color Index", help="Color index for kanban/list chips.")
    description = fields.Char(string="Description")
    company_id = fields.Many2one("res.company", string="Company", default=lambda s: s.env.company)
    active = fields.Boolean(default=True)

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Finding Tag must be unique per company.',
    )


# =============================================================================
# Clinical Imaging Finding (structured lesion/observation)
# =============================================================================
class ClinicalImagingFinding(models.Model):
    """
    Structured imaging finding (e.g., pulmonary nodule, hepatic lesion, fracture).
    Links to Imaging/Study/Series/Image for provenance, and to Result for reporting.

    Key features:
      - Standardized categorization (benign/suspicious), risk scores (BI-RADS, LI-RADS, PI-RADS, Lung-RADS)
      - Location & laterality, organ/segment
      - Size measurements (long/short axis) + optional detailed measure lines
      - Evolution/trend tracking vs prior (stable/increase/decrease/resolved)
      - Portal visibility with privacy levels
      - Many2many linkage to Results (bidirectional with clinical.imaging.result.finding_ids)
    """
    _name = "clinical.imaging.finding"
    _description = "Clinical Imaging Finding"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "display_name"
    _order = "create_date desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Finding Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        help="Unique identifier generated from sequence.",
        index=True,
        tracking=True,
    )
    display_name = fields.Char(
        string="Title",
        required=True,
        help="Short title for the finding (e.g., 'Right upper lobe nodule').",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda s: s.env.company,
        index=True,
    )
    active = fields.Boolean(string="Active", default=True)

    # -------------------------------------------------------------------------
    # Context Links (propagated from imaging/study/series/image)
    # -------------------------------------------------------------------------
    imaging_id = fields.Many2one(
        "clinical.imaging",
        string="Imaging",
        required=False,
        index=True,
        help="Imaging record that this finding is associated with.",
        tracking=True,
    )
    study_id = fields.Many2one(
        "clinical.imaging.study",
        string="Study",
        index=True,
        help="Study context of this finding (if known).",
    )
    series_id = fields.Many2one(
        "clinical.imaging.series",
        string="Series",
        index=True,
        help="Series context of this finding (if known).",
    )
    image_ids = fields.Many2many(
        "clinical.imaging.image",
        "clinical_imaging_finding_image_rel",
        "finding_id",
        "image_id",
        string="Related Images",
        help="Reference images for this finding (key slices/frames).",
    )
    annotation_ids = fields.Many2many(
        "clinical.imaging.image.annotation",
        "clinical_imaging_finding_annotation_rel",
        "finding_id",
        "annotation_id",
        string="Linked Annotations",
        help="Annotations (ROIs/measurements) that define or illustrate this finding.",
    )

    # Propagated care context
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="imaging_id.patient_id",
        store=True,
        readonly=True,
    )
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        related="imaging_id.appointment_id",
        store=True,
        readonly=True,
    )
    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     related="imaging_id.encounter_id",
    #     store=True,
    #     readonly=True,
    # )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="imaging_id.treatment_id",
        store=True,
        readonly=True,
    )
    procedure_session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Procedure Session",
        related="imaging_id.procedure_session_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Result Link (bidirectional M2M with clinical.imaging.result)
    # -------------------------------------------------------------------------
    # result_ids = fields.Many2many(
    #     "clinical.imaging.result",
    #     "clinical_imaging_result_finding_rel",
    #     "finding_id",
    #     "result_id",
    #     string="Results",
    #     help="Results that include this finding.",
    # )
    result_count = fields.Integer(
        string="Result Count",
        compute="_compute_counts",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Classification & Risk
    # -------------------------------------------------------------------------
    category = fields.Selection(
        [
            ("benign", "Benign"),
            ("likely_benign", "Likely Benign"),
            ("indeterminate", "Indeterminate"),
            ("suspicious", "Suspicious"),
            ("malignant", "Malignant"),
        ],
        string="Diagnostic Category",
        default="indeterminate",
        help="Overall diagnostic category for the finding.",
        tracking=True,
    )
    tags_ids = fields.Many2many(
        "clinical.imaging.finding.tag",
        "clinical_imaging_finding_tag_rel",
        "finding_id",
        "tag_id",
        string="Tags",
        help="Classification tags for this finding.",
    )

    # RADS scoring (optional)
    birads = fields.Selection(
        [(str(i), f"BI-RADS {i}") for i in range(0, 7)],
        string="BI-RADS",
        help="Breast Imaging-Reporting and Data System category.",
    )
    lirads = fields.Selection(
        [(str(i), f"LI-RADS {i}") for i in range(1, 6)] + [("nc", "LI-RADS NC")],
        string="LI-RADS",
        help="Liver Imaging Reporting and Data System category.",
    )
    pirads = fields.Selection(
        [(str(i), f"PI-RADS {i}") for i in range(1, 6)],
        string="PI-RADS",
        help="Prostate Imaging Reporting and Data System category.",
    )
    lungrads = fields.Selection(
        [(str(i), f"Lung-RADS {i}") for i in range(0, 5)] + [("s", "Lung-RADS S")],
        string="Lung-RADS",
        help="Lung CT Screening Reporting and Data System category.",
    )

    # Clinical severity and trend
    severity = fields.Selection(
        [
            ("low", "Low"),
            ("moderate", "Moderate"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Clinical Severity",
        default="moderate",
        help="Severity used for triage and follow-up urgency.",
        tracking=True,
    )
    trend = fields.Selection(
        [
            ("new", "New"),
            ("stable", "Stable"),
            ("increased", "Increased"),
            ("decreased", "Decreased"),
            ("resolved", "Resolved"),
            ("unknown", "Unknown"),
        ],
        string="Evolution vs Prior",
        default="unknown",
        help="Observed evolution when compared with prior studies.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Location & Description
    # -------------------------------------------------------------------------
    body_region = fields.Char(
        string="Body Region",
        help="General region (e.g., 'Chest', 'Abdomen', 'Pelvis').",
    )
    organ = fields.Char(
        string="Organ",
        help="Organ or structure (e.g., 'Liver', 'Left lung').",
    )
    organ_segment = fields.Char(
        string="Organ Segment",
        help="Segment/lobe (e.g., 'Segment VIII', 'Right upper lobe').",
    )
    side = fields.Selection(
        [("left", "Left"), ("right", "Right"), ("midline", "Midline"), ("bilateral", "Bilateral"), ("unknown", "Unknown")],
        string="Side",
        default="unknown",
        help="Laterality/side of the finding.",
    )
    location_notes = fields.Char(string="Location Notes")

    description = fields.Text(
        string="Description",
        help="Narrative description of the finding.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Size / Measurements (quick fields)
    # -------------------------------------------------------------------------
    long_axis_mm = fields.Float(string="Long Axis (mm)", help="Longest diameter in millimeters.")
    short_axis_mm = fields.Float(string="Short Axis (mm)", help="Shortest diameter in millimeters.")
    volume_mm3 = fields.Float(string="Volume (mm³)", help="Estimated volume, if applicable.")
    density_hu = fields.Float(string="Density (HU)", help="CT attenuation (Hounsfield Units).")
    suv_max = fields.Float(string="SUVmax", help="Peak standardized uptake value (PET).")
    suv_mean = fields.Float(string="SUVmean", help="Mean standardized uptake value (PET).")

    # Detailed measurement lines
    measure_ids = fields.One2many(
        "clinical.imaging.finding.measure", "finding_id",
        string="Measurements",
        help="Structured measurement rows linked to this finding.",
        copy=True,
    )
    measure_count = fields.Integer(string="Measurement Count", compute="_compute_counts", store=False)

    # -------------------------------------------------------------------------
    # Coding (optional SNOMED/ICD/Custom)
    # -------------------------------------------------------------------------
    code_system = fields.Selection(
        [
            ("snomed", "SNOMED CT"),
            ("icd10", "ICD-10"),
            ("local", "Local"),
            ("other", "Other"),
        ],
        string="Code System",
        default="local",
        help="Coding system used for the code below.",
    )
    code = fields.Char(string="Code", help="Code value in the selected coding system.")
    code_desc = fields.Char(string="Code Description", help="Description of the coded concept.")

    # -------------------------------------------------------------------------
    # Attachments & Portal
    # -------------------------------------------------------------------------
    attachment_count = fields.Integer(
        string="Attachment Count",
        compute="_compute_attachment_count",
        store=False,
    )
    portal_published = fields.Boolean(
        string="Visible on Portal",
        help="If checked, the patient can view this finding on the portal (subject to rules).",
        tracking=True,
    )
    privacy_level = fields.Selection(
        [("normal", "Normal"), ("restricted", "Restricted"), ("high", "Highly Restricted")],
        string="Privacy Level",
        default="normal",
        help="Controls how widely accessible the finding is to staff and on the portal.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # State & Audit
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_review", "In Review"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("resolved", "Resolved"),
            ("archived", "Archived"),
        ],
        string="Status",
        default="draft",
        index=True,
        tracking=True,
        help="Lifecycle state of this finding.",
    )
    author_doctor_id = fields.Many2one(
        "hr.employee",
        string="Authoring Doctor",
        domain=[("is_doctor", "=", True)],
        help="Doctor who documented this finding (e.g., radiologist).",
        tracking=True,
    )
    created_datetime = fields.Datetime(string="Created At", default=fields.Datetime.now)
    verified_datetime = fields.Datetime(string="Verified At")

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_counts(self):
        for rec in self:
            rec.result_count = len(rec.result_ids)
            rec.measure_count = len(rec.measure_ids)

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("series_id")
    def _onchange_series_id(self):
        for rec in self:
            if rec.series_id and not rec.study_id:
                rec.study_id = rec.series_id.study_id.id
            if rec.series_id and not rec.imaging_id:
                rec.imaging_id = rec.series_id.study_id.imaging_id.id

    @api.onchange("study_id")
    def _onchange_study_id(self):
        for rec in self:
            if rec.study_id and not rec.imaging_id:
                rec.imaging_id = rec.study_id.imaging_id.id

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("long_axis_mm", "short_axis_mm", "volume_mm3", "density_hu", "suv_max", "suv_mean")
    def _check_non_negative_metrics(self):
        for rec in self:
            for fname in ["long_axis_mm", "short_axis_mm", "volume_mm3", "suv_max", "suv_mean"]:
                val = getattr(rec, fname)
                if val is not None and val < 0:
                    raise ValidationError(_("%s cannot be negative.") % fname)
            # density_hu can be negative (e.g., fat), so no check

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging.finding") or _("New")
        records = super().create(vals_list)
        # Auto-subscribe doctor
        for rec in records:
            partner_ids = []
            if rec.author_doctor_id and rec.author_doctor_id.work_contact_id:
                partner_ids.append(rec.author_doctor_id.work_contact_id.id)
            if partner_ids:
                rec.message_subscribe(partner_ids=list(set(partner_ids)))
        return records

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("state", "draft")
        default.setdefault("portal_published", False)
        return super().copy(default)

    def unlink(self):
        for rec in self:
            if rec.state in ("approved", "resolved", "archived"):
                raise UserError(_("Approved/Resolved/Archived findings cannot be deleted."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # ACTIONS / WORKFLOW
    # -------------------------------------------------------------------------
    def action_submit_review(self):
        for rec in self:
            if rec.state not in ("draft",):
                raise UserError(_("Only Draft findings can be submitted for review."))
            rec.state = "in_review"
            rec.message_post(body=_("Finding submitted for review."))

    def action_approve(self):
        for rec in self:
            if rec.state not in ("in_review",):
                raise UserError(_("Only findings In Review can be approved."))
            if not rec.author_doctor_id:
                raise UserError(_("Please set Authoring Doctor before approval."))
            rec.state = "approved"
            rec.verified_datetime = fields.Datetime.now()
            rec.message_post(body=_("Finding approved."))

    def action_reject(self, reason=None):
        for rec in self:
            if rec.state not in ("in_review",):
                raise UserError(_("Only findings In Review can be rejected."))
            rec.state = "rejected"
            rec.message_post(body=_("Finding rejected. %s") % (reason or ""))

    def action_resolve(self, note=None):
        for rec in self:
            if rec.state not in ("approved", "rejected"):
                raise UserError(_("Only Approved or Rejected findings can be resolved."))
            rec.state = "resolved"
            if note:
                rec.message_post(body=_("Finding resolved. %s") % note)
            else:
                rec.message_post(body=_("Finding resolved."))

    def action_archive(self):
        for rec in self:
            if rec.state not in ("resolved", "rejected"):
                raise UserError(_("Only Resolved/Rejected findings can be archived."))
            rec.state = "archived"
            rec.active = False
            rec.message_post(body=_("Finding archived."))

    def action_toggle_portal(self):
        for rec in self:
            rec.portal_published = not rec.portal_published

    # Linking helpers
    # def action_add_to_result(self, result_id=None):
    #     """
    #     Add this finding to a Result. If result_id not provided, use latest final/amended result.
    #     """
    #     Result = self.env["clinical.imaging.result"]
    #     for rec in self:
    #         target = False
    #         if result_id:
    #             target = Result.browse(result_id).exists()
    #         elif rec.imaging_id:
    #             target = Result.search(
    #                 [("imaging_id", "=", rec.imaging_id.id), ("state", "in", ["final", "amended"])],
    #                 order="signed_datetime desc, write_date desc, id desc",
    #                 limit=1,
    #             )
    #         if not target:
    #             raise UserError(_("No target Result found to link this finding."))
    #         rec.result_ids = [(4, target.id)]
    #         target.message_post(body=_("Finding %s linked to this Result.") % rec.display_name)

    def action_view_attachments(self):
        self.ensure_one()
        return {
            "name": _("Attachments"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    # Display
    def name_get(self):
        res = []
        for rec in self:
            parts = [rec.name, rec.display_name]
            if rec.imaging_id:
                parts.append(f"({rec.imaging_id.name})")
            res.append((rec.id, " - ".join([p for p in parts if p])))
        return res

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Finding Number must be unique per company.',
    )


# =============================================================================
# Measurement lines for Findings
# =============================================================================
class ClinicalImagingFindingMeasure(models.Model):
    _name = "clinical.imaging.finding.measure"
    _description = "Clinical Imaging Finding Measurement"
    _order = "finding_id, sequence, id"
    _check_company_auto = True

    finding_id = fields.Many2one(
        "clinical.imaging.finding",
        string="Finding",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="finding_id.company_id",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)

    name = fields.Char(
        string="Measurement Name",
        required=True,
        help="Short title (e.g., 'Long-axis', 'Short-axis', 'Attenuation').",
    )
    method = fields.Char(
        string="Method",
        help="Measurement protocol/method (e.g., 'RECIST 1.1', 'Axial plane').",
    )
    value = fields.Float(string="Value")
    unit = fields.Char(string="Unit", help="Unit of the measured value (e.g., 'mm', 'cm³', 'HU').")
    related_image_id = fields.Many2one(
        "clinical.imaging.image",
        string="Related Image",
        help="Specific image used for this measurement.",
    )
    related_annotation_id = fields.Many2one(
        "clinical.imaging.image.annotation",
        string="Related Annotation",
        help="Annotation/ROI corresponding to this measurement.",
    )
    note = fields.Char(string="Notes")

    @api.constrains("value")
    def _check_value_not_nan(self):
        for rec in self:
            # Length/area/volume values should be non-negative; allow negatives for HU/CT numbers.
            if rec.unit and any(u in (rec.unit or "").lower() for u in ["mm", "cm", "m", "px", "²", "3", "³"]):
                if rec.value is not None and rec.value < 0:
                    raise ValidationError(_("Measurement value must be non-negative for length/area/volume units."))


# =============================================================================
# Convenience extensions for navigation from other models
# =============================================================================
# class ClinicalImagingResult(models.Model):
#     _inherit = "clinical.imaging.result"

#     def action_open_findings(self):
#         self.ensure_one()
#         return {
#             "name": _("Findings"),
#             "type": "ir.actions.act_window",
#             "res_model": "clinical.imaging.finding",
#             "view_mode": "list,form,kanban",
#             "domain": [("id", "in", self.finding_ids.ids)],
#             "target": "current",
#         }

#     def action_add_existing_finding(self):
#         """Open a chooser to link existing findings for the same imaging."""
#         self.ensure_one()
#         return {
#             "name": _("Add Existing Finding"),
#             "type": "ir.actions.act_window",
#             "res_model": "clinical.imaging.finding",
#             "view_mode": "list,form",
#             "domain": [("imaging_id", "=", self.imaging_id.id)],
#             "target": "current",
#             "context": {"default_imaging_id": self.imaging_id.id},
#         }


class ClinicalImagingStudy(models.Model):
    _inherit = "clinical.imaging.study"

    def action_open_findings(self):
        self.ensure_one()
        return {
            "name": _("Findings (Study)"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.finding",
            "view_mode": "list,form,kanban",
            "domain": [("study_id", "=", self.id)],
            "target": "current",
            "context": {"default_study_id": self.id, "default_imaging_id": self.imaging_id.id},
        }


class ClinicalImagingSeries(models.Model):
    _inherit = "clinical.imaging.series"

    def action_open_findings(self):
        self.ensure_one()
        return {
            "name": _("Findings (Series)"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.finding",
            "view_mode": "list,form,kanban",
            "domain": [("series_id", "=", self.id)],
            "target": "current",
            "context": {
                "default_series_id": self.id,
                "default_study_id": self.study_id.id,
                "default_imaging_id": self.imaging_id.id,
            },
        }


class ClinicalImaging(models.Model):
    _inherit = "clinical.imaging"

    finding_count = fields.Integer(
        string="Finding Count",
        compute="_compute_finding_count",
        store=False,
    )

    def _compute_finding_count(self):
        Finding = self.env["clinical.imaging.finding"]
        for rec in self:
            rec.finding_count = Finding.search_count([("imaging_id", "=", rec.id)])

    def action_open_findings(self):
        self.ensure_one()
        return {
            "name": _("Findings"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.finding",
            "view_mode": "list,form,kanban",
            "domain": [("imaging_id", "=", self.id)],
            "target": "current",
            "context": {"default_imaging_id": self.id},
        }


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import re


# =============================================================================
# Clinical Imaging Device (extend full master with integrations & telemetry)
# =============================================================================
class ClinicalImagingDevice(models.Model):
    _name = "clinical.imaging.device"
    _description = "Clinical Imaging Device"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name, modality, id"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Device Name", required=True, tracking=True,
        help="Human-friendly name of the device (e.g., 'MRI 1.5T Room A')."
    )
    code = fields.Char(
        string="Code", index=True, tracking=True,
        help="Short internal code for the device."
    )
    company_id = fields.Many2one(
        "res.company", string="Company", required=True,
        default=lambda self: self.env.company, index=True
    )
    active = fields.Boolean(
        string="Active", default=True,
        help="Uncheck to archive the device."
    )

    # -------------------------------------------------------------------------
    # Technical Identity
    # -------------------------------------------------------------------------
    manufacturer = fields.Char(string="Manufacturer", help="Device manufacturer.")
    model_name = fields.Char(string="Model", help="Model/series name.")
    serial_number = fields.Char(string="Serial Number", help="Manufacturer serial number.", index=True)
    udi_di = fields.Char(string="UDI-DI", help="Unique Device Identifier - Device Identifier (if applicable).")
    software_version = fields.Char(string="Software Version")
    firmware_version = fields.Char(string="Firmware Version")
    install_date = fields.Date(string="Installation Date", help="Date when the device was installed.")
    warranty_expiry_date = fields.Date(string="Warranty Expiry")

    # -------------------------------------------------------------------------
    # Modality & Capabilities
    # -------------------------------------------------------------------------
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
        string="Modality", required=True, tracking=True,
        help="Primary modality of the device."
    )
    max_patient_weight_kg = fields.Float(
        string="Max Patient Weight (kg)",
        help="Maximum supported patient weight."
    )
    bore_diameter_cm = fields.Float(
        string="Bore Diameter (cm)",
        help="For MRI/CT devices, the bore diameter."
    )
    throughput_per_hour = fields.Float(
        string="Throughput (/hour)",
        help="Typical number of studies per hour under normal operation."
    )
    supports_contrast = fields.Boolean(
        string="Supports Contrast", default=True,
        help="If the device supports contrast workflows."
    )

    # -------------------------------------------------------------------------
    # Organization & Scheduling
    # -------------------------------------------------------------------------
    department_id = fields.Many2one(
        "hr.department", string="Department",
        help="Owning clinical/technical department."
    )
    room_id = fields.Many2one(
        "clinic.room", string="Room",
        help="Room where the device is installed (from ClinicOne Room & Device module)."
    )
    location = fields.Char(
        string="Location",
        help="Free-text location/room label if not using room records."
    )
    calendar_id = fields.Many2one(
        "resource.calendar", string="Operating Hours",
        help="Default working time used for scheduling and SLA."
    )

    # -------------------------------------------------------------------------
    # Connectivity (DICOM / Network)
    # -------------------------------------------------------------------------
    ip_address = fields.Char(string="IP Address", help="Device IP address.")
    dicom_supported = fields.Boolean(string="DICOM Supported", default=True)
    ae_title = fields.Char(
        string="AE Title",
        help="DICOM Application Entity Title (≤16 chars, uppercase, no spaces)."
    )
    dicom_port = fields.Integer(string="DICOM Port", help="TCP port used by the DICOM SCP.", default=104)
    dicom_tls = fields.Boolean(string="DICOM TLS", help="Enable TLS for DICOM association if supported.")

    # -------------------------------------------------------------------------
    # Maintenance & QC
    # -------------------------------------------------------------------------
    vendor_contact_id = fields.Many2one(
        "res.partner", string="Vendor",
        help="Vendor / service provider for maintenance."
    )
    last_maintenance_date = fields.Date(string="Last Maintenance")
    maintenance_interval_days = fields.Integer(
        string="Maintenance Interval (days)", default=180,
        help="Interval in days for preventive maintenance."
    )
    next_maintenance_date = fields.Date(
        string="Next Maintenance", compute="_compute_next_maintenance",
        store=True
    )

    last_qc_date = fields.Date(string="Last QC/QA")
    qc_interval_days = fields.Integer(
        string="QC Interval (days)", default=30,
        help="Interval for quality control tests."
    )
    next_qc_date = fields.Date(
        string="Next QC/QA", compute="_compute_next_qc", store=True
    )
    qc_status = fields.Selection(
        [
            ("ok", "OK"),
            ("due", "Due"),
            ("overdue", "Overdue"),
        ],
        string="QC Status", compute="_compute_qc_status", store=True
    )

    # -------------------------------------------------------------------------
    # Operational State
    # -------------------------------------------------------------------------
    status = fields.Selection(
        [
            ("operational", "Operational"),
            ("maintenance", "Under Maintenance"),
            ("down", "Down"),
            ("retired", "Retired"),
        ],
        string="Status", default="operational", tracking=True, index=True,
        help="Current operational status of the device."
    )
    status_note = fields.Char(string="Status Note", help="Short note for current status.")
    retired_date = fields.Date(string="Retired Date")

    # -------------------------------------------------------------------------
    # Usage & Uptime Stats
    # -------------------------------------------------------------------------
    # imaging_count = fields.Integer(
    #     string="Imaging Count", compute="_compute_imaging_stats", store=False,
    #     help="Number of imaging records acquired using this device."
    # )
    downtime_hours_total = fields.Float(
        string="Total Downtime (h)", compute="_compute_downtime_stats", store=False
    )
    uptime_ratio_30d = fields.Float(
        string="Uptime Ratio (30d)", compute="_compute_downtime_stats", store=False,
        help="Approximate uptime ratio over the last 30 days."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("last_maintenance_date", "maintenance_interval_days")
    def _compute_next_maintenance(self):
        for rec in self:
            if rec.last_maintenance_date and rec.maintenance_interval_days:
                rec.next_maintenance_date = fields.Date.add(
                    rec.last_maintenance_date, days=int(rec.maintenance_interval_days)
                )
            else:
                rec.next_maintenance_date = False

    @api.depends("last_qc_date", "qc_interval_days")
    def _compute_next_qc(self):
        for rec in self:
            if rec.last_qc_date and rec.qc_interval_days:
                rec.next_qc_date = fields.Date.add(rec.last_qc_date, days=int(rec.qc_interval_days))
            else:
                rec.next_qc_date = False

    @api.depends("next_qc_date")
    def _compute_qc_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.next_qc_date:
                rec.qc_status = "due"
            else:
                if rec.next_qc_date < today:
                    rec.qc_status = "overdue"
                elif (rec.next_qc_date - today).days <= 3:
                    rec.qc_status = "due"
                else:
                    rec.qc_status = "ok"

    # def _compute_imaging_stats(self):
    #     Imaging = self.env["clinical.imaging"]
    #     for rec in self:
    #         rec.imaging_count = Imaging.search_count([("device_id", "=", rec.id)])

    def _compute_downtime_stats(self):
        Downtime = self.env["clinical.imaging.device.downtime"]
        now = fields.Datetime.now()
        for rec in self:
            # Total downtime (all time)
            all_dt = Downtime.search([("device_id", "=", rec.id), ("state", "=", "closed")])
            rec.downtime_hours_total = sum(all_dt.mapped("duration_hours"))

            # Uptime ratio for last 30 days (approx = 30*24 - downtime)
            start = fields.Datetime.subtract(now, days=30)
            last30 = Downtime.search([
                ("device_id", "=", rec.id),
                ("state", "=", "closed"),
                ("end_datetime", ">=", start),
            ])
            dt_hours_30 = 0.0
            for d in last30:
                dt_hours_30 += d._duration_hours_window(start, now)
            total_hours = 30.0 * 24.0
            rec.uptime_ratio_30d = max(0.0, min(1.0, (total_hours - dt_hours_30) / total_hours)) if total_hours else 1.0

    # -------------------------------------------------------------------------
    # ONCHANGE & VALIDATION
    # -------------------------------------------------------------------------
    @api.onchange("ae_title")
    def _onchange_ae_title_normalize(self):
        for rec in self:
            if rec.ae_title:
                rec.ae_title = rec.ae_title.strip().upper().replace(" ", "")

    @api.constrains("serial_number", "company_id")
    def _check_unique_serial(self):
        for rec in self:
            if rec.serial_number:
                domain = [("serial_number", "=", rec.serial_number), ("company_id", "=", rec.company_id.id)]
                if self.search_count(domain) > 1:
                    raise ValidationError(_("Serial Number must be unique per company."))

    @api.constrains("dicom_port")
    def _check_port_range(self):
        for rec in self:
            if rec.dicom_port is not None and (rec.dicom_port < 1 or rec.dicom_port > 65535):
                raise ValidationError(_("DICOM Port must be in range 1..65535."))

    @api.constrains("ip_address")
    def _check_ip_format(self):
        ip_regex = r"^(\d{1,3}\.){3}\d{1,3}$"
        for rec in self:
            if rec.ip_address and not re.match(ip_regex, rec.ip_address):
                raise ValidationError(_("IP Address appears invalid (expect IPv4 dotted decimal)."))

    @api.constrains("ae_title")
    def _check_ae_title(self):
        for rec in self:
            if rec.ae_title:
                if len(rec.ae_title) > 16:
                    raise ValidationError(_("AE Title must be 16 characters or fewer."))
                if " " in rec.ae_title:
                    raise ValidationError(_("AE Title cannot contain spaces."))
                if not rec.ae_title.isupper():
                    raise ValidationError(_("AE Title must be uppercase."))

    @api.constrains("status", "active")
    def _check_retired_archival(self):
        for rec in self:
            if rec.status == "retired" and rec.active:
                # Not hard error; gently align flags
                rec.active = False

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_set_operational(self):
        for rec in self:
            rec.status = "operational"
            rec.status_note = False
            rec.message_post(body=_("Device set to Operational."))

    def action_set_maintenance(self):
        for rec in self:
            rec.status = "maintenance"
            rec.message_post(body=_("Device set to Under Maintenance."))

    def action_set_down(self, reason=None):
        for rec in self:
            rec.status = "down"
            if reason:
                rec.status_note = reason
            rec.message_post(body=_("Device set to Down. %s") % (reason or ""))

    def action_retire(self, note=None):
        for rec in self:
            rec.status = "retired"
            rec.active = False
            rec.retired_date = fields.Date.context_today(self)
            if note:
                rec.status_note = note
            rec.message_post(body=_("Device retired."))

    # def action_open_imaging(self):
    #     self.ensure_one()
    #     return {
    #         "name": _("Imaging Records"),
    #         "type": "ir.actions.act_window",
    #         "res_model": "clinical.imaging",
    #         "view_mode": "list,form,kanban,calendar",
    #         "domain": [("device_id", "=", self.id)],
    #         "target": "current",
    #         "context": {"search_default_groupby_patient": 1},
    #     }

    def action_open_downtime(self):
        self.ensure_one()
        return {
            "name": _("Downtime Logs"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.device.downtime",
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.id)],
            "target": "current",
            "context": {"default_device_id": self.id},
        }

    def action_open_calibration(self):
        self.ensure_one()
        return {
            "name": _("Calibration / QC Logs"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.device.calibration",
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.id)],
            "target": "current",
            "context": {"default_device_id": self.id},
        }

    def action_open_connectivity(self):
        self.ensure_one()
        return {
            "name": _("Connectivity Endpoints"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.device.connectivity",
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.id)],
            "target": "current",
            "context": {"default_device_id": self.id},
        }

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            parts = [rec.name]
            if rec.code:
                parts.append("[%s]" % rec.code)
            if rec.modality:
                parts.append("(%s)" % rec.modality)
            res.append((rec.id, " ".join(parts)))
        return res

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Device code must be unique per company.',
    )
    _serial_company_unique = models.Constraint(
        'unique(serial_number, company_id)',
        'Serial number must be unique per company.',
    )


# =============================================================================
# Device Downtime Log
# =============================================================================
class ClinicalImagingDeviceDowntime(models.Model):
    _name = "clinical.imaging.device.downtime"
    _description = "Imaging Device Downtime"
    _order = "start_datetime desc, id desc"
    _check_company_auto = True

    device_id = fields.Many2one(
        "clinical.imaging.device", string="Device",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="device_id.company_id", store=True, readonly=True
    )
    start_datetime = fields.Datetime(string="Start", required=True, default=fields.Datetime.now)
    end_datetime = fields.Datetime(string="End", help="Leave empty if ongoing.")
    duration_hours = fields.Float(
        string="Duration (h)", compute="_compute_duration_hours", store=True
    )
    state = fields.Selection(
        [
            ("open", "Open"),
            ("in_progress", "In Progress"),
            ("closed", "Closed"),
        ],
        string="Status", default="open", index=True, tracking=True
    )
    severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Severity", default="medium"
    )
    reason = fields.Char(string="Reason", help="Short reason for downtime.")
    description = fields.Text(string="Description")
    reported_by = fields.Many2one("res.users", string="Reported By", default=lambda self: self.env.user)
    ticket_ref = fields.Char(string="Ticket Reference", help="Internal or vendor ticket number.")
    attachment_count = fields.Integer(
        string="Attachments", compute="_compute_attachment_count", store=False
    )

    @api.depends("start_datetime", "end_datetime")
    def _compute_duration_hours(self):
        for rec in self:
            start = rec.start_datetime
            end = rec.end_datetime or fields.Datetime.now()
            if start and end and end >= start:
                delta = fields.Datetime.to_datetime(end) - fields.Datetime.to_datetime(start)
                rec.duration_hours = delta.total_seconds() / 3600.0
            else:
                rec.duration_hours = 0.0

    def _duration_hours_window(self, window_start, window_end):
        """Helper for parent device: partial duration within [window_start, window_end]."""
        self.ensure_one()
        s = fields.Datetime.to_datetime(self.start_datetime)
        e = fields.Datetime.to_datetime(self.end_datetime or fields.Datetime.now())
        ws = fields.Datetime.to_datetime(window_start)
        we = fields.Datetime.to_datetime(window_end)
        if e <= ws or s >= we:
            return 0.0
        overlap_start = max(s, ws)
        overlap_end = min(e, we)
        if overlap_end <= overlap_start:
            return 0.0
        return (overlap_end - overlap_start).total_seconds() / 3600.0

    @api.constrains("end_datetime", "start_datetime")
    def _check_end_after_start(self):
        for rec in self:
            if rec.end_datetime and rec.start_datetime and rec.end_datetime < rec.start_datetime:
                raise ValidationError(_("End must be on or after Start."))

    def action_close(self):
        for rec in self:
            if rec.state == "closed":
                continue
            if not rec.end_datetime:
                rec.end_datetime = fields.Datetime.now()
            rec.state = "closed"
            rec.device_id.message_post(body=_("Downtime closed (%s h).") % round(rec.duration_hours, 2))

    def action_view_attachments(self):
        self.ensure_one()
        return {
            "name": _("Attachments"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", self._name), ("res_id", "=", rec.id)]
            )


# =============================================================================
# Device Calibration / QC Log
# =============================================================================
class ClinicalImagingDeviceCalibration(models.Model):
    _name = "clinical.imaging.device.calibration"
    _description = "Imaging Device Calibration / QC"
    _order = "date desc, id desc"
    _check_company_auto = True

    device_id = fields.Many2one(
        "clinical.imaging.device", string="Device",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="device_id.company_id", store=True, readonly=True
    )
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    type = fields.Selection(
        [
            ("install", "Installation Acceptance"),
            ("preventive", "Preventive Maintenance QC"),
            ("periodic", "Periodic QC"),
            ("postrepair", "Post-Repair QC"),
            ("dosecheck", "Dose Check"),
            ("other", "Other"),
        ],
        string="Type", default="periodic", required=True
    )
    passed = fields.Boolean(string="Passed", default=True)
    findings = fields.Text(string="Findings / Notes")
    attachment = fields.Binary(string="Report Attachment", attachment=True)
    attachment_filename = fields.Char(string="File Name")
    performed_by = fields.Many2one("hr.employee", string="Performed By",
                                   help="Technician or engineer who performed the QC/calibration.")
    next_due_date = fields.Date(string="Next Due Date", help="Next suggested QC/calibration date.")
    reference_measure = fields.Char(
        string="Reference Measure",
        help="Optional summarized metrics (e.g., calibration offsets)."
    )

    @api.constrains("next_due_date", "date")
    def _check_next_due_after_date(self):
        for rec in self:
            if rec.next_due_date and rec.date and rec.next_due_date < rec.date:
                raise ValidationError(_("Next Due Date must be on or after the QC/Calibration Date."))


# =============================================================================
# Device Connectivity (DICOM endpoints, etc.)
# =============================================================================
class ClinicalImagingDeviceConnectivity(models.Model):
    _name = "clinical.imaging.device.connectivity"
    _description = "Imaging Device Connectivity"
    _order = "device_id, ae_title, host, port"
    _check_company_auto = True

    device_id = fields.Many2one(
        "clinical.imaging.device", string="Device",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="device_id.company_id", store=True, readonly=True
    )

    # Endpoint definition
    role = fields.Selection(
        [
            ("scp", "Storage SCP"),
            ("scu", "Storage SCU"),
            ("qrs", "Query/Retrieve SCP"),
            ("qrq", "Query/Retrieve SCU"),
            ("worklist_scp", "MWL SCP"),
            ("print_scp", "Print SCP"),
            ("other", "Other"),
        ],
        string="DICOM Role", default="scp", required=True
    )
    ae_title = fields.Char(
        string="AE Title", required=True,
        help="AE Title for this endpoint (≤16 chars, uppercase, no spaces)."
    )
    host = fields.Char(string="Host/IP", required=True)
    port = fields.Integer(string="Port", required=True, default=104)
    use_tls = fields.Boolean(string="Use TLS")
    description = fields.Char(string="Description")
    is_default = fields.Boolean(
        string="Default Endpoint", default=False,
        help="Mark as default endpoint for this device/role."
    )

    @api.constrains("port")
    def _check_port_range(self):
        for rec in self:
            if rec.port < 1 or rec.port > 65535:
                raise ValidationError(_("Port must be in range 1..65535."))

    @api.constrains("ae_title")
    def _check_ae_title(self):
        for rec in self:
            if rec.ae_title:
                if len(rec.ae_title) > 16:
                    raise ValidationError(_("AE Title must be 16 characters or fewer."))
                if " " in rec.ae_title:
                    raise ValidationError(_("AE Title cannot contain spaces."))
                if not rec.ae_title.isupper():
                    raise ValidationError(_("AE Title must be uppercase."))

    _endpoint_unique = models.Constraint(
        'unique(device_id, ae_title, host, port, company_id)',
        'An identical endpoint already exists for this device.',
    )


# =============================================================================
# Soft links on Imaging to navigate back to Device logs (smart buttons)
# =============================================================================
# class ClinicalImaging(models.Model):
#     _inherit = "clinical.imaging"

#     device_downtime_count = fields.Integer(
#         string="Downtimes", compute="_compute_device_log_counts", store=False
#     )
#     device_calibration_count = fields.Integer(
#         string="Calibrations/QC", compute="_compute_device_log_counts", store=False
#     )

#     def _compute_device_log_counts(self):
#         Downtime = self.env["clinical.imaging.device.downtime"]
#         Calib = self.env["clinical.imaging.device.calibration"]
#         for rec in self:
#             if rec.device_id:
#                 rec.device_downtime_count = Downtime.search_count([("device_id", "=", rec.device_id.id)])
#                 rec.device_calibration_count = Calib.search_count([("device_id", "=", rec.device_id.id)])
#             else:
#                 rec.device_downtime_count = 0
#                 rec.device_calibration_count = 0

#     def action_open_device_downtime(self):
#         self.ensure_one()
#         if not self.device_id:
#             raise UserError(_("No device is linked to this imaging."))
#         return {
#             "name": _("Downtime Logs"),
#             "type": "ir.actions.act_window",
#             "res_model": "clinical.imaging.device.downtime",
#             "view_mode": "list,form",
#             "domain": [("device_id", "=", self.device_id.id)],
#             "target": "current",
#         }

#     def action_open_device_calibration(self):
#         self.ensure_one()
#         if not self.device_id:
#             raise UserError(_("No device is linked to this imaging."))
#         return {
#             "name": _("Calibration / QC Logs"),
#             "type": "ir.actions.act_window",
#             "res_model": "clinical.imaging.device.calibration",
#             "view_mode": "list,form",
#             "domain": [("device_id", "=", self.device_id.id)],
#             "target": "current",
#         }


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

    # Clinical context (payer may differ from patient)
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        help="Patient receiving the service. May differ from the invoice customer."
    )
    doctor_id = fields.Many2one(
        "hr.employee", string="Ordering/Reading Doctor",
        domain=[("is_doctor", "=", True)]
    )
    appointment_id = fields.Many2one("clinic.appointment", string="Appointment")
    encounter_id = fields.Many2one("clinic.encounter", string="Clinical Encounter")
    treatment_id = fields.Many2one("clinic.treatment", string="Treatment")
    prescription_order_id = fields.Many2one("clinic.prescription.order", string="Prescription Order")

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
    def name_get(self):
        res = super().name_get()
        out = []
        for rec_id, name in res:
            rec = self.browse(rec_id)
            suffix = []
            if rec.modality:
                suffix.append(rec.modality)
            if rec.imaging_type_id:
                suffix.append(rec.imaging_type_id.display_name)
            if suffix:
                name = f"{name} [{', '.join(suffix)}]"
            out.append((rec_id, name))
        return out


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
    def name_get(self):
        res = super().name_get()
        out = []
        for rec_id, name in res:
            line = self.browse(rec_id)
            tag = []
            if line.is_imaging_line:
                tag.append(_("Imaging"))
            if line.modality:
                tag.append(line.modality)
            if line.imaging_type_id:
                tag.append(line.imaging_type_id.display_name)
            if tag:
                name = f"{name} [{' / '.join(tag)}]"
            out.append((rec_id, name))
        return out


