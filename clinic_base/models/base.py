
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError, UserError, MissingError
from odoo.tools import date_utils
from odoo.osv.expression import AND, OR
import json

class ClinicMixinCompany(models.AbstractModel):
    """
    Clinic: Company & Active Mixin
    --------------------------------
    - Menyediakan field `company_id` (wajib, default = env.company)
    - Menyediakan field `active` (arsip/non-aktif)
    - Menyediakan helper untuk validasi dan domain multi-company
    - Tidak membuat table sendiri (abstract)

    Cara pakai (contoh):
        class ClinicSomething(models.Model):
            _name = "clinic.something"
            _inherit = ["clinic.mixin.company"]      # aktifkan scope company & active
            name = fields.Char("Name", required=True)

    Catatan:
    - Pastikan user memiliki akses ke `company_id` yang dipakai record.
    - Jika ingin mengizinkan record "global" (tanpa company), override `_clinic_allow_global_company = True`.
    - Jika ingin `company_id` opsional, override `_clinic_company_required = False`.
    """
    _name = "clinic.mixin.company"
    _description = "Clinic: Company & Active Mixin"
    _abstract = True

    # Konfigurasi default yang bisa dioverride oleh model turunan
    _clinic_allow_global_company = False    # izinkan company_id = False?
    _clinic_company_required = True         # company_id wajib?

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        index=True,
        default=lambda self: self.env.company,
        required=True,
        help="Owning company of this record."
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive the record."
    )

    # -----------------------------
    # Helper utilitas multi-company
    # -----------------------------
    @api.model
    def _clinic_allowed_company_ids(self):
        """Kembalikan daftar company yang diizinkan untuk user saat ini."""
        # env.companies = semua company yang sedang diizinkan di context
        ids = self.env.companies.ids or []
        return ids or [self.env.company.id]

    @api.model
    def _clinic_is_company_allowed(self, company):
        """True jika company diperbolehkan untuk user saat ini."""
        if not company:
            return bool(self._clinic_allow_global_company)
        return self.env.is_superuser() or (company.id in self._clinic_allowed_company_ids())

    @api.model
    def _clinic_company_domain(self):
        """
        Domain standar untuk membatasi record sesuai company user.
        - Jika _clinic_allow_global_company = True, maka juga mengizinkan company_id = False.
        """
        domain = [("company_id", "in", self._clinic_allowed_company_ids())]
        if self._clinic_allow_global_company:
            domain = ["|", ("company_id", "=", False)] + domain
        return domain

    # --------------------------------
    # Validasi konsistensi company_id
    # --------------------------------
    @api.constrains("company_id")
    def _check_company_scope(self):
        # Komentar (ID): Pastikan company_id valid untuk user (kecuali superuser)
        for rec in self:
            if not rec.company_id and not self._clinic_allow_global_company:
                raise ValidationError(_("Company is required for this record."))
            if rec.company_id and not self._clinic_is_company_allowed(rec.company_id):
                raise AccessError(_("You cannot assign a record to a company you don't have access to."))

    # ---------------------------------------------------
    # Override create/write untuk menjaga konsistensi scope
    # ---------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        # Komentar (ID): Isi default & validasi company pada saat create
        for vals in vals_list:
            # Tentukan company default bila kosong
            if "company_id" not in vals or not vals.get("company_id"):
                if self._clinic_company_required and not self._clinic_allow_global_company:
                    vals["company_id"] = self.env.company.id
            # Validasi akses company tujuan
            cmp = vals.get("company_id") and self.env["res.company"].browse(vals["company_id"]) or False
            if cmp and not self._clinic_is_company_allowed(cmp):
                raise AccessError(_("You cannot create a record in company '%s'.") % (cmp.display_name,))
            if not cmp and not self._clinic_allow_global_company and self._clinic_company_required:
                raise ValidationError(_("Company is required for this record."))
        return super().create(vals_list)

    def write(self, vals):
        # Komentar (ID): Cegah pindah company ke company yang tidak diizinkan
        if "company_id" in vals:
            new_cmp = vals.get("company_id") and self.env["res.company"].browse(vals["company_id"]) or False
            if new_cmp:
                if not self._clinic_is_company_allowed(new_cmp):
                    raise AccessError(_("You cannot move the record to company '%s'.") % (new_cmp.display_name,))
            else:
                if not self._clinic_allow_global_company and self._clinic_company_required:
                    raise ValidationError(_("Company is required for this record."))
        return super().write(vals)

    # -------------------------------------------------------
    # Utilitas context-switch untuk operasi lintas perusahaan
    # -------------------------------------------------------
    @api.model
    def with_company_ids(self, companies):
        """
        Kembalikan environment dengan allowed_company_ids dibatasi pada `companies`.
        Gunakan saat butuh evaluasi/compute di konteks perusahaan tertentu.

        Contoh:
            self.with_company_ids(self.env.company).search([...])
        """
        if not companies:
            return self
        if isinstance(companies, models.BaseModel):
            comp_ids = companies.ids
        elif isinstance(companies, (list, tuple, set)):
            comp_ids = [c.id if hasattr(c, "id") else int(c) for c in companies]
        else:
            comp_ids = [int(companies)]
        return self.with_context(allowed_company_ids=comp_ids).with_company(comp_ids[0])

    def ensure_same_company(self, other_records, allow_global=False):
        """
        Pastikan semua record berada pada company yang sama (atau global jika diizinkan).
        Lempar ValidationError bila tidak konsisten.

        Param:
            other_records (recordset): record lain untuk dibandingkan
            allow_global (bool): jika True, izinkan company_id False dianggap kompatibel
        """
        self_companies = set(self.mapped("company_id").ids)
        other_companies = set(other_records.mapped("company_id").ids)
        if allow_global:
            self_companies.discard(False)
            other_companies.discard(False)
        if self_companies and other_companies and self_companies != other_companies:
            raise ValidationError(_("Company mismatch between related records."))

    # ---------------------------------------------------
    # Hook ringan bagi model turunan (boleh dioverride)
    # ---------------------------------------------------
    @api.model
    def _clinic_company_onchange_hook(self, vals, old_company, new_company):
        """
        Hook opsional: dipanggil saat company berganti (pada write).
        Model turunan dapat override untuk mereset field terkait company.
        """
        return vals

class ClinicMixinAudit(models.AbstractModel):
    """
    Clinic: Audit Bridge Mixin
    --------------------------
    - Mencatat jejak audit create/write (siapa, kapan, apa yang berubah)
    - Jika modul `clinic_audit` terpasang & model logger tersedia (mis. `clinic.audit.log`),
      maka payload dikirim ke logger tersebut.
    - Jika tidak, fallback ke chatter (message_post) bila model mewarisi mail.thread;
      jika tidak ada chatter, tetap aman (no-op).

    Cara pakai (contoh):
        class ClinicPatient(models.Model):
            _name = "clinic.patient"
            _inherit = ["mail.thread", "mail.activity.mixin", "clinic.mixin.audit"]

        # (opsional) batasi field yang dilacak:
        _clinic_audit_track_fields = ["name", "phone", "email", "active"]

    Catatan:
    - Mixin ini *tidak* memaksa dependency ke clinic_audit.
    - Sensitif fields otomatis termask (token/password, dll).
    """
    _name = "clinic.mixin.audit"
    _description = "Clinic: Audit Bridge Mixin"
    _abstract = True

    # --------------------------------
    # Konfigurasi yang bisa dioverride
    # --------------------------------
    _clinic_audit_enabled = True  # bisa dimatikan per model
    _clinic_audit_track_fields = []  # kosong = auto: semua writable fields (kecuali mask)
    _clinic_audit_mask_fields = {"password", "token", "secret", "key", "ssn", "pin"}
    _clinic_audit_subtype_xmlid = "mail.mt_note"  # subtype untuk chatter fallback
    _clinic_audit_logger_model = "clinic.audit.log"  # target logger bila clinic_audit ada

    # -----------------
    # Helper: ketersediaan logger eksternal
    # -----------------
    @api.model
    def _clinic_audit_logger_available(self):
        """True jika model logger tersedia (dan modul aktif)."""
        try:
            # Cek model di registry
            return self._clinic_audit_logger_model in self.env
        except Exception:
            return False

    @api.model
    def _clinic_audit_context_enabled(self):
        """
        Audit bisa dimatikan via context:
            with_context(clinic_audit_skip=True)
        """
        return not self.env.context.get("clinic_audit_skip")

    # -----------------
    # Helper: pemilihan field & masking
    # -----------------
    @api.model
    def _clinic_audit_fields(self):
        """
        Daftar field yang akan diaudit.
        - Jika _clinic_audit_track_fields kosong -> pakai semua writable fields (kecuali x2many murni)
        - Exclude: computed-only, readonly tanpa inverse, fields transient tertentu.
        """
        if self._clinic_audit_track_fields:
            # Validasi hanya field yang ada
            return [f for f in self._clinic_audit_track_fields if f in self._fields]
        # Default: semua field "tulis" wajar (kecuali x2many karena berat)
        fields_obj = []
        for name, f in self._fields.items():
            # skip technicals
            if name in ("message_ids", "message_follower_ids", "activity_ids"):
                continue
            # skip o2m/m2m (karena diff kompleks & berat); relasi ini bisa di-audit di model relasinya sendiri
            if f.type in ("one2many", "many2many"):
                continue
            # skip computed-only tanpa inverse (readonly permanen)
            if f.compute and not f.inverse:
                continue
            fields_obj.append(name)
        return fields_obj

    @api.model
    def _clinic_audit_mask(self, field_name, value):
        """Mask nilai sensitif untuk payload audit."""
        if field_name in self._clinic_audit_mask_fields:
            return "******"
        return value

    @api.model
    def _clinic_audit_value_repr(self, field, value):
        """
        Representasi ringkas untuk nilai field dalam payload:
        - M2O -> {"id": id, "name": display}
        - Date/Datetime -> to string
        - Monetary/Float/Int/Boolean/Text/HTML/Char -> langsung
        """
        if value is None:
            return None
        t = field.type
        if t == "many2one":
            # value di vals bisa berupa int/id atau tuple (id, name) atau recordset
            if isinstance(value, models.BaseModel):
                return {"id": value.id, "name": value.display_name}
            if isinstance(value, (tuple, list)) and value and isinstance(value[0], int):
                return {"id": value[0], "name": str(value[1]) if len(value) > 1 else ""}
            if isinstance(value, int):
                rec = self.env[field.comodel_name].browse(value)
                return {"id": rec.id, "name": rec.display_name}
            return {"id": False, "name": str(value)}
        if t in ("date", "datetime"):
            return str(value)
        # lainnya: biarkan apa adanya (akan di-masking di call site jika perlu)
        return value

    def _clinic_audit_diff(self, vals):
        """
        Bangun diff untuk setiap record:
        {
          record_id: {
            "old": {field: value_repr_masked, ...},
            "new": {field: value_repr_masked, ...}
          }, ...
        }
        """
        tracked = self._clinic_audit_fields()
        diffs = {}
        for rec in self:
            rec_diff_old, rec_diff_new = {}, {}
            for fname, new_raw in vals.items():
                if fname not in tracked or fname not in self._fields:
                    continue
                field = self._fields[fname]
                # nilai lama
                old_val = rec[fname]
                old_repr = self._clinic_audit_value_repr(field, old_val)
                # nilai baru: perhatikan jika vals banyak format
                new_repr = self._clinic_audit_value_repr(field, new_raw)
                # masking
                old_masked = self._clinic_audit_mask(fname, old_repr)
                new_masked = self._clinic_audit_mask(fname, new_repr)
                # hanya catat jika berbeda
                if json.dumps(old_masked, sort_keys=True, default=str) != json.dumps(new_masked, sort_keys=True, default=str):
                    rec_diff_old[fname] = old_masked
                    rec_diff_new[fname] = new_masked
            if rec_diff_old or rec_diff_new:
                diffs[rec.id] = {"old": rec_diff_old, "new": rec_diff_new}
        return diffs

    # -----------------
    # Payload & emit
    # -----------------
    @api.model
    def _clinic_audit_make_payload(self, action, rec, diff=None, extra=None):
        """Bangun payload JSON-friendly untuk satu record."""
        user = self.env.user
        base = {
            "model": rec._name,
            "res_id": rec.id or 0,
            "action": action,  # 'create' / 'write' / custom
            "user_id": user.id,
            "user_name": user.display_name,
            "timestamp": fields.Datetime.now(),
        }
        if diff:
            base["diff"] = diff
        if extra:
            base["extra"] = extra
        return base

    def _clinic_audit_emit(self, payloads, message=None):
        """
        Kirim payload ke logger eksternal bila ada; fallback ke chatter.
        payloads: list of dict payload
        message : short text (untuk chatter)
        """
        if not payloads:
            return

        # 1) Target logger eksternal (clinic_audit) bila tersedia
        if self._clinic_audit_logger_available():
            Logger = self.env[self._clinic_audit_logger_model].sudo()
            # Deteksi field yang tersedia secara dinamis (agar kompatibel)
            logger_fields = set(Logger._fields.keys())
            mapped = []
            for p in payloads:
                data = {
                    # mapping generik; akan difilter terhadap field model
                    "name": "%s %s #%s" % (p.get("model"), p.get("action"), p.get("res_id")),
                    "model": p.get("model"),
                    "res_id": p.get("res_id"),
                    "action": p.get("action"),
                    "user_id": p.get("user_id"),
                    "payload_json": json.dumps(p, default=str),
                    "message": message or "",
                    "timestamp": p.get("timestamp") or fields.Datetime.now(),
                }
                # filter hanya keys yang ada di model target
                data = {k: v for k, v in data.items() if k in logger_fields}
                mapped.append(data)
            try:
                Logger.create(mapped)
                return
            except Exception:
                # Jika gagal, teruskan ke fallback chatter
                pass

        # 2) Fallback ke chatter (hanya jika model mewarisi mail.thread)
        if hasattr(self, "message_post"):
            # Gabungkan payload ringkas; hindari spam terlalu panjang
            brief_lines = []
            for p in payloads:
                meta = "[%s %s id=%s by %s]" % (p.get("model"), p.get("action"), p.get("res_id"), p.get("user_name"))
                if p.get("diff"):
                    # tampilkan key yang berubah saja
                    changed_keys = set()
                    try:
                        changed_keys = set(p["diff"].get("old", {}).keys()) | set(p["diff"].get("new", {}).keys())
                    except Exception:
                        pass
                    meta += " fields: " + ", ".join(sorted(changed_keys))
                brief_lines.append(meta)
            body = (message or "Audit trail") + "<br/>" + "<br/>".join(brief_lines)
            # Post satu pesan ke setiap record unik
            for rec in self:
                try:
                    rec.message_post(
                        body=body,
                        subtype_xmlid=self._clinic_audit_subtype_xmlid,
                    )
                except Exception:
                    # diamkan jika model tidak support message_post pada state tertentu
                    pass

    # -----------------
    # Hook high-level
    # -----------------
    @api.model_create_multi
    def create(self, vals_list):
        if (not self._clinic_audit_enabled) or (not self._clinic_audit_context_enabled()):
            return super().create(vals_list)

        records = super().create(vals_list)

        # Emit payload per record (create tidak punya diff lama; tampilkan nilai baru terbatas)
        payloads = []
        tracked = self._clinic_audit_fields()
        for rec, vals in zip(records, vals_list):
            # siapkan "new" snapshot terbatas pada tracked
            new_snapshot = {}
            for fname in tracked:
                if fname in self._fields:
                    try:
                        field = self._fields[fname]
                        new_snapshot[fname] = self._clinic_audit_mask(
                            fname, self._clinic_audit_value_repr(field, rec[fname])
                        )
                    except Exception:
                        continue
            payloads.append(self._clinic_audit_make_payload("create", rec, diff={"old": {}, "new": new_snapshot}))

        self._clinic_audit_emit(payloads, message=_("Record created"))
        return records

    def write(self, vals):
        if (not self._clinic_audit_enabled) or (not self._clinic_audit_context_enabled()) or not vals:
            return super().write(vals)

        # Siapkan diff sebelum write
        diffs = self._clinic_audit_diff(vals)  # {id: {old,new}}
        res = super().write(vals)

        # Bangun payload hanya untuk record yang benar2 berubah pada tracked fields
        payloads = []
        for rec in self:
            diff = diffs.get(rec.id)
            if not diff:
                continue
            # Setelah write, perbarui snapshot "new" dengan nilai terbaru (agar akurat jika orm menormalisasi)
            tracked = set(diff["old"].keys()) | set(diff["new"].keys())
            refreshed_new = {}
            for fname in tracked:
                field = rec._fields.get(fname)
                if not field:
                    continue
                try:
                    refreshed_new[fname] = self._clinic_audit_mask(
                        fname, self._clinic_audit_value_repr(field, rec[fname])
                    )
                except Exception:
                    continue
            payloads.append(self._clinic_audit_make_payload("write", rec, diff={"old": diff["old"], "new": refreshed_new}))

        if payloads:
            self._clinic_audit_emit(payloads, message=_("Record updated"))
        return res

    # -----------------
    # API untuk audit custom (opsional)
    # -----------------
    def clinic_audit_log(self, action, message=None, extra=None):
        """
        Panggil manual untuk mencatat aksi custom.
        Contoh: self.clinic_audit_log("merge", message="Merged duplicates", extra={"source_ids":[1,2]})
        """
        if (not self._clinic_audit_enabled) or (not self._clinic_audit_context_enabled()):
            return
        payloads = [self._clinic_audit_make_payload(action, rec, diff=None, extra=extra) for rec in self]
        self._clinic_audit_emit(payloads, message=message or _("Action: %s") % action)

class ClinicMixinSequence(models.AbstractModel):
    """
    Clinic: Sequence & Code Mixin
    -----------------------------
    Fitur utama:
    - Menyediakan kolom `code` (Char, index) sebagai nomor unik bisnis (mis. MRN, PAT, ENC, dll.)
    - Otomatis mengisi `code` dari ir.sequence saat create (jika kosong).
    - Opsi "per company" agar unik per perusahaan bila model memiliki company_id.
    - Menyediakan helper untuk ambil next number dan menyiapkan sequence jika belum ada.
    - Menyediakan `display_ref` (compute) sebagai "[CODE] Name" (opsional, ringan).
      *Jika kamu juga memakai `clinic.mixin.name_display`, mixin itu bisa
       membuat name_get yang konsisten memakai `display_ref`.*

    Cara pakai (contoh):
        class ClinicPatient(models.Model):
            _name = "clinic.patient"
            _inherit = ["clinic.mixin.sequence"]
            name = fields.Char("Name", required=True)

            # Override (opsional)
            _clinic_seq_field = "mrn"                   # pakai kolom lain selain 'code'
            _clinic_seq_code = "clinic.patient.mrn"     # key di ir.sequence
            _clinic_seq_prefix = "MRN%(y)s%(month)s-"   # prefix default
            _clinic_seq_padding = 5
            _clinic_seq_per_company = True              # unik per company
            _clinic_seq_allow_manual = False            # larang edit manual

    Catatan:
    - Jika _clinic_seq_per_company=True tapi model tidak punya company_id, fallback ke global.
    - Jika ingin nomor manual pada kasus tertentu, gunakan context:
      with_context(clinic_seq_skip=True) atau with_context(clinic_seq_allow_manual=True)
    """
    _name = "clinic.mixin.sequence"
    _description = "Clinic: Sequence & Code Mixin"
    _abstract = True

    # -------------------------------
    # Konfigurasi (boleh dioverride)
    # -------------------------------
    _clinic_seq_field = "code"              # nama field penomoran
    _clinic_seq_code = ""                   # wajib diisi di model turunan; contoh: "clinic.patient.mrn"
    _clinic_seq_prefix = ""                 # contoh: "MRN%(y)s%(month)s-"
    _clinic_seq_padding = 5
    _clinic_seq_per_company = True
    _clinic_seq_allow_manual = False        # izinkan user mengisi/edit manual?

    # Field "code" bawaan (boleh diabaikan jika model override _clinic_seq_field != "code")
    code = fields.Char(
        string="Code",
        index=True,
        copy=False,
        help="Business reference code generated from a sequence."
    )

    # Status internal sekadar indikator (tidak untuk logic wajib)
    sequence_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sequenced", "Sequenced"),
            ("manual", "Manual"),
        ],
        string="Sequence State",
        default="draft",
        help="Indicates whether the code was auto-generated or set manually."
    )

    # Tampilan ringkas untuk digunakan oleh name_display mixin atau views
    display_ref = fields.Char(
        string="Display Ref",
        compute="_compute_display_ref",
        store=False,
        help="Computed '[CODE] Name' for consistent display."
    )

    # ------------------------------------------------
    # Utility: deteksi field name utama untuk display
    # ------------------------------------------------
    @api.model
    def _clinic_seq_get_name_field(self):
        """Cari nama field terbaik untuk display (default 'name')."""
        if "name" in self._fields:
            return "name"
        # fallback: cari Char pertama
        for fname, f in self._fields.items():
            if f.type == "char":
                return fname
        return False

    @api.depends(lambda self: [self._clinic_seq_field] + ([self._clinic_seq_get_name_field()] if self._clinic_seq_get_name_field() else []))
    def _compute_display_ref(self):
        # Komentar (ID): Bangun "[CODE] Name" tanpa menyimpan ke DB
        name_field = self._clinic_seq_get_name_field()
        for rec in self:
            code_val = (rec[self._clinic_seq_field] or "").strip() if self._clinic_seq_field in rec._fields else ""
            name_val = (name_field and rec[name_field]) or ""
            if code_val and name_val:
                rec.display_ref = "[%s] %s" % (code_val, name_val)
            elif code_val:
                rec.display_ref = "[%s]" % code_val
            else:
                rec.display_ref = name_val or ""

    # ------------------------------------------------
    # Utility: cek & siapkan ir.sequence sesuai config
    # ------------------------------------------------
    @api.model
    def _clinic_seq_get_or_create_sequence(self, company=None):
        """
        Ambil ir.sequence sesuai _clinic_seq_code.
        Jika belum ada, buat dengan prefix/padding default dari konfigurasi.
        Jika per_company=True dan company tersedia, gunakan sequence per company.
        """
        if not self._clinic_seq_code:
            raise ValidationError(_("%s is missing _clinic_seq_code; set a unique sequence code.")
                                  % self._name)

        Seq = self.env["ir.sequence"].sudo()

        # Jika per company & ada company_id, cari sequence khusus company
        domain = [("code", "=", self._clinic_seq_code)]
        if self._clinic_seq_per_company and company:
            domain += [("company_id", "=", company.id)]
        else:
            domain += [("company_id", "=", False)]

        seq = Seq.search(domain, limit=1)
        if seq:
            return seq

        # Buat sequence baru bila tidak ditemukan
        vals = {
            "name": "%s Sequence%s" % (self._clinic_seq_code, (" (%s)" % (company.display_name,)) if company else ""),
            "code": self._clinic_seq_code,
            "implementation": "standard",
            "prefix": self._clinic_seq_prefix or "",
            "padding": self._clinic_seq_padding or 5,
            "company_id": company.id if (company and self._clinic_seq_per_company) else False,
        }
        return Seq.create(vals)

    @api.model
    def _clinic_seq_next_number(self, company=None):
        """
        Ambil nomor berikutnya menggunakan ir.sequence (per company bila diaktifkan).
        """
        seq = self._clinic_seq_get_or_create_sequence(company=company)
        # Catatan: next_by_id memperhatikan company_id sequence tsb.
        return seq.next_by_id()

    # ------------------------------------------------
    # Guard: bolehkah isi/edit manual?
    # ------------------------------------------------
    @api.model
    def _clinic_seq_manual_allowed(self):
        """
        True jika pengisian manual diizinkan:
        - Konfigurasi class _clinic_seq_allow_manual = True
        - atau context mengizinkan `clinic_seq_allow_manual=True`
        """
        return bool(self._clinic_seq_allow_manual or self.env.context.get("clinic_seq_allow_manual"))

    @api.model
    def _clinic_seq_skip(self):
        """
        True jika penomoran otomatis mau diskip via context:
        with_context(clinic_seq_skip=True)
        """
        return bool(self.env.context.get("clinic_seq_skip"))

    # ------------------------------------------------
    # Constraint unik (global atau per company)
    # ------------------------------------------------
    @api.constrains('code')
    def _check_code_unique(self):
        # Komentar (ID): Validasi unik sederhana via search; SQL constraint bisa ditambahkan di model turunan.
        for rec in self:
            code_field = self._clinic_seq_field
            if not code_field or code_field not in rec._fields:
                continue
            code_val = (rec[code_field] or "").strip()
            if not code_val:
                continue
            dom = [(code_field, "=", code_val)]
            # Unik per company jika memungkinkan
            if self._clinic_seq_per_company and "company_id" in rec._fields and rec.company_id:
                dom += [("company_id", "=", rec.company_id.id)]
            dup = self.search(dom + [("id", "!=", rec.id)], limit=1)
            if dup:
                raise ValidationError(_("Code must be unique."))

    # ------------------------------------------------
    # Create/Write override untuk auto-sequence & guard
    # ------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for vals in vals_list:
            code_field = self._clinic_seq_field
            manual_code = (code_field in vals) and bool(vals.get(code_field))
            # Jika manual diisi tapi tidak diizinkan
            if manual_code and not self._clinic_seq_manual_allowed():
                raise AccessError(_("Manual code is not allowed for %s.") % self._name)

            # Jika tidak diskip dan code kosong -> generate
            if (not manual_code) and (not self._clinic_seq_skip()):
                company = None
                if self._clinic_seq_per_company and "company_id" in vals and vals.get("company_id"):
                    company = self.env["res.company"].browse(vals["company_id"])
                elif self._clinic_seq_per_company and "company_id" in self._fields:
                    # fallback: gunakan env.company bila field ada tapi tidak diisi
                    company = self.env.company
                vals[code_field] = self._clinic_seq_next_number(company=company)
                # tandai state
                if "sequence_state" in self._fields and "sequence_state" not in vals:
                    vals["sequence_state"] = "sequenced"
            else:
                # manual
                if "sequence_state" in self._fields and "sequence_state" not in vals:
                    vals["sequence_state"] = "manual" if manual_code else "draft"

        records = super().create(vals_list)
        return records

    def write(self, vals):
        code_field = self._clinic_seq_field
        if code_field in vals:
            # Komentar (ID): Mencegah perubahan code tanpa izin
            if vals.get(code_field) and not self._clinic_seq_manual_allowed():
                raise AccessError(_("Manual code change is not allowed for %s.") % self._name)
            # Jika clearing code -> larang (umumnya tidak diizinkan)
            if vals.get(code_field) in (False, "", None) and not self._clinic_seq_manual_allowed():
                raise AccessError(_("Clearing the code is not allowed."))

        res = super().write(vals)

        # Update sequence_state jika perlu
        if "sequence_state" in self._fields and code_field in vals:
            for rec in self:
                if rec[code_field]:
                    rec.sequence_state = "manual" if self._clinic_seq_manual_allowed() else rec.sequence_state or "sequenced"
                else:
                    rec.sequence_state = "draft"

        return res

    # ------------------------------------------------
    # API tambahan (opsional)
    # ------------------------------------------------
    def clinic_seq_regenerate(self, force=False):
        """
        Regenerasi nomor sequence untuk record yang belum punya code.
        Jika force=True, timpa nomor yang ada (perlu allow_manual).
        """
        code_field = self._clinic_seq_field
        if force and not self._clinic_seq_manual_allowed():
            raise AccessError(_("Manual overwrite is not allowed."))

        for rec in self:
            need = force or not rec[code_field]
            if not need:
                continue
            company = None
            if self._clinic_seq_per_company and "company_id" in rec._fields and rec.company_id:
                company = rec.company_id
            new_code = rec._clinic_seq_next_number(company=company)
            rec.write({code_field: new_code, "sequence_state": "sequenced" if not self._clinic_seq_manual_allowed() else "manual"})
        return True

class ClinicMixinPhone(models.AbstractModel):
    """
    Clinic: Phone Normalization Mixin
    ---------------------------------
    Tujuan:
    - Menyediakan normalisasi nomor telepon ke format E.164 agar:
      * pencarian konsisten
      * deduplikasi mudah
      * integrasi eksternal stabil
    - Menyediakan field `phone_normalized` sebagai "primary normalized phone".
    - Menyediakan helper untuk normalisasi, domain pencarian, dan (opsional) keunikan.

    Cara pakai (contoh):
        class ClinicPatient(models.Model):
            _name = "clinic.patient"
            _inherit = ["mail.thread", "clinic.mixin.phone"]
            # Pastikan ada salah satu field di _clinic_phone_fields, default: ['mobile', 'phone']
            # (misal karena _inherits res.partner, fields 'mobile'/'phone' sudah tersedia)

        # (opsional) Konfigurasi:
        _clinic_phone_fields = ["mobile", "phone"]  # urutan prioritas baca
        _clinic_phone_primary_field = "mobile"      # sumber utama untuk phone_normalized
        _clinic_phone_country_field = "country_id"  # sumber region default (res.country)
        _clinic_phone_unique = False                # aktifkan jika ingin unik per model

    Catatan:
    - Mixin ini tidak menambah field 'phone'/'mobile'. Field tersebut diasumsikan sudah ada
      di model (atau via _inherits). Jika tidak ada, atur _clinic_phone_fields sesuai field Anda.
    - Normalisasi mencoba gunakan API Odoo (partner._phone_format / phone_sanitize_number)
      dan akan fallback ke pembersihan sederhana jika modul/helper tidak tersedia.
    """
    _name = "clinic.mixin.phone"
    _description = "Clinic: Phone Normalization Mixin"
    _abstract = True

    # -------------------------------
    # Konfigurasi (boleh dioverride)
    # -------------------------------
    _clinic_phone_fields = ["mobile", "phone"]     # urutan prioritas sumber nomor
    _clinic_phone_primary_field = "mobile"         # sumber utama untuk phone_normalized
    _clinic_phone_country_field = "country_id"     # Many2one res.country (opsional)
    _clinic_phone_unique = False                   # enforce uniqueness on phone_normalized?

    phone_normalized = fields.Char(
        string="Phone (E.164)",
        index=True,
        copy=False,
        readonly=True,
        help="Primary phone normalized to E.164 for reliable lookup."
    )

    # ----------------------------------------
    # Utility: deteksi negara/region normalisasi
    # ----------------------------------------
    def _clinic_phone_get_region_country(self):
        """
        Kembalikan record res.country untuk konteks normalisasi.
        Urutan:
          1) field di record sesuai _clinic_phone_country_field (jika ada & bernilai)
          2) company saat ini (env.company.country_id)
          3) False (tanpa region; normalisasi best-effort)
        """
        country_field = getattr(self.__class__, "_clinic_phone_country_field", "country_id")
        for rec in self:
            if country_field in rec._fields:
                country = rec[country_field]
                if country:
                    return country
        # fallback ke company
        if self.env.company and self.env.company.country_id:
            return self.env.company.country_id
        return False

    # ----------------------------------------
    # Utility: ambil nomor kandidat dari record
    # ----------------------------------------
    def _clinic_phone_get_candidate_numbers(self):
        """
        Ambil daftar kandidat nomor telepon dari record sesuai _clinic_phone_fields.
        Hanya mengembalikan string non-kosong.
        """
        numbers = []
        fields_list = list(getattr(self.__class__, "_clinic_phone_fields", [])) or ["mobile", "phone"]
        for rec in self:
            for fname in fields_list:
                if fname in rec._fields:
                    val = (rec[fname] or "").strip()
                    if val:
                        numbers.append(val)
            break  # hanya perlu template dari satu record (struktur sama)
        # unik + pertahankan urutan
        seen = set()
        ordered = []
        for n in numbers:
            if n not in seen:
                seen.add(n)
                ordered.append(n)
        return ordered

    # ----------------------------------------
    # Normalizer: gunakan tools Odoo bila ada
    # ----------------------------------------
    @api.model
    def _clinic_phone_normalize_raw(self, number, country=False):
        """
        Normalisasi satu nomor menjadi E.164 semampu mungkin.
        Preferensi:
          - res.partner._phone_format(force_format='E164') jika tersedia
          - res.partner.phone_sanitize_number
          - fallback: hapus spasi/tanda umum + pastikan awalan '+' jika mungkin
        """
        number = (number or "").strip()
        if not number:
            return False

        # 1) Coba _phone_format dari res.partner (memerlukan konteks record)
        try:
            Partner = self.env["res.partner"]
            # buat record in-memory agar _phone_format punya konteks country
            partner_ctx = Partner.new({})
            region = country or self.env.company.country_id or False
            normalized = partner_ctx._phone_format(
                number,  # raw
                region,  # record res.country atau False
                record_country=None,
                force_format="E164"
            )
            if normalized:
                return normalized
        except Exception:
            pass

        # 2) Coba sanitizer dari res.partner (versi berbeda-beda antar Odoo)
        try:
            Partner = self.env["res.partner"]
            if hasattr(Partner, "phone_sanitize_number"):
                normalized = Partner.phone_sanitize_number(number, country=country)
                if normalized:
                    # pastikan diawali '+' jika bukan extension; sanitizer kadang mengembalikan tanpa '+'
                    return normalized if normalized.startswith("+") else "+" + normalized
        except Exception:
            pass

        # 3) Fallback: pembersihan kasar
        import re
        digits = re.sub(r"[^\d+]", "", number)   # sisakan digit dan '+'
        # Jika tidak ada '+' dan ada region country_code, tambahkan (best-effort)
        if not digits.startswith("+") and country and getattr(country, "phone_code", False):
            digits = "+" + str(country.phone_code) + digits.lstrip("0")
        # Validasi minimal: harus ada min 7 digit setelah kode negara
        min_len = 7
        only_digits = digits[1:] if digits.startswith("+") else digits
        if len(re.sub(r"[^\d]", "", only_digits)) < min_len:
            return False
        return digits if digits.startswith("+") else "+" + digits

    # ----------------------------------------
    # Compute & hook normalisasi
    # ----------------------------------------
    def _clinic_phone_compute_primary(self):
        """
        Isi `phone_normalized` berdasarkan prioritas:
          primary field -> kandidat _clinic_phone_fields -> False.
        Dipanggil dari create/write atau on-demand.
        """
        Country = self.env["res.country"]
        for rec in self:
            # tentukan source utama
            primary = getattr(self.__class__, "_clinic_phone_primary_field", "mobile")
            raw = None
            if primary in rec._fields:
                raw = (rec[primary] or "").strip()
            if not raw:
                # fallback: kandidat lain
                for fn in getattr(self.__class__, "_clinic_phone_fields", ["mobile", "phone"]):
                    if fn in rec._fields and (rec[fn] or "").strip():
                        raw = (rec[fn] or "").strip()
                        break

            region = rec._clinic_phone_get_region_country()
            rec.phone_normalized = self._clinic_phone_normalize_raw(raw, country=region) if raw else False

    @api.model_create_multi
    def create(self, vals_list):
        # Komentar (ID): isi phone_normalized saat create bila tersedia source-nya
        records = super().create(vals_list)
        # Normalisasi setelah create (punya access ke computed fields seperti country_id via default)
        # Hanya hit yang relevan agar hemat
        to_update = records.filtered(lambda r: any(f in r._fields for f in getattr(self.__class__, "_clinic_phone_fields", ["mobile", "phone"])))
        to_update._clinic_phone_compute_primary()
        return records

    def write(self, vals):
        # Komentar (ID): jika ada perubahan phone/country -> recompute
        res = super().write(vals)
        watched = set(getattr(self.__class__, "_clinic_phone_fields", ["mobile", "phone"]))
        watched.add(getattr(self.__class__, "_clinic_phone_country_field", "country_id"))
        if any(k in watched for k in vals.keys()):
            self._clinic_phone_compute_primary()
        return res

    # ----------------------------------------
    # (Opsional) Keunikan
    # ----------------------------------------
    @api.constrains("phone_normalized")
    def _check_phone_normalized_unique(self):
        """
        Jika _clinic_phone_unique=True, enforce uniqueness pada phone_normalized (non-empty).
        Perlu dipertimbangkan: multi-company; jika ingin unik per perusahaan, override method ini.
        """
        if not getattr(self.__class__, "_clinic_phone_unique", False):
            return
        for rec in self:
            pn = (rec.phone_normalized or "").strip()
            if not pn:
                continue
            dup = self.search([("phone_normalized", "=", pn), ("id", "!=", rec.id)], limit=1)
            if dup:
                raise ValidationError(_("Normalized phone must be unique: %s") % pn)

    # ----------------------------------------
    # Helper domain & pencarian
    # ----------------------------------------
    @api.model
    def clinic_phone_domain(self, raw_number):
        """
        Bangun domain pencarian dari input raw:
          - normalisasi input
          - cari pada phone_normalized
          - fallback: LIKE pada field sumber (_clinic_phone_fields)
        """
        raw = (raw_number or "").strip()
        if not raw:
            return [("id", "=", 0)]
        country = self.env.company.country_id
        normalized = self._clinic_phone_normalize_raw(raw, country=country)
        if normalized:
            return ["|"] + [("phone_normalized", "=", normalized)] + self._clinic_phone_like_domain(raw)
        return self._clinic_phone_like_domain(raw)

    @api.model
    def _clinic_phone_like_domain(self, raw):
        """
        Domain LIKE sederhana ke field sumber (untuk fallback).
        """
        dom = []
        fields_list = list(getattr(self.__class__, "_clinic_phone_fields", [])) or ["mobile", "phone"]
        # gabungkan dengan OR
        if not fields_list:
            return [("id", "=", 0)]
        if len(fields_list) == 1:
            return [(fields_list[0], "ilike", raw)]
        # build "OR" chain
        dom = ["|"] * (len(fields_list) - 1)
        for fname in fields_list:
            dom.append((fname, "ilike", raw))
        return dom

    # ----------------------------------------
    # API publik ringkas
    # ----------------------------------------
    def clinic_phone_refresh(self):
        """
        Recompute manual untuk phone_normalized (misal untuk data lama).
        """
        self._clinic_phone_compute_primary()
        return True

    @api.model
    def clinic_phone_search(self, raw_number):
        """
        Pencarian cepat berdasarkan nomor (raw).
        """
        return self.search(self.clinic_phone_domain(raw_number), limit=80)

class ClinicMixinNameDisplay(models.AbstractModel):
    """
    Clinic: Name Display Mixin
    --------------------------
    Tujuan:
    - Menyeragamkan tampilan nama record (name_get) ke format ringkas & informatif.
    - Prioritas menampilkan CODE (mis. MRN/sequence) + Name: "[CODE] Name".
    - Menyediakan name_search yang fleksibel: cari by code / name / (opsional) phone.

    Cara pakai (contoh):
        class ClinicPatient(models.Model):
            _name = "clinic.patient"
            _inherit = ["mail.thread", "clinic.mixin.name_display", "clinic.mixin.sequence", "clinic.mixin.phone"]
            name = fields.Char("Name", required=True)

        # (opsional) Konfigurasi:
        _clinic_name_code_field = "mrn"             # kalau bukan 'code'
        _clinic_name_main_field = "name"            # field utama nama
        _clinic_name_format = "[{code}] {name}"     # template string
        _clinic_name_use_display_ref = True         # jika model punya field display_ref (dari mixin sequence)
        _clinic_name_fallback_id = True             # fallback ke "#ID" bila semua kosong
        _clinic_name_search_extra = True            # aktifkan pencarian ekstra (mrn/code/phone)

    Catatan:
    - Jika model juga memakai `clinic.mixin.sequence`, field `display_ref` sudah tersedia
      dan bisa langsung digunakan.
    - Jika model tidak punya `code/mrn`, mixin ini akan otomatis pakai `name` saja.
    """
    _name = "clinic.mixin.name_display"
    _description = "Clinic: Name Display Mixin"
    _abstract = True

    # -------------------------------
    # Konfigurasi (boleh dioverride)
    # -------------------------------
    _clinic_name_code_field = "code"            # nama field untuk kode bisnis (mis. 'code'/'mrn')
    _clinic_name_main_field = "name"            # nama field untuk nama utama
    _clinic_name_format = "[{code}] {name}"     # format display
    _clinic_name_use_display_ref = True         # gunakan display_ref jika tersedia (dari mixin sequence)
    _clinic_name_fallback_id = True             # fallback: "#<id>" bila kosong
    _clinic_name_search_extra = True            # perluas name_search (code, name, phone_normalized)

    # ------------------------------------------------
    # Helper: ambil nama & kode yang "terbaik"
    # ------------------------------------------------
    @api.model
    def _clinic_name_get_code_field(self):
        """
        Tentukan field kode:
        - Respect _clinic_name_code_field
        - Jika model juga punya _clinic_seq_field (dari mixin sequence), pakai itu bila cocok
        """
        # Jika model sequence override field
        seq_field = getattr(self.__class__, "_clinic_seq_field", None)
        if seq_field and seq_field in self._fields:
            return seq_field
        # Jika config code field ada & valid
        cfg = getattr(self.__class__, "_clinic_name_code_field", "code")
        return cfg if cfg in self._fields else False

    @api.model
    def _clinic_name_get_main_field(self):
        """
        Tentukan field nama utama (default 'name'; fallback cari Char pertama).
        """
        cfg = getattr(self.__class__, "_clinic_name_main_field", "name")
        if cfg in self._fields:
            return cfg
        # fallback: cari Char pertama
        for fname, f in self._fields.items():
            if f.type == "char":
                return fname
        return False

    def _clinic_name_pick(self):
        """
        Kembalikan tuple (code, name) untuk setiap record, dengan fallback aman.
        """
        code_field = self._clinic_name_get_code_field()
        name_field = self._clinic_name_get_main_field()
        for rec in self:
            code_val = (code_field and rec[code_field]) or False
            name_val = (name_field and rec[name_field]) or ""
            yield (code_val and str(code_val).strip()) or False, (name_val and str(name_val).strip()) or ""

    # ------------------------------------------------
    # Odoo 19 display_name + compatibility name_get
    # ------------------------------------------------
    def _clinic_name_format_display(self):
        """Return the ClinicOne display label for one record."""
        self.ensure_one()

        use_display_ref = bool(getattr(self.__class__, "_clinic_name_use_display_ref", True))
        tmpl = getattr(self.__class__, "_clinic_name_format", "[{code}] {name}")
        fallback_id = bool(getattr(self.__class__, "_clinic_name_fallback_id", True))

        if use_display_ref and "display_ref" in self._fields:
            value = (self.display_ref or "").strip()
            if value:
                return value

        code_val, name_val = next(self._clinic_name_pick())
        if code_val and name_val:
            return tmpl.format(code=code_val, name=name_val)
        if code_val:
            return "[%s]" % code_val
        if name_val:
            return name_val
        if fallback_id and self.id:
            return "#%s" % self.id
        return _("(unknown)")

    @api.depends(
        lambda self: [
            fname
            for fname in (
                self._clinic_name_get_code_field(),
                self._clinic_name_get_main_field(),
                "display_ref" if "display_ref" in self._fields else False,
            )
            if fname
        ]
    )
    def _compute_display_name(self):
        """Odoo 19-native display name computation."""
        for rec in self:
            rec.display_name = rec._clinic_name_format_display()

    def name_get(self):
        """
        Compatibility wrapper for ClinicOne code that still calls ``name_get``.
        Odoo 19 itself uses ``display_name`` / ``_compute_display_name``.
        """
        return [(rec.id, rec._clinic_name_format_display()) for rec in self]

    # ------------------------------------------------
    # name_search: code/name/phone while respecting caller domain
    # ------------------------------------------------
    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        """
        Flexible Odoo 19-compatible name search.

        The caller-provided domain is always AND-ed with ClinicOne search
        criteria so relational-field restrictions cannot be bypassed.
        """
        domain = domain or []

        if not name:
            records = self.search(domain, limit=limit)
            return [(rec.id, rec.display_name) for rec in records.sudo()]

        code_field = self._clinic_name_get_code_field()
        if code_field:
            exact_domain = AND([domain, [(code_field, "=", name)]])
            records = self.search(exact_domain, limit=limit)
            if records:
                return [(rec.id, rec.display_name) for rec in records.sudo()]

        domain_parts = []
        if code_field:
            domain_parts.append([(code_field, operator, name)])

        name_field = self._clinic_name_get_main_field()
        if name_field:
            domain_parts.append([(name_field, operator, name)])

        if bool(getattr(self.__class__, "_clinic_name_search_extra", True)):
            if "phone_normalized" in self._fields:
                domain_parts.append([("phone_normalized", operator, name)])
            for fname in ("mobile", "phone"):
                if fname in self._fields:
                    domain_parts.append([(fname, operator, name)])

        search_domain = OR(domain_parts) if domain_parts else []
        final_domain = AND([domain, search_domain]) if search_domain else domain
        records = self.search(final_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in records.sudo()]

class ClinicMixinSecurity(models.AbstractModel):
    """
    Clinic: Security Helper Mixin
    -----------------------------
    Tujuan:
    - Menyediakan API ringkas untuk:
        * cek grup: any/all
        * require grup (lempar AccessError)
        * cek akses model (read/write/create/unlink)
        * cek access rules (record rules) untuk record tertentu
        * guard util: ensure_can_{read,write,create,unlink}()
        * (opsional) validasi company jika field company_id tersedia

    Cara pakai (contoh):
        class ClinicPatient(models.Model):
            _name = "clinic.patient"
            _inherit = ["mail.thread", "clinic.mixin.security"]

        # Opsional override di model turunan:
        _clinic_admin_groups = ("base.group_system",)              # grup yang dianggap admin modul ini
        _clinic_manager_groups = ()                                # grup manager modul ini
        _clinic_enforce_company_on_write = True                    # cek company saat write/unlink
        _clinic_enforce_company_on_create = True                   # cek company saat create

    Catatan:
    - Mixin ini tidak menggantikan ACL/record rule; hanya *helper* dan guard tambahan.
    - Untuk model yang juga memakai `clinic.mixin.company`, validasi company akan saling melengkapi.
    """
    _name = "clinic.mixin.security"
    _description = "Clinic: Security Helper Mixin"
    _abstract = True

    # -------------------------------
    # Konfigurasi (boleh dioverride)
    # -------------------------------
    _clinic_admin_groups = ("base.group_system",)     # XMLIDs grup yang dipandang 'admin' untuk model ini
    _clinic_manager_groups = tuple()                  # XMLIDs grup manager (model turunan dapat set)
    _clinic_enforce_company_on_write = False          # enforce cek company_id saat write/unlink
    _clinic_enforce_company_on_create = False         # enforce cek company_id saat create

    # --------------------------------
    # Util: Normalisasi daftar XMLID
    # --------------------------------
    @api.model
    def _clinic_sec__norm_groups(self, groups):
        if not groups:
            return tuple()
        if isinstance(groups, (list, tuple, set)):
            return tuple(str(g) for g in groups if g)
        return (str(groups),)

    # --------------------------------
    # Cek grup user
    # --------------------------------
    @api.model
    def user_has_any_group(self, groups):
        """True jika user memiliki minimal salah satu grup."""
        xmlids = self._clinic_sec__norm_groups(groups)
        if not xmlids:
            return False
        return self.env.user.has_groups(",".join(xmlids))

    @api.model
    def user_has_all_groups(self, groups):
        """True jika user memiliki SEMUA grup di daftar."""
        xmlids = self._clinic_sec__norm_groups(groups)
        if not xmlids:
            return False
        user = self.env.user
        return all(user.has_group(x) for x in xmlids)

    # --------------------------------
    # Require grup (raise)
    # --------------------------------
    @api.model
    def require_any_group(self, groups, msg=None):
        """Wajib minimal salah satu grup."""
        if not self.user_has_any_group(groups):
            raise AccessError(msg or _("You don't have the required role to perform this action."))

    @api.model
    def require_all_groups(self, groups, msg=None):
        """Wajib semua grup."""
        if not self.user_has_all_groups(groups):
            raise AccessError(msg or _("You don't have the required role to perform this action."))

    # --------------------------------
    # Helpers: admin/manager flag
    # --------------------------------
    @api.model
    def is_admin_like(self):
        """User dianggap admin modul ini jika termasuk salah satu _clinic_admin_groups."""
        return self.user_has_any_group(getattr(self, "_clinic_admin_groups", ()))

    @api.model
    def is_manager_like(self):
        """User dianggap manager modul ini jika termasuk salah satu _clinic_manager_groups."""
        return self.user_has_any_group(getattr(self, "_clinic_manager_groups", ()))

    # --------------------------------
    # Cek akses model-level
    # --------------------------------
    @api.model
    def check_model_access(self, mode, raise_exception=False):
        """
        Cek ACL model (tanpa record rule).
        mode: 'read' | 'write' | 'create' | 'unlink'
        """
        model_records = self.browse()
        if raise_exception:
            model_records.check_access(mode)
            return True
        return model_records.has_access(mode)

    # --------------------------------
    # Cek record rules untuk recordset saat ini
    # --------------------------------
    def check_rules(self, mode, raise_exception=False):
        """
        Cek record rules (domain) untuk recordset ini.
        mode: 'read' | 'write' | 'create' | 'unlink'
        """
        if raise_exception:
            self.check_access(mode)
            return True
        return self.has_access(mode)

    # --------------------------------
    # Guard: ensure_can_*  (kombinasi ACL + Rules)
    # --------------------------------
    @api.model
    def ensure_can_create(self):
        self.check_model_access("create", raise_exception=True)
        return True

    def ensure_can_read(self):
        self.check_model_access("read", raise_exception=True)
        self.check_rules("read", raise_exception=True)
        return True

    def ensure_can_write(self):
        self.check_model_access("write", raise_exception=True)
        self.check_rules("write", raise_exception=True)
        # (opsional) enforce company konsisten
        if getattr(self, "_clinic_enforce_company_on_write", False):
            self._clinic_sec__ensure_company_allowed()
        return True

    def ensure_can_unlink(self):
        self.check_model_access("unlink", raise_exception=True)
        self.check_rules("unlink", raise_exception=True)
        # (opsional) enforce company konsisten
        if getattr(self, "_clinic_enforce_company_on_write", False):
            self._clinic_sec__ensure_company_allowed()
        return True

    # --------------------------------
    # API boolean untuk UI logic
    # --------------------------------
    @api.model
    def can_create(self):
        return self.check_model_access("create", raise_exception=False)

    def can_read(self):
        if not self.check_model_access("read", raise_exception=False):
            return False
        return self.check_rules("read", raise_exception=False)

    def can_write(self):
        if not self.check_model_access("write", raise_exception=False):
            return False
        return self.check_rules("write", raise_exception=False)

    def can_unlink(self):
        if not self.check_model_access("unlink", raise_exception=False):
            return False
        return self.check_rules("unlink", raise_exception=False)

    # --------------------------------
    # Enforce company (opsional, ringan)
    # --------------------------------
    def _clinic_sec__ensure_company_allowed(self):
        """
        Jika record punya field company_id, pastikan user punya akses ke company tersebut.
        (Melengkapi clinic.mixin.company bila dipakai bersamaan.)
        """
        if "company_id" not in self._fields:
            return True
        allowed = set(self.env.companies.ids or [self.env.company.id])
        for rec in self:
            # izinkan kosong (global) — guard lebih ketat ada di clinic.mixin.company
            cmp = rec.company_id.id if rec.company_id else None
            if cmp and cmp not in allowed and not self.env.is_superuser():
                raise AccessError(_("You cannot access records of another company."))
        return True

    # --------------------------------
    # Guard di lifecycle (opsional)
    # --------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        # Guard ACL 'create' terlebih dulu
        self.ensure_can_create()

        # Enforce company pada create bila diaktifkan
        if getattr(self, "_clinic_enforce_company_on_create", False):
            for vals in vals_list:
                if "company_id" in self._fields:
                    # set default ke env.company bila kosong (tanpa override logic mixin lain)
                    if "company_id" not in vals or not vals.get("company_id"):
                        vals["company_id"] = self.env.company.id

        records = super().create(vals_list)

        # Validasi company setelah create (untuk case diisi manual)
        if getattr(self, "_clinic_enforce_company_on_create", False):
            records._clinic_sec__ensure_company_allowed()

        return records

    def write(self, vals):
        # Cek ACL + rules
        self.ensure_can_write()

        res = super().write(vals)

        # Validasi company setelah write (untuk case pindah company)
        if getattr(self, "_clinic_enforce_company_on_write", False):
            self._clinic_sec__ensure_company_allowed()

        return res

    def unlink(self):
        # Cek ACL + rules
        self.ensure_can_unlink()
        return super().unlink()

    # --------------------------------
    # Eskalasi terbatas via context
    # --------------------------------
    @api.model
    def with_elevated_if_group(self, groups):
        """
        Kembalikan environment 'sudo' hanya jika user memiliki salah satu grup yang diizinkan.
        Bermanfaat untuk operasi administratif terbatas.
        """
        if self.user_has_any_group(groups):
            return self.sudo()
        return self

    # --------------------------------
    # Helper util kecil untuk UI/domain
    # --------------------------------
    @api.model
    def domain_company_allowed(self):
        """
        Domain singkat untuk filter company yang diizinkan (jika field company_id ada).
        """
        if "company_id" not in self._fields:
            return []
        allowed = self.env.companies.ids or [self.env.company.id]
        return [("company_id", "in", allowed)]

    @api.model
    def domain_internal_users(self):
        """Domain untuk user internal (bukan portal/public)."""
        return [("share", "=", False)]

    # --------------------------------
    # Utility error message konsisten
    # --------------------------------
    @api.model
    def _sec_err(self, mode):
        return _("You are not allowed to %s %s records.") % (mode, self._description or self._name)

class ClinicMixinInterop(models.AbstractModel):
    """
    Clinic: Interop Helper Mixin
    ----------------------------
    Tujuan:
    - Mempermudah integrasi lintas modul dengan cara yang defensif & aman:
      * Cek apakah suatu model/field/xmlid tersedia
      * Memanggil method model lain hanya jika ada (fallback nilai default)
      * Helper get/set konfigurasi (ir.config_parameter) dengan namespace
      * Helper membaca/mengatur feature flags (boolean)
      * Helper pencarian/akses record 'safe' (browse/search) jika model ada
      * Cek apakah modul tertentu sudah terpasang

    Cara pakai (contoh):
        class ClinicPatient(models.Model):
            _name = "clinic.patient"
            _inherit = ["clinic.mixin.interop"]

        # Contoh pemakaian:
        if self.interop_has_model("booking.booking"):
            Booking = self.interop_model("booking.booking")
            future = self.interop_safe_search("booking.booking", [("patient_id","=",self.id),("date_start",">=", fields.Datetime.now())], limit=1)

        # Feature flag:
        if self.interop_feature_enabled("use_new_booking_flow"):
            ...

        # Config:
        timeout = self.interop_get_param_float("api.timeout", default=3.0)

        # Safe call:
        count = self.interop_safe_call("clinic.encounter", "count_for_patient", self.id, _default=0)

    Catatan:
    - Semua operasi bersifat *best-effort*; bila target tidak ada, kembalikan nilai aman/default.
    - Namespace default untuk config adalah `clinic` (mis. key: clinic.api.timeout).
    """
    _name = "clinic.mixin.interop"
    _description = "Clinic: Interop Helper Mixin"
    _abstract = True

    # -------------------------------
    # Konfigurasi (boleh dioverride)
    # -------------------------------
    _interop_namespace = "clinic"   # prefix untuk kunci konfigurasi

    # -------------------------------
    # Model & Field availability
    # -------------------------------
    @api.model
    def interop_has_model(self, model_name):
        """True jika model tersedia di registry."""
        try:
            return model_name in self.env
        except Exception:
            return False

    @api.model
    def interop_model(self, model_name):
        """
        Kembalikan env[model_name] bila ada, selain itu None.
        (Gunakan ini alih-alih langsung self.env[...] untuk menghindari KeyError.)
        """
        return self.env[model_name] if self.interop_has_model(model_name) else None

    @api.model
    def interop_has_field(self, model_name, field_name):
        """True jika field ada pada model yang dimaksud."""
        Model = self.interop_model(model_name)
        return bool(Model and (field_name in Model._fields))

    # -------------------------------
    # XMLID (ref) availability
    # -------------------------------
    @api.model
    def interop_has_xmlid(self, xmlid):
        """
        True jika xmlid bisa di-resolve. Tidak me-raise error.
        """
        try:
            self.env.ref(xmlid)
            return True
        except Exception:
            return False

    @api.model
    def interop_ref(self, xmlid, raise_if_not_found=False):
        """
        Resolve xmlid ke record. Jika tidak ditemukan:
        - raise MissingError jika raise_if_not_found=True
        - atau kembalikan recordset kosong
        """
        try:
            return self.env.ref(xmlid)
        except Exception:
            if raise_if_not_found:
                raise MissingError(_("XMLID not found: %s") % xmlid)
            # kembalikan recordset kosong dari model generic (res.partner agar aman)
            return self.env["ir.model.data"].browse([])

    # -------------------------------
    # Safe browse/search/create/call
    # -------------------------------
    @api.model
    def interop_safe_browse(self, model_name, ids):
        """
        Safe browse: jika model tidak ada → kembalikan recordset kosong (ir.model).
        """
        if not self.interop_has_model(model_name):
            return self.env["ir.model"].browse([])
        if isinstance(ids, (int, str)):
            ids = [int(ids)]
        return self.env[model_name].browse(ids or [])

    @api.model
    def interop_safe_search(self, model_name, domain=None, limit=None, order=None):
        """
        Safe search: jika model tidak ada → kembalikan recordset kosong.
        """
        domain = domain or []
        if not self.interop_has_model(model_name):
            return self.env["ir.model"].browse([])
        return self.env[model_name].search(domain, limit=limit, order=order)

    @api.model
    def interop_safe_create(self, model_name, vals, sudo=False, default=None):
        """
        Safe create: buat record bila model tersedia; selain itu, kembalikan default (atau False).
        """
        if not self.interop_has_model(model_name):
            return default
        Model = self.env[model_name].sudo() if sudo else self.env[model_name]
        try:
            return Model.create(vals)
        except Exception:
            return default

    @api.model
    def interop_safe_call(self, model_name, method_name, *args, **kwargs):
        """
        Safe call: panggil method sebuah model jika tersedia dan method ada.
        Gunakan argumen khusus `_default=<nilai>` untuk fallback.
        """
        default = kwargs.pop("_default", None)
        if not self.interop_has_model(model_name):
            return default
        Model = self.env[model_name]
        if not hasattr(Model, method_name):
            return default
        try:
            method = getattr(Model, method_name)
            return method(*args, **kwargs)
        except Exception:
            return default

    # -------------------------------
    # Module installed?
    # -------------------------------
    @api.model
    def interop_is_installed(self, module_name):
        """
        True jika modul `module_name` berada pada status 'installed'/'to upgrade' (best effort).
        Menggunakan ir.module.module (sudo) agar tidak dibatasi hak akses.
        """
        try:
            mod = self.env["ir.module.module"].sudo().search([("name", "=", module_name)], limit=1)
            return bool(mod and mod.state in ("installed", "to upgrade"))
        except Exception:
            return False

    # -------------------------------
    # ir.config_parameter helpers
    # -------------------------------
    def _interop_ns_key(self, key):
        """Bangun nama kunci ter-*namespace* (mis. 'clinic.api.timeout')."""
        ns = getattr(self.__class__, "_interop_namespace", "clinic") or "clinic"
        key = (key or "").strip().lstrip(".")
        return f"{ns}.{key}" if not key.startswith(ns + ".") else key

    @api.model
    def interop_get_param(self, key, default=None):
        """
        Get config (string). Namespaced.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        val = ICP.get_param(self._interop_ns_key(key), default=None)
        return default if val is None else val

    @api.model
    def interop_set_param(self, key, value):
        """
        Set config (string). Namespaced.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(self._interop_ns_key(key), "" if value is None else str(value))
        return True

    # -- typed getters/setters ------------------------------------

    @api.model
    def interop_get_param_bool(self, key, default=False):
        """
        Get config boolean. Menerima '1', 'true', 'True', 'yes', dsb.
        """
        val = self.interop_get_param(key, default=None)
        if val is None:
            return bool(default)
        return str(val).strip().lower() in ("1", "true", "yes", "y", "on")

    @api.model
    def interop_set_param_bool(self, key, value):
        self.interop_set_param(key, "1" if value else "0")
        return True

    @api.model
    def interop_get_param_int(self, key, default=0):
        val = self.interop_get_param(key, default=None)
        try:
            return int(val)
        except Exception:
            return int(default or 0)

    @api.model
    def interop_set_param_int(self, key, value):
        self.interop_set_param(key, int(value) if value is not None else None)
        return True

    @api.model
    def interop_get_param_float(self, key, default=0.0):
        val = self.interop_get_param(key, default=None)
        try:
            return float(val)
        except Exception:
            return float(default or 0.0)

    @api.model
    def interop_set_param_float(self, key, value):
        self.interop_set_param(key, float(value) if value is not None else None)
        return True

    @api.model
    def interop_get_param_json(self, key, default=None):
        """
        Get config sebagai JSON (dict/list). Jika parsing gagal → default.
        """
        val = self.interop_get_param(key, default=None)
        if val is None or val == "":
            return default
        try:
            return json.loads(val)
        except Exception:
            return default

    @api.model
    def interop_set_param_json(self, key, value):
        """
        Set config sebagai JSON (dict/list).
        """
        try:
            dumped = json.dumps(value) if value is not None else ""
        except Exception:
            dumped = ""
        self.interop_set_param(key, dumped)
        return True

    # -------------------------------
    # Feature flags (boolean)
    # -------------------------------
    @api.model
    def interop_feature_enabled(self, feature_name, default=False):
        """
        Baca feature flag bernama `feature_name` (boolean) dari
        kunci: "<ns>.feature.<feature_name>"
        """
        key = f"feature.{feature_name}"
        return self.interop_get_param_bool(key, default=default)

    @api.model
    def interop_feature_set(self, feature_name, enabled=True):
        key = f"feature.{feature_name}"
        return self.interop_set_param_bool(key, bool(enabled))

    # -------------------------------
    # Utilities kecil lain
    # -------------------------------
    @api.model
    def interop_safe_count(self, model_name, domain=None):
        """
        Hitung jumlah record jika model tersedia (search_count), selain itu 0.
        """
        domain = domain or []
        if not self.interop_has_model(model_name):
            return 0
        try:
            return self.env[model_name].search_count(domain)
        except Exception:
            return 0

    @api.model
    def interop_m2o_tuple(self, record):
        """
        Representasi ringkas untuk Many2one:
        - Jika record ada -> (id, display_name)
        - Jika kosong -> (False, "")
        """
        if record:
            return (record.id, record.display_name)
        return (False, "")

    @api.model
    def interop_as_bool(self, value):
        """
        Konversi nilai bebas menjadi bool dengan aturan longgar (untuk parsing input).
        """
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        s = str(value).strip().lower()
        return s in ("1", "true", "yes", "y", "on")

