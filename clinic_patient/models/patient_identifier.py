# -*- coding: utf-8 -*-
import re
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =========================================================
# TYPE MASTER: clinic.patient.identifier.type
# =========================================================
class ClinicPatientIdentifierType(models.Model):
    _name = "clinic.patient.identifier.type"
    _description = "Patient Identifier Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Short code (e.g., MRN, NIK, BPJS, PASSPORT, INS_MEMBER, OTHER).",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    # Validasi & format
    validation_regex = fields.Char(
        help="Regular expression to validate the identifier format. "
             "Leave empty to disable strict validation."
    )
    validation_help = fields.Char(
        help="Short help to guide correct format (e.g., '16 digits for NIK')."
    )
    force_case = fields.Selection(
        [("upper", "UPPERCASE"), ("lower", "lowercase"), ("none", "No change")],
        default="none",
        help="Force case for the identifier value on input/write."
    )

    # Otomatisasi nomor (sequence)
    use_sequence = fields.Boolean(
        string="Auto Generate with Sequence",
        help="If enabled, identifier values can be auto-generated "
             "using the assigned sequence."
    )
    sequence_id = fields.Many2one(
        "ir.sequence",
        string="Sequence",
        help="Sequence used when auto-generating identifiers for this type."
    )

    # Flag fungsional (membantu integrasi lintas-modul)
    is_mrn = fields.Boolean(
        string="Is MRN",
        help="Mark this type as the MRN (Medical Record Number). "
             "Will try to keep in sync with patient_code."
    )
    is_national_id = fields.Boolean(
        string="Is National ID",
        help="Mark as national identity number (e.g., NIK for Indonesia)."
    )
    is_passport = fields.Boolean(string="Is Passport")
    is_tax_id = fields.Boolean(
        string="Is Tax ID",
        help="E.g., NPWP (ID), SSN/TIN (other countries)."
    )
    is_insurance_member = fields.Boolean(
        string="Is Insurance Member ID",
        help="Insurance / payer membership number."
    )

    # Prefer at most one primary per patient per type
    single_primary_per_patient = fields.Boolean(
        default=True,
        help="If enabled, a patient can have only ONE primary identifier of this type."
    )

    # Mapping ke field partner (opsional)
    partner_mapping = fields.Selection(
        [
            ("none", "None"),
            ("ref", "Partner Reference"),
            ("vat", "VAT / Tax ID"),
            ("custom_nik", "Partner NIK (if available)"),
            ("custom_bpjs", "Partner BPJS (if available)"),
        ],
        default="none",
        help="Optionally map this identifier to a partner field for convenience."
    )

    # Info visual (untuk report/label; tidak berpengaruh logic di sini)
    barcode_symbology = fields.Selection(
        [
            ("code128", "Code128"),
            ("qrcode", "QR Code"),
            ("none", "None"),
        ],
        default="none",
        help="Preferred symbology for printing labels/cards."
    )

    _constraint_code_unique = models.Constraint(
        'unique(code)',
        'Identifier Type code must be unique.',
    )

    @api.depends("name", "code")
    def _compute_display_name(self):
        """Preserve the legacy '[CODE] Name' label under the Odoo 19 API."""
        for record in self:
            record.display_name = (
                f"[{record.code}] {record.name}"
                if record.code
                else (record.name or _("Identifier Type"))
            )

    def name_get(self):
        res = []
        for rec in self:
            name = rec.name
            if rec.code:
                name = f"[{rec.code}] {rec.name}"
            res.append((rec.id, name))
        return res


# =========================================================
# DETAIL: clinic.patient.identifier
# =========================================================
class ClinicPatientIdentifier(models.Model):
    _name = "clinic.patient.identifier"
    _description = "Patient Identifier"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "is_primary DESC, create_date DESC"

    # ------------------------
    # Relations & company scope
    # ------------------------
    patient_id = fields.Many2one(
        "clinic.patient",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="patient_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    type_id = fields.Many2one(
        "clinic.patient.identifier.type",
        string="Type",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )

    # ------------------------
    # Identifier value & status
    # ------------------------
    value = fields.Char(
        required=False,  # boleh kosong saat create jika use_sequence=True
        copy=False,
        index=True,
        tracking=True,
        help="Identifier value (e.g., MRN/NIK/PASSPORT/BPJS). "
             "Will be auto-generated if the type uses sequence and value is empty."
    )
    is_primary = fields.Boolean(
        default=False,
        tracking=True,
        help="Mark as the primary identifier of this type for this patient."
    )
    active = fields.Boolean(default=True, tracking=True)

    # Informasi penerbitan & masa berlaku
    issue_date = fields.Date(string="Issue Date", tracking=True)
    expiry_date = fields.Date(string="Expiry Date", tracking=True)
    issuing_authority = fields.Char(string="Issuing Authority")
    place_of_issue = fields.Char(string="Place of Issue")

    # Status terhitung (untuk indikator UI/report)
    status = fields.Selection(
        [
            ("valid", "Valid"),
            ("expired", "Expired"),
            ("unknown", "Unknown"),
            ("revoked", "Revoked"),
        ],
        compute="_compute_status",
        store=False,
    )
    revoked = fields.Boolean(
        help="If checked, this identifier is revoked (no longer valid)."
    )

    # Tampilan
    display_name = fields.Char(compute="_compute_display_name", store=True)

    # Catatan
    notes = fields.Text()

    # ------------------------
    # Constraints (SQL)
    # ------------------------
    _constraint_uniq_company_type_value = models.Constraint(
        'unique(company_id, type_id, value)',
        'Identifier value must be unique per company and type.',
    )

    # =========================================================
    # COMPUTE
    # =========================================================
    @api.depends("type_id.code", "value", "is_primary")
    def _compute_display_name(self):
        for rec in self:
            tcode = rec.type_id.code or "ID"
            base = rec.value or "-"
            if rec.is_primary:
                rec.display_name = f"[{tcode}★] {base}"
            else:
                rec.display_name = f"[{tcode}] {base}"

    @api.depends("expiry_date", "revoked")
    def _compute_status(self):
        today = date.today()
        for rec in self:
            if rec.revoked:
                rec.status = "revoked"
            elif rec.expiry_date:
                rec.status = "expired" if rec.expiry_date < today else "valid"
            else:
                rec.status = "unknown"

    # =========================================================
    # ONCHANGE / HELPERS
    # =========================================================
    @api.onchange("type_id", "value")
    def _onchange_type_force_case(self):
        """Terapkan force_case dari type saat mengetik."""
        for rec in self:
            if rec.value and rec.type_id and rec.type_id.force_case != "none":
                if rec.type_id.force_case == "upper":
                    rec.value = rec.value.upper()
                elif rec.type_id.force_case == "lower":
                    rec.value = rec.value.lower()

    def _apply_force_case(self, type_id, value):
        """Helper untuk memastikan case di create/write."""
        if not value or not type_id:
            return value
        if type_id.force_case == "upper":
            return value.upper()
        if type_id.force_case == "lower":
            return value.lower()
        return value

    def _validate_against_regex(self, type_id, value):
        """Validasi dengan regex jika di-setup pada type."""
        if not value or not type_id or not type_id.validation_regex:
            return
        pattern = re.compile(type_id.validation_regex)
        if not pattern.fullmatch(value):
            msg = _("Identifier '%s' does not match expected format.") % (value,)
            if type_id.validation_help:
                msg += _(" Hint: %s") % type_id.validation_help
            raise ValidationError(msg)

    def _validate_known_formats(self, type_id, value):
        """Validasi ringan untuk beberapa tipe umum tanpa regex (fallback).
        Jangan over-strict: cukup panjang & numeric check untuk menghindari false positive.
        """
        if not value or not type_id:
            return

        code = (type_id.code or "").upper()
        val = value.replace(" ", "").replace("-", "")

        # NIK Indonesia = 16 digit (ringan)
        if type_id.is_national_id or code == "NIK":
            if not (len(val) == 16 and val.isdigit()):
                raise ValidationError(_("NIK should be exactly 16 digits."))

        # BPJS Indonesia = 13 digit (umum)
        if code == "BPJS":
            if not (len(val) == 13 and val.isdigit()):
                raise ValidationError(_("BPJS number should be 13 digits."))

        # PASSPORT (fallback ringan): alnum 6-9+ char
        if type_id.is_passport or code == "PASSPORT":
            if not (len(val) >= 6 and val.isalnum()):
                raise ValidationError(_("Passport should be alphanumeric with length >= 6."))

        # Tax ID (NPWP Indonesia sering 15 digit + format khusus; gunakan check ringan)
        if type_id.is_tax_id or code in ("NPWP", "TAXID"):
            if not (len(val) >= 12):
                raise ValidationError(_("Tax ID looks too short."))

    def _ensure_single_primary(self):
        """Pastikan hanya 1 primary per patient+type bila diaktifkan."""
        for rec in self:
            if rec.is_primary and rec.type_id.single_primary_per_patient:
                others = self.search([
                    ("id", "!=", rec.id),
                    ("patient_id", "=", rec.patient_id.id),
                    ("type_id", "=", rec.type_id.id),
                    ("is_primary", "=", True),
                ])
                if others:
                    # jadikan record ini primary, nonaktifkan yang lain
                    others.write({"is_primary": False})

    def _sync_with_patient_mrn(self):
        """Jika type.is_mrn = True, jaga sinkronisasi ringan dengan patient.patient_code:
        - Jika value kosong saat create, isi dari patient.patient_code
        - Jika value diisi berbeda, biarkan coexist (tidak memaksa).
        - Jika belum ada identifier MRN primary, tandai yang ini primary.
        """
        for rec in self:
            if rec.type_id and rec.type_id.is_mrn:
                # Tandai primary bila belum ada primary MRN
                if rec.type_id.single_primary_per_patient and not rec.is_primary:
                    # cek apakah sudah ada primary MRN
                    already_primary = self.search_count([
                        ("id", "!=", rec.id),
                        ("patient_id", "=", rec.patient_id.id),
                        ("type_id", "=", rec.type_id.id),
                        ("is_primary", "=", True),
                    ])
                    if not already_primary:
                        rec.is_primary = True

                # Jika value kosong dan patient_code tersedia → isi
                if not rec.value and rec.patient_id.patient_code:
                    rec.value = rec.patient_id.patient_code

    def _map_to_partner_if_configured(self):
        """Opsional: mapping ke field partner bila user mengaktifkan di type."""
        for rec in self:
            partner = rec.patient_id.partner_id
            if not partner or not rec.value:
                continue

            pm = rec.type_id.partner_mapping
            if pm == "ref":
                if partner.ref != rec.value:
                    partner.ref = rec.value
            elif pm == "vat":
                if partner.vat != rec.value:
                    partner.vat = rec.value
            elif pm == "custom_nik":
                # hanya jika field tersedia
                if hasattr(partner, "nik"):
                    if getattr(partner, "nik") != rec.value:
                        setattr(partner, "nik", rec.value)
            elif pm == "custom_bpjs":
                if hasattr(partner, "bpjs_no"):
                    if getattr(partner, "bpjs_no") != rec.value:
                        setattr(partner, "bpjs_no", rec.value)
            # else: none → do nothing

    # =========================================================
    # CONSTRAINTS
    # =========================================================
    @api.constrains("issue_date", "expiry_date")
    def _check_dates(self):
        for rec in self:
            if rec.issue_date and rec.expiry_date and rec.expiry_date < rec.issue_date:
                raise ValidationError(_("Expiry Date cannot be before Issue Date."))

    @api.constrains("value", "type_id", "company_id")
    def _check_value_constraints(self):
        for rec in self:
            # Case forcing
            if rec.value:
                forced = rec._apply_force_case(rec.type_id, rec.value)
                if forced != rec.value:
                    # write langsung agar konsisten
                    super(ClinicPatientIdentifier, rec).write({"value": forced})

            # Regex validation (if provided)
            rec._validate_against_regex(rec.type_id, rec.value)

            # Light known checks (NIK/BPJS/PASSPORT/NPWP fallback)
            rec._validate_known_formats(rec.type_id, rec.value)

    @api.constrains("is_primary", "type_id", "patient_id")
    def _check_single_primary_flag(self):
        for rec in self:
            if rec.is_primary and rec.type_id.single_primary_per_patient:
                dup = self.search_count([
                    ("id", "!=", rec.id),
                    ("patient_id", "=", rec.patient_id.id),
                    ("type_id", "=", rec.type_id.id),
                    ("is_primary", "=", True),
                ])
                if dup:
                    raise ValidationError(
                        _("Only one primary identifier of type '%s' is allowed per patient.")
                        % (rec.type_id.display_name,)
                    )

    # =========================================================
    # CRUD OVERRIDES
    # =========================================================
    @api.model_create_multi
    def create(self, vals_list):
        # Preprocess: auto-generate value if needed
        for vals in vals_list:
            # coerce basic keys
            type_id = vals.get("type_id")
            value = vals.get("value")
            is_primary = vals.get("is_primary", False)

            # Fetch type record (only if needed)
            Type = None
            if type_id:
                Type = self.env["clinic.patient.identifier.type"].browse(type_id)

            # Force case before validations
            if Type and value:
                vals["value"] = self._apply_force_case(Type, value)

            # Auto-generate from sequence
            if Type and not vals.get("value") and Type.use_sequence and Type.sequence_id:
                vals["value"] = Type.sequence_id.next_by_id()

            # If this type is MRN and value still empty, try sync with patient.patient_code later
            # Mark primary for MRN if configured and not explicitly set
            if Type and Type.is_mrn and "is_primary" not in vals and Type.single_primary_per_patient:
                vals["is_primary"] = True

        records = super().create(vals_list)

        # Post-create sync:
        for rec in records:
            # MRN sync (fill value from patient_code if still empty; set primary)
            rec._sync_with_patient_mrn()

            # After value exists, validate per type (regex & known formats)
            rec._validate_against_regex(rec.type_id, rec.value)
            rec._validate_known_formats(rec.type_id, rec.value)

            # Ensure single primary (soft enforcement; if conflicts, demote others)
            rec._ensure_single_primary()

            # Optional mapping to partner fields
            rec._map_to_partner_if_configured()

        return records

    def write(self, vals):
        # Keep a snapshot for logic
        toggle_primary = "is_primary" in vals
        change_type = "type_id" in vals
        change_value = "value" in vals

        # Normalize case on incoming values
        if change_value or change_type:
            # we may need the resulting type to decide case
            # approach: compute target type per record (old/new)
            for rec in self:
                target_type = rec.type_id
                if change_type:
                    target_type = self.env["clinic.patient.identifier.type"].browse(vals["type_id"])
                if change_value and vals.get("value"):
                    vals["value"] = rec._apply_force_case(target_type, vals["value"])
                # else leave as is

        res = super().write(vals)

        for rec in self:
            # MRN sync in case of type change or empty value previously
            rec._sync_with_patient_mrn()

            # Re-validate
            rec._validate_against_regex(rec.type_id, rec.value)
            rec._validate_known_formats(rec.type_id, rec.value)

            # Enforce single primary (demote others if needed)
            if toggle_primary or change_type:
                rec._ensure_single_primary()

            # Optional mapping to partner fields if value changed or type changed
            if change_value or change_type:
                rec._map_to_partner_if_configured()

        return res

    # =========================================================
    # ACTIONS / UTILITIES
    # =========================================================
    def action_set_primary(self):
        """Set record ini sebagai primary untuk type yang sama pada patient."""
        self.ensure_one()
        if not self.type_id.single_primary_per_patient:
            raise UserError(_("This identifier type does not restrict primary to a single record."))
        self.write({"is_primary": True})

    def name_get(self):
        res = []
        for rec in self:
            tcode = rec.type_id.code or "ID"
            val = rec.value or "-"
            star = "★" if rec.is_primary else ""
            res.append((rec.id, f"[{tcode}{star}] {val}"))
        return res

