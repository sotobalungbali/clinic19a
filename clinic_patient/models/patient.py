# -*- coding: utf-8 -*-
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =====================================================================
# Helper kecil untuk cek ketersediaan model lintas-modul secara aman
# =====================================================================
def _has_model(env, model_name):
    """Return True jika model terdaftar di registry (module terpasang)."""
    try:
        env[model_name]
        return True
    except KeyError:
        return False


# =====================================================================
# Referensi: Stage/Tahapan Pasien (untuk statusbar di form pasien)
# Di-seed via data/patient_stage_data.xml
# =====================================================================
class ClinicPatientStage(models.Model):
    _name = "clinic.patient.stage"
    _description = "Patient Stage"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean(
        help="Jika dicentang, kolom statusbar akan dilipat (fold) di kanban/list."
    )
    # Flag fungsional untuk otomatisasi
    is_default_new = fields.Boolean(
        help="Tandai sebagai default saat membuat pasien baru."
    )
    is_registered = fields.Boolean(help="Tandai tahap sebagai 'Registered'.")
    is_inactive = fields.Boolean(help="Tandai tahap sebagai 'Inactive'.")
    is_deceased = fields.Boolean(help="Tandai tahap sebagai 'Deceased'.")


# =====================================================================
# Referensi: Tag Pasien (kategori, VIP, Corporate, dll.)
# Di-seed via data/patient_tag_data.xml
# =====================================================================
class ClinicPatientTag(models.Model):
    _name = "clinic.patient.tag"
    _description = "Patient Tag"

    name = fields.Char(required=True, translate=True)
    color = fields.Integer("Color Index")


# =====================================================================
# Model Inti: clinic.patient
# =====================================================================
class ClinicPatient(models.Model):
    _name = "clinic.patient"
    _description = "Clinic Patient"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "display_name"
    _order = "create_date DESC, id DESC"

    # -------------------------------
    # Multicompany & aktif
    # -------------------------------
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(default=True, tracking=True)

    # -------------------------------
    # Identitas dasar
    # -------------------------------
    patient_code = fields.Char(
        string="Patient Code",
        copy=False,
        readonly=True,
        index=True,
        tracking=True,
        help="Nomor MRN/Patient Code; diisi otomatis oleh sequence.",
    )
    name = fields.Char(
        string="Full Name",
        required=True,
        tracking=True,
        help="Nama lengkap pasien.",
    )
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
        help="Tampilan nama: [CODE] Name",
    )
    image_1920 = fields.Image(max_width=1920, max_height=1920, string="Photo")

    # Tautan ke contact card (res.partner)
    partner_id = fields.Many2one(
        "res.partner",
        string="Contact",
        ondelete="restrict",
        tracking=True,
        help="Kartu kontak yang ditautkan dengan pasien ini.",
    )
    is_vip = fields.Boolean(string="VIP", tracking=True)
    tag_ids = fields.Many2many(
        "clinic.patient.tag",
        "clinic_patient_tag_rel",
        "patient_id",
        "tag_id",
        string="Tags",
    )

    # -------------------------------
    # Demografi & Info medis ringkas
    # -------------------------------
    gender = fields.Selection(
        [
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
            ("unknown", "Unknown"),
        ],
        tracking=True,
        default="unknown",
    )
    birth_date = fields.Date(string="Date of Birth", tracking=True)
    age_years = fields.Integer(
        compute="_compute_age",
        string="Age (Years)",
        store=True,
    )
    age_display = fields.Char(
        compute="_compute_age",
        string="Age",
        store=True,
        help="Format ramah: 34y 2m 10d",
    )
    blood_type = fields.Selection(
        [
            ("A", "A"),
            ("B", "B"),
            ("AB", "AB"),
            ("O", "O"),
        ],
        string="Blood Type",
        tracking=True,
    )
    rh_factor = fields.Selection(
        [("+", "+ (Positive)"), ("-", "- (Negative)")],
        string="Rh",
        tracking=True,
    )

    # Status hidup
    is_deceased = fields.Boolean(
        string="Deceased",
        tracking=True,
        help="Tandai bila pasien telah meninggal.",
    )
    deceased_date = fields.Date(string="Date of Death", tracking=True)

    # Kontak utama (related ke partner agar konsisten lintas modul)
    phone = fields.Char(related="partner_id.phone", string="Phone", store=True, readonly=False)
    # mobile = fields.Char(related="partner_id.mobile", string="Mobile", store=True, readonly=False)
    email = fields.Char(related="partner_id.email", string="Email", store=True, readonly=False)

    # Tambahan kompatibilitas Odoo 19:
    # - Di Odoo 19, base tidak punya 'mobile' -> kita definisikan agar related field di clinic.patient tetap aman
    mobile = fields.Char(
        string="Mobile",
        help="Mobile phone number.",
        tracking=True,
    )

    # Alamat (tersinkron lewat partner)
    street = fields.Char(related="partner_id.street", store=True, readonly=False)
    street2 = fields.Char(related="partner_id.street2", store=True, readonly=False)
    city = fields.Char(related="partner_id.city", store=True, readonly=False)
    state_id = fields.Many2one(related="partner_id.state_id", comodel_name="res.country.state", store=True, readonly=False)
    zip = fields.Char(related="partner_id.zip", store=True, readonly=False)
    country_id = fields.Many2one(related="partner_id.country_id", comodel_name="res.country", store=True, readonly=False)

    # Kontak darurat (emergency)
    emergency_contact_id = fields.Many2one(
        "res.partner", string="Emergency Contact", ondelete="restrict"
    )
    emergency_phone = fields.Char(
        string="Emergency Phone",
        help="Nomor darurat (fallback: akan gunakan phone/mobile dari kontak darurat).",
    )

    # -------------------------------
    # Pipeline/Tahapan Pasien
    # -------------------------------
    stage_id = fields.Many2one(
        "clinic.patient.stage", string="Stage", ondelete="restrict", tracking=True, index=True
    )
    stage_fold = fields.Boolean(related="stage_id.fold", store=True)
    registered_date = fields.Datetime(
        string="Registered On",
        help="Diisi saat pasien berpindah ke tahap Registered.",
        tracking=True,
    )
    last_seen_date = fields.Datetime(
        string="Last Seen",        
        store=False,
        help="Tanggal encounter/booking terakhir (tergantung modul).",
    )   # compute="_compute_last_seen", # TEMPORARILY DISABLED

    # -------------------------------
    # Relasi ke sub-objek di addon ini
    # (detail model ada di file lain)
    # -------------------------------
    identifier_ids = fields.One2many(
        "clinic.patient.identifier", "patient_id", string="Identifiers"
    )
    allergy_ids = fields.One2many("clinic.patient.allergy", "patient_id", string="Allergies")
    condition_ids = fields.One2many("clinic.patient.condition", "patient_id", string="Conditions")
    vital_ids = fields.One2many("clinic.patient.vital", "patient_id", string="Vitals")

    # -------------------------------
    # Integrasi lintas-modul (counter/smart data)
    # Semua aman bila modul belum terpasang
    # -------------------------------
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
    # booking_count = fields.Integer(compute="_compute_integration_counters")
    # encounter_count = fields.Integer(compute="_compute_integration_counters")
    # invoice_count = fields.Integer(compute="_compute_integration_counters")
    # attachment_count = fields.Integer(compute="_compute_integration_counters")
    # coverage_count = fields.Integer(
    #     compute="_compute_integration_counters",
    #     help="Jumlah active coverage/authorization (jika modul insurance aktif).",
    # )
    # wallet_balance = fields.Monetary(
    #     compute="_compute_integration_counters",
    #     currency_field="currency_id",
    #     help="Saldo wallet (jika modul clinic_wallet aktif).",
    # )
    # has_active_consent = fields.Boolean(
    #     compute="_compute_integration_counters",
    #     help="Ada consent legal aktif (jika modul consent aktif)."
    # )

    # -------------------------------
    # SQL Constraints
    # -------------------------------
    _constraint_patient_code_company_uniq = models.Constraint(
        'unique(company_id, patient_code)',
        'Patient Code must be unique per company.',
    )

    _constraint_partner_company_uniq = models.Constraint(
        'unique(company_id, partner_id)',
        'This partner already has a patient card in this company.',
    )

    # =========================================================
    # DEFAULTS & COMPUTE
    # =========================================================
    @api.model
    def _default_stage(self):
        stage = self.env["clinic.patient.stage"].search([("is_default_new", "=", True)], limit=1)
        if not stage:
            # fallback ke stage pertama bila data belum di-load (misal initial install)
            stage = self.env["clinic.patient.stage"].search([], order="sequence", limit=1)
        return stage

    @api.depends("name", "patient_code")
    def _compute_display_name(self):
        for rec in self:
            if rec.patient_code:
                rec.display_name = "[%s] %s" % (rec.patient_code, rec.name or "")
            else:
                rec.display_name = rec.name or ""

    @api.depends("birth_date")
    def _compute_age(self):
        today = date.today()
        for rec in self:
            if not rec.birth_date:
                rec.age_years = 0
                rec.age_display = ""
                continue
            # umur: tahun, bulan, hari
            years = today.year - rec.birth_date.year - (
                (today.month, today.day) < (rec.birth_date.month, rec.birth_date.day)
            )
            # hitung bulan & hari untuk tampilan
            months = (today.month - rec.birth_date.month) % 12
            if today.day < rec.birth_date.day:
                months = (months - 1) % 12
                # hari aproksimasi: cukup tampil estetis
                days = (date(today.year, today.month, 1) - date(today.year, (today.month - 1) or 12, 1)).days
                days = (today.day + (days - rec.birth_date.day)) % 31
            else:
                days = today.day - rec.birth_date.day
            rec.age_years = max(0, years)
            # format ringkas
            parts = []
            if years > 0:
                parts.append(f"{years}y")
            if months > 0:
                parts.append(f"{months}m")
            if days > 0:
                parts.append(f"{days}d")
            rec.age_display = " ".join(parts) if parts else "0d"

    def _safe_domain_partner(self):
        """Ambil commercial partner untuk domain invoice dsb."""
        partners = self.mapped("partner_id")
        return partners.mapped("commercial_partner_id").ids

    # @api.depends()
    # def _compute_integration_counters(self):
    #     Booking = _has_model(self.env, "booking.booking") and self.env["booking.booking"] or False
    #     Encounter = _has_model(self.env, "clinic.encounter") and self.env["clinic.encounter"] or False
    #     Insurance = _has_model(self.env, "clinic.insurance.authorization") and self.env["clinic.insurance.authorization"] or False
    #     Wallet = _has_model(self.env, "clinic.wallet") and self.env["clinic.wallet"] or False
    #     Consent = _has_model(self.env, "clinic.consent") and self.env["clinic.consent"] or False

    #     Attachment = self.env["ir.attachment"]
    #     AccountMove = _has_model(self.env, "account.move") and self.env["account.move"] or False

    #     for rec in self:
    #         # Default nol
    #         rec.booking_count = 0
    #         rec.encounter_count = 0
    #         rec.invoice_count = 0
    #         rec.attachment_count = 0
    #         rec.coverage_count = 0
    #         rec.wallet_balance = 0.0
    #         rec.has_active_consent = False

    #         # Booking
    #         if Booking:
    #             rec.booking_count = Booking.search_count([("patient_id", "=", rec.id)])

    #         # Encounter
    #         if Encounter:
    #             rec.encounter_count = Encounter.search_count([("patient_id", "=", rec.id)])

    #         # Invoices (Sales invoices) berdasarkan partner (commercial)
    #         if AccountMove and rec.partner_id:
    #             rec.invoice_count = AccountMove.search_count([
    #                 ("move_type", "=", "out_invoice"),
    #                 ("state", "!=", "cancel"),
    #                 ("partner_id", "in", rec._safe_domain_partner()),
    #                 ("company_id", "=", rec.company_id.id),
    #             ])

    #         # Attachments
    #         rec.attachment_count = Attachment.search_count([
    #             ("res_model", "=", self._name),
    #             ("res_id", "=", rec.id),
    #         ])

    #         # Insurance coverage/authorization
    #         if Insurance:
    #             rec.coverage_count = Insurance.search_count([
    #                 ("patient_id", "=", rec.id),
    #                 ("state", "in", ["approved", "authorized"]),
    #             ])

    #         # Wallet
    #         if Wallet:
    #             # Asumsi model clinic.wallet menyimpan 1 record saldo aggregate per patient+company
    #             wallet = Wallet.search([
    #                 ("patient_id", "=", rec.id),
    #                 ("company_id", "=", rec.company_id.id),
    #             ], limit=1)
    #             rec.wallet_balance = wallet.balance if wallet else 0.0

    #         # Consent legal
    #         if Consent:
    #             active_consent = Consent.search_count([
    #                 ("patient_id", "=", rec.id),
    #                 ("state", "=", "active"),
    #             ])
    #             rec.has_active_consent = bool(active_consent)

    # def _compute_last_seen(self):
    #     """Last seen diambil dari encounter terbaru, fallback ke booking."""
    #     Encounter = _has_model(self.env, "clinic.encounter") and self.env["clinic.encounter"] or False
    #     Booking = _has_model(self.env, "booking.booking") and self.env["booking.booking"] or False
    #     for rec in self:
    #         last_dt = False
    #         if Encounter:
    #             enc = Encounter.search(
    #                 [("patient_id", "=", rec.id)],
    #                 order="encounter_datetime DESC, id DESC",
    #                 limit=1,
    #             )
    #             last_dt = enc.encounter_datetime or False
    #         if not last_dt and Booking:
    #             bk = Booking.search(
    #                 [("patient_id", "=", rec.id)],
    #                 order="checkin_datetime DESC, id DESC",
    #                 limit=1,
    #             )
    #             last_dt = bk.checkin_datetime or False
    #         rec.last_seen_date = last_dt

    # =========================================================
    # ONCHANGE & CONSTRAINTS
    # =========================================================
    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        """Sinkron nama pasien dengan nama partner ketika partner dipilih."""
        for rec in self:
            if rec.partner_id and (not rec.name or rec.name.strip() == ""):
                rec.name = rec.partner_id.name

    @api.constrains("birth_date")
    def _check_birth_date(self):
        for rec in self:
            if rec.birth_date and rec.birth_date > date.today():
                raise ValidationError(_("Birth Date cannot be in the future."))

    @api.constrains("is_deceased", "deceased_date")
    def _check_deceased_date(self):
        for rec in self:
            if rec.is_deceased and not rec.deceased_date:
                raise ValidationError(_("Please fill Date of Death when marking patient as deceased."))
            if rec.deceased_date and rec.deceased_date > date.today():
                raise ValidationError(_("Date of Death cannot be in the future."))

    # =========================================================
    # CREATE/WRITE OVERRIDES
    # =========================================================
    @api.model_create_multi
    def create(self, vals_list):
        """Otomatisasi:
        - Assign patient_code dari sequence bila kosong
        - Set default stage
        - Auto-create partner bila tidak disediakan
        - Tandai is_patient di partner inherit
        """
        seq = self.env["ir.sequence"]
        Stage = self.env["clinic.patient.stage"]

        # Ambil default stage sekali saja
        default_stage = Stage.search([("is_default_new", "=", True)], limit=1)
        if not default_stage:
            default_stage = Stage.search([], order="sequence", limit=1)

        for vals in vals_list:
            # Patient code
            if not vals.get("patient_code"):
                vals["patient_code"] = seq.next_by_code("clinic_patient.seq_patient_code")

            # Stage default
            if not vals.get("stage_id") and default_stage:
                vals["stage_id"] = default_stage.id

            # Company default
            vals.setdefault("company_id", self.env.company.id)

            # Buat partner otomatis jika tidak di-provide
            if not vals.get("partner_id"):
                pname = vals.get("name") or _("Unnamed Patient")
                partner = self.env["res.partner"].create({
                    "name": pname,
                    "company_id": vals["company_id"],
                    # sinkron beberapa field umum jika ada di vals:
                    "phone": vals.get("phone"),
                    "mobile": vals.get("mobile"),
                    "email": vals.get("email"),
                    "street": vals.get("street"),
                    "street2": vals.get("street2"),
                    "city": vals.get("city"),
                    "zip": vals.get("zip"),
                    "state_id": vals.get("state_id"),
                    "country_id": vals.get("country_id"),
                })
                # set flag is_patient di inherit (file res_partner_inherit.py)
                if hasattr(partner, "is_patient"):
                    partner.is_patient = True
                vals["partner_id"] = partner.id

        records = super().create(vals_list)

        # Pastikan partner yang ditautkan ditandai sebagai patient
        for rec in records:
            if rec.partner_id and hasattr(rec.partner_id, "is_patient") and not rec.partner_id.is_patient:
                rec.partner_id.is_patient = True

        return records

    def write(self, vals):
        """Sinkron ringan:
        - Perubahan stage ke 'registered' → set registered_date bila kosong
        - Tandai partner.is_patient bila belum
        """
        # detect perubahan stage
        stage_changed = "stage_id" in vals and vals["stage_id"]
        res = super().write(vals)

        if stage_changed:
            # Jika stage yang dipilih bertanda is_registered, set registered_date
            Stage = self.env["clinic.patient.stage"]
            for rec in self:
                if rec.stage_id:
                    stage = Stage.browse(rec.stage_id.id)
                    if stage and stage.is_registered and not rec.registered_date:
                        rec.registered_date = fields.Datetime.now()

                # Otomatis: jika ditandai deceased → pindahkan stage ke is_deceased bila tersedia
                if rec.is_deceased:
                    deceased_stage = Stage.search([("is_deceased", "=", True)], limit=1)
                    if deceased_stage:
                        rec.stage_id = deceased_stage.id

        # Pastikan partner diset patient
        if "partner_id" in vals:
            for rec in self:
                if rec.partner_id and hasattr(rec.partner_id, "is_patient") and not rec.partner_id.is_patient:
                    rec.partner_id.is_patient = True

        return res

    # =========================================================
    # SMART BUTTONS / ACTIONS
    # (Aman meskipun modul terkait belum terpasang)
    # =========================================================
    def _action_open_generic(self, xmlid_candidates, domain, context_add=None, name=None, res_model=None):
        """Helper buka action window dengan fallback:
        - Coba pakai XML ID dari modul terkait (urut kandidat).
        - Jika tidak ada, buat action dinamis (act_window) sederhana.
        """
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
            # fallback ke action dinamis
            if not res_model:
                raise UserError(_("No target model specified for fallback action."))
            action = {
                "type": "ir.actions.act_window",
                "name": name or _("Records"),
                "res_model": res_model,
                "view_mode": "list,form,kanban,pivot,graph,calendar",
                "target": "current",
                "domain": domain,
                "context": {},
            }

        # enforce domain + context default patient
        action["domain"] = domain
        ctx = action.get("context", {}) or {}
        ctx.update({
            "default_patient_id": self.id,
            "search_default_patient_id": self.id,
        })
        if context_add:
            ctx.update(context_add)
        action["context"] = ctx
        return action

    # def action_open_bookings(self):
    #     """Smart button Bookings/Appointments (clinic_booking)."""
    #     self.ensure_one()
    #     if not _has_model(self.env, "booking.booking"):
    #         raise UserError(_("Module 'clinic_booking' is not installed."))
    #     domain = [("patient_id", "=", self.id)]
    #     return self._action_open_generic(
    #         xmlid_candidates=[
    #             "clinic_booking.action_clinic_booking_from_patient",
    #             "clinic_booking.action_clinic_booking",
    #         ],
    #         domain=domain,
    #         name=_("Bookings"),
    #         res_model="booking.booking",
    #     )

    # def action_open_encounters(self):
    #     """Smart button Encounters (clinic_encounter)."""
    #     self.ensure_one()
    #     if not _has_model(self.env, "clinic.encounter"):
    #         raise UserError(_("Module 'clinic_encounter' is not installed."))
    #     domain = [("patient_id", "=", self.id)]
    #     return self._action_open_generic(
    #         xmlid_candidates=[
    #             "clinic_encounter.action_clinic_encounter_from_patient",
    #             "clinic_encounter.action_clinic_encounter",
    #         ],
    #         domain=domain,
    #         name=_("Encounters"),
    #         res_model="clinic.encounter",
    #     )

    def action_open_contact(self):
        """Open the linked Odoo contact without duplicating contact logic."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("No contact is linked to this patient."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Contact"),
            "res_model": "res.partner",
            "res_id": self.partner_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_invoices(self):
        """Smart button Invoices (account)."""
        self.ensure_one()
        if not _has_model(self.env, "account.move"):
            raise UserError(_("Accounting is not installed."))
        partner_ids = self._safe_domain_partner()
        domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "!=", "cancel"),
            ("partner_id", "in", partner_ids),
            ("company_id", "=", self.company_id.id),
        ]
        return self._action_open_generic(
            xmlid_candidates=[
                "account.action_move_out_invoice_type",
            ],
            domain=domain,
            name=_("Invoices"),
            res_model="account.move",
            context_add={"default_partner_id": self.partner_id.id},
        )

    def action_open_attachments(self):
        """Smart button Attachments (ir.attachment)."""
        self.ensure_one()
        domain = [("res_model", "=", self._name), ("res_id", "=", self.id)]
        return self._action_open_generic(
            xmlid_candidates=[
                "base.action_attachment",
            ],
            domain=domain,
            name=_("Attachments"),
            res_model="ir.attachment",
        )

    # def action_open_wallet(self):
    #     """Smart button Wallet (clinic_wallet)."""
    #     self.ensure_one()
    #     if not _has_model(self.env, "clinic.wallet"):
    #         raise UserError(_("Module 'clinic_wallet' is not installed."))
    #     domain = [("patient_id", "=", self.id), ("company_id", "=", self.company_id.id)]
    #     return self._action_open_generic(
    #         xmlid_candidates=[
    #             "clinic_wallet.action_clinic_wallet_from_patient",
    #             "clinic_wallet.action_clinic_wallet",
    #         ],
    #         domain=domain,
    #         name=_("Wallet"),
    #         res_model="clinic.wallet",
    #     )

    # def action_open_insurance(self):
    #     """Smart button Insurance Authorization (clinic_insurance_authorization)."""
    #     self.ensure_one()
    #     if not _has_model(self.env, "clinic.insurance.authorization"):
    #         raise UserError(_("Module 'clinic_insurance_authorization' is not installed."))
    #     domain = [("patient_id", "=", self.id)]
    #     return self._action_open_generic(
    #         xmlid_candidates=[
    #             "clinic_insurance_authorization.action_clinic_insurance_authorization_from_patient",
    #             "clinic_insurance_authorization.action_clinic_insurance_authorization",
    #         ],
    #         domain=domain,
    #         name=_("Insurance Authorizations"),
    #         res_model="clinic.insurance.authorization",
    #     )

    def action_set_registered(self):
        """Tombol cepat pindah ke stage 'Registered' bila tersedia."""
        Stage = self.env["clinic.patient.stage"]
        registered = Stage.search([("is_registered", "=", True)], limit=1)
        if not registered:
            raise UserError(_("No stage configured as 'Registered'."))
        for rec in self:
            rec.stage_id = registered.id
            if not rec.registered_date:
                rec.registered_date = fields.Datetime.now()

    def action_print_patient_card(self):
        """Cetak kartu pasien (QWeb report di modul ini)."""
        self.ensure_one()
        act = self.env.ref(
            "clinic_patient.action_report_patient_card",
            raise_if_not_found=False,
        )
        if not act:
            raise UserError(_("Patient Card report is not configured."))
        return act.report_action(self)

    # =========================================================
    # NAME GET / SEARCH
    # =========================================================
    def name_get(self):
        res = []
        for rec in self:
            name = rec.display_name or rec.name or _("Patient")
            res.append((rec.id, name))
        return res

    @api.model
    @api.readonly
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        """Search patients by code, name, phone, or email using the Odoo 19 API."""
        domain = domain or []
        search_domain = []
        if name:
            search_domain = [
                "|", "|", "|",
                ("patient_code", operator, name),
                ("name", operator, name),
                ("phone", operator, name),
                ("email", operator, name),
            ]

        records = self.search(search_domain + domain, limit=limit)
        return [(record.id, record.display_name) for record in records.sudo()]


