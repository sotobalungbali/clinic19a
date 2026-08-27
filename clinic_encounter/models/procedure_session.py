# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/procedure_session.py
#
# Gabungan penuh:
# - BASE clinic.procedure.session (timer, performer, billing, inventory bridges)
# - + Result bridges (result_ids, result_count, actions)
# - + Consent bridges (consent_valid compute)
# - + Checklist bridges (checklist_ids, compliant, actions, preflight check)
# - + Adverse Event bridges (ae_ids, actions)
# - + Execution Log hooks (auto-log create/start/pause/resume/done/cancel, log_note)
#
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicProcedureSession(models.Model):
    _name = "clinic.procedure.session"
    _description = "Procedure Session"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identitas & Perusahaan
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Session #",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
        tracking=True,
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10, index=True)

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

    # -------------------------------------------------------------------------
    # Konteks Encounter & Rencana
    # -------------------------------------------------------------------------
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    encounter_procedure_id = fields.Many2one(
        "clinic.encounter.procedure",
        string="Plan Line",
        ondelete="set null",
        index=True,
        help="The plan line this session belongs to.",
    )
    diagnosis_id = fields.Many2one(
        "clinic.diagnosis",
        string="Diagnosis",
        ondelete="set null",
        index=True,
    )

    # Master procedure (untuk referensi/label/report)
    procedure_id = fields.Many2one(
        "clinic.procedure.catalog",
        string="Procedure",
        ondelete="restrict",
        index=True,
        help="The catalog procedure being executed.",
    )
    # Produk & harga (diizinkan override per session)
    product_id = fields.Many2one("product.product", string="Product")
    uom_id = fields.Many2one("uom.uom", string="UoM")
    quantity = fields.Float(string="Quantity", default=1.0, digits="Product Unit of Measure")

    # -------------------------------------------------------------------------
    # Performer, Room, & Scheduling
    # -------------------------------------------------------------------------
    performer_user_id = fields.Many2one("res.users", string="Performer (User)", tracking=True)
    performer_doctor_id = fields.Many2one("clinic.doctor", string="Performer (Doctor)", tracking=True)
    room_id = fields.Many2one("clinic.room", string="Room")

    planned_start = fields.Datetime(string="Planned Start")
    planned_end = fields.Datetime(string="Planned End")
    planned_duration = fields.Float(string="Planned Duration (min)")

    date_start = fields.Datetime(string="Start", tracking=True)
    date_end = fields.Datetime(string="End", tracking=True)
    actual_duration = fields.Float(
        string="Actual Duration (min)",
        compute="_compute_actual_duration",
        store=True,
    )

    # State machine
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("paused", "Paused"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Consent, Checklist, Hasil
    # -------------------------------------------------------------------------
    require_consent = fields.Boolean(
        string="Require Consent",
        compute="_compute_requirements",
        store=True,
        help="Derived from catalog. Start is blocked if True and there is no valid consent covering this procedure.",
    )
    require_checklist = fields.Boolean(
        string="Require Checklist",
        compute="_compute_requirements",
        store=True,
    )
    # VALIDITAS consent yang relevan dengan prosedur di sesi ini
    consent_valid = fields.Boolean(
        string="Consent Valid for Session",
        compute="_compute_consent_valid_for_session",
        store=False,
        help="True if the encounter has a signed, non-expired consent that covers this session's procedure (or is generic).",
    )
    # CHECKLIST bridges
    checklist_ids = fields.One2many("clinic.checklist", "session_id", string="Checklists")
    checklist_count = fields.Integer(compute="_compute_checklist_count", string="Checklists", store=False)
    checklist_compliant = fields.Boolean(
        string="Checklist Compliant",
        compute="_compute_checklist_compliant",
        store=False,
        help="True if there exists at least one DONE & PASSED checklist linked to this session.",
    )
    # RESULT bridges
    result_ids = fields.One2many("clinic.result.document", "session_id", string="Results")
    result_count = fields.Integer(compute="_compute_result_count", string="Results", store=False)
    # AE bridges
    ae_ids = fields.One2many("clinic.adverse.event", "session_id", string="Adverse Events")
    ae_count = fields.Integer(string="Adverse Events", compute="_compute_ae_count", store=False)

    # Catatan outcome sesi
    result_text = fields.Html(string="Result / Outcome")
    adverse_event_note = fields.Text(string="Adverse Event Note")
    internal_note = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # Penagihan (Per-Session) & Pajak
    # -------------------------------------------------------------------------
    billing_policy = fields.Selection(
        [
            ("per_plan", "Bill per Plan Line"),
            ("per_session", "Bill per Session"),
            ("no_bill", "Do Not Bill"),
        ],
        string="Billing Policy",
        default="per_session",
        help="Default follows plan/catalog; can be overridden for this session.",
    )
    price_unit = fields.Monetary(
        string="Unit Price (Override)",
        currency_field="currency_id",
        help="Leave empty to inherit price from plan line; filled to override.",
    )
    discount = fields.Float(string="Discount (%)", digits=(16, 4))
    tax_ids = fields.Many2many(
        "account.tax",
        "clinic_proc_session_tax_rel",
        "session_id",
        "tax_id",
        string="Customer Taxes",
        domain=[("type_tax_use", "in", ["sale", "none"])],
    )

    price_unit_effective = fields.Monetary(
        string="Effective Unit Price",
        currency_field="currency_id",
        compute="_compute_effective_price",
        store=True,
    )
    price_subtotal = fields.Monetary(string="Subtotal", currency_field="currency_id", compute="_compute_amount", store=True)
    price_tax = fields.Monetary(string="Tax", currency_field="currency_id", compute="_compute_amount", store=True)
    price_total = fields.Monetary(string="Total", currency_field="currency_id", compute="_compute_amount", store=True)

    invoice_line_ids = fields.Many2many(
        "account.move.line",
        "clinic_session_invoice_line_rel",
        "session_id",
        "aml_id",
        string="Invoice Lines",
        help="Billing lines generated from this session.",
    )
    invoice_count = fields.Integer(string="Invoices", compute="_compute_invoice_count", store=False)

    # -------------------------------------------------------------------------
    # Inventory Bridge (opsional melalui aksi)
    # -------------------------------------------------------------------------
    stock_move_ids = fields.Many2many(
        "stock.move",
        "clinic_session_stock_move_rel",
        "session_id",
        "move_id",
        string="Stock Moves",
        help="Consumption/transfer moves linked to this session.",
    )
    stock_move_count = fields.Integer(string="Stock Moves", compute="_compute_stock_move_count", store=False)

    # UI
    color = fields.Integer(string="Color Index")
    priority = fields.Selection([("0", "Normal"), ("1", "High"), ("2", "Urgent")], default="0", index=True)

    # treatment_id = fields.Many2one(
    #     "clinic.treatment.catalog",
    #     string="Treatment (Compatibility)",
    #     ondelete="set null",
    #     index=True,
    #     help="Compatibility alias for legacy modules expecting 'treatment_id'. "
    #          "New workflow uses 'procedure_id' to 'clinic.procedure.catalog'."
    # )

    # Kompatibilitas untuk modul lama yang punya One2many(..., 'treatment_id')
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment (Legacy Link)",
        index=True,
        ondelete="set null",
        help="Compatibility anchor for modules that define One2many to clinic.procedure.session via 'treatment_id'."
    )

    # -------------------------------------------------------------------------
    # Komputasi
    # -------------------------------------------------------------------------
    @api.depends("date_start", "date_end")
    def _compute_actual_duration(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end >= rec.date_start:
                delta = rec.date_end - rec.date_start
                rec.actual_duration = delta.total_seconds() / 60.0
            else:
                rec.actual_duration = 0.0

    @api.depends("procedure_id.require_consent", "procedure_id.require_checklist")
    def _compute_requirements(self):
        for rec in self:
            rec.require_consent = bool(rec.procedure_id and rec.procedure_id.require_consent)
            rec.require_checklist = bool(rec.procedure_id and rec.procedure_id.require_checklist)

    @api.depends("price_unit", "encounter_procedure_id.price_unit", "procedure_id.list_price")
    def _compute_effective_price(self):
        for rec in self:
            if rec.price_unit:
                rec.price_unit_effective = rec.price_unit
            elif rec.encounter_procedure_id and rec.encounter_procedure_id.price_unit:
                rec.price_unit_effective = rec.encounter_procedure_id.price_unit
            elif rec.procedure_id and rec.procedure_id.list_price:
                rec.price_unit_effective = rec.procedure_id.list_price
            else:
                rec.price_unit_effective = 0.0

    @api.depends("price_unit_effective", "quantity", "discount", "tax_ids", "currency_id", "product_id", "encounter_id.partner_id")
    def _compute_amount(self):
        for rec in self:
            qty = rec.quantity or 0.0
            unit = rec.price_unit_effective or 0.0
            effective_price = unit * (1 - (rec.discount or 0.0) / 100.0)

            if rec.tax_ids:
                taxes = rec.tax_ids.compute_all(
                    effective_price,
                    currency=rec.currency_id,
                    quantity=qty,
                    product=rec.product_id,
                    partner=rec.encounter_id.partner_id if rec.encounter_id else None,
                )
                rec.price_subtotal = taxes["total_excluded"]
                rec.price_total = taxes["total_included"]
                rec.price_tax = sum(t["amount"] for t in taxes.get("taxes", []))
            else:
                rec.price_subtotal = effective_price * qty
                rec.price_total = effective_price * qty
                rec.price_tax = 0.0

    def _compute_invoice_count(self):
        AccountMove = self.env["account.move"]
        for rec in self:
            moves = AccountMove.search([
                ("line_ids", "in", rec.invoice_line_ids.ids or [0]),
                ("company_id", "=", rec.company_id.id),
                ("move_type", "in", ["out_invoice", "out_refund"]),
            ])
            rec.invoice_count = len(moves)

    def _compute_stock_move_count(self):
        for rec in self:
            rec.stock_move_count = len(rec.stock_move_ids)

    def _compute_result_count(self):
        for rec in self:
            rec.result_count = len(rec.result_ids)

    def _compute_ae_count(self):
        for rec in self:
            rec.ae_count = len(rec.ae_ids)

    def _compute_checklist_count(self):
        for rec in self:
            rec.checklist_count = len(rec.checklist_ids)

    @api.depends("checklist_ids.state", "checklist_ids.passed")
    def _compute_checklist_compliant(self):
        for rec in self:
            ok = any(cl.state == "done" and cl.passed for cl in rec.checklist_ids)
            rec.checklist_compliant = ok

    @api.depends("encounter_id.consent_ids.state", "encounter_id.consent_ids.date_expiry", "procedure_id")
    def _compute_consent_valid_for_session(self):
        for rec in self:
            valid = False
            enc = rec.encounter_id
            if enc:
                for c in enc.consent_ids.filtered(lambda r: r.state == "signed" and not r.is_expired):
                    if c.covers_procedure(rec.procedure_id):
                        valid = True
                        break
            rec.consent_valid = valid

    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------
    @api.onchange("encounter_procedure_id")
    def _onchange_plan_line(self):
        line = self.encounter_procedure_id
        if not line:
            return
        vals = {}
        # Tarik konteks dari plan
        vals.update({
            "procedure_id": line.procedure_id.id if line.procedure_id else False,
            "product_id": line.product_id.id if line.product_id else False,
            "uom_id": line.uom_id.id if line.uom_id else False,
            "quantity": 1.0,  # per-session default qty 1
            "billing_policy": line.billing_policy or "per_session",
            "tax_ids": [(6, 0, line.tax_ids.ids)] if line.tax_ids else [],
        })
        # Durasi dari plan jika ada
        if line.planned_duration and not self.planned_duration:
            vals["planned_duration"] = line.planned_duration
        # Performer/room preferensi
        if line.performer_user_id and not self.performer_user_id:
            vals["performer_user_id"] = line.performer_user_id.id
        if line.performer_doctor_id and not self.performer_doctor_id:
            vals["performer_doctor_id"] = line.performer_doctor_id.id
        if line.room_id and not self.room_id:
            vals["room_id"] = line.room_id.id
        # Diagnosis dari plan jika ada
        if line.diagnosis_id and not self.diagnosis_id:
            vals["diagnosis_id"] = line.diagnosis_id.id
        self.update(vals)

    @api.onchange("procedure_id")
    def _onchange_procedure(self):
        proc = self.procedure_id
        if not proc:
            return
        vals = {}
        # Isi product/uom bila kosong
        if proc.product_id and not self.product_id:
            vals["product_id"] = proc.product_id.id
        if not self.uom_id:
            vals["uom_id"] = proc.uom_id.id if proc.uom_id else (proc.product_id.uom_id.id if proc.product_id else False)
        # Pajak default
        if proc.tax_ids and not self.tax_ids:
            vals["tax_ids"] = [(6, 0, proc.tax_ids.ids)]
        # Durasi default
        if proc.default_duration_min and not self.planned_duration:
            vals["planned_duration"] = proc.default_duration_min
        # Billing policy default bila kosong
        if not self.billing_policy:
            vals["billing_policy"] = proc.billing_policy or "per_session"
        self.update(vals)

    @api.onchange("product_id")
    def _onchange_product(self):
        prod = self.product_id
        if not prod:
            return
        vals = {}
        if not self.uom_id:
            vals["uom_id"] = prod.uom_id.id
        if prod.taxes_id and not self.tax_ids:
            vals["tax_ids"] = [(6, 0, prod.taxes_id.ids)]
        self.update(vals)

    # -------------------------------------------------------------------------
    # Constraint & Validasi
    # -------------------------------------------------------------------------
    _constraint_uniq_session_name_company = models.Constraint(
        'unique(name, company_id)',
        'Session number must be unique per company.',
    )
    _constraint_qty_nonneg = models.Constraint(
        'CHECK (quantity >= 0)',
        'Quantity must be positive or zero.',
    )

    @api.constrains("company_id", "encounter_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.encounter_id and rec.company_id and rec.company_id != rec.encounter_id.company_id:
                raise ValidationError(_("Session company must match Encounter company."))

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
                vals["name"] = seq.next_by_code("clinic.procedure.session") or _("New")
            # Warisi encounter dari plan jika belum diisi
            if not vals.get("encounter_id") and vals.get("encounter_procedure_id"):
                line = self.env["clinic.encounter.procedure"].browse(vals["encounter_procedure_id"])
                if line and line.encounter_id:
                    vals["encounter_id"] = line.encounter_id.id
        recs = super().create(vals_list)
        # Aktivitas default: minta start/eksekusi + EXEC-LOG create
        for rec in recs:
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Execute procedure session"),
                    user_id=rec.performer_user_id.id or (rec.encounter_id.user_id.id if rec.encounter_id and rec.encounter_id.user_id else self.env.user.id),
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
            # Auto-log "create"
            try:
                rec._log_event("create", message=_("Session created"), role="system")
            except Exception:
                pass
        return recs

    # -------------------------------------------------------------------------
    # Workflow Actions (+Execution Log hooks)
    # -------------------------------------------------------------------------
    def _preflight_start_checks(self):
        """
        Validasi pra-mulai:
        - Consent: jika diwajibkan oleh catalog, harus ada consent yang valid & mencakup prosedur.
        - Checklist: jika diwajibkan, harus ada checklist DONE & PASSED untuk session ini.
        """
        for rec in self:
            # Consent
            if rec.require_consent and not rec.consent_valid:
                raise UserError(_("Consent is required (valid and covering the procedure) before starting this session."))
            # Checklist
            if rec.require_checklist:
                ok = any(cl.state == "done" and cl.passed for cl in rec.checklist_ids)
                if not ok:
                    raise UserError(_("Checklist is required before starting this session. Please complete the required checklist."))
            # Catatan jika billing per session tapi tidak ada product/procedure
            if rec.billing_policy == "per_session" and not rec.product_id and not rec.procedure_id:
                rec.message_post(body=_("Billing policy is per session but product/procedure is not set."))

    def action_start(self):
        self._preflight_start_checks()
        now = fields.Datetime.now()
        for rec in self:
            updates = {"state": "in_progress"}
            if not rec.date_start:
                updates["date_start"] = now
            # Jika encounter masih draft, ubah ke in_progress
            try:
                if rec.encounter_id and rec.encounter_id.state == "draft":
                    rec.encounter_id.action_start()
            except Exception:
                pass
            rec.write(updates)
            # EXEC-LOG
            try:
                rec._log_event("start", message=_("Session started"), role="performer")
            except Exception:
                pass
        return True

    def action_pause(self, reason=None):
        for rec in self:
            if rec.state != "in_progress":
                raise UserError(_("Only 'In Progress' sessions can be paused."))
            rec.write({"state": "paused"})
            if reason:
                rec.message_post(body=_("Session paused: %s") % reason)
            # EXEC-LOG
            try:
                msg = _("Session paused") + (": %s" % reason if reason else "")
                rec._log_event("pause", message=msg, role="performer")
            except Exception:
                pass
        return True

    def action_resume(self):
        for rec in self:
            if rec.state != "paused":
                raise UserError(_("Only 'Paused' sessions can be resumed."))
            rec.write({"state": "in_progress"})
            # EXEC-LOG
            try:
                rec._log_event("resume", message=_("Session resumed"), role="performer")
            except Exception:
                pass
        return True

    def action_done(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state not in ("in_progress", "paused", "draft"):
                raise UserError(_("Only Draft/In Progress/Paused sessions can be completed."))
            updates = {"state": "done"}
            if not rec.date_start:
                updates["date_start"] = now
            if not rec.date_end:
                updates["date_end"] = now
            rec.write(updates)

            # Tandai plan line done bila semua sesi pada line selesai
            line = rec.encounter_procedure_id
            if line:
                other_open = line.session_ids.filtered(lambda s: s.state not in ("done", "cancelled") and s.id != rec.id)
                if not other_open:
                    try:
                        line.action_done()
                    except Exception:
                        pass

            # Jadwalkan follow-up activity (opsional)
            try:
                rec.encounter_id.push_activity_followup(
                    summary=_("Review session results"),
                    days=1,
                    user=rec.encounter_id.user_id or rec.performer_user_id,
                )
            except Exception:
                pass
            # EXEC-LOG
            try:
                rec._log_event("done", message=_("Session completed"), role="performer")
            except Exception:
                pass
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            rec.write({"state": "cancelled"})
            if reason:
                rec.message_post(body=_("Session cancelled: %s") % reason)
            # EXEC-LOG
            try:
                msg = _("Session cancelled") + (": %s" % reason if reason else "")
                rec._log_event("cancel", message=msg, role="performer")
            except Exception:
                pass
        return True

    # -------------------------------------------------------------------------
    # Billing Bridges
    # -------------------------------------------------------------------------
    def action_prepare_invoice_line_vals(self):
        """
        Kembalikan list of dict untuk pembuatan account.move.line.
        - Hanya aktif jika billing_policy == 'per_session'.
        - Qty default 1.0 (jumlah sesi), bisa diganti dengan rec.quantity bila diinginkan.
        """
        self.ensure_one()
        if self.billing_policy != "per_session":
            return []

        partner = self.encounter_id.partner_id if self.encounter_id else None
        if not partner:
            raise UserError(_("Patient partner is not set on the Encounter."))

        # Map pajak via fiscal position
        taxes = self.tax_ids
        fpos = partner.property_account_position_id if partner else False
        if fpos:
            taxes = fpos.map_tax(taxes, product=self.product_id, partner=partner)

        # Ambil account income dari product/category bila ada
        account_id = False
        if self.product_id and getattr(self.product_id, "property_account_income_id", False) and self.product_id.property_account_income_id:
            account_id = self.product_id.property_account_income_id.id
        elif self.product_id and self.product_id.categ_id and self.product_id.categ_id.property_account_income_categ_id:
            account_id = self.product_id.categ_id.property_account_income_categ_id.id

        price_unit = (self.price_unit_effective or 0.0) * (1 - (self.discount or 0.0) / 100.0)
        descr = self._default_invoice_line_description()

        return [{
            "name": descr,
            "quantity": self.quantity or 1.0,
            "price_unit": price_unit,
            "discount": 0.0,  # diskon sudah dihitung
            "product_id": self.product_id.id if self.product_id else False,
            "product_uom_id": self.uom_id.id if self.uom_id else (self.product_id.uom_id.id if self.product_id else False),
            "tax_ids": [(6, 0, taxes.ids)] if taxes else [],
            "account_id": account_id,
            "currency_id": self.currency_id.id,
        }]

    def _default_invoice_line_description(self):
        self.ensure_one()
        base = self.procedure_id.display_name if self.procedure_id else (self.product_id.display_name if self.product_id else self.name)
        parts = [base, self.name]
        if self.diagnosis_id:
            parts.append(_("Dx: %s") % (self.diagnosis_id.display_code or self.diagnosis_id.name))
        return " — ".join([p for p in parts if p])

    def action_open_billing(self):
        """Buka invoice yang terkait (berdasarkan invoice_line_ids atau invoice_origin encounter)."""
        self.ensure_one()
        AccountMove = self.env["account.move"]
        moves = AccountMove.search([
            ("line_ids", "in", self.invoice_line_ids.ids or [0]),
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", ["out_invoice", "out_refund"]),
        ])
        if not moves:
            # Fallback via invoice_origin = encounter.name
            moves = AccountMove.search([
                ("invoice_origin", "=", self.encounter_id.name if self.encounter_id else False),
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("company_id", "=", self.company_id.id),
            ])
        if not moves:
            # Arahkan ke wizard generate bill (punya modul ini)
            action = self.env.ref("clinic_encounter.action_generate_bill_wizard").read()[0]
            action["context"] = {"default_encounter_id": self.encounter_id.id}
            return action
        action = self.env.ref("account.action_move_out_invoice_type").read()[0]
        action["domain"] = [("id", "in", moves.ids)]
        return action

    # -------------------------------------------------------------------------
    # Inventory Bridges (opsional di-trigger manual)
    # -------------------------------------------------------------------------
    def action_issue_consumables(self):
        """
        Buat draft picking & stock moves untuk konsumsi default procedure.consumable_ids.
        Membutuhkan konfigurasi lokasi & picking type.
        - System Parameters (optional):
            clinic.inventory.location_src_id     -> ID lokasi sumber (Many2one stock.location)
            clinic.inventory.location_consume_id -> ID lokasi tujuan konsumsi (Many2one stock.location)
            clinic.inventory.picking_type_int_id -> ID picking type internal (Many2one stock.picking.type)
        """
        StockPicking = self.env["stock.picking"]
        StockMove = self.env["stock.move"]
        Param = self.env["ir.config_parameter"].sudo()

        for rec in self:
            proc = rec.procedure_id
            if not proc or not proc.consumable_ids:
                raise UserError(_("No default consumables defined on the procedure."))

            # Ambil konfigurasi lokasi
            try:
                src_id = int(Param.get_param("clinic.inventory.location_src_id", 0)) or False
                dst_id = int(Param.get_param("clinic.inventory.location_consume_id", 0)) or False
                ptype_id = int(Param.get_param("clinic.inventory.picking_type_int_id", 0)) or False
            except Exception:
                src_id = dst_id = ptype_id = False

            if not (src_id and dst_id and ptype_id):
                raise UserError(_(
                    "Inventory configuration is missing.\n"
                    "Please set System Parameters: clinic.inventory.location_src_id, "
                    "clinic.inventory.location_consume_id, clinic.inventory.picking_type_int_id."
                ))

            picking_vals = {
                "picking_type_id": ptype_id,
                "location_id": src_id,
                "location_dest_id": dst_id,
                "origin": rec.encounter_id.name if rec.encounter_id else rec.name,
                "company_id": rec.company_id.id,
                "note": _("Consumables for %s") % (rec.display_name or rec.name),
            }
            picking = StockPicking.create(picking_vals)

            # Buat moves sesuai consumables
            for cons in proc.consumable_ids:
                if not cons.product_id:
                    continue
                uom = cons.uom_id or cons.product_id.uom_id
                qty = (cons.quantity or 0.0) * (rec.quantity or 1.0)
                if qty <= 0.0:
                    continue
                move_vals = {
                    "name": "%s — %s" % (rec.name, cons.product_id.display_name),
                    "product_id": cons.product_id.id,
                    "product_uom_qty": qty,
                    "product_uom": uom.id,
                    "location_id": src_id,
                    "location_dest_id": dst_id,
                    "picking_id": picking.id,
                    "company_id": rec.company_id.id,
                    "origin": picking.origin,
                }
                move = StockMove.create(move_vals)
                rec.stock_move_ids = [(4, move.id)]
            # Tampilkan picking
            action = self.env.ref("stock.action_picking_tree_all").read()[0]
            action["domain"] = [("id", "=", picking.id)]
            return action

    def action_open_stock_moves(self):
        self.ensure_one()
        if not self.stock_move_ids:
            raise UserError(_("No stock moves linked to this session."))
        action = self.env.ref("stock.stock_move_action").read()[0]
        action["domain"] = [("id", "in", self.stock_move_ids.ids)]
        return action

    # -------------------------------------------------------------------------
    # Result / Checklist / AE Actions
    # -------------------------------------------------------------------------
    def action_open_results(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_result_document").read()[0]
        action["domain"] = [("session_id", "=", self.id)]
        action["context"] = {"default_session_id": self.id, "default_encounter_id": self.encounter_id.id}
        return action

    def action_create_quick_result(self):
        """Buat hasil kosong terhubung ke sesi ini (helper cepat)."""
        self.ensure_one()
        res = self.env["clinic.result.document"].create({
            "encounter_id": self.encounter_id.id,
            "session_id": self.id,
            "procedure_id": self.procedure_id.id if self.procedure_id else False,
            "title": _("Result — %s") % (self.procedure_id.display_name if self.procedure_id else self.name),
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Result"),
            "res_model": "clinic.result.document",
            "res_id": res.id,
            "view_mode": "form",
        }

    def action_open_checklists(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_checklist").read()[0]
        action["domain"] = [("session_id", "=", self.id)]
        action["context"] = {
            "default_session_id": self.id,
            "default_encounter_id": self.encounter_id.id,
            "default_procedure_id": self.procedure_id.id if self.procedure_id else False,
        }
        return action

    def action_create_checklist_from_template(self, template):
        """
        Helper: buat satu checklist instance untuk session dari template tertentu.
        """
        self.ensure_one()
        if not template or template._name != "clinic.checklist.template":
            raise UserError(_("A Checklist Template is required."))
        vals = template.prepare_instance_vals(
            encounter=self.encounter_id, session=self, procedure=self.procedure_id
        )
        cl = self.env["clinic.checklist"].create(vals)
        return {
            "type": "ir.actions.act_window",
            "name": _("Checklist"),
            "res_model": "clinic.checklist",
            "res_id": cl.id,
            "view_mode": "form",
        }

    def action_open_adverse_events(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_adverse_event").read()[0]
        action["domain"] = [("session_id", "=", self.id)]
        action["context"] = {
            "default_session_id": self.id,
            "default_encounter_id": self.encounter_id.id,
            "default_procedure_id": self.procedure_id.id if self.procedure_id else False,
            "default_diagnosis_id": self.diagnosis_id.id if self.diagnosis_id else False,
        }
        return action

    # -------------------------------------------------------------------------
    # Execution Log helper (dipanggil dari workflow)
    # -------------------------------------------------------------------------
    def _log_event(self, event_type, message=None, role="user", **kwargs):
        """
        Panggil helper log untuk session ini (single).
        event_type: start/pause/resume/done/cancel/note/create
        """
        self.ensure_one()
        Log = self.env["clinic.execution.log"].sudo()
        try:
            Log.log_for_session(self, event_type=event_type, message=message, role=role, **kwargs)
        except Exception:
            # Jangan gagalkan workflow hanya karena gagal log
            pass

    # Utilitas publik agar UI/otomasi dapat mencatat catatan bebas
    def log_note(self, message, role="user", **extra_vals):
        """
        Catat event 'note' ke log sesi.
        Use case: operator menambahkan catatan manual, sistem perangkat mengirim telemetry, dsb.
        """
        self.ensure_one()
        if not message:
            raise UserError(_("Message is required to create a note log."))
        self._log_event("note", message=message, role=role, **extra_vals)
        return True

    # -------------------------------------------------------------------------
    # Name & Smart Buttons
    # -------------------------------------------------------------------------
    @api.depends("name", "procedure_id")
    def _compute_display_name(self):
        for rec in self:
            label = rec.name or ""
            if rec.procedure_id:
                label = f"{rec.name or ''} • {rec.procedure_id.display_name or rec.procedure_id.name}"
            rec.display_name = label

    def action_open_encounter(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter").read()[0]
        action["res_id"] = self.encounter_id.id
        action["domain"] = [("id", "=", self.encounter_id.id)]
        action["view_mode"] = "form"
        return action

    def action_open_plan_line(self):
        self.ensure_one()
        if not self.encounter_procedure_id:
            raise UserError(_("This session is not linked to a plan line."))
        action = self.env.ref("clinic_encounter.action_clinic_encounter_procedure").read()[0]
        action["res_id"] = self.encounter_procedure_id.id
        action["domain"] = [("id", "=", self.encounter_procedure_id.id)]
        action["view_mode"] = "form"
        return action
