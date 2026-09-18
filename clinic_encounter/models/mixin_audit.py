# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/mixin_audit.py
#
# Fitur utama:
# - Abstract mixin (clinic.audit.mixin) untuk auto-audit create/write.
# - Log audit generik (clinic.audit.log) dengan reference model/id + diff JSON.
# - Deteksi transisi state/stage_id; helper untuk log custom & attachment events.
# - Konfigurasi enable/disable via System Parameter: clinic.audit.enabled (default: true).
# - Soft-coupled: aman walau modul lain tidak aktif; tidak memaksa mail.thread.
#
import json
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# MODEL: Audit Log (Generic)
# =============================================================================
class ClinicAuditLog(models.Model):
    _name = "clinic.audit.log"
    _description = "ClinicOne Audit Log"
    _order = "date_event desc, id desc"
    _check_company_auto = True

    # Identitas & perusahaan
    name = fields.Char(
        string="Log #",
        required=True,
        copy=False,
        default=lambda s: _("New"),
        index=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company, index=True
    )
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", store=True, readonly=True)

    # Referensi — simpan sebagai field terstruktur & reference
    ref_model = fields.Char(string="Model", required=True, index=True)
    ref_res_id = fields.Integer(string="Record ID", required=True, index=True)
    ref = fields.Reference(
        string="Record",
        selection="_referenceable_models",
        compute="_compute_ref",
        store=False,
    )
    ref_display_name = fields.Char(string="Record Display", compute="_compute_ref_display", store=False)

    # Event
    category = fields.Selection(
        [
            ("create", "Create"),
            ("update", "Update"),
            ("state", "State Transition"),
            ("stage", "Stage Transition"),
            ("attach", "Attachment"),
            ("comment", "Comment"),
            ("custom", "Custom"),
        ],
        string="Category",
        required=True,
        index=True,
        default="update",
    )
    date_event = fields.Datetime(string="When", required=True, default=lambda s: fields.Datetime.now(), index=True)
    user_id = fields.Many2one("res.users", string="Who", default=lambda s: s.env.user, index=True)
    role = fields.Selection(
        [
            ("system", "System"),
            ("user", "User"),
            ("performer", "Performer"),
            ("supervisor", "Supervisor"),
        ],
        string="Role",
        default="user",
        index=True,
    )

    # Ringkasan & alasan
    summary = fields.Char(string="Summary")
    reason_code = fields.Selection(
        [
            ("initial", "Initial"),
            ("edit", "Edit"),
            ("correction", "Correction"),
            ("approval", "Approval"),
            ("rejection", "Rejection"),
            ("auto", "Automated"),
            ("other", "Other"),
        ],
        string="Reason",
        default="edit",
        index=True,
    )
    note = fields.Text(string="Note")

    # Diff konten
    field_name = fields.Char(string="Field (Single)")
    old_value_text = fields.Char(string="Old (text)")
    new_value_text = fields.Char(string="New (text)")

    # Versi agregat (multi-field write)
    changes_json = fields.Text(
        string="Changes (JSON)",
        help='JSON object: {"field": {"old": "...", "new": "..."}, ...}',
    )

    # Metadata tambahan (opsional dari ctx)
    client_ip = fields.Char(string="Client IP")
    user_agent = fields.Char(string="User Agent")

    color = fields.Integer(string="Color Index")

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------
    def _referenceable_models(self):
        """
        Daftar model yang bisa direferensikan. Ambil semua model yang dimulai "clinic."
        + beberapa model Odoo umum bila diperlukan.
        """
        IrModel = self.env["ir.model"].sudo()
        models = IrModel.search([("model", "like", "clinic.%")]).mapped(lambda m: (m.model, m.name))
        # Tambahkan opsi umum (opsional)
        models += [("account.move", "Journal Entry / Invoice"), ("stock.picking", "Stock Picking")]
        # Hilangkan duplikat mempertahankan urutan
        seen = set()
        sel = []
        for m in models:
            if m[0] not in seen:
                sel.append(m)
                seen.add(m[0])
        return sel

    def _compute_ref(self):
        for rec in self:
            rec.ref = (rec.ref_model, rec.ref_res_id)

    def _compute_ref_display(self):
        for rec in self:
            name = False
            try:
                if rec.ref_model and rec.ref_res_id:
                    rec_obj = self.env[rec.ref_model].browse(rec.ref_res_id)
                    if rec_obj.exists():
                        name = rec_obj.display_name
            except Exception:
                pass
            rec.ref_display_name = name

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
                vals["name"] = seq.next_by_code("clinic.audit.log") or _("New")
            # Sanitasi JSON agar selalu string
            if isinstance(vals.get("changes_json"), dict):
                vals["changes_json"] = json.dumps(vals["changes_json"], ensure_ascii=False)
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # Action helpers
    # -------------------------------------------------------------------------
    # def action_open_record(self):
    #     self.ensure_one()
    #     if not (self.ref_model and self.ref_res_id):
    #         raise UserError(_("No referenced record."))
    #     # Cari action bawaan model
    #     try:
    #         # Konvensi action xml id
    #         xml_map = {
    #             "clinic.encounter": "clinic_encounter.action_clinic_encounter",
    #             "clinic.procedure.session": "clinic_encounter.action_clinic_procedure_session",
    #             "clinic.result.document": "clinic_encounter.action_clinic_result_document",
    #             "clinic.consent.document": "clinic_encounter.action_clinic_consent_document",
    #             "clinic.anesthesia.case": "clinic_encounter.action_clinic_anesthesia_case",
    #             "clinic.adverse.event": "clinic_encounter.action_clinic_adverse_event",
    #             "clinic.checklist": "clinic_encounter.action_clinic_checklist",
    #         }
    #         xmlid = xml_map.get(self.ref_model)
    #         if xmlid:
    #             action = self.env.ref(xmlid).read()[0]
    #             action["res_id"] = self.ref_res_id
    #             action["domain"] = [("id", "=", self.ref_res_id)]
    #             action["view_mode"] = "form"
    #             return action
    #     except Exception:
    #         pass
    #     # Fallback generic
    #     return {
    #         "type": "ir.actions.act_window",
    #         "name": _("Record"),
    #         "res_model": self.ref_model,
    #         "res_id": self.ref_res_id,
    #         "view_mode": "form",
    #     }


# =============================================================================
# MIXIN: Audit
# =============================================================================
class ClinicAuditMixin(models.AbstractModel):
    _name = "clinic.audit.mixin"
    _description = "Audit Mixin (ClinicOne)"
    _inherit = []
    _check_company_auto = True
    _abstract = True

    # Counter & quick-open
    audit_log_count = fields.Integer(string="Audit Logs", compute="_compute_audit_log_count", store=False)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    def action_view_audit_logs(self):
        """Open audit logs for current records."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Audit Logs"),
            "res_model": "clinic.audit.log",
            "view_mode": "list,form",
            "domain": [("ref_model", "=", self._name), ("ref_res_id", "=", self.id)],
            "context": {"search_default_group_by_category": 1},
        }

    def audit_log_custom(self, summary=None, note=None, category="custom", reason="other", changes=None, role="user"):
        """
        Tulis log audit kustom dari kode bisnis.
        - summary: ringkasan singkat
        - note: detail
        - category: custom/state/stage/attach/comment/...
        - reason: initial/edit/correction/approval/rejection/auto/other
        - changes: dict {'field': {'old': x, 'new': y}}
        """
        self.ensure_one()
        if not self._audit_is_enabled():
            return False
        vals = self._audit_base_vals(category=category, reason=reason, role=role)
        vals.update({
            "summary": summary or _("Custom event"),
            "note": note or False,
            "changes_json": json.dumps(changes or {}, ensure_ascii=False),
        })
        return self.env["clinic.audit.log"].sudo().create(vals)

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------
    def _compute_audit_log_count(self):
        Audit = self.env["clinic.audit.log"]
        for rec in self:
            rec.audit_log_count = Audit.search_count([("ref_model", "=", rec._name), ("ref_res_id", "=", rec.id)])

    # -------------------------------------------------------------------------
    # Config & policy
    # -------------------------------------------------------------------------
    def _audit_is_enabled(self):
        """
        Audit bisa dimatikan:
        - context['no_audit'] / context['audit_skip'] → True = skip
        - System Parameter 'clinic.audit.enabled' = 'false'
        """
        ctx = self.env.context or {}
        if ctx.get("no_audit") or ctx.get("audit_skip"):
            return False
        Param = self.env["ir.config_parameter"].sudo()
        enabled = Param.get_param("clinic.audit.enabled", "true").strip().lower()
        return enabled not in ("0", "false", "no")

    def _audit_excluded_fields(self):
        """
        Field yang dikecualikan dari diff (chatter, komputasi umum, timestamp).
        Tambahkan field-field khusus model Anda melalui override (return superset).
        """
        base = {
            "id", "create_uid", "create_date", "write_uid", "write_date",
            "display_name", "message_ids", "message_follower_ids",
            "activity_ids", "activity_state", "activity_user_id",
            "activity_date_deadline", "activity_summary", "activity_exception_icon",
            "__last_update",
            # Komputasi amount/total yang diproduksi ulang dari baris
            "price_subtotal", "price_total", "price_tax",
            "actual_duration", "anesthesia_duration_min", "percent_complete",
            "score_total", "score_max", "score_percent", "required_ok",
            "abnormal_count", "critical_count",
            # Warna/tag yang tidak kritikal
            "color",
        }
        # Exclude fields starting with 'x_'? (custom) — jangan, biarkan tercatat.
        return base

    def _audit_included_fields(self):
        """
        Jika diset (return set non-empty), maka hanya field-field ini yang dicatat.
        Default: kosong → catat semua (kecuali excluded).
        """
        return set()

    def _audit_stage_fields(self):
        """
        Field yang diperlakukan sebagai 'stage transition': default: stage_id bila ada.
        """
        fields = []
        if "stage_id" in self._fields:
            fields.append("stage_id")
        return fields

    def _audit_state_fields(self):
        """
        Field yang diperlakukan sebagai 'state transition': default: 'state' bila ada.
        """
        return ["state"] if "state" in self._fields else []

    def _audit_user_role(self):
        """
        Heuristik sederhana menentukan role untuk log.
        Bisa dioverride (misal mengacu ke performer_user_id/doctor_id).
        """
        return "user"

    # -------------------------------------------------------------------------
    # Create/Write overrides
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self._audit_is_enabled():
            return records
        for rec, vals in zip(records, vals_list):
            try:
                # Log initial snapshot (tanpa diff field-by-field agar ringan)
                summary = _("Record created")
                stage_info = []
                for f in rec._audit_state_fields():
                    if f in vals or rec[f]:
                        stage_info.append("%s=%s" % (f, rec._audit_fmt_value(f, rec[f])))
                for f in rec._audit_stage_fields():
                    if f in vals or rec[f]:
                        stage_info.append("%s=%s" % (f, rec._audit_fmt_value(f, rec[f])))
                if stage_info:
                    summary += " (" + ", ".join(stage_info) + ")"

                rec._audit_create_log(category="create", reason="initial", summary=summary, changes=self._audit_pack_changes({}, rec.read()[0]))
            except Exception:
                # Jangan menggagalkan create karena audit
                pass
        return records

    def write(self, vals):
        # Simpan old values per-record untuk diff
        if not self:
            return super().write(vals)

        # Jika audit disabled → langsung write
        if not self._audit_is_enabled():
            return super().write(vals)

        excluded = self._audit_excluded_fields()
        included = self._audit_included_fields()
        interesting_keys = [k for k in vals.keys() if (k not in excluded) and (not included or k in included)]
        if not interesting_keys:
            return super().write(vals)

        # Baca nilai lama yang relevan
        old_snap = {rec.id: rec.read(interesting_keys)[0] for rec in self}
        # Jalankan write
        res = super().write(vals)

        # Untuk tiap record, hitung diff dan tulis audit
        for rec in self:
            try:
                new_snap = rec.read(interesting_keys)[0]
                changes = {}
                category = "update"
                summary_parts = []

                # Deteksi state/stage
                for st_field in rec._audit_state_fields():
                    if st_field in old_snap[rec.id] and st_field in new_snap:
                        if old_snap[rec.id].get(st_field) != new_snap.get(st_field):
                            category = "state"
                            old_txt = rec._audit_fmt_value(st_field, old_snap[rec.id].get(st_field))
                            new_txt = rec._audit_fmt_value(st_field, new_snap.get(st_field))
                            summary_parts.append(_("%s: %s → %s") % (st_field, old_txt, new_txt))
                            changes[st_field] = {"old": old_txt, "new": new_txt}

                for sg_field in rec._audit_stage_fields():
                    if sg_field in old_snap[rec.id] and sg_field in new_snap:
                        if old_snap[rec.id].get(sg_field) != new_snap.get(sg_field):
                            category = "stage" if category == "update" else category
                            old_txt = rec._audit_fmt_value(sg_field, old_snap[rec.id].get(sg_field))
                            new_txt = rec._audit_fmt_value(sg_field, new_snap.get(sg_field))
                            summary_parts.append(_("%s: %s → %s") % (sg_field, old_txt, new_txt))
                            changes[sg_field] = {"old": old_txt, "new": new_txt}

                # Field biasa
                for f in interesting_keys:
                    if f in changes:
                        continue
                    if old_snap[rec.id].get(f) != new_snap.get(f):
                        old_txt = rec._audit_fmt_value(f, old_snap[rec.id].get(f))
                        new_txt = rec._audit_fmt_value(f, new_snap.get(f))
                        changes[f] = {"old": old_txt, "new": new_txt}

                if not changes:
                    continue

                summary = " | ".join(summary_parts) if summary_parts else _("Fields updated")
                rec._audit_create_log(category=category, summary=summary, changes=changes)
            except Exception:
                # Jangan menggagalkan bisnis karena audit
                pass

        return res

    # -------------------------------------------------------------------------
    # Helpers (internal)
    # -------------------------------------------------------------------------
    def _audit_base_vals(self, category="update", reason="edit", role=None):
        self.ensure_one()
        ctx = self.env.context or {}
        vals = {
            "company_id": self.env.company.id,
            "ref_model": self._name,
            "ref_res_id": self.id,
            "category": category,
            "reason_code": reason,
            "date_event": fields.Datetime.now(),
            "user_id": self.env.user.id,
            "role": role or self._audit_user_role(),
            "client_ip": ctx.get("client_ip") or ctx.get("audit_ip") or False,
            "user_agent": ctx.get("user_agent") or ctx.get("http_user_agent") or False,
        }
        return vals

    def _audit_create_log(self, category="update", summary=None, changes=None, reason="edit", role=None, note=None):
        self.ensure_one()
        Audit = self.env["clinic.audit.log"].sudo()
        vals = self._audit_base_vals(category=category, reason=reason, role=role)
        vals.update({
            "summary": summary or False,
            "note": note or False,
            "changes_json": json.dumps(changes or {}, ensure_ascii=False),
        })
        return Audit.create(vals)

    def _audit_pack_changes(self, old_dict, new_dict):
        """Bungkus perbandingan dict lama→baru menjadi dict JSON sederhana."""
        excluded = self._audit_excluded_fields()
        included = self._audit_included_fields()
        changes = {}
        keys = set(new_dict.keys()) | set(old_dict.keys())
        for f in keys:
            if f in excluded:
                continue
            if included and f not in included:
                continue
            if old_dict.get(f) != new_dict.get(f):
                old_txt = self._audit_fmt_value(f, old_dict.get(f))
                new_txt = self._audit_fmt_value(f, new_dict.get(f))
                changes[f] = {"old": old_txt, "new": new_txt}
        return changes

    def _audit_fmt_value(self, field_name, value):
        """Ubah value mentah menjadi string ringkas untuk audit."""
        field = self._fields.get(field_name)
        if not field:
            return self._safe_str(value)

        # Selection → label
        if field.type == "selection":
            sel = dict(field.selection(self) if callable(field.selection) else field.selection or [])
            return self._safe_str(sel.get(value, value))

        # Many2one → display_name
        if field.type == "many2one":
            if isinstance(value, tuple):
                # read() of many2one returns (id, display_name)
                return self._safe_str(value[1])
            if isinstance(value, int) and value:
                try:
                    return self._safe_str(self.env[field.comodel_name].browse(value).display_name)
                except Exception:
                    return self._safe_str(value)
            return ""

        # Date/Datetime → ISO
        if field.type in ("date", "datetime"):
            return self._safe_str(value)

        # Boolean/Float/Char/Html/Text
        if field.type in ("boolean", "float", "char", "html", "text", "integer", "monetary"):
            return self._safe_str(value)

        # Many2many/One2many → tampilkan ringkas jumlah
        if field.type in ("many2many", "one2many"):
            # read() biasanya kembalikan list of ids
            if isinstance(value, list):
                return _("%s items") % len(value)
            return _("[list]")

        # JSON/serialized
        return self._safe_str(value)

    @staticmethod
    def _safe_str(v):
        if v in (None, False):
            return ""
        try:
            return str(v)
        except Exception:
            try:
                return json.dumps(v, ensure_ascii=False)
            except Exception:
                return "<unserializable>"

    # -------------------------------------------------------------------------
    # Convenience hooks yang bisa dipanggil model
    # -------------------------------------------------------------------------
    def audit_log_state_transition(self, old_state, new_state, reason="edit", note=None):
        """Catat transisi state eksplisit (bisa dipanggil dalam action_*)"""
        self.ensure_one()
        if not self._audit_is_enabled():
            return False
        summary = _("State: %s → %s") % (old_state, new_state)
        return self._audit_create_log(category="state", summary=summary, reason=reason, note=note,
                                      changes={"state": {"old": old_state, "new": new_state}})

    def audit_log_stage_transition(self, field_name="stage_id", old_stage=None, new_stage=None, reason="edit", note=None):
        self.ensure_one()
        if not self._audit_is_enabled():
            return False
        old_txt = self._audit_fmt_value(field_name, old_stage)
        new_txt = self._audit_fmt_value(field_name, new_stage)
        summary = _("%s: %s → %s") % (field_name, old_txt, new_txt)
        return self._audit_create_log(category="stage", summary=summary, reason=reason, note=note,
                                      changes={field_name: {"old": old_txt, "new": new_txt}})

    def audit_log_attachment(self, attachments, added=True, note=None):
        """Catat penambahan/penghapusan lampiran."""
        self.ensure_one()
        if not self._audit_is_enabled():
            return False
        names = []
        try:
            if hasattr(attachments, "mapped"):
                names = attachments.mapped("name")
            elif isinstance(attachments, list):
                names = [getattr(a, "name", str(a)) for a in attachments]
        except Exception:
            pass
        summary = _("Attachments %s: %s") % ("added" if added else "removed", ", ".join(names[:5]))
        return self._audit_create_log(category="attach", summary=summary, note=note,
                                      changes={"attachments": {"old": "" if added else ", ".join(names),
                                                               "new": ", ".join(names) if added else ""}})

    def audit_log_comment(self, text):
        """Catat komentar singkat ke audit (bukan chatter)."""
        self.ensure_one()
        if not self._audit_is_enabled():
            return False
        return self._audit_create_log(category="comment", summary=_("Comment"), note=text, changes={})

