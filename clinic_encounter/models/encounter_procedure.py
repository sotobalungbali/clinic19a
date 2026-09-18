# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/encounter_procedure.py
#
# Fungsi utama:
# - Menyimpan rencana/proposal prosedur klinis pada sebuah Encounter.
# - Integrasi ke katalog prosedur (clinic.procedure.catalog) & diagnosis.
# - Penjadwalan sesi tindakan (clinic.procedure.session) per rencana prosedur.
# - Perhitungan harga, pajak, dan total — siap dipakai untuk penagihan.
# - Many2many ke account.move.line (invoice lines) sebagai jejak billing.
#
# Catatan Integrasi:
# - encounter_id: header Encounter (models/encounter.py)
# - procedure_id: master prosedur (models/procedure_catalog.py)
# - diagnosis_id: opsional, mengikat rencana prosedur ke diagnosis tertentu
# - session_ids: sesi eksekusi tindakan (models/procedure_session.py) → asumsi field
#       'encounter_procedure_id' pada session (lihat _prepare_session_vals)
# - invoice_line_ids: keterkaitan ke penagihan berbasis account.move.line
# - konvensi invoice: invoice_origin == encounter.name
#
from math import isclose

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicEncounterProcedure(models.Model):
    _name = "clinic.encounter.procedure"
    _description = "Encounter Procedure Plan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, id"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identitas & Perusahaan
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Line #",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
        tracking=True,
    )
    sequence = fields.Integer(default=10, index=True)
    active = fields.Boolean(default=True, tracking=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Konteks Encounter & Diagnosis
    # -------------------------------------------------------------------------
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        related="encounter_id.patient_id",
        store=True,
        readonly=True,
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Patient Partner",
        related="patient_id.partner_id",
        store=True,
        readonly=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Provider/Doctor",
        related="encounter_id.doctor_id",
        store=True,
        readonly=True,
        index=True,
    )
    diagnosis_id = fields.Many2one(
        "clinic.diagnosis",
        string="Linked Diagnosis",
        ondelete="set null",
        index=True,
        help="Optional diagnosis associated with this procedure plan.",
    )

    # -------------------------------------------------------------------------
    # Master Prosedur & Produk (Pricing)
    # -------------------------------------------------------------------------
    procedure_id = fields.Many2one(
        "clinic.procedure.catalog",
        string="Procedure",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        help="Mapped product/service for pricing and taxation.",
    )
    uom_id = fields.Many2one("uom.uom", string="Unit of Measure")
    quantity = fields.Float(string="Quantity", default=1.0, digits="Product Unit of Measure")
    planned_sessions = fields.Integer(
        string="Planned Sessions",
        default=1,
        help="Default number of sessions to generate from this plan.",
    )
    planned_duration = fields.Float(
        string="Planned Duration (min)",
        help="Estimated duration per session (minutes). Pulled from procedure if available.",
    )
    price_unit = fields.Monetary(string="Unit Price", currency_field="currency_id")
    discount = fields.Float(string="Discount (%)", digits=(16, 4), help="Percentage discount per unit.")
    tax_ids = fields.Many2many(
        "account.tax",
        "clinic_encounter_proc_tax_rel",
        "line_id",
        "tax_id",
        string="Customer Taxes",
        domain=[("type_tax_use", "in", ["sale", "none"])],
        help="Taxes applied for patient/customer billing.",
    )
    price_subtotal = fields.Monetary(string="Subtotal", compute="_compute_amount", store=True)
    price_tax = fields.Monetary(string="Tax", compute="_compute_amount", store=True)
    price_total = fields.Monetary(string="Total", compute="_compute_amount", store=True)

    billing_policy = fields.Selection(
        [
            ("per_plan", "Bill per Plan Line"),
            ("per_session", "Bill per Session"),
            ("no_bill", "Do Not Bill"),
        ],
        string="Billing Policy",
        default="per_plan",
        help="Billing approach for this procedure plan."
    )
    invoice_line_ids = fields.Many2many(
        "account.move.line",
        "clinic_enc_proc_invoice_line_rel",
        "proc_line_id",
        "aml_id",
        string="Invoice Lines",
        help="Billing lines generated from this plan (or its sessions).",
    )

    # -------------------------------------------------------------------------
    # Status & Eksekusi
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("planned", "Planned"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )
    session_ids = fields.One2many(
        "clinic.procedure.session",
        "encounter_procedure_id",
        string="Sessions",
        help="Execution sessions generated from this plan.",
    )
    session_count = fields.Integer(string="Sessions", compute="_compute_session_count", store=False)
    done_session_count = fields.Integer(string="Sessions Done", compute="_compute_session_done_count", store=False)

    performer_user_id = fields.Many2one(
        "res.users",
        string="Performer (User)",
        help="Default performer when generating sessions (optional).",
    )
    performer_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Performer (Doctor)",
        help="Default doctor/clinician for sessions (optional).",
    )
    room_id = fields.Many2one(
        "clinic.room",
        string="Room",
        help="Preferred room if available (soft-coupled with queue/room module).",
    )

    notes = fields.Text(string="Notes for Performer")
    internal_note = fields.Text(string="Internal Notes")

    # UI
    color = fields.Integer(string="Color Index")
    priority = fields.Selection(
        [("0", "Normal"), ("1", "High"), ("2", "Urgent")],
        string="Priority",
        default="0",
        index=True,
    )

    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment (Legacy)",
        index=True,
        ondelete="set null",
        help="Compatibility field so legacy treatment.* can point to plan lines via 'treatment_id'."
    )

    # -------------------------------------------------------------------------
    # KOMPUTASI JUMLAH
    # -------------------------------------------------------------------------
    @api.depends("price_unit", "quantity", "discount", "tax_ids", "currency_id")
    def _compute_amount(self):
        """Hitung subtotal, pajak, total — menggunakan account.tax.compute_all."""
        for rec in self:
            qty = rec.quantity or 0.0
            unit = rec.price_unit or 0.0
            # Diskon persen
            effective_price = unit * (1 - (rec.discount or 0.0) / 100.0)
            taxes = rec.tax_ids.compute_all(
                effective_price,
                currency=rec.currency_id,
                quantity=qty,
                product=rec.product_id,
                partner=rec.partner_id,
            ) if rec.tax_ids else {
                "total_excluded": effective_price * qty,
                "total_included": effective_price * qty,
                "taxes": [],
            }
            rec.price_subtotal = taxes["total_excluded"]
            rec.price_total = taxes["total_included"]
            # Akumulasi pajak
            rec.price_tax = sum(t["amount"] for t in taxes.get("taxes", []))

    @api.depends("session_ids")
    def _compute_session_count(self):
        for rec in self:
            rec.session_count = len(rec.session_ids)

    @api.depends("session_ids.state")
    def _compute_session_done_count(self):
        for rec in self:
            rec.done_session_count = len(rec.session_ids.filtered(lambda s: s.state == "done"))

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("procedure_id")
    def _onchange_procedure_id(self):
        """Prefill produk, UoM, durasi, harga, dan pajak dari master prosedur."""
        proc = self.procedure_id
        if not proc:
            return
        vals = {}
        # Map product & UOM
        if getattr(proc, "product_id", False):
            vals["product_id"] = proc.product_id.id
            if not self.uom_id:
                vals["uom_id"] = proc.product_id.uom_id.id
        elif getattr(proc, "uom_id", False) and not self.uom_id:
            vals["uom_id"] = proc.uom_id.id

        # Durasi default
        if getattr(proc, "default_duration_min", False) and not self.planned_duration:
            vals["planned_duration"] = proc.default_duration_min

        # Harga default dari procedure (prioritas) lalu fallback ke product.list_price
        price = False
        if getattr(proc, "list_price", False):
            price = proc.list_price
        elif getattr(proc, "product_id", False):
            price = proc.product_id.lst_price
        if price is not False:
            vals["price_unit"] = price

        # Pajak dari product (customer taxes)
        if getattr(proc, "product_id", False) and proc.product_id.taxes_id:
            vals["tax_ids"] = [(6, 0, proc.product_id.taxes_id.ids)]

        # Billing policy dari master (jika ada)
        if getattr(proc, "billing_policy", False) and not self.billing_policy:
            vals["billing_policy"] = proc.billing_policy

        if vals:
            self.update(vals)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        """Sinkronisasi UoM, pajak, dan harga bila user memilih produk langsung."""
        prod = self.product_id
        if not prod:
            return
        vals = {}
        if not self.uom_id:
            vals["uom_id"] = prod.uom_id.id
        if prod.taxes_id:
            vals["tax_ids"] = [(6, 0, prod.taxes_id.ids)]
        # Jika price_unit belum diisi atau 0, ambil dari list_price
        if not self.price_unit or isclose(self.price_unit, 0.0, rel_tol=1e-9, abs_tol=1e-9):
            vals["price_unit"] = prod.lst_price
        if vals:
            self.update(vals)

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    _constraint_qty_positive = models.Constraint(
        'CHECK (quantity >= 0)',
        'Quantity must be positive.',
    )
    _constraint_uniq_line_name_company = models.Constraint(
        'unique(name, company_id)',
        'Line number must be unique per company.',
    )

    @api.constrains("encounter_id", "company_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.encounter_id and rec.company_id and rec.company_id != rec.encounter_id.company_id:
                raise ValidationError(_("Procedure line company must match Encounter company."))

    @api.constrains("uom_id", "product_id")
    def _check_uom_category(self):
        for rec in self:
            if rec.product_id and rec.uom_id and rec.product_id.uom_id.category_id != rec.uom_id.category_id:
                raise ValidationError(_("The selected Unit of Measure is not compatible with the product's UoM."))

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
                vals["name"] = seq.next_by_code("clinic.encounter.procedure") or _("New")
        recs = super().create(vals_list)
        # Activity default
        for rec in recs:
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Prepare procedure plan"),
                    user_id=(rec.encounter_id.user_id.id if rec.encounter_id and rec.encounter_id.user_id else self.env.user.id),
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        # Jika quantity diubah dan sudah ada sesi, bisa beri peringatan ringan via chatter
        if "quantity" in vals or "planned_sessions" in vals:
            for rec in self.filtered(lambda r: r.session_ids):
                rec.message_post(body=_("Quantity/Sessions changed after sessions were generated. Please reconcile scheduling."))
        return res

    def unlink(self):
        for rec in self:
            if rec.invoice_line_ids:
                raise UserError(_("Cannot delete a billed procedure line. Consider cancelling instead."))
            if any(s.state in ("in_progress", "done") for s in rec.session_ids):
                raise UserError(_("Cannot delete a procedure line with in-progress/done sessions."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # WORKFLOW
    # -------------------------------------------------------------------------
    def action_plan(self):
        """Set status Planned; biasa dipanggil setelah melengkapi detail rencana."""
        for rec in self:
            rec.write({"state": "planned"})
        return True

    def action_start(self):
        """Tandai In Progress. Biasanya saat sesi pertama dimulai."""
        for rec in self:
            rec.write({"state": "in_progress"})
        return True

    def action_done(self):
        """Tandai Done. Biasanya setelah semua sesi tuntas (atau secara manual)."""
        for rec in self:
            # Validasi: bila ada planned sessions, pastikan minimal ada sesi selesai
            if rec.planned_sessions and not rec.session_ids.filtered(lambda s: s.state == "done"):
                rec.message_post(body=_("Marked done without any completed sessions."))
            rec.write({"state": "done"})
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            rec.write({"state": "cancelled"})
            if reason:
                rec.message_post(body=_("Cancelled: %s") % reason)
        return True

    # -------------------------------------------------------------------------
    # SESSIONS
    # -------------------------------------------------------------------------
    def action_generate_sessions(self):
        """
        Generate sessions sebanyak 'planned_sessions'.
        Bila sesi sudah ada, tidak digandakan — gunakan tambah manual kalau perlu.
        """
        Session = self.env["clinic.procedure.session"]
        generated = self.env[self._name]
        for rec in self:
            remain = max(rec.planned_sessions - len(rec.session_ids), 0)
            for i in range(remain):
                vals = rec._prepare_session_vals(index=i + 1)
                sess = Session.create(vals)
                generated |= rec
            # Autoplan status
            if rec.state == "draft":
                rec.state = "planned"
        return {
            "type": "ir.actions.act_window",
            "name": _("Sessions"),
            "res_model": "clinic.procedure.session",
            "view_mode": "list,form,calendar,kanban",
            "domain": [("encounter_procedure_id", "in", self.ids)],
            "context": {"search_default_encounter_procedure_id": self.ids},
        }

    def _prepare_session_vals(self, index=1):
        """
        Siapkan nilai default pembuatan session dari rencana ini.
        Asumsi di model session terdapat field:
        - encounter_id, encounter_procedure_id, diagnosis_id
        - performer_user_id, performer_doctor_id
        - room_id
        - planned_duration (menit)
        - billing_policy (inherit dari line)
        """
        self.ensure_one()
        return {
            "name": "%s • S%02d" % (self.procedure_id.display_name if self.procedure_id else self.name, index),
            "encounter_id": self.encounter_id.id,
            "encounter_procedure_id": self.id,
            "diagnosis_id": self.diagnosis_id.id if self.diagnosis_id else False,
            "performer_user_id": self.performer_user_id.id if self.performer_user_id else False,
            "performer_doctor_id": self.performer_doctor_id.id if self.performer_doctor_id else False,
            "room_id": self.room_id.id if self.room_id else False,
            "planned_duration": self.planned_duration or 0.0,
            "billing_policy": self.billing_policy,
            # Bridge ke inventory/billing dapat ditangani di model session saat start/done
        }

    def action_open_sessions(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_procedure_session").read()[0]
        action["domain"] = [("encounter_procedure_id", "=", self.id)]
        action["context"] = {
            "default_encounter_id": self.encounter_id.id,
            "default_encounter_procedure_id": self.id,
            "default_diagnosis_id": self.diagnosis_id.id if self.diagnosis_id else False,
        }
        return action

    # -------------------------------------------------------------------------
    # BILLING (BRIDGES)
    # -------------------------------------------------------------------------
    def action_prepare_invoice_line_vals(self):
        """
        Kembalikan list of dict vals untuk pembuatan account.move.line berdasarkan
        kebijakan billing line ini. Dipakai wizard Generate Bill.
        - per_plan  : 1 line dari plan
        - per_session: 1 line per session (yang eligible) → di sini hanya siapkan untuk sesi yang 'done'
        - no_bill   : return []
        """
        self.ensure_one()
        if self.billing_policy == "no_bill":
            return []

        if not self.partner_id:
            raise UserError(_("Patient partner is not set on the Encounter."))

        if self.billing_policy == "per_session":
            lines = []
            sessions = self.session_ids.filtered(lambda s: s.state == "done")
            if not sessions:
                # Masih kembalikan kosong, wizard bisa tampilkan info ke user
                return []
            for s in sessions:
                vals = self._prepare_single_invoice_line(
                    description="%s — %s" % (self.procedure_id.display_name, s.display_name or s.name),
                    qty=1.0,
                )
                lines.append(vals)
            return lines

        # per_plan
        return [self._prepare_single_invoice_line(description=self._get_default_description(), qty=self.quantity or 1.0)]

    def _prepare_single_invoice_line(self, description, qty=1.0):
        """
        Siapkan 1 baris account.move.line (dalam konteks pembuatan invoice customer).
        """
        self.ensure_one()
        # Pemetaan pajak berdasarkan fiscal position partner (jika ada)
        partner = self.partner_id
        fpos = partner.property_account_position_id if partner else False
        taxes = self.tax_ids
        if fpos:
            taxes = fpos.map_tax(taxes, product=self.product_id, partner=partner)

        # Harga bersih setelah diskon
        price_unit = (self.price_unit or 0.0) * (1 - (self.discount or 0.0) / 100.0)

        # Akun pendapatan (ambil dari product atau kategori)
        account_id = False
        if self.product_id and getattr(self.product_id, "property_account_income_id", False) and self.product_id.property_account_income_id:
            account_id = self.product_id.property_account_income_id.id
        elif self.product_id and self.product_id.categ_id and self.product_id.categ_id.property_account_income_categ_id:
            account_id = self.product_id.categ_id.property_account_income_categ_id.id
        # Do not invent an account from a tax field as a fallback. In Odoo 19
        # the invoice line account can be computed from the product/fiscal setup
        # when it is omitted.
        vals = {
            "name": description,
            "quantity": qty,
            "price_unit": price_unit,
            "discount": 0.0,  # discount is already reflected in price_unit
            "product_id": self.product_id.id if self.product_id else False,
            "product_uom_id": self.uom_id.id if self.uom_id else (self.product_id.uom_id.id if self.product_id else False),
            "tax_ids": [(6, 0, taxes.ids)] if taxes else [],
            "currency_id": self.currency_id.id,
        }
        if account_id:
            vals["account_id"] = account_id
        return vals

    def _get_default_description(self):
        self.ensure_one()
        base = self.procedure_id.display_name if self.procedure_id else (self.product_id.display_name if self.product_id else self.name)
        if self.diagnosis_id:
            return "%s — Dx: %s" % (base, self.diagnosis_id.display_code or self.diagnosis_id.name)
        return base

    def action_open_billing(self):
        """Buka invoice yang berasal dari Encounter (konvensi invoice_origin)."""
        self.ensure_one()
        AccountMove = self.env["account.move"]
        moves = AccountMove.search([
            ("invoice_origin", "=", self.encounter_id.name if self.encounter_id else False),
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("company_id", "=", self.company_id.id),
        ])
        if not moves:
            raise UserError(_("No related invoices found via Encounter."))
        action = self.env.ref("account.action_move_out_invoice_type").read()[0]
        action["domain"] = [("id", "in", moves.ids)]
        return action

    # -------------------------------------------------------------------------
    # SMART BUTTONS
    # -------------------------------------------------------------------------
    def action_view_invoices(self):
        return self.action_open_billing()

    # -------------------------------------------------------------------------
    # NAME & SEARCH
    # -------------------------------------------------------------------------
    @api.depends("name", "procedure_id", "product_id")
    def _compute_display_name(self):
        for rec in self:
            base = (
                rec.procedure_id.display_name
                if rec.procedure_id
                else (rec.product_id.display_name if rec.product_id else rec.name or "")
            )
            rec.display_name = f"{rec.name or ''} • {base}".strip(" •")

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", "|",
                  ("name", operator, name),
                  ("procedure_id.display_name", operator, name),
                  ("encounter_id.name", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]

