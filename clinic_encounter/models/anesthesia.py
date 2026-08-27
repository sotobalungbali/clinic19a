# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/anesthesia.py
#
# Fitur utama:
# - Anesthesia Case (pra → intra → pasca/PACU) terhubung Encounter/Session/Procedure.
# - Preop assessment (ASA, Mallampati, airway), checklist, consent indicator.
# - Intraop timeline: obat, vital signs berkala, airway events, cairan (in/out), estimasi perdarahan.
# - Postop: Aldrete score, nyeri, PONV, komplikasi, readiness discharge.
# - Durasi, net fluid balance, indikator abnormal; workflow start/pause/resume/done/cancel.
# - Billing bridge: per-case / per-time (unit menit) / no-bill.
# - Interop: memanfaatkan Execution Log (jika Session tersedia) & Result Document (opsional).
#
import math
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# Header: Anesthesia Case
# =============================================================================
class ClinicAnesthesiaCase(models.Model):
    _name = "clinic.anesthesia.case"
    _description = "Anesthesia Case"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identitas & Konteks
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Anesthesia #",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
        tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Procedure Session",
        ondelete="set null",
        index=True,
        help="If linked to a specific surgical/operative session.",
    )
    procedure_id = fields.Many2one(
        "clinic.procedure.catalog",
        string="Procedure",
        ondelete="set null",
        index=True,
    )
    diagnosis_id = fields.Many2one("clinic.diagnosis", string="Diagnosis", ondelete="set null", index=True)

    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        related="encounter_id.patient_id",
        store=True,
        readonly=True,
        index=True,
    )
    partner_id = fields.Many2one("res.partner", related="patient_id.partner_id", store=True, readonly=True)
    doctor_id = fields.Many2one("clinic.doctor", string="Responsible Surgeon/Doctor", related="encounter_id.doctor_id", store=True, readonly=True)
    anesthetist_id = fields.Many2one("clinic.doctor", string="Anesthetist", index=True, tracking=True)
    performer_user_id = fields.Many2one("res.users", string="Operator (User)", default=lambda s: s.env.user)
    room_id = fields.Many2one("clinic.room", string="Room/OR")

    # Consent awareness (read-only indikator dari encounter/session)
    consent_required = fields.Boolean(
        string="Consent Required",
        compute="_compute_consent_required",
        store=True,
        help="Derived from procedure template/policy; start will be blocked if not valid.",
    )
    consent_ok = fields.Boolean(
        string="Consent OK",
        compute="_compute_consent_ok",
        store=True,
        help="Encounter-level consent validity indicator.",
    )

    # -------------------------------------------------------------------------
    # Waktu & Status
    # -------------------------------------------------------------------------
    planned_start = fields.Datetime(string="Planned Start")
    planned_end = fields.Datetime(string="Planned End")

    date_start = fields.Datetime(string="Start", tracking=True)
    date_end = fields.Datetime(string="End", tracking=True)
    anesthesia_duration_min = fields.Float(
        string="Duration (min)",
        compute="_compute_duration",
        store=True,
        help="End - Start in minutes.",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("paused", "Paused"),
            ("done", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )

    # -------------------------------------------------------------------------
    # PREOP — Assessment & Checklist
    # -------------------------------------------------------------------------
    asa_class = fields.Selection(
        [
            ("1", "ASA I"),
            ("2", "ASA II"),
            ("3", "ASA III"),
            ("4", "ASA IV"),
            ("5", "ASA V"),
            ("6", "ASA VI"),
        ],
        string="ASA Class",
        index=True,
        help="American Society of Anesthesiologists physical status classification.",
    )
    asa_emergency = fields.Boolean(string="Emergency (E)", help="Append E for emergency cases.")
    mallampati = fields.Selection(
        [("1", "I"), ("2", "II"), ("3", "III"), ("4", "IV")],
        string="Mallampati Score",
        help="Oropharyngeal view classification.",
    )
    airway_difficult_predicted = fields.Boolean(string="Predicted Difficult Airway")
    airway_findings = fields.Char(string="Airway Notes")
    thyromental_distance_cm = fields.Float(string="Thyromental Distance (cm)")
    mouth_opening_cm = fields.Float(string="Mouth Opening (cm)")
    neck_mobility = fields.Selection(
        [("normal", "Normal"), ("limited", "Limited")],
        string="Neck Mobility",
    )
    allergies = fields.Text(string="Allergies")
    fasting_since = fields.Datetime(string="Fasting Since")
    preop_checklist_ok = fields.Boolean(string="Preop Checklist OK")
    preop_notes = fields.Text(string="Preoperative Notes")

    # -------------------------------------------------------------------------
    # TEKNIK — Plan & Technique
    # -------------------------------------------------------------------------
    anesthesia_type = fields.Selection(
        [
            ("general", "General"),
            ("regional", "Regional"),
            ("neuraxial", "Neuraxial (Spinal/Epidural)"),
            ("sedation", "Monitored Anesthesia Care/ Sedation"),
            ("local", "Local"),
            ("combined", "Combined"),
        ],
        string="Anesthesia Type",
        index=True,
    )
    technique_notes = fields.Text(string="Technique Notes")
    airway_device = fields.Selection(
        [
            ("mask", "Face Mask"),
            ("lma", "Laryngeal Mask Airway"),
            ("ett", "Endotracheal Tube"),
            ("trach", "Tracheostomy"),
            ("none", "None / Nasal Cannula"),
        ],
        string="Airway Device (Primary)",
    )
    airway_device_size = fields.Char(string="Device Size")
    laryngoscopy_grade = fields.Selection(
        [("1", "Cormack-Lehane I"), ("2", "II"), ("3", "III"), ("4", "IV")],
        string="Laryngoscopy Grade",
        help="Worst grade during intubation.",
    )
    intubation_attempts = fields.Integer(string="Intubation Attempts")
    intubation_success = fields.Boolean(string="Intubation Successful")

    # -------------------------------------------------------------------------
    # INTRAOP — Lines
    # -------------------------------------------------------------------------
    medication_ids = fields.One2many("clinic.anesthesia.medication", "case_id", string="Medications")
    vital_ids = fields.One2many("clinic.anesthesia.vital", "case_id", string="Vitals Timeline")
    fluid_ids = fields.One2many("clinic.anesthesia.fluid", "case_id", string="Fluids In/Out")
    airway_ids = fields.One2many("clinic.anesthesia.airway", "case_id", string="Airway Events")
    event_ids = fields.One2many("clinic.anesthesia.event", "case_id", string="Intraop Events/Notes")

    total_fluid_in_ml = fields.Float(string="Total In (ml)", compute="_compute_fluid_totals", store=True)
    total_fluid_out_ml = fields.Float(string="Total Out (ml)", compute="_compute_fluid_totals", store=True)
    net_fluid_balance_ml = fields.Float(string="Net Balance (ml)", compute="_compute_fluid_totals", store=True)
    total_blood_loss_ml = fields.Float(string="Total Blood Loss (ml)", compute="_compute_fluid_totals", store=True)
    total_urine_ml = fields.Float(string="Urine Output (ml)", compute="_compute_fluid_totals", store=True)

    intraop_complication = fields.Boolean(string="Any Intraop Complication?")
    intraop_complication_note = fields.Text(string="Complication Details")

    # -------------------------------------------------------------------------
    # POSTOP / PACU
    # -------------------------------------------------------------------------
    pain_scale = fields.Selection([(str(i), str(i)) for i in range(0, 11)], string="Pain Scale (0–10)")
    nausea_vomiting = fields.Selection(
        [("none", "None"), ("mild", "Mild"), ("moderate", "Moderate"), ("severe", "Severe")],
        string="Nausea/Vomiting",
    )
    rass_score = fields.Integer(string="RASS (−5..+4)", help="Richmond Agitation-Sedation Scale")
    aldrete_activity = fields.Selection([("0", "0"), ("1", "1"), ("2", "2")], string="Aldrete: Activity", default="2")
    aldrete_respiration = fields.Selection([("0", "0"), ("1", "1"), ("2", "2")], string="Aldrete: Respiration", default="2")
    aldrete_circulation = fields.Selection([("0", "0"), ("1", "1"), ("2", "2")], string="Aldrete: Circulation", default="2")
    aldrete_consciousness = fields.Selection([("0", "0"), ("1", "1"), ("2", "2")], string="Aldrete: Consciousness", default="2")
    aldrete_color = fields.Selection([("0", "0"), ("1", "1"), ("2", "2")], string="Aldrete: O2 Sat/Color", default="2")
    aldrete_total = fields.Integer(string="Aldrete Total", compute="_compute_aldrete", store=True)
    ready_for_discharge = fields.Boolean(string="Ready for Discharge")

    postop_complication = fields.Boolean(string="Any Postop Complication?")
    postop_complication_note = fields.Text(string="Postop Complication Details")

    # -------------------------------------------------------------------------
    # Billing (soft-coupled)
    # -------------------------------------------------------------------------
    billing_policy = fields.Selection(
        [
            ("per_case", "Bill per Case"),
            ("per_time", "Bill by Time Unit"),
            ("no_bill", "Do Not Bill"),
        ],
        string="Billing Policy",
        default="per_case",
        help="Control how invoice lines are prepared for this anesthesia case.",
    )
    product_case_id = fields.Many2one("product.product", string="Product (Case)")
    product_time_id = fields.Many2one("product.product", string="Product (Time Unit)")
    time_unit_minutes = fields.Integer(string="Time Unit (min)", default=15)
    base_units = fields.Integer(string="Base Units", default=0, help="Optional fixed units billed per case (anesthesia base units).")
    invoice_line_ids = fields.Many2many(
        "account.move.line",
        "clinic_anesthesia_invoice_line_rel",
        "case_id",
        "aml_id",
        string="Invoice Lines",
        help="Billing lines associated with this anesthesia case.",
    )
    invoice_count = fields.Integer(string="Invoices", compute="_compute_invoice_count", store=False)

    # UI
    tag_ids = fields.Many2many("clinic.soap.tag", string="Tags")
    color = fields.Integer(string="Color Index")
    note_internal = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------
    @api.depends("procedure_id.require_consent", "session_id", "session_id.require_consent")
    def _compute_consent_required(self):
        for rec in self:
            # Prioritaskan policy dari procedure catalog atau session
            need = False
            if rec.session_id and rec.session_id.require_consent:
                need = True
            elif rec.procedure_id and rec.procedure_id.require_consent:
                need = True
            rec.consent_required = need

    @api.depends("encounter_id.consent_ok")
    def _compute_consent_ok(self):
        for rec in self:
            rec.consent_ok = bool(rec.encounter_id and rec.encounter_id.consent_ok)

    @api.depends("date_start", "date_end")
    def _compute_duration(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end >= rec.date_start:
                delta = rec.date_end - rec.date_start
                rec.anesthesia_duration_min = delta.total_seconds() / 60.0
            else:
                rec.anesthesia_duration_min = 0.0

    @api.depends(
        "fluid_ids.direction",
        "fluid_ids.volume_ml",
        "fluid_ids.is_blood_loss",
        "fluid_ids.is_urine"
    )
    def _compute_fluid_totals(self):
        for rec in self:
            ins = sum(l.volume_ml for l in rec.fluid_ids.filtered(lambda x: x.direction == "in"))
            outs = sum(l.volume_ml for l in rec.fluid_ids.filtered(lambda x: x.direction == "out"))
            blood = sum(l.volume_ml for l in rec.fluid_ids.filtered(lambda x: x.is_blood_loss))
            urine = sum(l.volume_ml for l in rec.fluid_ids.filtered(lambda x: x.is_urine))
            rec.total_fluid_in_ml = ins
            rec.total_fluid_out_ml = outs
            rec.net_fluid_balance_ml = ins - outs
            rec.total_blood_loss_ml = blood
            rec.total_urine_ml = urine

    @api.depends(
        "aldrete_activity",
        "aldrete_respiration",
        "aldrete_circulation",
        "aldrete_consciousness",
        "aldrete_color",
    )
    def _compute_aldrete(self):
        for rec in self:
            def v(x): return int(x or 0)
            rec.aldrete_total = v(rec.aldrete_activity) + v(rec.aldrete_respiration) + v(rec.aldrete_circulation) + v(rec.aldrete_consciousness) + v(rec.aldrete_color)

    def _compute_invoice_count(self):
        AccountMove = self.env["account.move"]
        for rec in self:
            moves = AccountMove.search([
                ("line_ids", "in", rec.invoice_line_ids.ids or [0]),
                ("company_id", "=", rec.company_id.id),
                ("move_type", "in", ["out_invoice", "out_refund"]),
            ])
            rec.invoice_count = len(moves)

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
        if sess.room_id and not self.room_id:
            vals["room_id"] = sess.room_id.id
        if sess.performer_doctor_id and not self.anesthetist_id:
            # Jika modul anesthetist terpisah tidak ada, gunakan field doctor umum
            vals["anesthetist_id"] = sess.performer_doctor_id.id
        if sess.diagnosis_id and not self.diagnosis_id:
            vals["diagnosis_id"] = sess.diagnosis_id.id
        self.update(vals)

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    _constraint_uniq_anesthesia_name_company = models.Constraint(
        'unique(name, company_id)',
        'Anesthesia number must be unique per company.',
    )
    _constraint_check_time_unit = models.Constraint(
        'CHECK (time_unit_minutes > 0)',
        'Time unit must be positive.',
    )

    @api.constrains("company_id", "encounter_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.encounter_id and rec.company_id and rec.company_id != rec.encounter_id.company_id:
                raise ValidationError(_("Anesthesia company must match Encounter company."))

    @api.constrains("planned_start", "planned_end")
    def _check_planned_window(self):
        for rec in self:
            if rec.planned_start and rec.planned_end and rec.planned_end < rec.planned_start:
                raise ValidationError(_("Planned End cannot be earlier than Planned Start."))

    @api.constrains("date_start", "date_end")
    def _check_actual_window(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("End cannot be earlier than Start."))

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
                vals["name"] = seq.next_by_code("clinic.anesthesia.case") or _("New")
            # Backfill encounter dari session bila perlu
            if not vals.get("encounter_id") and vals.get("session_id"):
                sess = self.env["clinic.procedure.session"].browse(vals["session_id"])
                if sess and sess.encounter_id:
                    vals["encounter_id"] = sess.encounter_id.id
        recs = super().create(vals_list)
        # Activity default
        for rec in recs:
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Prepare anesthesia preop assessment"),
                    user_id=rec.performer_user_id.id or self.env.user.id,
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
        return recs

    # -------------------------------------------------------------------------
    # Workflow
    # -------------------------------------------------------------------------
    def _preflight_start(self):
        for rec in self:
            if rec.consent_required and not rec.consent_ok:
                raise UserError(_("Consent is required before starting anesthesia."))
            if rec.asa_class in (False, None):
                rec.message_post(body=_("Starting without ASA classification."))

    def action_start(self):
        self._preflight_start()
        now = fields.Datetime.now()
        for rec in self:
            updates = {"state": "in_progress"}
            if not rec.date_start:
                updates["date_start"] = now
            rec.write(updates)
            # Log ke execution log (jika punya session)
            try:
                if rec.session_id:
                    rec.session_id._log_event("note", message=_("Anesthesia started"), role="performer")
            except Exception:
                pass
        return True

    def action_pause(self, reason=None):
        for rec in self:
            if rec.state != "in_progress":
                raise UserError(_("Only 'In Progress' case can be paused."))
            rec.write({"state": "paused"})
            if reason:
                rec.message_post(body=_("Paused: %s") % reason)
        return True

    def action_resume(self):
        for rec in self:
            if rec.state != "paused":
                raise UserError(_("Only 'Paused' case can be resumed."))
            rec.write({"state": "in_progress"})
        return True

    def action_done(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state not in ("in_progress", "paused", "draft"):
                raise UserError(_("Only Draft/In Progress/Paused case can be completed."))
            updates = {"state": "done"}
            if not rec.date_start:
                updates["date_start"] = now
            if not rec.date_end:
                updates["date_end"] = now
            rec.write(updates)
            # Tandai session done bila relevan (tidak memaksa)
            try:
                if rec.session_id and rec.session_id.state not in ("done", "cancelled"):
                    rec.session_id.action_done()
            except Exception:
                pass
            # Follow-up ke owner encounter
            try:
                rec.encounter_id.push_activity_followup(
                    summary=_("Review anesthesia record"),
                    days=1,
                    user=rec.encounter_id.user_id or rec.performer_user_id,
                )
            except Exception:
                pass
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            rec.write({"state": "cancelled"})
            if reason:
                rec.message_post(body=_("Cancelled: %s") % reason)
        return True

    # -------------------------------------------------------------------------
    # Billing Bridges
    # -------------------------------------------------------------------------
    def _map_taxes(self, taxes, partner, product=None):
        fpos = partner.property_account_position_id if partner else False
        return fpos.map_tax(taxes, product=product, partner=partner) if fpos else taxes

    def _income_account_from_product(self, product):
        if not product:
            return False
        if getattr(product, "property_account_income_id", False) and product.property_account_income_id:
            return product.property_account_income_id.id
        if product.categ_id and product.categ_id.property_account_income_categ_id:
            return product.categ_id.property_account_income_categ_id.id
        return False

    def action_prepare_invoice_line_vals(self):
        """
        Siapkan list of dict untuk pembuatan account.move.line:
        - per_case: 1 baris menggunakan product_case_id
        - per_time: base_units (opsional) + ceil(durasi/time_unit_minutes) time units menggunakan product_time_id
        - no_bill : []
        """
        lines = []
        for rec in self:
            if rec.billing_policy == "no_bill":
                continue
            partner = rec.partner_id
            if not partner:
                raise UserError(_("Patient partner is not set on the Encounter."))

            # per_case
            if rec.billing_policy == "per_case":
                if not rec.product_case_id:
                    rec.message_post(body=_("Billing per case but product_case is not set."))
                    continue
                taxes = rec._map_taxes(rec.product_case_id.taxes_id, partner, rec.product_case_id)
                account_id = rec._income_account_from_product(rec.product_case_id)
                lines.append({
                    "name": _("Anesthesia Case — %s") % (rec.procedure_id.display_name if rec.procedure_id else rec.name),
                    "quantity": 1.0,
                    "price_unit": rec.product_case_id.lst_price,
                    "discount": 0.0,
                    "product_id": rec.product_case_id.id,
                    "product_uom_id": rec.product_case_id.uom_id.id,
                    "tax_ids": [(6, 0, taxes.ids)] if taxes else [],
                    "account_id": account_id,
                    "currency_id": rec.currency_id.id,
                })

            # per_time
            if rec.billing_policy == "per_time":
                if not rec.product_time_id:
                    rec.message_post(body=_("Billing by time but product_time is not set."))
                    continue
                units = 0
                # Base units opsional
                units += max(int(rec.base_units or 0), 0)
                # Time units dari durasi
                if rec.time_unit_minutes > 0 and rec.anesthesia_duration_min > 0:
                    units += int(math.ceil(rec.anesthesia_duration_min / float(rec.time_unit_minutes)))
                if units <= 0:
                    continue
                taxes = rec._map_taxes(rec.product_time_id.taxes_id, partner, rec.product_time_id)
                account_id = rec._income_account_from_product(rec.product_time_id)
                lines.append({
                    "name": _("Anesthesia Time Units — %s min units") % rec.time_unit_minutes,
                    "quantity": units,
                    "price_unit": rec.product_time_id.lst_price,
                    "discount": 0.0,
                    "product_id": rec.product_time_id.id,
                    "product_uom_id": rec.product_time_id.uom_id.id,
                    "tax_ids": [(6, 0, taxes.ids)] if taxes else [],
                    "account_id": account_id,
                    "currency_id": rec.currency_id.id,
                })
        return lines

    def action_open_billing(self):
        """Buka invoice terkait; fallback ke invoice_origin encounter."""
        self.ensure_one()
        AccountMove = self.env["account.move"]
        moves = AccountMove.search([
            ("line_ids", "in", self.invoice_line_ids.ids or [0]),
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", ["out_invoice", "out_refund"]),
        ])
        if not moves and self.encounter_id:
            moves = AccountMove.search([
                ("invoice_origin", "=", self.encounter_id.name),
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("company_id", "=", self.company_id.id),
            ])
        if not moves:
            raise UserError(_("No related invoices found."))
        action = self.env.ref("account.action_move_out_invoice_type").read()[0]
        action["domain"] = [("id", "in", moves.ids)]
        return action

    # -------------------------------------------------------------------------
    # Result document (opsional)
    # -------------------------------------------------------------------------
    def action_generate_result_document(self):
        """
        Buat result document ringkas dari data anesthesia (opsional).
        """
        self.ensure_one()
        Result = self.env["clinic.result.document"]
        title = _("Anesthesia Report — %s") % (self.procedure_id.display_name if self.procedure_id else self.name)
        # Ringkasan sederhana
        summary = "<p><b>Type:</b> %s</p>" % dict(self._fields["anesthesia_type"].selection).get(self.anesthesia_type, _("N/A"))
        summary += "<p><b>ASA:</b> %s%s</p>" % (
            self.asa_class or "-",
            "E" if self.asa_emergency else "",
        )
        summary += "<p><b>Duration:</b> %.0f min</p>" % (self.anesthesia_duration_min or 0)
        res = Result.create({
            "encounter_id": self.encounter_id.id,
            "session_id": self.session_id.id if self.session_id else False,
            "procedure_id": self.procedure_id.id if self.procedure_id else False,
            "diagnosis_id": self.diagnosis_id.id if self.diagnosis_id else False,
            "title": title,
            "summary": summary,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Result"),
            "res_model": "clinic.result.document",
            "res_id": res.id,
            "view_mode": "form",
        }

    # -------------------------------------------------------------------------
    # Name & Search
    # -------------------------------------------------------------------------
    @api.depends("name", "procedure_id")
    def _compute_display_name(self):
        for rec in self:
            label = rec.name or ""
            if rec.procedure_id:
                label = f"{rec.name or ''} • {rec.procedure_id.display_name or rec.procedure_id.name}"
            rec.display_name = label

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", "|",
                  ("name", operator, name),
                  ("procedure_id.name", operator, name),
                  ("encounter_id.name", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# =============================================================================
# Lines: Medications
# =============================================================================
class ClinicAnesthesiaMedication(models.Model):
    _name = "clinic.anesthesia.medication"
    _description = "Anesthesia Medication Line"
    _order = "case_id, time_admin, id"
    _check_company_auto = True

    case_id = fields.Many2one("clinic.anesthesia.case", string="Anesthesia Case", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="case_id.company_id", store=True, readonly=True)

    time_admin = fields.Datetime(string="Time", default=lambda s: fields.Datetime.now(), index=True)
    product_id = fields.Many2one("product.product", string="Drug/Product", required=True, ondelete="restrict", index=True)
    dose = fields.Float(string="Dose")
    dose_uom = fields.Many2one("uom.uom", string="Dose UoM")
    route = fields.Selection(
        [("iv", "IV"), ("im", "IM"), ("po", "PO"), ("inh", "Inhalation"), ("sc", "SC"), ("topical", "Topical"), ("other", "Other")],
        string="Route",
        default="iv",
    )
    remark = fields.Char(string="Remark / Purpose")

    @api.onchange("product_id")
    def _onchange_product(self):
        if self.product_id and not self.dose_uom:
            self.dose_uom = self.product_id.uom_id


# =============================================================================
# Lines: Vitals Timeline
# =============================================================================
class ClinicAnesthesiaVital(models.Model):
    _name = "clinic.anesthesia.vital"
    _description = "Anesthesia Vital Sign"
    _order = "case_id, time_point asc, id asc"
    _check_company_auto = True

    case_id = fields.Many2one("clinic.anesthesia.case", string="Anesthesia Case", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="case_id.company_id", store=True, readonly=True)

    time_point = fields.Datetime(string="Time", required=True, default=lambda s: fields.Datetime.now(), index=True)
    hr = fields.Integer(string="HR")
    rr = fields.Integer(string="RR")
    spo2 = fields.Integer(string="SpO₂ (%)")
    sbp = fields.Integer(string="SBP")
    dbp = fields.Integer(string="DBP")
    map = fields.Integer(string="MAP")
    temp = fields.Float(string="Temp (°C)", digits=(16, 2))
    etco2 = fields.Integer(string="EtCO₂ (mmHg)")
    fio2 = fields.Integer(string="FiO₂ (%)")
    agent = fields.Char(string="Agent (End-tidal)")
    agent_et = fields.Float(string="Agent ET (%)", digits=(16, 2))

    note = fields.Char(string="Note")


# =============================================================================
# Lines: Fluids In/Out
# =============================================================================
class ClinicAnesthesiaFluid(models.Model):
    _name = "clinic.anesthesia.fluid"
    _description = "Anesthesia Fluid In/Out"
    _order = "case_id, time_move, id"
    _check_company_auto = True

    case_id = fields.Many2one("clinic.anesthesia.case", string="Anesthesia Case", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="case_id.company_id", store=True, readonly=True)
    time_move = fields.Datetime(string="Time", default=lambda s: fields.Datetime.now(), index=True)

    direction = fields.Selection([("in", "In"), ("out", "Out")], string="Direction", required=True, default="in", index=True)
    product_id = fields.Many2one("product.product", string="Fluid/Blood Product", ondelete="restrict", index=True)
    volume_ml = fields.Float(string="Volume (ml)", required=True)
    is_blood_loss = fields.Boolean(string="Blood Loss?")
    is_urine = fields.Boolean(string="Urine?")

    remark = fields.Char(string="Remark")

    _constraint_qty_nonneg = models.Constraint(
        'CHECK (volume_ml >= 0)',
        'Volume must be positive or zero.',
    )


# =============================================================================
# Lines: Airway Events
# =============================================================================
class ClinicAnesthesiaAirway(models.Model):
    _name = "clinic.anesthesia.airway"
    _description = "Anesthesia Airway Event"
    _order = "case_id, time_event, id"
    _check_company_auto = True

    case_id = fields.Many2one("clinic.anesthesia.case", string="Anesthesia Case", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="case_id.company_id", store=True, readonly=True)

    time_event = fields.Datetime(string="Time", default=lambda s: fields.Datetime.now(), index=True)
    event = fields.Selection(
        [
            ("preoxygenation", "Preoxygenation"),
            ("induction", "Induction"),
            ("laryngoscopy", "Laryngoscopy"),
            ("intubation", "Intubation"),
            ("lma_insertion", "LMA Insertion"),
            ("airway_change", "Airway Device Change"),
            ("extubation", "Extubation"),
            ("emergence", "Emergence"),
            ("other", "Other"),
        ],
        string="Event",
        required=True,
    )
    device = fields.Selection(
        [("mask", "Face Mask"), ("lma", "LMA"), ("ett", "ETT"), ("nc", "Nasal Cannula"), ("other", "Other")],
        string="Device",
    )
    device_size = fields.Char(string="Size")
    attempts = fields.Integer(string="Attempts")
    success = fields.Boolean(string="Successful?")
    grade = fields.Selection([("1", "CL I"), ("2", "CL II"), ("3", "CL III"), ("4", "CL IV")], string="Laryngoscopy Grade")
    confirmation = fields.Selection(
        [("capno", "EtCO₂"), ("ausc", "Auscultation"), ("chest", "Chest Rise"), ("other", "Other")],
        string="Confirmation",
    )
    note = fields.Char(string="Note")


# =============================================================================
# Lines: Generic Intraop Event/Note
# =============================================================================
class ClinicAnesthesiaEvent(models.Model):
    _name = "clinic.anesthesia.event"
    _description = "Anesthesia Intraop Event/Note"
    _order = "case_id, time_event, id"
    _check_company_auto = True

    case_id = fields.Many2one("clinic.anesthesia.case", string="Anesthesia Case", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="case_id.company_id", store=True, readonly=True)

    time_event = fields.Datetime(string="Time", default=lambda s: fields.Datetime.now(), index=True)
    category = fields.Selection(
        [
            ("induction", "Induction"),
            ("maintenance", "Maintenance"),
            ("emergence", "Emergence"),
            ("positioning", "Positioning"),
            ("device", "Device"),
            ("complication", "Complication"),
            ("communication", "Communication"),
            ("other", "Other"),
        ],
        string="Category",
        default="other",
        required=True,
    )
    description = fields.Text(string="Description")
    critical = fields.Boolean(string="Critical?")
