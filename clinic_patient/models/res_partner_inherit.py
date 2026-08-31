
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =========================================================
# Helper: cek ketersediaan model lintas-modul (graceful)
# =========================================================
def _has_model(env, model_name):
    try:
        env[model_name]
        return True
    except KeyError:
        return False


class ResPartner(models.Model):
    _inherit = "res.partner"

    # ------------------------------------------------------
    # Penanda & tautan patient
    # ------------------------------------------------------
    is_patient = fields.Boolean(
        string="Is a Patient",
        help="Enable if this contact is (or will be) a patient.",
        tracking=True,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient Card",
        ondelete="set null",
        copy=False,
        help="Linked patient card for this contact.",
    )
    # Info dasar dari patient (related; store=True agar dapat difilter/sort)
    patient_code = fields.Char(
        related="patient_id.patient_code", store=True, readonly=True
    )
    patient_stage_id = fields.Many2one(
        related="patient_id.stage_id", comodel_name="clinic.patient.stage", store=True, readonly=True
    )
    patient_registered_date = fields.Datetime(
        related="patient_id.registered_date", store=True, readonly=True
    )
    patient_last_seen = fields.Datetime(
        related="patient_id.last_seen_date", store=True, readonly=True
    )
    is_vip_patient = fields.Boolean(
        related="patient_id.is_vip", store=True, readonly=False,
        string="VIP Patient"
    )
    # Demografi (ambil dari patient agar konsisten lintas modul)
    patient_birth_date = fields.Date(related="patient_id.birth_date", store=True, readonly=False)
    patient_age_years = fields.Integer(related="patient_id.age_years", store=True, readonly=True)
    patient_age_display = fields.Char(related="patient_id.age_display", store=True, readonly=True)
    patient_gender = fields.Selection(related="patient_id.gender", store=True, readonly=False)

    # ------------------------------------------------------
    # Field opsional untuk integrasi lokal (Indonesia)
    # (Dipakai oleh patient_identifier.py via partner_mapping)
    # ------------------------------------------------------
    nik = fields.Char(string="NIK", help="Nomor Induk Kependudukan (Indonesia).")
    bpjs_no = fields.Char(string="BPJS No.", help="Nomor peserta BPJS (Indonesia).")

    # Ringkasan medis ringan (diisi otomatis opsional oleh modul allergy/condition)
    medical_allergy_note = fields.Text(help="Auto-filled summary of active allergies.")
    medical_condition_note = fields.Text(help="Auto-filled summary of active conditions.")

    # ------------------------------------------------------
    # Counters & integrasi lintas-modul (computed, non-store)
    # ------------------------------------------------------
    booking_count = fields.Integer(compute="_compute_integration_counters")
    encounter_count = fields.Integer(compute="_compute_integration_counters")
    invoice_count = fields.Integer(compute="_compute_integration_counters")
    attachment_count = fields.Integer(compute="_compute_integration_counters")
    coverage_count = fields.Integer(compute="_compute_integration_counters")
    wallet_balance = fields.Monetary(
        compute="_compute_integration_counters",
        currency_field="currency_id",
        help="Wallet balance if Clinic Wallet is installed.",
    )
    has_active_consent = fields.Boolean(
        compute="_compute_integration_counters",
        help="True if there is an active legal consent record.",
    )

    # Gunakan currency dari company yang sedang aktif
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)

    # ------------------------------------------------------
    # VALIDASI
    # ------------------------------------------------------
    @api.constrains("is_patient", "patient_id")
    def _check_patient_link_consistency(self):
        for partner in self:
            if partner.is_patient and not partner.patient_id:
                # tidak error; akan dibuat otomatis di create/write
                continue
            if partner.patient_id and partner.patient_id.partner_id and partner.patient_id.partner_id != partner:
                raise ValidationError(_("Linked patient card belongs to a different contact."))

    # ------------------------------------------------------
    # ONCHANGE
    # ------------------------------------------------------
    @api.onchange("is_patient")
    def _onchange_is_patient(self):
        for rec in self:
            if rec.is_patient and not rec.patient_id:
                # Tidak membuat record di onchange (baru membuat di write/create)
                rec._warn_create_patient_placeholder = True  # penanda UI non-fungsional

    # ------------------------------------------------------
    # CREATE / WRITE
    # ------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        # Auto-create patient card bila is_patient=True & belum punya patient_id
        for partner, vals in zip(records, vals_list):
            if vals.get("is_patient") and not vals.get("patient_id"):
                partner._ensure_patient_card_created()

        return records

    def write(self, vals):
        res = super().write(vals)

        # Jika user menandai is_patient = True dan belum punya patient_id → buat
        if "is_patient" in vals and vals.get("is_patient"):
            for partner in self:
                if not partner.patient_id:
                    partner._ensure_patient_card_created()

        # Jika ada patient_id baru, amankan konsistensi tautan searah
        if "patient_id" in vals:
            for partner in self:
                if partner.patient_id and partner.patient_id.partner_id != partner:
                    partner.patient_id.partner_id = partner

        return res

    # ------------------------------------------------------
    # UTILITIES
    # ------------------------------------------------------
    def _ensure_patient_card_created(self):
        """Buat clinic.patient yang terhubung bila belum ada."""
        self.ensure_one()
        Patient = self.env["clinic.patient"]
        # Cek apakah sudah ada patient card untuk partner ini pada company aktif
        existing = Patient.search([
            ("partner_id", "=", self.id),
            ("company_id", "=", self.env.company.id),
        ], limit=1)
        if existing:
            # set flag di partner
            if not self.patient_id:
                self.patient_id = existing.id
            if not self.is_patient:
                self.is_patient = True
            return existing

        # Buat baru
        patient = Patient.create({
            "name": self.name or _("Unnamed Patient"),
            "partner_id": self.id,
            "company_id": self.env.company.id,
        })
        # Pastikan flag
        if not self.is_patient:
            self.is_patient = True
        if not self.patient_id:
            self.patient_id = patient.id
        return patient
    # TEMPORARILY DISABLED
    @api.depends()
    def _compute_integration_counters(self):
        # Booking = _has_model(self.env, "booking.booking") and self.env["booking.booking"] or False
        # Encounter = _has_model(self.env, "clinic.encounter") and self.env["clinic.encounter"] or False
        # Insurance = _has_model(self.env, "clinic.insurance.authorization") and self.env["clinic.insurance.authorization"] or False
        # Wallet = _has_model(self.env, "clinic.wallet") and self.env["clinic.wallet"] or False
        # Consent = _has_model(self.env, "clinic.consent") and self.env["clinic.consent"] or False
        AccountMove = _has_model(self.env, "account.move") and self.env["account.move"] or False
        Attachment = self.env["ir.attachment"]

        for partner in self:
            # init
            partner.booking_count = 0
            partner.encounter_count = 0
            partner.invoice_count = 0
            partner.attachment_count = 0
            partner.coverage_count = 0
            partner.wallet_balance = 0.0
            partner.has_active_consent = False

            # Booking & Encounter berdasarkan patient_id bila ada
            # if partner.patient_id and Booking:
            #     partner.booking_count = Booking.search_count([("patient_id", "=", partner.patient_id.id)])
            # if partner.patient_id and Encounter:
            #     partner.encounter_count = Encounter.search_count([("patient_id", "=", partner.patient_id.id)])

            # Invoice berdasarkan commercial partner
            if AccountMove:
                cp = partner.commercial_partner_id.id
                partner.invoice_count = AccountMove.search_count([
                    ("move_type", "=", "out_invoice"),
                    ("state", "!=", "cancel"),
                    ("partner_id", "=", cp),
                    ("company_id", "=", partner.company_id.id or self.env.company.id),
                ])

            # Attachments pada res.partner (bukan patient)
            partner.attachment_count = Attachment.search_count([
                ("res_model", "=", "res.partner"),
                ("res_id", "=", partner.id),
            ])

            # Insurance coverage/authorization
            # if partner.patient_id and Insurance:
            #     partner.coverage_count = Insurance.search_count([
            #         ("patient_id", "=", partner.patient_id.id),
            #         ("state", "in", ["approved", "authorized"]),
            #     ])

            # Wallet
            # if partner.patient_id and Wallet:
            #     wallet = Wallet.search([
            #         ("patient_id", "=", partner.patient_id.id),
            #         ("company_id", "=", partner.company_id.id or self.env.company.id),
            #     ], limit=1)
            #     partner.wallet_balance = wallet.balance if wallet else 0.0

            # Consent
            # if partner.patient_id and Consent:
            #     partner.has_active_consent = bool(Consent.search_count([
            #         ("patient_id", "=", partner.patient_id.id),
            #         ("state", "=", "active"),
            #     ]))

    # ------------------------------------------------------
    # SMART BUTTONS / ACTIONS
    # ------------------------------------------------------
    def _action_open_generic(self, xmlid_candidates, domain, name, res_model, context_add=None):
        self.ensure_one()
        action = False
        for xmlid in xmlid_candidates:
            if not xmlid:
                continue
            act = self.env.ref(xmlid, raise_if_not_found=False)
            if act:
                action = act.read()[0]
                break
        if not action:
            action = {
                "type": "ir.actions.act_window",
                "name": name,
                "res_model": res_model,
                "view_mode": "list,form,kanban,calendar,graph,pivot",
                "target": "current",
                "domain": domain,
                "context": {},
            }
        ctx = action.get("context", {}) or {}
        if self.patient_id:
            ctx.update({
                "default_patient_id": self.patient_id.id,
                "search_default_patient_id": self.patient_id.id,
            })
        if context_add:
            ctx.update(context_add)
        action["context"] = ctx
        action["domain"] = domain
        return action

    def action_open_patient(self):
        """Buka kartu pasien (buat dulu jika belum ada)."""
        self.ensure_one()
        if not self.patient_id and self.is_patient:
            self._ensure_patient_card_created()
        if not self.patient_id:
            raise UserError(_("This contact is not a patient yet. Enable 'Is a Patient' first."))
        act = self.env.ref("clinic_patient.action_clinic_patient", raise_if_not_found=False)
        if act:
            action = act.read()[0]
            action.update({"res_id": self.patient_id.id, "view_mode": "form"})
            return action
        # fallback
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient"),
            "res_model": "clinic.patient",
            "res_id": self.patient_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_create_patient(self):
        """Tombol cepat untuk membuat Patient Card dari partner."""
        self.ensure_one()
        if self.patient_id:
            return self.action_open_patient()
        self.is_patient = True
        self._ensure_patient_card_created()
        return self.action_open_patient()
    # TEMPORARILY DISABLED booking.booking
    # def action_open_bookings(self):
    #     self.ensure_one()
    #     if not _has_model(self.env, "booking.booking"):
    #         raise UserError(_("Module 'clinic_booking' is not installed."))
    #     domain = []
    #     if self.patient_id:
    #         domain = [("patient_id", "=", self.patient_id.id)]
    #     return self._action_open_generic(
    #         xmlid_candidates=[
    #             "clinic_booking.action_clinic_booking_from_patient",
    #             "clinic_booking.action_clinic_booking",
    #         ],
    #         domain=domain,
    #         name=_("Bookings"),
    #         res_model="booking.booking",
    #     )
    # TEMPORARILY DISABLED clinic.encounter
    # def action_open_encounters(self):
    #     self.ensure_one()
    #     if not _has_model(self.env, "clinic.encounter"):
    #         raise UserError(_("Module 'clinic_encounter' is not installed."))
    #     domain = []
    #     if self.patient_id:
    #         domain = [("patient_id", "=", self.patient_id.id)]
    #     return self._action_open_generic(
    #         xmlid_candidates=[
    #             "clinic_encounter.action_clinic_encounter_from_patient",
    #             "clinic_encounter.action_clinic_encounter",
    #         ],
    #         domain=domain,
    #         name=_("Encounters"),
    #         res_model="clinic.encounter",
    #     )

    def action_open_invoices(self):
        self.ensure_one()
        if not _has_model(self.env, "account.move"):
            raise UserError(_("Accounting is not installed."))
        partner_ids = [self.commercial_partner_id.id]
        domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "!=", "cancel"),
            ("partner_id", "in", partner_ids),
            ("company_id", "=", self.company_id.id or self.env.company.id),
        ]
        return self._action_open_generic(
            xmlid_candidates=["account.action_move_out_invoice_type"],
            domain=domain,
            name=_("Invoices"),
            res_model="account.move",
            context_add={"default_partner_id": self.commercial_partner_id.id},
        )
    # TEMPORARILY DISABLED clinic.wallet
    # def action_open_wallet(self):
    #     self.ensure_one()
    #     if not _has_model(self.env, "clinic.wallet"):
    #         raise UserError(_("Module 'clinic_wallet' is not installed."))
    #     if not self.patient_id:
    #         raise UserError(_("No patient card linked to this contact."))
    #     domain = [("patient_id", "=", self.patient_id.id), ("company_id", "=", self.company_id.id or self.env.company.id)]
    #     return self._action_open_generic(
    #         xmlid_candidates=[
    #             "clinic_wallet.action_clinic_wallet_from_patient",
    #             "clinic_wallet.action_clinic_wallet",
    #         ],
    #         domain=domain,
    #         name=_("Wallet"),
    #         res_model="clinic.wallet",
    #     )
    # TEMPORARILY DISABLED clinic.insurance.authorization
    # def action_open_insurance(self):
    #     self.ensure_one()
    #     if not _has_model(self.env, "clinic.insurance.authorization"):
    #         raise UserError(_("Module 'clinic_insurance_authorization' is not installed."))
    #     if not self.patient_id:
    #         raise UserError(_("No patient card linked to this contact."))
    #     domain = [("patient_id", "=", self.patient_id.id)]
    #     return self._action_open_generic(
    #         xmlid_candidates=[
    #             "clinic_insurance_authorization.action_clinic_insurance_authorization_from_patient",
    #             "clinic_insurance_authorization.action_clinic_insurance_authorization",
    #         ],
    #         domain=domain,
    #         name=_("Insurance Authorizations"),
    #         res_model="clinic.insurance.authorization",
    #     )

    def action_open_attachments(self):
        """Lampiran milik contact (bukan patient)."""
        self.ensure_one()
        action = self.env.ref("base.action_attachment", raise_if_not_found=False)
        result = action and action.read()[0] or {
            "type": "ir.actions.act_window",
            "name": _("Attachments"),
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "target": "current",
        }
        result["domain"] = [("res_model", "=", "res.partner"), ("res_id", "=", self.id)]
        return result

