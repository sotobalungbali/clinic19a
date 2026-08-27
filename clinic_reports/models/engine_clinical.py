from odoo import fields, models, _


class ClinicReportEngineClinical(models.AbstractModel):
    """Clinical reporting over Encounter, Procedure, Triage, Safety, Post-Care and Feedback."""

    _name = "clinic.report.engine.clinical"
    _description = "Clinic Reports Clinical Engine"

    # Encounter metrics are observational snapshots and never change clinical encounter state.
    def _generate_clinical_encounter(self):
        self.ensure_one()
        Encounter = self.env["clinic.encounter"]
        encounters = Encounter.sudo().search(
            self._report_domain(
                "clinic.encounter",
                "date_start",
                self.date_from,
                self.date_to,
            ),
            order="date_start, id",
        )

        done = encounters.filtered(lambda rec: rec.state == "done")
        cancelled = encounters.filtered(lambda rec: rec.state == "cancelled")
        durations = []
        for encounter in encounters:
            if encounter.date_start and encounter.date_end:
                delta = fields.Datetime.to_datetime(
                    encounter.date_end
                ) - fields.Datetime.to_datetime(encounter.date_start)
                durations.append(delta.total_seconds() / 60.0)

        avg_duration = sum(durations) / len(durations) if durations else 0.0
        procedure_count = sum(len(rec.procedure_line_ids) for rec in encounters)
        total_value = sum(encounters.mapped("amount_total"))

        self._add_metric("ENCOUNTER_COUNT", _("Encounters"), len(encounters), "count", 10)
        self._add_metric("ENCOUNTER_DONE", _("Completed Encounters"), len(done), "count", 20)
        self._add_metric("ENCOUNTER_CANCELLED", _("Cancelled Encounters"), len(cancelled), "count", 30)
        self._add_metric(
            "ENCOUNTER_COMPLETION_RATE",
            _("Encounter Completion Rate"),
            self._percentage(len(done), len(encounters)),
            "percentage",
            40,
        )
        self._add_metric("ENCOUNTER_AVG_DURATION", _("Average Encounter Duration"), avg_duration, "duration", 50)
        self._add_metric("ENCOUNTER_PROCEDURE_LINES", _("Planned Procedure Lines"), procedure_count, "count", 60)
        self._add_metric("ENCOUNTER_CLINICAL_VALUE", _("Encounter Clinical Value"), total_value, "amount", 70)
        self._state_breakdown_metrics(encounters, "ENCOUNTER_STATE", 100)

        for encounter in encounters:
            duration = 0.0
            if encounter.date_start and encounter.date_end:
                duration = (
                    fields.Datetime.to_datetime(encounter.date_end)
                    - fields.Datetime.to_datetime(encounter.date_start)
                ).total_seconds() / 60.0

            self._add_detail(
                encounter,
                _("Clinical Encounter"),
                event_date=encounter.date_start,
                reference=encounter.name,
                state_label=encounter.state,
                partner=encounter.partner_id,
                patient=encounter.patient_id,
                doctor=encounter.doctor_id,
                treatment=encounter.treatment_id,
                amount=encounter.amount_total,
                quantity=len(encounter.procedure_line_ids),
                duration_minutes=duration,
            )

    def _generate_clinical_procedure(self):
        self.ensure_one()
        Session = self.env["clinic.procedure.session"]
        sessions = Session.sudo().search(
            self._report_domain(
                "clinic.procedure.session",
                "date_start",
                self.date_from,
                self.date_to,
            ),
            order="date_start, id",
        )

        done = sessions.filtered(lambda rec: rec.state == "done")
        cancelled = sessions.filtered(lambda rec: rec.state == "cancelled")
        duration_values = [
            value for value in sessions.mapped("actual_duration")
            if value is not False
        ]
        avg_duration = (
            sum(duration_values) / len(duration_values)
            if duration_values
            else 0.0
        )
        total_value = sum(sessions.mapped("price_total"))
        ae_count = sum(len(session.ae_ids) for session in sessions)

        self._add_metric("PROCEDURE_SESSION_COUNT", _("Procedure Sessions"), len(sessions), "count", 10)
        self._add_metric("PROCEDURE_DONE", _("Completed Procedures"), len(done), "count", 20)
        self._add_metric("PROCEDURE_CANCELLED", _("Cancelled Procedures"), len(cancelled), "count", 30)
        self._add_metric(
            "PROCEDURE_COMPLETION_RATE",
            _("Procedure Completion Rate"),
            self._percentage(len(done), len(sessions)),
            "percentage",
            40,
        )
        self._add_metric("PROCEDURE_AVG_DURATION", _("Average Actual Duration"), avg_duration, "duration", 50)
        self._add_metric("PROCEDURE_VALUE", _("Procedure Value"), total_value, "amount", 60)
        self._add_metric("PROCEDURE_AE_COUNT", _("Linked Adverse Events"), ae_count, "count", 70)
        self._state_breakdown_metrics(sessions, "PROCEDURE_STATE", 100)

        for session in sessions:
            encounter = session.encounter_id
            self._add_detail(
                session,
                _("Procedure Session"),
                event_date=session.date_start,
                reference=session.name,
                state_label=session.state,
                partner=encounter.partner_id if encounter else False,
                patient=encounter.patient_id if encounter else False,
                doctor=session.performer_doctor_id or (
                    encounter.doctor_id if encounter else False
                ),
                treatment=session.treatment_id,
                room=session.room_id,
                amount=session.price_total,
                quantity=session.quantity,
                duration_minutes=session.actual_duration,
                note=session.procedure_id.display_name if session.procedure_id else "",
            )

    # Triage reporting reuses upstream SLA and abnormal-vital signals; it does not diagnose patients.
    def _generate_clinical_triage(self):
        self.ensure_one()
        Triage = self.env["clinic.triage.session"]
        sessions = Triage.sudo().search(
            self._report_domain(
                "clinic.triage.session",
                "arrival_datetime",
                self.date_from,
                self.date_to,
            ),
            order="arrival_datetime, id",
        )

        completed = sessions.filtered(lambda rec: rec.state == "completed")
        referred = sessions.filtered(lambda rec: rec.state == "referred")
        sla = sessions.filtered("sla_breached")
        abnormal = sessions.filtered("has_abnormal_vitals")

        waits = [
            value for value in sessions.mapped("wait_time_minutes")
            if value is not False
        ]
        durations = [
            value for value in sessions.mapped("triage_duration_minutes")
            if value is not False
        ]
        avg_wait = sum(waits) / len(waits) if waits else 0.0
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        self._add_metric("TRIAGE_COUNT", _("Triage Sessions"), len(sessions), "count", 10)
        self._add_metric("TRIAGE_COMPLETED", _("Completed Triage"), len(completed), "count", 20)
        self._add_metric("TRIAGE_REFERRED", _("Referred"), len(referred), "count", 30)
        self._add_metric("TRIAGE_SLA_BREACH", _("SLA Breaches"), len(sla), "count", 40)
        self._add_metric(
            "TRIAGE_SLA_BREACH_RATE",
            _("Triage SLA Breach Rate"),
            self._percentage(len(sla), len(sessions)),
            "percentage",
            50,
        )
        self._add_metric("TRIAGE_ABNORMAL_VITALS", _("Sessions with Abnormal Vitals"), len(abnormal), "count", 60)
        self._add_metric("TRIAGE_AVG_WAIT", _("Average Triage Wait"), avg_wait, "duration", 70)
        self._add_metric("TRIAGE_AVG_DURATION", _("Average Triage Duration"), avg_duration, "duration", 80)
        self._state_breakdown_metrics(sessions, "TRIAGE_STATE", 100)

        for session in sessions:
            self._add_detail(
                session,
                _("Triage Session"),
                event_date=session.arrival_datetime,
                reference=session.name,
                state_label=session.state,
                patient=session.patient_id,
                doctor=session.assigned_doctor_id,
                duration_minutes=session.wait_time_minutes,
                rating=1.0 if session.has_abnormal_vitals else 0.0,
                note=_("Triage %.2f min | SLA %s")
                % (
                    session.triage_duration_minutes or 0.0,
                    _("Breached") if session.sla_breached else _("OK"),
                ),
            )

    # Adverse Event reporting is read-only and does not create future Incident/Quality records.
    def _generate_clinical_adverse(self):
        self.ensure_one()
        Event = self.env["clinic.adverse.event"]
        events = Event.sudo().search(
            self._report_domain(
                "clinic.adverse.event",
                "date_occurred",
                self.date_from,
                self.date_to,
            ),
            order="date_occurred, id",
        )

        serious = events.filtered("is_serious")
        closed = events.filtered(lambda rec: rec.state == "closed")
        severe = events.filtered(
            lambda rec: rec.severity in ("severe", "death")
        )
        sentinel = events.filtered(
            lambda rec: rec.classification == "sentinel"
        )

        self._add_metric("AE_COUNT", _("Adverse Events"), len(events), "count", 10)
        self._add_metric("AE_SERIOUS", _("Serious Events"), len(serious), "count", 20)
        self._add_metric("AE_SEVERE_DEATH", _("Severe / Death"), len(severe), "count", 30)
        self._add_metric("AE_SENTINEL", _("Sentinel Events"), len(sentinel), "count", 40)
        self._add_metric("AE_CLOSED", _("Closed Events"), len(closed), "count", 50)
        self._add_metric(
            "AE_CLOSURE_RATE",
            _("Adverse Event Closure Rate"),
            self._percentage(len(closed), len(events)),
            "percentage",
            60,
        )
        self._state_breakdown_metrics(events, "AE_STATE", 100)

        for event in events:
            self._add_detail(
                event,
                _("Adverse Event"),
                event_date=event.date_occurred,
                reference=event.name,
                state_label=event.state,
                partner=event.partner_id,
                patient=event.patient_id,
                doctor=event.doctor_id,
                treatment=event.treatment_id,
                room=event.room_id,
                rating=1.0 if event.is_serious else 0.0,
                note=_("%s | Severity %s")
                % (
                    (event.classification or "").replace("_", " ").title(),
                    (event.severity or "").replace("_", " ").title(),
                ),
            )

    # Post-Care outcomes use the frozen addon-26 counters and workflow as the authoritative operational source.
    def _generate_clinical_postcare(self):
        self.ensure_one()
        Plan = self.env["clinic.postcare.plan"]
        plans = Plan.sudo().search(
            self._report_domain(
                "clinic.postcare.plan",
                "start_datetime",
                self.date_from,
                self.date_to,
            ),
            order="start_datetime, id",
        )

        completed = plans.filtered(
            lambda rec: rec.state in ("completed", "closed")
        )
        escalated = plans.filtered(lambda rec: rec.state == "escalated")
        task_count = sum(plans.mapped("task_count"))
        overdue_tasks = sum(plans.mapped("overdue_task_count"))
        open_escalations = sum(plans.mapped("open_escalation_count"))
        red_flags = sum(plans.mapped("red_flag_count"))
        avg_progress = (
            sum(plans.mapped("progress")) / len(plans)
            if plans
            else 0.0
        )

        self._add_metric("POSTCARE_PLAN_COUNT", _("Post-Care Plans"), len(plans), "count", 10)
        self._add_metric("POSTCARE_COMPLETED", _("Completed / Closed"), len(completed), "count", 20)
        self._add_metric("POSTCARE_ESCALATED", _("Currently Escalated"), len(escalated), "count", 30)
        self._add_metric(
            "POSTCARE_COMPLETION_RATE",
            _("Post-Care Completion Rate"),
            self._percentage(len(completed), len(plans)),
            "percentage",
            40,
        )
        self._add_metric("POSTCARE_TASKS", _("Follow-up Tasks"), task_count, "count", 50)
        self._add_metric("POSTCARE_OVERDUE_TASKS", _("Overdue Tasks"), overdue_tasks, "count", 60)
        self._add_metric("POSTCARE_OPEN_ESCALATIONS", _("Open Escalations"), open_escalations, "count", 70)
        self._add_metric("POSTCARE_RED_FLAGS", _("Patient Check-in Red Flags"), red_flags, "count", 80)
        self._add_metric("POSTCARE_AVG_PROGRESS", _("Average Progress"), avg_progress, "percentage", 90)
        self._state_breakdown_metrics(plans, "POSTCARE_STATE", 100)

        for plan in plans:
            self._add_detail(
                plan,
                _("Post-Care Plan"),
                event_date=plan.start_datetime,
                reference=plan.name,
                state_label=plan.state,
                partner=plan.partner_id,
                patient=plan.patient_id,
                doctor=plan.doctor_id,
                staff=plan.responsible_staff_id,
                treatment=plan.treatment_id,
                quantity=plan.task_count,
                rating=plan.progress,
                note=_("Overdue %s | Escalations %s | Red Flags %s")
                % (
                    plan.overdue_task_count,
                    plan.open_escalation_count,
                    plan.red_flag_count,
                ),
            )

    # NPS follows the standard formula: percentage Promoters minus percentage Detractors.
    def _generate_clinical_feedback(self):
        self.ensure_one()
        Feedback = self.env["clinic.feedback"]
        responses = Feedback.sudo().search(
            self._report_domain(
                "clinic.feedback",
                "submitted_at",
                self.date_from,
                self.date_to,
                extra=[("state", "!=", "draft")],
            ),
            order="submitted_at, id",
        )

        ratings = [
            value for value in responses.mapped("overall_rating")
            if value > 0
        ]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

        nps_values = [
            value for value in responses.mapped("nps_score")
            if value >= 0
        ]
        promoters = len([value for value in nps_values if value >= 9])
        detractors = len([value for value in nps_values if value <= 6])
        nps = (
            ((promoters - detractors) / len(nps_values)) * 100.0
            if nps_values
            else 0.0
        )

        complaints = responses.filtered(
            lambda rec: rec.feedback_type == "complaint"
        )
        escalation_needed = responses.filtered("needs_escalation")
        escalated = responses.filtered(lambda rec: rec.state == "escalated")

        self._add_metric("FEEDBACK_COUNT", _("Patient Feedback Responses"), len(responses), "count", 10)
        self._add_metric("FEEDBACK_AVG_RATING", _("Average Overall Rating"), avg_rating, "score", 20)
        self._add_metric("FEEDBACK_NPS", _("Net Promoter Score"), nps, "score", 30)
        self._add_metric("FEEDBACK_PROMOTERS", _("Promoters"), promoters, "count", 40)
        self._add_metric("FEEDBACK_DETRACTORS", _("Detractors"), detractors, "count", 50)
        self._add_metric("FEEDBACK_COMPLAINTS", _("Complaints"), len(complaints), "count", 60)
        self._add_metric("FEEDBACK_NEEDS_ESCALATION", _("Responses Meeting Escalation Threshold"), len(escalation_needed), "count", 70)
        self._add_metric("FEEDBACK_CURRENTLY_ESCALATED", _("Currently Escalated"), len(escalated), "count", 80)
        self._add_metric(
            "FEEDBACK_ESCALATION_RATE",
            _("Escalation Threshold Rate"),
            self._percentage(len(escalation_needed), len(responses)),
            "percentage",
            90,
        )
        self._state_breakdown_metrics(responses, "FEEDBACK_STATE", 100)

        for feedback in responses:
            self._add_detail(
                feedback,
                _("Patient Feedback"),
                event_date=feedback.submitted_at,
                reference=feedback.name,
                state_label=feedback.state,
                partner=feedback.patient_id,
                patient=feedback.patient_card_id,
                doctor=feedback.doctor_id,
                staff=feedback.staff_id,
                treatment=feedback.treatment_id,
                rating=feedback.overall_rating,
                note=_("NPS %s | %s")
                % (
                    feedback.nps_score
                    if feedback.nps_score >= 0
                    else "-",
                    (feedback.feedback_type or "").title(),
                ),
            )
