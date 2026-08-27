# -*- coding: utf-8 -*-
"""
res_users_inherit.py

Tujuan:
- Menautkan res.users <-> clinic.patient secara aman (multi-company aware).
- Otomatisasi linking saat user bertipe portal & partner ditandai patient.
- Smart buttons & counters untuk akses cepat ke data Booking/Encounter/Invoice/Wallet/Insurance.
- Graceful fallback jika modul lain belum terpasang.

Catatan:
- Tidak memaksa dependensi antar 38 addon; semua referensi eksternal dicek aman.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =========================================================
# Helper: cek ketersediaan model lintas-modul
# =========================================================
def _has_model(env, model_name):
    try:
        env[model_name]
        return True
    except KeyError:
        return False


class ResUsers(models.Model):
    _inherit = "res.users"

    # ------------------------------------------------------
    # Link ke Patient
    # ------------------------------------------------------
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Linked Patient",
        ondelete="set null",
        help="If this user is a patient portal user, link to their patient card.",
        index=True,
        copy=False,
    )
    is_patient_user = fields.Boolean(
        string="Is Patient User",
        compute="_compute_is_patient_user",
        store=False,
        help="True if user is in the Portal group and partner is marked as patient."
    )
    # Company scope untuk patient (membantu filtering multi-company)
    patient_company_id = fields.Many2one(
        "res.company",
        string="Patient Company",
        compute="_compute_patient_company",
        store=True,
        readonly=False,
        help="Company scope for the linked patient (defaults to user's company).",
    )

    # ------------------------------------------------------
    # Mirror ringan dari partner/patient (read-only)
    # ------------------------------------------------------
    partner_is_patient = fields.Boolean(
        related="partner_id.is_patient",
        store=True, readonly=True,
    )
    patient_code = fields.Char(
        related="patient_id.patient_code",
        store=True, readonly=True,
    )
    patient_stage_id = fields.Many2one(
        related="patient_id.stage_id",
        comodel_name="clinic.patient.stage",
        store=True, readonly=True,
    )
    patient_last_seen = fields.Datetime(
        related="patient_id.last_seen_date",
        store=True, readonly=True,
    )
    wallet_balance = fields.Monetary(
        string="Wallet Balance",
        compute="_compute_integration_counters",
        currency_field="currency_id",
        help="Shown if Clinic Wallet is installed.",
    )

    # ------------------------------------------------------
    # Counters lintas-modul (non-store)
    # ------------------------------------------------------
    booking_count = fields.Integer(compute="_compute_integration_counters")
    encounter_count = fields.Integer(compute="_compute_integration_counters")
    invoice_count = fields.Integer(compute="_compute_integration_counters")
    coverage_count = fields.Integer(compute="_compute_integration_counters")
    attachment_count = fields.Integer(compute="_compute_integration_counters")
    has_active_consent = fields.Boolean(compute="_compute_integration_counters")

    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True, readonly=True,
    )

    # ------------------------------------------------------
    # COMPUTE
    # ------------------------------------------------------
    # @api.depends("groups_id", "partner_id.is_patient")
    # def _compute_is_patient_user(self):
    #     for user in self:
    #         try:
    #             portal_group = self.env.ref("base.group_portal")
    #         except Exception:
    #             portal_group = False
    #         user.is_patient_user = bool(
    #             portal_group and portal_group in user.groups_id and user.partner_id.is_patient
    #         )

    # sebelum:
    # @api.depends("groups_id", "partner_id.is_patient")
    # def _compute_is_patient_user(self):
    #     for user in self:
    #         try:
    #             portal_group = self.env.ref("base.group_portal")
    #         except Exception:
    #             portal_group = False
    #         user.is_patient_user = bool(
    #             portal_group and portal_group in user.groups_id and user.partner_id.is_patient
    #         )

    # sesudah:
    @api.depends("partner_id.is_patient")  # non-store: aman tanpa groups_id
    def _compute_is_patient_user(self):
        for user in self:
            in_portal = False
            try:
                # lebih robust lintas versi & tidak butuh field groups_id
                in_portal = user.has_group("base.group_portal")
            except Exception:
                in_portal = False
            user.is_patient_user = bool(in_portal and user.partner_id.is_patient)


    @api.depends("patient_id.company_id", "company_id")
    def _compute_patient_company(self):
        for user in self:
            user.patient_company_id = user.patient_id.company_id or user.company_id
    # TEMPORARILY DISABLED booking.booking
    @api.depends()
    def _compute_integration_counters(self):
        # Booking = _has_model(self.env, "booking.booking") and self.env["booking.booking"] or False
        # Encounter = _has_model(self.env, "clinic.encounter") and self.env["clinic.encounter"] or False
        AccountMove = _has_model(self.env, "account.move") and self.env["account.move"] or False
        # Insurance = _has_model(self.env, "clinic.insurance.authorization") and self.env["clinic.insurance.authorization"] or False
        # Wallet = _has_model(self.env, "clinic.wallet") and self.env["clinic.wallet"] or False
        # Consent = _has_model(self.env, "clinic.consent") and self.env["clinic.consent"] or False
        Attachment = self.env["ir.attachment"]

        for user in self:
            user.booking_count = 0
            user.encounter_count = 0
            user.invoice_count = 0
            user.coverage_count = 0
            user.attachment_count = 0
            user.wallet_balance = 0.0
            user.has_active_consent = False

            # Hitung berdasarkan patient link jika ada
            patient = user.patient_id
            # if patient and Booking:
            #     user.booking_count = Booking.search_count([("patient_id", "=", patient.id)])
            # if patient and Encounter:
            #     user.encounter_count = Encounter.search_count([("patient_id", "=", patient.id)])
            if patient and AccountMove and user.partner_id:
                user.invoice_count = AccountMove.search_count([
                    ("move_type", "=", "out_invoice"),
                    ("state", "!=", "cancel"),
                    ("partner_id", "=", user.partner_id.commercial_partner_id.id),
                    ("company_id", "=", (patient.company_id or user.company_id).id),
                ])
            # if patient and Insurance:
            #     user.coverage_count = Insurance.search_count([
            #         ("patient_id", "=", patient.id),
            #         ("state", "in", ["approved", "authorized"]),
            #     ])
            # if patient and Wallet:
            #     wallet = Wallet.search([
            #         ("patient_id", "=", patient.id),
            #         ("company_id", "=", (patient.company_id or user.company_id).id),
            #     ], limit=1)
            #     user.wallet_balance = wallet.balance if wallet else 0.0

            # Lampiran pada patient record
            if patient:
                user.attachment_count = Attachment.search_count([
                    ("res_model", "=", "clinic.patient"),
                    ("res_id", "=", patient.id),
                ])

            # Consent aktif
            # if patient and Consent:
            #     user.has_active_consent = bool(Consent.search_count([
            #         ("patient_id", "=", patient.id),
            #         ("state", "=", "active"),
            #     ]))

    # ------------------------------------------------------
    # VALIDATIONS
    # ------------------------------------------------------
    @api.constrains("patient_id", "partner_id")
    def _check_patient_partner_alignment(self):
        for user in self:
            if user.patient_id and user.patient_id.partner_id != user.partner_id:
                raise ValidationError(
                    _("The linked patient card must belong to the same partner as the user.")
                )

    @api.constrains("patient_id", "company_id")
    def _check_patient_company_membership(self):
        for user in self:
            if user.patient_id and user.patient_id.company_id and user.patient_id.company_id not in user.company_ids:
                # Tidak memaksa, tetapi beri peringatan tegas melalui error agar admin menambahkan company akses
                raise ValidationError(
                    _("User must have access to the patient's company (%s).")
                    % (user.patient_id.company_id.display_name,)
                )

    # ------------------------------------------------------
    # CREATE / WRITE
    # ------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)

        # Auto-link patient bila:
        # - Partner is_patient = True dan sudah punya patient_id
        # - atau partner is_patient = True tapi belum punya patient, maka buat
        for user, vals in zip(users, vals_list):
            user._ensure_patient_link_post_create(vals)

        return users

    def write(self, vals):
        res = super().write(vals)

        # Bila admin mengubah partner_id atau menambahkan group portal, coba link patient
        if "partner_id" in vals or "groups_id" in vals or "patient_id" in vals:
            for user in self:
                # Jangan override pilihan admin jika sudah isi patient_id
                if not user.patient_id:
                    user._ensure_patient_link_from_partner()

        return res

    # ------------------------------------------------------
    # UTILITIES
    # ------------------------------------------------------
    def _ensure_patient_link_post_create(self, incoming_vals):
        """Dipanggil setelah create: coba tautkan/membuat patient sesuai partner."""
        self.ensure_one()
        if not self.partner_id:
            return

        # Jika sudah diberikan patient_id di vals, cukup cek konsistensi dan selesai
        if incoming_vals.get("patient_id"):
            return

        # Jika partner sudah is_patient dan punya patient_id ⇒ link
        partner = self.partner_id
        if partner.is_patient and partner.patient_id:
            self.patient_id = partner.patient_id.id
            return

        # Jika partner.is_patient = True namun belum punya patient ⇒ buat
        if partner.is_patient and not partner.patient_id:
            patient = self.env["clinic.patient"].create({
                "name": partner.name or _("Unnamed Patient"),
                "partner_id": partner.id,
                "company_id": self.company_id.id,
            })
            partner.patient_id = patient.id
            self.patient_id = patient.id

        # Jika user sudah portal & partner bukan patient ⇒ bisa otomatis buat (opsional)
        try:
            portal_group = self.env.ref("base.group_portal")
        except Exception:
            portal_group = False
        if portal_group and portal_group in self.groups_id and not partner.is_patient:
            partner.is_patient = True
            # ensure patient card exists
            patient = self.env["clinic.patient"].create({
                "name": partner.name or _("Unnamed Patient"),
                "partner_id": partner.id,
                "company_id": self.company_id.id,
            })
            partner.patient_id = patient.id
            self.patient_id = patient.id

    def _ensure_patient_link_from_partner(self):
        """Panggil saat write bila partner berubah/portal granted."""
        self.ensure_one()
        if not self.partner_id:
            return
        partner = self.partner_id

        # Link jika sudah ada
        if partner.patient_id:
            self.patient_id = partner.patient_id.id
            return

        # Buat bila partner ditandai patient
        if partner.is_patient and not partner.patient_id:
            patient = self.env["clinic.patient"].create({
                "name": partner.name or _("Unnamed Patient"),
                "partner_id": partner.id,
                "company_id": self.company_id.id,
            })
            partner.patient_id = patient.id
            self.patient_id = patient.id

    # ------------------------------------------------------
    # SMART ACTIONS (untuk admin/staff)
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
        """Buka kartu patient milik user ini (admin-side)."""
        self.ensure_one()
        if not self.patient_id:
            raise UserError(_("No linked patient for this user."))
        act = self.env.ref("clinic_patient.action_clinic_patient", raise_if_not_found=False)
        if act:
            action = act.read()[0]
            action.update({"res_id": self.patient_id.id, "view_mode": "form"})
            return action
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient"),
            "res_model": "clinic.patient",
            "res_id": self.patient_id.id,
            "view_mode": "form",
            "target": "current",
        }
    # TEMPORARILY DISABLED booking.booking
    # def action_open_bookings(self):
    #     self.ensure_one()
    #     if not self.patient_id:
    #         raise UserError(_("No linked patient for this user."))
    #     if not _has_model(self.env, "booking.booking"):
    #         raise UserError(_("Module 'clinic_booking' is not installed."))
    #     domain = [("patient_id", "=", self.patient_id.id)]
    #     return self._action_open_generic(
    #         ["clinic_booking.action_clinic_booking_from_patient", "clinic_booking.action_clinic_booking"],
    #         domain, _("Bookings"), "booking.booking"
    #     )
    # TEMPORARILY DISABLED clinic.encounter
    # def action_open_encounters(self):
    #     self.ensure_one()
    #     if not self.patient_id:
    #         raise UserError(_("No linked patient for this user."))
    #     if not _has_model(self.env, "clinic.encounter"):
    #         raise UserError(_("Module 'clinic_encounter' is not installed."))
    #     domain = [("patient_id", "=", self.patient_id.id)]
    #     return self._action_open_generic(
    #         ["clinic_encounter.action_clinic_encounter_from_patient", "clinic_encounter.action_clinic_encounter"],
    #         domain, _("Encounters"), "clinic.encounter"
    #     )

    def action_open_invoices(self):
        self.ensure_one()
        if not _has_model(self.env, "account.move"):
            raise UserError(_("Accounting is not installed."))
        domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "!=", "cancel"),
            ("partner_id", "=", self.partner_id.commercial_partner_id.id),
            ("company_id", "=", (self.patient_company_id or self.company_id).id),
        ]
        return self._action_open_generic(
            ["account.action_move_out_invoice_type"],
            domain, _("Invoices"), "account.move",
            context_add={"default_partner_id": self.partner_id.commercial_partner_id.id},
        )
    # TEMPORARILY DISABLED clinic.wallet
    # def action_open_wallet(self):
    #     self.ensure_one()
    #     if not self.patient_id:
    #         raise UserError(_("No linked patient for this user."))
    #     if not _has_model(self.env, "clinic.wallet"):
    #         raise UserError(_("Module 'clinic_wallet' is not installed."))
    #     domain = [
    #         ("patient_id", "=", self.patient_id.id),
    #         ("company_id", "=", (self.patient_company_id or self.company_id).id),
    #     ]
    #     return self._action_open_generic(
    #         ["clinic_wallet.action_clinic_wallet_from_patient", "clinic_wallet.action_clinic_wallet"],
    #         domain, _("Wallet"), "clinic.wallet"
    #     )
    # TEMPORARILY DISABLED clinic.insurance.authorization
    # def action_open_insurance(self):
    #     self.ensure_one()
    #     if not self.patient_id:
    #         raise UserError(_("No linked patient for this user."))
    #     if not _has_model(self.env, "clinic.insurance.authorization"):
    #         raise UserError(_("Module 'clinic_insurance_authorization' is not installed."))
    #     domain = [("patient_id", "=", self.patient_id.id)]
    #     return self._action_open_generic(
    #         [
    #             "clinic_insurance_authorization.action_clinic_insurance_authorization_from_patient",
    #             "clinic_insurance_authorization.action_clinic_insurance_authorization",
    #         ],
    #         domain, _("Insurance Authorizations"), "clinic.insurance.authorization"
    #     )

    def action_open_patient_attachments(self):
        """Lampiran milik record patient yang ditaut (bukan res.users)."""
        self.ensure_one()
        if not self.patient_id:
            raise UserError(_("No linked patient for this user."))
        action = self.env.ref("base.action_attachment", raise_if_not_found=False)
        result = action and action.read()[0] or {
            "type": "ir.actions.act_window",
            "name": _("Attachments"),
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "target": "current",
        }
        result["domain"] = [("res_model", "=", "clinic.patient"), ("res_id", "=", self.patient_id.id)]
        return result

