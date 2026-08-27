# -*- coding: utf-8 -*-
"""Historical Treatment Session behavior preserved from the 19.0.1.0.0 draft.

The model/field declaration lives in ``treatment_session.py``. Keeping legacy
behavior in this focused file makes the addon materially easier to review and
manually maintain without changing any public method names.
"""

import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicTreatmentSessionLegacyBehavior(models.Model):
    _inherit = "clinic.treatment.session"

    @api.depends("name", "patient_id", "treatment_id", "start_datetime")
    def _compute_display_name(self):
        """
        Build a human-friendly display name:
          <SessionNumber> - <PatientName> - <TreatmentName> - <Date>
        """
        for session in self:
            parts = []
            if session.name:
                parts.append(session.name)
            if session.patient_id:
                parts.append(session.patient_id.name or "")
            if session.treatment_id:
                parts.append(session.treatment_id.name or "")
            if session.start_datetime:
                parts.append(
                    fields.Datetime.to_string(session.start_datetime)
                )
            session.display_name = " - ".join(p for p in parts if p)

    @api.depends("start_datetime", "end_datetime")
    def _compute_duration_actual(self):
        """
        Compute actual duration in minutes from start & end datetime.
        """
        for session in self:
            if session.start_datetime and session.end_datetime:
                start = fields.Datetime.to_datetime(session.start_datetime)
                end = fields.Datetime.to_datetime(session.end_datetime)
                delta = end - start
                minutes = delta.total_seconds() / 60.0
                session.duration_actual = max(minutes, 0.0)
            else:
                session.duration_actual = 0.0

    @api.depends("duration_planned", "duration_actual")
    def _compute_is_overtime(self):
        """
        Flag session as overtime when actual duration exceeds planned duration.
        If there is no planned duration, we don't consider it overtime.
        """
        for session in self:
            if session.duration_planned and session.duration_actual:
                session.is_overtime = session.duration_actual > session.duration_planned
            else:
                session.is_overtime = False

    @api.depends("state")
    def _compute_can_edit(self):
        """
        In ClinicOne, umumnya sesi yang sudah DONE / NO_SHOW / CANCELLED
        tidak boleh diubah lagi oleh user biasa (hanya manager yang boleh).
        Field ini bisa dipakai di view untuk readonly kondisi tertentu.
        """
        non_editable_states = ("done", "no_show", "cancelled")
        for session in self:
            session.can_edit = session.state not in non_editable_states

    # @api.depends("billing_invoice_id.state", "move_id.payment_state")
    # def _compute_is_fully_invoiced(self):
    #     """
    #     Sederhana: dianggap fully invoiced jika:
    #       - billing_invoice_id ada dan bukan 'draft'/'cancel'
    #     ATAU
    #       - move_id ada dan payment_state in ('paid', 'in_payment')
    #     Addon lain bisa override/extend logic ini sesuai kebutuhan.
    #     """
    #     for session in self:
    #         fully = False
    #         if session.billing_invoice_id and getattr(
    #             session.billing_invoice_id, "state", False
    #         ) not in ("draft", "cancel"):
    #             fully = True
    #         if session.move_id and getattr(session.move_id, "payment_state", False) in (
    #             "paid",
    #             "in_payment",
    #         ):
    #             fully = True
    #         session.is_fully_invoiced = fully

    @api.depends()
    def _compute_attachment_count(self):
        """
        Hitung jumlah lampiran (ir.attachment) yang terkait ke session ini.
        Digunakan untuk smart button di form view.
        """
        Attachment = self.env["ir.attachment"].sudo()
        for session in self:
            session.attachment_count = Attachment.search_count(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "=", session.id),
                ]
            )

    @api.depends()
    def _compute_activity_count(self):
        """
        Hitung jumlah aktivitas chatter (mail.activity).
        """
        Activity = self.env["mail.activity"].sudo()
        for session in self:
            session.activity_count = Activity.search_count(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "=", session.id),
                ]
            )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("start_datetime", "end_datetime")
    def _check_dates(self):
        for session in self:
            if (
                session.start_datetime
                and session.end_datetime
                and session.end_datetime < session.start_datetime
            ):
                raise ValidationError(
                    _(
                        "End time (%s) cannot be earlier than start time (%s) for session %s."
                    )
                    % (
                        session.end_datetime,
                        session.start_datetime,
                        session.display_name or session.name,
                    )
                )

    @api.constrains("company_id", "patient_id", "clinic_doctor_id", "booking_id", "room_id")
    def _check_company_consistency(self):
        """
        Pastikan company dari entity utama konsisten dengan company session.
        Tidak dipaksa untuk semua field (boleh kosong),
        tapi jika terisi, sebaiknya sama.
        """
        for session in self:
            company = session.company_id
            # Patient company
            if (
                session.patient_id
                and session.patient_id.company_id
                and session.patient_id.company_id != company
            ):
                raise ValidationError(
                    _(
                        "Patient company (%s) must match session company (%s) "
                        "for session %s."
                    )
                    % (
                        session.patient_id.company_id.display_name,
                        company.display_name,
                        session.display_name or session.name,
                    )
                )

            # Doctor company (jika di-set)
            if (
                session.clinic_doctor_id
                and session.clinic_doctor_id.company_id
                and session.clinic_doctor_id.company_id != company
            ):
                raise ValidationError(
                    _(
                        "Doctor company (%s) must match session company (%s) "
                        "for session %s."
                    )
                    % (
                        session.clinic_doctor_id.company_id.display_name,
                        company.display_name,
                        session.display_name or session.name,
                    )
                )

            # Booking company
            if (
                session.booking_id
                and session.booking_id.company_id
                and session.booking_id.company_id != company
            ):
                raise ValidationError(
                    _(
                        "Booking company (%s) must match session company (%s) "
                        "for session %s."
                    )
                    % (
                        session.booking_id.company_id.display_name,
                        company.display_name,
                        session.display_name or session.name,
                    )
                )

    # -------------------------------------------------------------------------
    # ORM OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Preserve legacy defaults using the Odoo 19 multi-create contract."""
        prepared = []

        for values in vals_list:
            vals = dict(values)

            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id

            if not vals.get("name") or vals.get("name") in ("New", "/"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "clinic_treatment_session.session"
                    )
                    or "New"
                )

            prepared.append(vals)

        sessions = super().create(prepared)
        sessions._subscribe_related_partners()
        return sessions

    def write(self, vals):
        """
        - Jika mencoba mengubah field inti pada state yang tidak boleh edit,
          raise error (kecuali user dengan hak khusus override).
        - Pastikan perubahan company_id dan relasi tetap konsisten.
        """
        restricted_states = ("done", "no_show", "cancelled")
        if any(
            field_name
            in {
                "patient_id",
                "clinic_doctor_id",
                "treatment_id",
                "booking_id",
                "room_id",
                "start_datetime",
                "end_datetime",
            }
            for field_name in vals.keys()
        ):
            for session in self:
                if session.state in restricted_states and not self.env.user.has_group(
                    "base.group_system"
                ):
                    raise UserError(
                        _(
                            "You cannot modify core session information when the status "
                            "is Done, No-show, or Cancelled.\nSession: %s"
                        )
                        % (session.display_name or session.name,)
                    )

        result = super().write(vals)

        # If relations changed, refresh followers
        if any(
            key in vals for key in ("patient_id", "clinic_doctor_id", "company_id")
        ):
            self._subscribe_related_partners()

        return result

    def unlink(self):
        """
        Sesi yang bukan DRAFT/CONFIRMED tidak boleh dihapus secara normal.
        Manager bisa override lewat hak akses atau aksi khusus.
        """
        for session in self:
            if session.state not in ("draft", "cancelled"):
                raise UserError(
                    _(
                        "You can only delete sessions in Draft or Cancelled state.\n"
                        "Session: %s"
                    )
                    % (session.display_name or session.name,)
                )
        return super().unlink()

    # -------------------------------------------------------------------------
    # FOLLOWERS
    # -------------------------------------------------------------------------
    def _subscribe_related_partners(self):
        """
        Subscribe patient & doctor user as followers in the chatter.
        Bisa di-extend oleh addon lain (mis. membership, wallet, dsb).
        """
        for session in self:
            partners = self.env["res.partner"]
            if session.patient_id:
                partners |= session.patient_id
            if session.clinic_doctor_id and session.clinic_doctor_id.user_id:
                partners |= session.clinic_doctor_id.user_id.partner_id
            if partners:
                session.message_subscribe(partner_ids=partners.ids)

    # -------------------------------------------------------------------------
    # STATE MACHINE ACTIONS
    # -------------------------------------------------------------------------
    def action_confirm(self):
        """
        Move session from DRAFT → CONFIRMED.
        Biasanya dipanggil dari booking atau frontdesk ketika jadwal fix.
        """
        for session in self:
            if session.state not in ("draft", "cancelled"):
                continue
            session.state = "confirmed"
            session._sync_stage_with_state()
        return True

    def action_start(self):
        """
        Move session to IN PROGRESS.
        Jika start_datetime belum terisi, isi dengan now sebagai actual start.
        """
        now = fields.Datetime.now()
        for session in self:
            if session.state not in ("draft", "confirmed"):
                continue
            # Jika start kosong, set ke sekarang (actual)
            if not session.start_datetime:
                session.start_datetime = now
            session.state = "in_progress"
            session._sync_stage_with_state()
        return True

    def action_done(self):
        """
        Close session as DONE:
          - Pastikan minimal ada Start (kalau tidak, set sekarang).
          - Kalau End belum ada, set ke sekarang.
          - Panggil hook post-done dan billing preparation.
        """
        now = fields.Datetime.now()
        for session in self:
            if session.state not in ("in_progress", "confirmed", "draft"):
                continue

            if not session.start_datetime:
                session.start_datetime = now
            if not session.end_datetime:
                session.end_datetime = now

            session.state = "done"
            session._sync_stage_with_state()

            # Hook yang bisa di-override oleh addon lain
            session._post_done_hook()
        return True

    def action_no_show(self):
        """
        Tandai sebagai NO-SHOW. Biasanya dipanggil dari frontdesk jika pasien tidak hadir.
        """
        for session in self:
            if session.state not in ("draft", "confirmed"):
                continue
            session.state = "no_show"
            session._sync_stage_with_state()
        return True

    def action_cancel(self):
        """
        Batalkan sesi. Resource (ruang/dokter) dianggap tidak terpakai.
        """
        for session in self:
            if session.state in ("done", "no_show"):
                raise UserError(
                    _(
                        "You cannot cancel a session that is already Done or No-show.\n"
                        "Session: %s"
                    )
                    % (session.display_name or session.name,)
                )
            session.state = "cancelled"
            session._sync_stage_with_state()
        return True

    def _sync_stage_with_state(self):
        """
        Helper untuk mensinkronkan stage_id dengan state.
        Data stage disediakan di session_stages.xml.
        Modul lain boleh override mapping ini.
        """
        Stage = self.env["clinic.treatment.session.stage"].sudo()
        for session in self:
            if not Stage:
                continue
            # Simple mapping by code or name
            target_stage = Stage.search(
                [("technical_state", "=", session.state)], limit=1
            )
            if not target_stage:
                # fallback by name if technical_state not available
                target_stage = Stage.search(
                    [("name", "ilike", session.state.replace("_", " "))], limit=1
                )
            if target_stage:
                session.stage_id = target_stage.id

    # -------------------------------------------------------------------------
    # HOOKS: POST DONE & BILLING INTEGRATION
    # -------------------------------------------------------------------------
    def _post_done_hook(self):
        """
        Hook yang dipanggil setiap sesi di-set ke DONE.

        Default:
          - Tidak otomatis buat invoice.
          - Hanya menyiapkan struktur data billing (action_prepare_billing).

        Addon lain dapat:
          - Override method ini untuk:
              * Buat/merge clinic.billing.invoice
              * Buat account.move (out_invoice)
              * Integrasi ke wallet / membership / package, dsb.
        """
        self.ensure_one()
        # Prepare billing payload for other modules.
        self.action_prepare_billing()
        return True

    def action_prepare_billing(self):
        """
        Build struktur data billing untuk addon lain.

        Return dictionary dengan payload standar:
          {
            'session_id': self.id,
            'company_id': self.company_id.id,
            'patient_id': self.patient_id.id,
            'treatment_id': self.treatment_id.id,
            'lines': [
                {
                    'product_id': ...,
                    'qty': ...,
                    'price_unit': ...,
                    'name': ...,
                },
                ...
            ],
          }

        Addon seperti clinic_billing bisa override method ini untuk
        langsung membuat record clinic.billing.invoice atau lainnya.
        """
        self.ensure_one()
        lines_payload = []

        # Jika line_ids ada, pakai product di line sebagai dasar billing
        if self.line_ids:
            for line in self.line_ids:
                if not line.product_id:
                    continue
                lines_payload.append(
                    {
                        "session_line_id": line.id,
                        "product_id": line.product_id.id,
                        "qty": line.quantity or 1.0,
                        "price_unit": getattr(line, "price_unit", 0.0),
                        "name": line.name or line.product_id.display_name,
                    }
                )
        elif self.treatment_id and getattr(self.treatment_id, "product_id", False):
            # fallback sederhana: langsung ambil product dari treatment_id
            lines_payload.append(
                {
                    "session_line_id": False,
                    "product_id": self.treatment_id.product_id.id,
                    "qty": 1.0,
                    "price_unit": getattr(self.treatment_id.product_id, "list_price", 0.0),
                    "name": self.treatment_id.product_id.display_name,
                }
            )

        payload = {
            "session_id": self.id,
            "company_id": self.company_id.id,
            "patient_id": self.patient_id.id if self.patient_id else False,
            "treatment_id": self.treatment_id.id if self.treatment_id else False,
            "lines": lines_payload,
        }
        # Default implementation hanya mengembalikan payload.
        # Addon lain dapat memanggil super dan memproses payload ini.
        return payload

    def action_create_invoice(self):
        """
        Generic helper untuk membuat invoice standar (account.move)
        berdasarkan payload billing.

        Default:
          - Membuat account.move (out_invoice) jika modul accounting aktif.
          - Tidak handle pajak/discount kompleks (diserahkan ke addon khusus).
          - Jika move berhasil dibuat, simpan ke move_id.

        Boleh di-override / di-extend oleh addon lain.
        """
        self.ensure_one()

        if not self.patient_id:
            raise UserError(_("Cannot create invoice without a patient."))

        # Cek apakah model account.move tersedia di registry
        if not self.env.registry.get("account.move"):
            raise UserError(
                _(
                    "The Accounting module is not available in this database. "
                    "Install it first to create invoices."
                )
            )

        payload = self.action_prepare_billing()
        if not payload.get("lines"):
            raise UserError(
                _(
                    "Cannot create invoice because there are no billable lines "
                    "for this session."
                )
            )

        Move = self.env["account.move"].with_company(self.company_id)
        line_vals = []
        for line in payload["lines"]:
            product = self.env["product.product"].browse(line["product_id"])
            line_vals.append(
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "name": line.get("name") or product.display_name,
                        "quantity": line.get("qty") or 1.0,
                        "price_unit": line.get("price_unit") or 0.0,
                        "account_id": (
                            product.property_account_income_id.id
                            or product.categ_id.property_account_income_categ_id.id
                        ),
                    },
                )
            )

        move_vals = {
            "move_type": "out_invoice",
            "partner_id": self.patient_id.id,
            "invoice_origin": self.name,
            "invoice_user_id": self.env.user.id,
            "company_id": self.company_id.id,
            "invoice_line_ids": line_vals,
        }

        move = Move.create(move_vals)
        self.move_id = move.id
        return move

    def action_link_payment(self):
        """
        Hook sederhana untuk sinkronisasi status sesi berdasarkan status pembayaran.
        Addon lain bisa override untuk logic yang lebih kompleks.
        """
        self.ensure_one()
        if self.move_id and self.move_id.payment_state in ("paid", "in_payment"):
            self.is_fully_invoiced = True
        return True

    # -------------------------------------------------------------------------
    # CRON & REMINDER
    # -------------------------------------------------------------------------
    @api.model
    def cron_send_session_reminders(self):
        """
        Dipanggil oleh ir.cron (session_cron.xml).

        Logika:
          - Ambil parameter jam offset reminder dari ir.config_parameter:
              clinic_treatment_session.reminder_offset_hours (default: 2 jam)
          - Cari sesi dengan state DRAFT/CONFIRMED yang akan mulai dalam window
            [now + offset, now + offset + 1 jam].
          - Kirim email reminder dengan mail template:
              clinic_treatment_session.mail_template_treatment_session_reminder
            (boleh tidak ada; kalau tidak ada, cron akan diam saja).
        """
        Param = self.env["ir.config_parameter"].sudo()
        offset_hours = int(
            Param.get_param(
                "clinic_treatment_session.reminder_offset_hours",
                default="2",
            )
        )

        now = fields.Datetime.now()
        window_start = now + datetime.timedelta(hours=offset_hours)
        window_end = window_start + datetime.timedelta(hours=1)

        domain = [
            ("state", "in", ("draft", "confirmed")),
            ("start_datetime", ">=", window_start),
            ("start_datetime", "<", window_end),
        ]
        sessions = self.search(domain)

        template = self.env.ref(
            "clinic_treatment_session.mail_template_treatment_session_reminder",
            raise_if_not_found=False,
        )
        if not template:
            return True  # silently ignore if template not installed

        for session in sessions:
            session._send_session_reminder(template)

        return True

    def _send_session_reminder(self, template):
        """
        Kirim reminder email untuk sesi tertentu.
        Logic bisa di-override oleh addon lain jika perlu channel lain (WA/SMS).
        """
        self.ensure_one()
        if not self.patient_id or not self.patient_email:
            return False
        template.send_mail(self.id, force_send=True)
        return True

    # -------------------------------------------------------------------------
    # WIZARD / BUTTON HELPERS
    # -------------------------------------------------------------------------
    def action_view_attachments(self):
        """
        Smart button untuk melihat semua lampiran session.
        """
        self.ensure_one()
        return {
            "name": _("Attachments"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "kanban,tree,form",
            "domain": [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
            ],
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }

    def action_view_activities(self):
        """
        Smart button untuk melihat aktivitas (mail.activity) terkait sesi.
        """
        self.ensure_one()
        return {
            "name": _("Activities"),
            "type": "ir.actions.act_window",
            "res_model": "mail.activity",
            "view_mode": "tree,form",
            "domain": [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
            ],
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }

    def action_view_patient(self):
        """
        Smart button / relate action untuk membuka data pasien.
        """
        self.ensure_one()
        if not self.patient_id:
            raise UserError(_("There is no patient linked to this session."))
        action = self.env.ref("base.action_partner_form").read()[0]
        action["res_id"] = self.patient_id.id
        action["views"] = [(False, "form")]
        return action

    # def action_view_billing(self):
    #     """
    #     Smart button untuk membuka clinic.billing.invoice jika ada.
    #     """
    #     self.ensure_one()
    #     if not self.billing_invoice_id:
    #         raise UserError(_("No clinic billing is linked to this session yet."))
    #     return {
    #         "name": _("Clinic Billing"),
    #         "type": "ir.actions.act_window",
    #         "res_model": "clinic.billing.invoice",
    #         "view_mode": "form,tree",
    #         "res_id": self.billing_invoice_id.id,
    #     }

    def action_view_invoice(self):
        """
        Smart button untuk membuka account.move (invoice) jika ada.
        """
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No customer invoice is linked to this session yet."))
        return {
            "name": _("Customer Invoice"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form,tree",
            "res_id": self.move_id.id,
        }

    # -------------------------------------------------------------------------
    # API FOR WIZARD (RESCHEDULE, BULK UPDATE, EXPORT, etc.)
    # -------------------------------------------------------------------------
    def reschedule(self, new_start, new_end=None, room_id=False, doctor_id=False):
        """
        Helper method yang bisa dipanggil dari wizard Reschedule Session.

        Parameter:
          - new_start: datetime baru untuk mulai
          - new_end: datetime baru untuk selesai (optional)
          - room_id: ID room baru (optional)
          - doctor_id: ID doctor baru (optional)
        """
        self.ensure_one()
        if self.state in ("done", "no_show", "cancelled"):
            raise UserError(
                _(
                    "You cannot reschedule a session that is Done, No-show, or Cancelled.\n"
                    "Session: %s"
                )
                % (self.display_name or self.name,)
            )

        vals = {
            "start_datetime": new_start,
        }
        if new_end:
            vals["end_datetime"] = new_end
        if room_id:
            vals["room_id"] = room_id
        if doctor_id:
            vals["clinic_doctor_id"] = doctor_id

        self.write(vals)
        return True
