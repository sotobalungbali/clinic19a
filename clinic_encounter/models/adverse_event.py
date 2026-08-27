# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/adverse_event.py
#
# Tujuan:
# - Mencatat Adverse Event / Near Miss terhubung Encounter/Session/Procedure/Diagnosis/Result/Anesthesia.
# - Klasifikasi (category, type), severity, outcome, kausalitas, faktor kontribusi.
# - Workflow: draft → under_review → closed / cancelled.
# - CAPA (Corrective & Preventive Actions), lampiran, saksi, notifikasi, dan pelaporan regulator.
# - Indikator seriousness & needs_reporting (computed).
#
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# Master: Kategori dan Tipe Kejadian
# =============================================================================
class ClinicAdverseEventCategory(models.Model):
    _name = "clinic.ae.category"
    _description = "Adverse Event Category"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, index=True)
    code = fields.Char(index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company, required=True, index=True)

    _constraint_uniq_code_company = models.Constraint(
        'unique(code, company_id)',
        'Category code must be unique per company.',
    )


class ClinicAdverseEventType(models.Model):
    _name = "clinic.ae.type"
    _description = "Adverse Event Type"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, index=True)
    code = fields.Char(index=True)
    category_id = fields.Many2one("clinic.ae.category", string="Category", index=True, ondelete="set null")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company, required=True, index=True)


# =============================================================================
# Master: Faktor Kontribusi (People, Process, Equipment, Environment, etc.)
# =============================================================================
class ClinicAdverseEventFactor(models.Model):
    _name = "clinic.ae.factor"
    _description = "Adverse Event Contributing Factor"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, index=True)
    code = fields.Char(index=True)
    group = fields.Selection(
        [
            ("people", "People"),
            ("process", "Process/Protocol"),
            ("equipment", "Equipment/Device"),
            ("medication", "Medication"),
            ("environment", "Environment"),
            ("communication", "Communication"),
            ("other", "Other"),
        ],
        string="Group",
        default="other",
        index=True,
    )
    description = fields.Text()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company, required=True, index=True)


# =============================================================================
# Header: Adverse Event
# =============================================================================
class ClinicAdverseEvent(models.Model):
    _name = "clinic.adverse.event"
    _description = "Adverse Event / Near Miss"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_occurred desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identitas & Konteks
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="AE #",
        required=True,
        copy=False,
        default=lambda s: _("New"),
        index=True,
        tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)

    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company, index=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", store=True, readonly=True)

    # Konteks klinis
    encounter_id = fields.Many2one(
        "clinic.encounter", string="Encounter", required=True, ondelete="cascade", index=True, tracking=True
    )
    session_id = fields.Many2one(
        "clinic.procedure.session", string="Procedure Session", ondelete="set null", index=True
    )
    procedure_id = fields.Many2one("clinic.procedure.catalog", string="Procedure", ondelete="set null", index=True)
    diagnosis_id = fields.Many2one("clinic.diagnosis", string="Diagnosis", ondelete="set null", index=True)
    result_id = fields.Many2one("clinic.result.document", string="Related Result", ondelete="set null", index=True)
    anesthesia_case_id = fields.Many2one("clinic.anesthesia.case", string="Anesthesia Case", ondelete="set null", index=True)

    patient_id = fields.Many2one("clinic.patient", related="encounter_id.patient_id", store=True, readonly=True, index=True)
    partner_id = fields.Many2one("res.partner", related="patient_id.partner_id", store=True, readonly=True)
    doctor_id = fields.Many2one("clinic.doctor", related="encounter_id.doctor_id", store=True, readonly=True, index=True)
    room_id = fields.Many2one("clinic.room", string="Location/Room")

    # -------------------------------------------------------------------------
    # Waktu, Pelapor, Saksi
    # -------------------------------------------------------------------------
    date_occurred = fields.Datetime(string="Occurred On", required=True, index=True, tracking=True)
    date_detected = fields.Datetime(string="Detected On", index=True, help="If different from occurrence time.")
    reported_by_id = fields.Many2one("res.users", string="Reported By", default=lambda s: s.env.user, index=True)
    reporter_role = fields.Selection(
        [("staff", "Staff"), ("performer", "Performer"), ("supervisor", "Supervisor"), ("patient", "Patient/Family"), ("other", "Other")],
        string="Reporter Role",
        default="staff",
        index=True,
    )
    witness_partner_ids = fields.Many2many("res.partner", string="Witnesses")

    # -------------------------------------------------------------------------
    # Klasifikasi
    # -------------------------------------------------------------------------
    category_id = fields.Many2one("clinic.ae.category", string="Category", index=True)
    type_id = fields.Many2one("clinic.ae.type", string="Type", index=True)
    factor_ids = fields.Many2many("clinic.ae.factor", string="Contributing Factors")

    classification = fields.Selection(
        [
            ("near_miss", "Near Miss (No Harm)"),
            ("no_harm", "No Harm Incident"),
            ("harm", "Harmful Incident"),
            ("sentinel", "Sentinel Event"),
        ],
        string="Classification",
        default="no_harm",
        index=True,
        tracking=True,
    )
    severity = fields.Selection(
        [
            ("none", "No Harm"),
            ("minor", "Minor"),
            ("moderate", "Moderate"),
            ("severe", "Severe"),
            ("death", "Death"),
        ],
        string="Severity",
        default="none",
        index=True,
        tracking=True,
    )
    outcome = fields.Selection(
        [
            ("recovered", "Recovered"),
            ("recovering", "Recovering"),
            ("sequelae", "Sequelae"),
            ("death", "Death"),
            ("not_applicable", "Not Applicable"),
            ("unknown", "Unknown"),
        ],
        string="Outcome",
        default="unknown",
        index=True,
    )

    # Skala harm (opsional WHO A–I; A–B no harm, C–I harm)
    harm_scale = fields.Selection(
        [
            ("A", "A – Circumstances"),
            ("B", "B – Near Miss"),
            ("C", "C – Reached patient, no harm"),
            ("D", "D – Monitoring/Intervention required"),
            ("E", "E – Temporary harm"),
            ("F", "F – Temporary harm, hospitalization"),
            ("G", "G – Permanent harm"),
            ("H", "H – Intervention to sustain life"),
            ("I", "I – Death"),
        ],
        string="WHO Harm Scale",
        index=True,
    )

    causality = fields.Selection(
        [
            ("certain", "Certain"),
            ("probable", "Probable/Likely"),
            ("possible", "Possible"),
            ("unlikely", "Unlikely"),
            ("conditional", "Conditional/Unclassified"),
            ("unassessable", "Unassessable/Unclassifiable"),
        ],
        string="Causality (WHO-UMC)",
        index=True,
    )

    # Flag seriousness dan kebutuhan pelaporan
    is_serious = fields.Boolean(string="Serious?", compute="_compute_flags", store=True)
    needs_reporting = fields.Boolean(
        string="Needs Regulatory Reporting?",
        compute="_compute_flags",
        store=True,
        help="Computed from severity/classification/outcome; can be overridden.",
    )

    # -------------------------------------------------------------------------
    # Detail klinis & paparan
    # -------------------------------------------------------------------------
    description = fields.Html(string="Description / Narrative", required=True, help="What happened?")
    immediate_action = fields.Text(string="Immediate Actions Taken")
    patient_impact = fields.Text(string="Patient Impact / Symptoms")
    recurrence_risk = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        string="Recurrence Risk",
        default="low",
        index=True,
    )

    # Produk obat / alat (opsional)
    drug_product_id = fields.Many2one("product.product", string="Suspected Drug/Product", ondelete="set null", index=True)
    device_product_id = fields.Many2one("product.product", string="Suspected Device", ondelete="set null", index=True)
    device_lot = fields.Char(string="Device Lot/Serial")
    medication_line_note = fields.Char(string="Dose/Time (if drug-related)")

    # Lampiran & Tag
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_ae_attachment_rel",
        "ae_id",
        "attachment_id",
        string="Attachments",
    )
    tag_ids = fields.Many2many("clinic.soap.tag", string="Tags")

    # -------------------------------------------------------------------------
    # Workflow & Pelaporan Regulator
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("under_review", "Under Review"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        index=True,
        tracking=True,
    )
    reviewer_id = fields.Many2one("res.users", string="Reviewer/QA", index=True)
    date_closed = fields.Datetime(string="Closed On")
    resolution_summary = fields.Text(string="Resolution / Root Cause Summary")

    # Pelaporan regulator
    to_regulator = fields.Boolean(string="Report to Regulator?")
    regulator_body = fields.Char(string="Regulatory Body")
    regulator_reference = fields.Char(string="Regulator Ref #")
    date_reported = fields.Datetime(string="Reported On")

    # CAPA
    action_ids = fields.One2many("clinic.ae.action", "ae_id", string="Actions (CAPA)")
    followup_ids = fields.One2many("clinic.ae.followup", "ae_id", string="Follow-ups / Notes")

    color = fields.Integer(string="Color Index")
    note_internal = fields.Text(string="Internal Notes")

    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment (Legacy)",
        index=True,
        ondelete="set null",
        help="Compatibility field for legacy modules that reference adverse events via 'treatment_id'."
    )


    # -------------------------------------------------------------------------
    # Komputasi Flag
    # -------------------------------------------------------------------------
    @api.depends("severity", "classification", "outcome", "harm_scale", "to_regulator")
    def _compute_flags(self):
        for rec in self:
            # Serious jika: severity ∈ {severe, death} atau classification sentinel, atau harm_scale ∈ {G,H,I} atau outcome death
            serious = False
            if rec.severity in ("severe", "death"):
                serious = True
            if rec.classification == "sentinel":
                serious = True
            if rec.harm_scale in ("G", "H", "I"):
                serious = True
            if rec.outcome == "death":
                serious = True
            rec.is_serious = serious

            # needs_reporting: jika serious atau explicit to_regulator = True
            rec.needs_reporting = bool(serious or rec.to_regulator)

    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------
    @api.onchange("session_id")
    def _onchange_session(self):
        sess = self.session_id
        if not sess:
            return
        vals = {}
        if sess.procedure_id and not self.procedure_id:
            vals["procedure_id"] = sess.procedure_id.id
        if sess.diagnosis_id and not self.diagnosis_id:
            vals["diagnosis_id"] = sess.diagnosis_id.id
        if sess.room_id and not self.room_id:
            vals["room_id"] = sess.room_id.id
        self.update(vals)

    @api.onchange("type_id")
    def _onchange_type(self):
        if self.type_id and self.type_id.category_id and not self.category_id:
            self.category_id = self.type_id.category_id

    # -------------------------------------------------------------------------
    # Constraint & Validasi
    # -------------------------------------------------------------------------
    _constraint_uniq_ae_name_company = models.Constraint(
        'unique(name, company_id)',
        'AE number must be unique per company.',
    )

    @api.constrains("company_id", "encounter_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.encounter_id and rec.company_id and rec.company_id != rec.encounter_id.company_id:
                raise ValidationError(_("Adverse Event company must match Encounter company."))

    @api.constrains("date_occurred", "date_detected")
    def _check_dates(self):
        for rec in self:
            if rec.date_occurred and rec.date_detected and rec.date_detected < rec.date_occurred:
                raise ValidationError(_("Detected On cannot be earlier than Occurred On."))

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = seq.next_by_code("clinic.adverse.event") or _("New")
            # Backfill encounter dari session
            if not vals.get("encounter_id") and vals.get("session_id"):
                sess = self.env["clinic.procedure.session"].browse(vals["session_id"])
                if sess and sess.encounter_id:
                    vals["encounter_id"] = sess.encounter_id.id
        recs = super().create(vals_list)
        # Aktivitas default untuk QA review
        for rec in recs:
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Triage adverse event"),
                    user_id=rec.reviewer_id.id or (rec.encounter_id.user_id.id if rec.encounter_id and rec.encounter_id.user_id else self.env.user.id),
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        # Auto escalate jika serius
        if {"severity", "classification", "harm_scale", "outcome"} & set(vals.keys()):
            for rec in self:
                if rec.is_serious and rec.state == "draft":
                    try:
                        rec.activity_schedule(
                            "mail.mail_activity_data_todo",
                            summary=_("Serious event: start investigation"),
                            user_id=rec.reviewer_id.id or self.env.user.id,
                            date_deadline=fields.Date.today(),
                        )
                    except Exception:
                        pass
        return res

    # -------------------------------------------------------------------------
    # Workflow Actions
    # -------------------------------------------------------------------------
    def action_submit_review(self):
        for rec in self:
            if rec.state not in ("draft", "under_review"):
                raise UserError(_("Only Draft or Under Review can be submitted."))
            rec.write({"state": "under_review"})
        return True

    def action_close(self):
        for rec in self:
            if rec.state not in ("draft", "under_review"):
                raise UserError(_("Only Draft/Under Review can be closed."))
            if not rec.resolution_summary:
                raise UserError(_("Please provide a resolution/root cause summary before closing."))
            rec.write({"state": "closed", "date_closed": fields.Datetime.now()})
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            rec.write({"state": "cancelled"})
            if reason:
                rec.message_post(body=_("Cancelled: %s") % reason)
        return True

    def action_mark_reported(self):
        for rec in self:
            if not rec.regulator_body:
                raise UserError(_("Please fill Regulatory Body before marking reported."))
            rec.write({"date_reported": fields.Datetime.now(), "to_regulator": True})
        return True

    # -------------------------------------------------------------------------
    # Smart Buttons / Actions
    # -------------------------------------------------------------------------
    def action_open_encounter(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter").read()[0]
        action["res_id"] = self.encounter_id.id
        action["domain"] = [("id", "=", self.encounter_id.id)]
        action["view_mode"] = "form"
        return action

    def action_open_session(self):
        self.ensure_one()
        if not self.session_id:
            raise UserError(_("This adverse event is not linked to a session."))
        action = self.env.ref("clinic_encounter.action_clinic_procedure_session").read()[0]
        action["res_id"] = self.session_id.id
        action["domain"] = [("id", "=", self.session_id.id)]
        action["view_mode"] = "form"
        return action

    def action_open_result(self):
        self.ensure_one()
        if not self.result_id:
            raise UserError(_("This adverse event is not linked to a result."))
        action = self.env.ref("clinic_encounter.action_clinic_result_document").read()[0]
        action["res_id"] = self.result_id.id
        action["domain"] = [("id", "=", self.result_id.id)]
        action["view_mode"] = "form"
        return action

    def action_open_anesthesia(self):
        self.ensure_one()
        if not self.anesthesia_case_id:
            raise UserError(_("This adverse event is not linked to an anesthesia case."))
        action = self.env.ref("clinic_encounter.action_clinic_anesthesia_case").read()[0]
        action["res_id"] = self.anesthesia_case_id.id
        action["domain"] = [("id", "=", self.anesthesia_case_id.id)]
        action["view_mode"] = "form"
        return action

    # -------------------------------------------------------------------------
    # Name & Search
    # -------------------------------------------------------------------------
    @api.depends("name", "severity", "type_id")
    def _compute_display_name(self):
        severity_labels = dict(self._fields["severity"].selection)
        for rec in self:
            parts = [rec.name or ""]
            if rec.severity and rec.severity != "none":
                parts.append(severity_labels.get(rec.severity))
            if rec.type_id:
                parts.append(rec.type_id.name)
            rec.display_name = " • ".join([part for part in parts if part])

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", "|", "|",
                  ("name", operator, name),
                  ("type_id.name", operator, name),
                  ("category_id.name", operator, name),
                  ("encounter_id.name", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# =============================================================================
# CAPA (Corrective/Preventive) & Follow-ups
# =============================================================================
class ClinicAdverseEventAction(models.Model):
    _name = "clinic.ae.action"
    _description = "Adverse Event Action (CAPA)"
    _order = "ae_id, deadline, id"
    _check_company_auto = True

    ae_id = fields.Many2one("clinic.adverse.event", string="Adverse Event", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="ae_id.company_id", store=True, readonly=True)

    name = fields.Char(string="Action", required=True, translate=True)
    type = fields.Selection(
        [("corrective", "Corrective"), ("preventive", "Preventive"), ("mitigation", "Mitigation"), ("training", "Training"), ("other", "Other")],
        string="Type",
        default="corrective",
        index=True,
    )
    owner_id = fields.Many2one("res.users", string="Owner", index=True)
    deadline = fields.Datetime(string="Deadline")
    done = fields.Boolean(string="Done?")
    date_done = fields.Datetime(string="Done On")
    effectiveness_note = fields.Text(string="Effectiveness / Verification")
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")

    @api.onchange("done")
    def _onchange_done(self):
        if self.done and not self.date_done:
            self.date_done = fields.Datetime.now()


class ClinicAdverseEventFollowup(models.Model):
    _name = "clinic.ae.followup"
    _description = "Adverse Event Follow-up / Note"
    _order = "ae_id, date_note, id"
    _check_company_auto = True

    ae_id = fields.Many2one("clinic.adverse.event", string="Adverse Event", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="ae_id.company_id", store=True, readonly=True)

    date_note = fields.Datetime(string="Date", default=lambda s: fields.Datetime.now(), index=True)
    user_id = fields.Many2one("res.users", string="By", default=lambda s: s.env.user, index=True)
    note = fields.Text(string="Note / Investigation Step", required=True)
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")


# # =============================================================================
# # Extensions: Encounter & Session bridges
# # =============================================================================
# class ClinicEncounter_AdverseEvent(models.Model):
#     _inherit = "clinic.encounter"

#     ae_ids = fields.One2many("clinic.adverse.event", "encounter_id", string="Adverse Events")
#     ae_count = fields.Integer(string="Adverse Events", compute="_compute_ae_count", store=False)

#     def _compute_ae_count(self):
#         for rec in self:
#             rec.ae_count = len(rec.ae_ids)

#     def action_open_adverse_events(self):
#         self.ensure_one()
#         action = self.env.ref("clinic_encounter.action_clinic_adverse_event").read()[0]
#         action["domain"] = [("encounter_id", "=", self.id)]
#         action["context"] = {"default_encounter_id": self.id}
#         return action


# class ClinicProcedureSession_AdverseEvent(models.Model):
#     _inherit = "clinic.procedure.session"

#     ae_ids = fields.One2many("clinic.adverse.event", "session_id", string="Adverse Events")
#     ae_count = fields.Integer(string="Adverse Events", compute="_compute_ae_count", store=False)

#     def _compute_ae_count(self):
#         for rec in self:
#             rec.ae_count = len(rec.ae_ids)

#     def action_open_adverse_events(self):
#         self.ensure_one()
#         action = self.env.ref("clinic_encounter.action_clinic_adverse_event").read()[0]
#         action["domain"] = [("session_id", "=", self.id)]
#         action["context"] = {
#             "default_session_id": self.id,
#             "default_encounter_id": self.encounter_id.id,
#             "default_procedure_id": self.procedure_id.id if self.procedure_id else False,
#             "default_diagnosis_id": self.diagnosis_id.id if self.diagnosis_id else False,
#         }
#         return action
