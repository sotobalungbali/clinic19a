import base64

from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.utils import secure_filename

from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.clinic_portal.controllers.portal import ClinicPatientPortal


class ClinicTelemedicinePortal(ClinicPatientPortal):
    """Exact-patient portal routes for Teleconsultation and Secure Messaging."""

    def _telemedicine_profile(self, feature):
        # Never create/activate Portal profiles from clinical communication
        # routes. Addon 31 remains the access-profile owner.
        profile = self._clinic_profile(allow_create=False)
        if not profile or profile.state != "active":
            raise Forbidden()

        if feature == "session" and not profile.allow_telemedicine_access:
            raise Forbidden()
        if feature == "messaging" and not profile.allow_secure_messaging:
            raise Forbidden()
        return profile

    def _telemedicine_base_values(self, profile, page_name):
        values = self._clinic_base_values(profile, page_name)
        values.update({
            "clinic_telemedicine_profile": profile,
            "clinic_telemedicine_enabled": bool(
                profile.state == "active"
                and profile.allow_telemedicine_access
            ),
            "clinic_secure_messaging_enabled": bool(
                profile.state == "active"
                and profile.allow_secure_messaging
            ),
        })
        return values

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        profile = self._clinic_profile(allow_create=False)

        values["clinic_telemedicine_profile"] = profile
        values["clinic_telemedicine_enabled"] = bool(
            profile
            and profile.state == "active"
            and profile.allow_telemedicine_access
        )
        values["clinic_secure_messaging_enabled"] = bool(
            profile
            and profile.state == "active"
            and profile.allow_secure_messaging
        )

        summary = {
            "clinic_telemedicine_session_count": 0,
            "clinic_secure_thread_count": 0,
        }
        if profile:
            summary = profile._portal_telemedicine_counts()

        for counter_name, value in summary.items():
            if counter_name in counters:
                values[counter_name] = value
        return values

    def _secure_thread_values(self, profile, thread, error=None):
        # Opening a thread is itself evidence that clinic-originated messages
        # have been read by the patient.
        unread = thread.message_ids.filtered(
            lambda message:
            message.author_kind != "patient"
            and not message.patient_read_at
        )
        if unread:
            unread.with_context(
                telemedicine_portal_patient_read=True,
                telemedicine_portal_partner_id=profile.partner_id.id,
                telemedicine_portal_user_id=request.env.user.id,
            )._mark_patient_read()

        values = self._telemedicine_base_values(
            profile,
            "clinic_secure_thread",
        )
        values.update({
            "thread": thread,
            "secure_messages": thread.message_ids.sorted(
                key=lambda message: (message.sent_at, message.id)
            ),
            "secure_attachments": thread.attachment_ids,
            "error_message": error,
            "max_file_mb": thread.company_id.clinic_telemedicine_max_file_mb,
            "max_message_chars": (
                thread.company_id.clinic_telemedicine_max_message_chars
            ),
        })
        return values

    @http.route(
        [
            "/my/clinic/telemedicine",
            "/my/clinic/telemedicine/page/<int:page>",
        ],
        type="http",
        auth="user",
        website=True,
        readonly=False,
    )
    def clinic_telemedicine_sessions(self, page=1, **kwargs):
        profile = self._telemedicine_profile("session")
        Session = request.env["clinic.telemedicine.session"].sudo()
        domain = profile._portal_telemedicine_session_domain()

        count = Session.search_count(domain)
        pager = portal_pager(
            url="/my/clinic/telemedicine",
            total=count,
            page=page,
            step=self._clinic_page_size(),
        )
        sessions = Session.search(
            domain,
            order="scheduled_start desc, id desc",
            limit=self._clinic_page_size(),
            offset=pager["offset"],
        )

        values = self._telemedicine_base_values(
            profile,
            "clinic_telemedicine_sessions",
        )
        values.update({
            "telemedicine_sessions": sessions,
            "pager": pager,
        })
        return request.render(
            "clinic_telemedicine_secure_messaging.portal_telemedicine_sessions",
            values,
        )

    @http.route(
        ["/my/clinic/telemedicine/<int:session_id>"],
        type="http",
        auth="user",
        website=True,
        readonly=False,
    )
    def clinic_telemedicine_session(self, session_id, **kwargs):
        profile = self._telemedicine_profile("session")
        session = request.env[
            "clinic.telemedicine.session"
        ].sudo().search(
            [("id", "=", session_id)]
            + profile._portal_telemedicine_session_domain(),
            limit=1,
        )
        if not session:
            raise NotFound()

        values = self._telemedicine_base_values(
            profile,
            "clinic_telemedicine_session",
        )
        values.update({
            "telemedicine_session": session,
            "secure_thread": session.thread_ids[:1],
        })
        return request.render(
            "clinic_telemedicine_secure_messaging.portal_telemedicine_session",
            values,
        )

    @http.route(
        ["/my/clinic/telemedicine/<int:session_id>/join"],
        type="http",
        auth="user",
        website=True,
        readonly=False,
    )
    def clinic_telemedicine_join(self, session_id, **kwargs):
        profile = self._telemedicine_profile("session")
        session = request.env[
            "clinic.telemedicine.session"
        ].sudo().search(
            [("id", "=", session_id)]
            + profile._portal_telemedicine_session_domain(),
            limit=1,
        )
        if not session:
            raise NotFound()
        if not session._patient_join_allowed():
            raise Forbidden()

        session.with_context(
            telemedicine_patient_join=True,
            telemedicine_portal_partner_id=profile.partner_id.id,
            telemedicine_portal_user_id=request.env.user.id,
        )._record_patient_join()

        # Odoo 19 Request.redirect explicitly supports external URLs through
        # `local=False`; the Meeting URL was already validated as HTTPS.
        return request.redirect(
            session.meeting_url,
            code=303,
            local=False,
        )

    @http.route(
        [
            "/my/clinic/messages",
            "/my/clinic/messages/page/<int:page>",
        ],
        type="http",
        auth="user",
        website=True,
        readonly=False,
    )
    def clinic_secure_threads(self, page=1, **kwargs):
        profile = self._telemedicine_profile("messaging")
        Thread = request.env["clinic.telemedicine.thread"].sudo()
        domain = profile._portal_secure_thread_domain()

        count = Thread.search_count(domain)
        pager = portal_pager(
            url="/my/clinic/messages",
            total=count,
            page=page,
            step=self._clinic_page_size(),
        )
        threads = Thread.search(
            domain,
            order="attention_required desc, last_message_at desc, id desc",
            limit=self._clinic_page_size(),
            offset=pager["offset"],
        )

        values = self._telemedicine_base_values(
            profile,
            "clinic_secure_threads",
        )
        values.update({
            "secure_threads": threads,
            "pager": pager,
            "allow_new_thread": (
                profile.company_id
                .clinic_telemedicine_allow_patient_new_threads
            ),
        })
        return request.render(
            "clinic_telemedicine_secure_messaging.portal_secure_threads",
            values,
        )

    @http.route(
        ["/my/clinic/messages/new"],
        type="http",
        auth="user",
        website=True,
        readonly=False,
        methods=["GET", "POST"],
    )
    def clinic_secure_thread_new(self, **kwargs):
        profile = self._telemedicine_profile("messaging")
        company = profile.company_id
        if not company.clinic_telemedicine_allow_patient_new_threads:
            raise Forbidden()

        Doctor = request.env["clinic.doctor"].sudo()
        doctors = Doctor.search([
            ("company_id", "=", company.id),
            ("active", "=", True),
            ("telemedicine_enabled", "=", True),
        ], order="name, id")

        error = None
        if request.httprequest.method == "POST":
            try:
                doctor_id = int(kwargs.get("doctor_id") or 0)
            except (TypeError, ValueError):
                doctor_id = 0

            subject = (kwargs.get("subject") or "").strip()[:200]
            body = (kwargs.get("body") or "").strip()
            doctor = Doctor.search([
                ("id", "=", doctor_id),
                ("company_id", "=", company.id),
                ("active", "=", True),
                ("telemedicine_enabled", "=", True),
            ], limit=1)

            try:
                if not doctor:
                    raise ValidationError(_("Select an available Telemedicine Doctor."))
                if not subject:
                    raise ValidationError(_("Conversation Subject is required."))

                Thread = request.env["clinic.telemedicine.thread"].sudo()
                open_count = Thread.search_count([
                    ("company_id", "=", company.id),
                    ("partner_id", "=", profile.partner_id.id),
                    ("session_id", "=", False),
                    ("state", "=", "open"),
                ])
                if open_count >= company.clinic_telemedicine_max_open_threads:
                    raise UserError(
                        _(
                            "You already have the maximum number of open "
                            "patient-initiated conversations. Please use an "
                            "existing conversation or contact the clinic."
                        )
                    )

                with request.env.cr.savepoint():
                    thread = Thread.with_context(
                        telemedicine_portal_patient_create=True,
                        telemedicine_portal_partner_id=profile.partner_id.id,
                    ).create({
                        "company_id": company.id,
                        "branch_id": profile.partner_id.branch_id.id
                        if (
                            company.policy_branch_scope_telemedicine
                            and profile.partner_id.branch_id
                        )
                        else False,
                        "patient_id": profile.patient_id.id,
                        "doctor_id": doctor.id,
                        "subject": subject,
                    })
                    if body:
                        request.env[
                            "clinic.telemedicine.message"
                        ].sudo().with_context(
                            telemedicine_portal_patient_message=True,
                            telemedicine_portal_partner_id=profile.partner_id.id,
                            telemedicine_portal_user_id=request.env.user.id,
                        ).create({
                            "thread_id": thread.id,
                            "body": body,
                        })

                return request.redirect(thread.portal_url)

            except (AccessError, UserError, ValidationError) as exc:
                error = str(exc)

        values = self._telemedicine_base_values(
            profile,
            "clinic_secure_thread_new",
        )
        values.update({
            "telemedicine_doctors": doctors,
            "error_message": error,
            "submitted_subject": kwargs.get("subject") or "",
            "submitted_body": kwargs.get("body") or "",
        })
        return request.render(
            "clinic_telemedicine_secure_messaging.portal_secure_thread_new",
            values,
        )

    @http.route(
        ["/my/clinic/messages/<int:thread_id>"],
        type="http",
        auth="user",
        website=True,
        readonly=False,
    )
    def clinic_secure_thread(self, thread_id, **kwargs):
        profile = self._telemedicine_profile("messaging")
        thread = request.env[
            "clinic.telemedicine.thread"
        ].sudo().search(
            [("id", "=", thread_id)]
            + profile._portal_secure_thread_domain(),
            limit=1,
        )
        if not thread:
            raise NotFound()

        return request.render(
            "clinic_telemedicine_secure_messaging.portal_secure_thread",
            self._secure_thread_values(profile, thread),
        )

    @http.route(
        ["/my/clinic/messages/<int:thread_id>/send"],
        type="http",
        auth="user",
        website=True,
        readonly=False,
        methods=["POST"],
    )
    def clinic_secure_thread_send(self, thread_id, **kwargs):
        profile = self._telemedicine_profile("messaging")
        thread = request.env[
            "clinic.telemedicine.thread"
        ].sudo().search(
            [("id", "=", thread_id)]
            + profile._portal_secure_thread_domain(),
            limit=1,
        )
        if not thread:
            raise NotFound()
        if thread.state != "open" or not thread.patient_can_reply:
            raise Forbidden()

        body = (kwargs.get("body") or "").strip()
        upload = request.httprequest.files.get("attachment")

        if not body and not upload:
            return request.render(
                "clinic_telemedicine_secure_messaging.portal_secure_thread",
                self._secure_thread_values(
                    profile,
                    thread,
                    _("Write a message or choose a file before sending."),
                ),
            )

        try:
            with request.env.cr.savepoint():
                filename = False
                raw_file = False
                mimetype = False

                if upload:
                    filename = secure_filename(upload.filename or "")
                    max_bytes = (
                        thread.company_id.clinic_telemedicine_max_file_mb
                        or 10
                    ) * 1024 * 1024
                    raw_file = upload.stream.read(max_bytes + 1)
                    if len(raw_file) > max_bytes:
                        raise ValidationError(
                            _(
                                "File exceeds the company limit of %(limit)s MB."
                            ) % {
                                "limit": (
                                    thread.company_id
                                    .clinic_telemedicine_max_file_mb
                                    or 10
                                )
                            }
                        )
                    mimetype = upload.mimetype or False

                message_body = body
                if not message_body and filename:
                    message_body = _(
                        "Shared a file: %(filename)s"
                    ) % {"filename": filename}

                message = request.env[
                    "clinic.telemedicine.message"
                ].sudo().with_context(
                    telemedicine_portal_patient_message=True,
                    telemedicine_portal_partner_id=profile.partner_id.id,
                    telemedicine_portal_user_id=request.env.user.id,
                ).create({
                    "thread_id": thread.id,
                    "body": message_body,
                })

                if raw_file is not False:
                    if not thread.patient_can_upload:
                        raise AccessError(
                            _("Patient file upload is disabled for this conversation.")
                        )
                    request.env[
                        "clinic.telemedicine.attachment"
                    ].sudo().with_context(
                        telemedicine_portal_patient_upload=True,
                        telemedicine_portal_partner_id=profile.partner_id.id,
                        telemedicine_portal_user_id=request.env.user.id,
                    ).create({
                        "thread_id": thread.id,
                        "message_id": message.id,
                        "name": filename,
                        "datas": base64.b64encode(raw_file),
                        "mimetype": mimetype,
                    })

            return request.redirect(thread.portal_url)

        except (AccessError, UserError, ValidationError) as exc:
            return request.render(
                "clinic_telemedicine_secure_messaging.portal_secure_thread",
                self._secure_thread_values(profile, thread, str(exc)),
            )

    @http.route(
        ["/clinic/telemedicine/attachment/<int:attachment_id>/download"],
        type="http",
        auth="user",
        website=False,
        readonly=False,
    )
    def clinic_telemedicine_attachment_download(
        self,
        attachment_id,
        **kwargs,
    ):
        attachment = request.env[
            "clinic.telemedicine.attachment"
        ].sudo().browse(attachment_id).exists()
        if not attachment:
            raise NotFound()

        internal_allowed = (
            request.env.user.has_group(
                "clinic_telemedicine_secure_messaging.group_telemedicine_user"
            )
            and attachment.company_id in request.env.user.company_ids
        )

        patient_allowed = False
        if not internal_allowed:
            try:
                profile = self._telemedicine_profile("messaging")
                patient_allowed = bool(
                    attachment.company_id == profile.company_id
                    and attachment.partner_id == profile.partner_id
                    and attachment.thread_id.state != "archived"
                )
            except Forbidden:
                patient_allowed = False

        if not internal_allowed and not patient_allowed:
            raise NotFound()

        raw = attachment._decode_payload(attachment.datas)
        filename = secure_filename(attachment.name or "shared-file")
        headers = [
            ("Content-Type", attachment.mimetype or "application/octet-stream"),
            (
                "Content-Disposition",
                f'attachment; filename="{filename}"',
            ),
            ("Content-Length", str(len(raw))),
            ("Cache-Control", "private, no-store, max-age=0"),
            ("Pragma", "no-cache"),
            ("X-Content-Type-Options", "nosniff"),
        ]
        return request.make_response(raw, headers=headers)

