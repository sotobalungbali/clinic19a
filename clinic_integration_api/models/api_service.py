# -*- coding: utf-8 -*-
import hashlib
import json
import uuid
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError


class ClinicApiService(models.AbstractModel):
    """Fixed, code-owned resource adapter for ClinicOne.

    Security design:
    - bearer token authenticates an Odoo service user;
    - normal business searches/writes use that user's environment (no sudo);
    - API client policy narrows companies, branches, scopes, and rate;
    - caller cannot choose arbitrary model, method, fields, or domains.
    """

    _name = "clinic.api.service"
    _description = "Clinic Integration API Service"

    # Fixed resource contract. These are deliberately code-owned and are never
    # populated from request parameters or database configuration.
    RESOURCE_SPECS = {
        "patients": {
            "model": "clinic.patient", "scope": "clinical.read",
            "fields": ("id", "patient_code", "name", "gender", "birth_date", "phone", "mobile", "email", "is_vip", "stage_id", "company_id", "active"),
            "search": ("patient_code", "name", "phone", "mobile", "email"),
            "company_path": "company_id", "branch_path": "partner_id.branch_id",
        },
        "doctors": {
            "model": "clinic.doctor", "scope": "clinical.read",
            "fields": ("id", "name", "work_email", "work_phone", "mobile", "license_no", "availability_state", "telemedicine_enabled", "company_id", "active"),
            "search": ("name", "work_email", "license_no"),
            "company_path": "company_id", "branch_path": "partner_id.branch_id",
        },
        "treatments": {
            "model": "clinic.treatment", "scope": "operations.read",
            "fields": ("id", "code", "name", "category_id", "base_price", "minimum_price", "duration_minutes", "allow_online_booking", "company_id", "active"),
            "search": ("code", "name"), "company_path": "company_id", "branch_shared": True,
        },
        "bookings": {
            "model": "booking.booking", "scope": "operations.read",
            "fields": ("id", "name", "patient_id", "doctor_id", "treatment_id", "start_datetime", "end_datetime", "duration_minutes", "state", "deposit_status", "amount_total", "company_id", "active"),
            "search": ("name",),
            "company_path": "company_id", "branch_path": "patient_id.branch_id",
        },
        "queue_visits": {
            "model": "clinic.queue.visit", "scope": "operations.read",
            "fields": ("id", "name", "patient_id", "doctor_id", "treatment_id", "queue_id", "room_id", "checkin_time", "start_time", "end_time", "state", "waiting_duration_min", "service_duration_min", "company_id"),
            "search": ("name",), "company_path": "company_id", "branch_path": "patient_id.branch_id",
        },
        "rooms": {
            "model": "clinic.room", "scope": "operations.read",
            "fields": ("id", "code", "name", "room_type_id", "status", "capacity", "is_bookable", "location_id", "company_id", "active"),
            "search": ("code", "name"), "company_path": "company_id",
        },
        "triage_sessions": {
            "model": "clinic.triage.session", "scope": "clinical.read",
            "fields": ("id", "name", "patient_id", "assigned_doctor_id", "assigned_nurse_id", "arrival_datetime", "start_datetime", "end_datetime", "triage_level_id", "priority_score", "state", "sla_breached", "company_id", "active"),
            "search": ("name",), "company_path": "company_id", "branch_path": "patient_id.partner_id.branch_id",
        },
        "encounters": {
            "model": "clinic.encounter", "scope": "clinical.read",
            "fields": ("id", "name", "patient_id", "doctor_id", "treatment_id", "appointment_id", "date_planned_start", "date_start", "date_end", "state", "priority", "consent_ok", "company_id", "active"),
            "search": ("name",), "company_path": "company_id", "branch_path": "patient_id.partner_id.branch_id",
        },
        "emar_orders": {
            "model": "clinic.emar.order", "scope": "clinical.read",
            "fields": ("id", "name", "patient_id", "doctor_id", "booking_id", "encounter_id", "date_start", "date_end", "state", "safety_state", "billing_state", "company_id", "active"),
            "search": ("name",), "company_path": "company_id", "branch_path": "patient_id.partner_id.branch_id",
        },
        "billing_invoices": {
            "model": "clinic.billing.invoice", "scope": "finance.read",
            "fields": ("id", "name", "clinic_patient_id", "patient_id", "booking_id", "encounter_id", "invoice_date", "invoice_date_due", "state", "payment_state", "amount_total", "amount_residual", "currency_id", "company_id"),
            "search": ("name",), "company_path": "company_id", "branch_path": "patient_id.branch_id",
        },
        "ar_invoices": {
            "model": "clinic.ar.invoice", "scope": "finance.read",
            "fields": ("id", "name", "patient_id", "partner_id", "billing_id", "invoice_date", "due_date", "state", "payment_state", "amount_total", "amount_residual", "currency_id", "company_id"),
            "search": ("name",), "company_path": "company_id", "branch_path": "patient_id.partner_id.branch_id",
        },
        "ap_documents": {
            "model": "clinic.ap", "scope": "finance.read",
            "fields": ("id", "name", "vendor_id", "reference", "invoice_date", "invoice_date_due", "purchase_id", "state", "payment_state", "amount_total", "amount_residual", "currency_id", "company_id"),
            "search": ("name", "reference"), "company_path": "company_id",
        },
        "wallets": {
            "model": "clinic.wallet", "scope": "finance.read",
            "fields": ("id", "name", "patient_id", "partner_id", "state", "balance", "reserved_amount", "total_topup", "total_redeem", "total_refund", "currency_id", "expiry_date", "company_id", "active"),
            "search": ("name",), "company_path": "company_id", "branch_path": "partner_id.branch_id",
        },
        "memberships": {
            "model": "membership.contract", "scope": "finance.read",
            "fields": ("id", "name", "patient_id", "partner_id", "plan_id", "start_date", "end_date", "state", "payment_state", "point_balance", "remaining_days", "company_id"),
            "search": ("name",), "company_path": "company_id", "branch_path": "partner_id.branch_id",
        },
        "packages": {
            "model": "clinic.package", "scope": "operations.read",
            "fields": ("id", "code", "name", "state", "list_price", "duration_days", "valid_from", "valid_to", "company_id", "active"),
            "search": ("code", "name"), "company_path": "company_id", "branch_shared": True,
        },
        "insurance_authorizations": {
            "model": "clinic.insurance.authorization", "scope": "finance.read",
            "fields": ("id", "name", "patient_id", "insurer_partner_id", "authorization_code", "request_date", "service_date", "state", "requested_amount", "approved_amount", "currently_valid", "company_id"),
            "search": ("name", "authorization_code", "patient_id.name"), "company_path": "company_id", "branch_path": "patient_id.partner_id.branch_id",
        },
        "postcare_plans": {
            "model": "clinic.postcare.plan", "scope": "engagement.read",
            "fields": ("id", "name", "patient_id", "doctor_id", "protocol_id", "start_date", "expected_end_date", "state", "priority", "progress", "next_due_at", "branch_id", "company_id"),
            "search": ("name",), "company_path": "company_id", "branch_path": "branch_id",
        },
        "feedback": {
            "model": "clinic.feedback", "scope": "engagement.read",
            "fields": ("id", "name", "patient_id", "doctor_id", "feedback_type", "overall_rating", "nps_score", "state", "submitted_at", "needs_escalation", "branch_id", "company_id"),
            "search": ("name",), "company_path": "company_id", "branch_path": "branch_id",
        },
        "report_runs": {
            "model": "clinic.report.run", "scope": "governance.read",
            "fields": ("id", "name", "definition_id", "family", "report_key", "date_from", "date_to", "state", "generated_at", "finalized_at", "metric_count", "detail_count", "branch_id", "company_id"),
            "search": ("name",), "company_path": "company_id", "branch_path": "branch_id",
        },
        "incidents": {
            "model": "clinic.incident", "scope": "governance.read",
            "fields": ("id", "name", "title", "patient_id", "doctor_id", "incident_type", "classification", "severity", "harm_level", "occurred_at", "state", "is_serious", "regulatory_required", "branch_id", "company_id", "active"),
            "search": ("name", "title", "patient_id.name"), "company_path": "company_id", "branch_path": "branch_id",
        },
        "quality_sops": {
            "model": "clinic.quality.sop", "scope": "governance.read",
            "fields": ("id", "code", "name", "state", "current_version_id", "owner_user_id", "approver_user_id", "next_review_date", "branch_ids", "company_id", "active"),
            "search": ("code", "name"), "company_path": "company_id", "branch_path": "branch_ids",
        },
        "quality_checks": {
            "model": "clinic.quality.check", "scope": "governance.read",
            "fields": ("id", "name", "title", "template_id", "planned_date", "state", "overall_result", "compliance_score", "critical_fail_count", "incident_count", "branch_id", "company_id", "active"),
            "search": ("name", "title"), "company_path": "company_id", "branch_path": "branch_id",
        },
        "telemedicine_sessions": {
            "model": "clinic.telemedicine.session", "scope": "clinical.read",
            "fields": ("id", "name", "patient_id", "doctor_id", "booking_id", "encounter_id", "scheduled_start", "scheduled_end", "state", "provider_mode", "provider_reference", "meeting_ready", "patient_can_join", "branch_id", "company_id"),
            "search": ("name", "patient_id.name", "doctor_id.name"), "company_path": "company_id", "branch_path": "branch_id",
        },
        "branches": {
            "model": "clinic.branch", "scope": "operations.read",
            "fields": ("id", "code", "name", "city", "is_franchise", "tz", "parent_id", "company_id", "active"),
            "search": ("code", "name", "city"), "company_path": "company_id", "branch_identity": True,
        },
    }

    MUTATION_SPECS = {
        "patients": {
            "scope": "patient.write",
            "create_fields": ("name", "gender", "birth_date", "phone", "mobile", "email", "street", "street2", "city", "zip", "state_id", "country_id", "is_vip"),
            "write_fields": ("name", "gender", "birth_date", "phone", "mobile", "email", "street", "street2", "city", "zip", "state_id", "country_id", "is_vip", "active"),
        },
        "bookings": {
            "scope": "booking.write",
            "create_fields": ("patient_id", "doctor_id", "treatment_id", "start_datetime", "end_datetime", "notes"),
            "write_fields": ("doctor_id", "treatment_id", "start_datetime", "end_datetime", "notes"),
            "actions": {
                "confirm": ("booking.action", "action_confirm"),
                "start": ("booking.action", "action_start"),
                "done": ("booking.action", "action_done"),
                "cancel": ("booking.action", "action_cancel"),
                "no_show": ("booking.action", "action_mark_no_show"),
            },
        },
    }

    @api.model
    def new_request_id(self):
        return str(uuid.uuid4())

    @api.model
    def get_active_client(self):
        # One bearer user maps to exactly one policy record. The database
        # constraint on clinic.api.client.user_id prevents ambiguous tokens.
        client = self.env["clinic.api.client"].sudo().search([
            ("user_id", "=", self.env.user.id),
            ("state", "=", "active"),
            ("active", "=", True),
        ], limit=1)
        if not client:
            raise AccessError(_("No active Clinic Integration API client is configured for this bearer user."))
        allowed_companies = client.allowed_company_ids or client.company_id
        if self.env.company not in allowed_companies:
            raise AccessError(_("The active Odoo company is outside this API client's company scope."))
        return client

    @api.model
    def require_scope(self, client, scope_code):
        if scope_code not in client.scope_ids.mapped("code"):
            raise AccessError(_("API scope '%s' is required.") % scope_code)
        return True

    @api.model
    def enforce_rate_limit(self, client):
        one_minute_ago = fields.Datetime.now() - timedelta(minutes=1)
        count = self.env["clinic.api.request.log"].sudo().search_count([
            ("client_id", "=", client.id), ("requested_at", ">=", one_minute_ago)
        ])
        if count >= client.requests_per_minute:
            raise UserError(_("API rate limit exceeded. Retry after the current one-minute window."))
        client.sudo().write({"last_used_at": fields.Datetime.now()})
        return True

    @api.model
    def _spec(self, resource):
        spec = self.RESOURCE_SPECS.get(resource)
        if not spec:
            raise MissingError(_("Unknown ClinicOne API resource."))
        return spec

    @api.model
    def _scope_domain(self, client, spec):
        companies = client.allowed_company_ids or client.company_id
        domain = []
        company_path = spec.get("company_path")
        if company_path:
            domain.append((company_path, "in", companies.ids))
        branches = client.branch_ids
        if branches:
            if spec.get("branch_identity"):
                domain.append(("id", "in", branches.ids))
            elif spec.get("branch_path"):
                domain.append((spec["branch_path"], "in", branches.ids))
            elif not spec.get("branch_shared"):
                raise AccessError(_("This resource has no authoritative branch path and cannot be used by a branch-restricted API client."))
        return domain

    @api.model
    def _search_domain(self, client, spec, query=None):
        domain = self._scope_domain(client, spec)
        query = (query or "").strip()
        if query:
            fields_to_search = spec.get("search") or ()
            if fields_to_search:
                domain += ["|"] * (len(fields_to_search) - 1)
                domain += [(field_name, "ilike", query[:100]) for field_name in fields_to_search]
        return domain

    @api.model
    def _serialize_value(self, field, value):
        if field.type == "many2one":
            return value.id if value else False
        if field.type in ("one2many", "many2many"):
            return value.ids
        if field.type == "date":
            return fields.Date.to_string(value) if value else False
        if field.type == "datetime":
            return fields.Datetime.to_string(value) if value else False
        if field.type == "binary":
            return False
        return value

    @api.model
    def _serialize(self, resource, record, spec):
        values = {}
        for field_name in spec["fields"]:
            if field_name == "id":
                values["id"] = record.id
                continue
            field = record._fields.get(field_name)
            if not field:
                continue
            values[field_name] = self._serialize_value(field, record[field_name])
        if resource == "bookings":
            partner = record.patient_id
            patient = self.env["clinic.patient"].search([("partner_id", "=", partner.id)], limit=1) if partner else self.env["clinic.patient"]
            values["patient_id"] = patient.id or False
            values["patient_partner_id"] = partner.id or False
        return values

    @api.model
    def list_resource(self, client, resource, query=None, limit=50, offset=0):
        """Return one bounded page of a fixed resource inside client company/branch scope."""
        spec = self._spec(resource); self.require_scope(client, spec["scope"])
        limit = min(max(int(limit or 50), 1), 100); offset = max(int(offset or 0), 0)
        Model = self.env[spec["model"]]
        domain = self._search_domain(client, spec, query)
        records = Model.search(domain, limit=limit, offset=offset, order="id desc")
        return {"resource": resource, "count": len(records), "limit": limit, "offset": offset, "items": [self._serialize(resource, rec, spec) for rec in records]}

    @api.model
    def get_resource(self, client, resource, record_id):
        spec = self._spec(resource); self.require_scope(client, spec["scope"])
        Model = self.env[spec["model"]]
        record = Model.search([("id", "=", int(record_id))] + self._scope_domain(client, spec), limit=1)
        if not record:
            raise MissingError(_("Requested ClinicOne resource record was not found in the allowed scope."))
        return {"resource": resource, "item": self._serialize(resource, record, spec)}

    @api.model
    def _force_company_values(self, client, model, values):
        # Mutations follow the current allowed Odoo company, not merely the
        # client's primary company. This preserves normal multi-company rules.
        allowed_companies = client.allowed_company_ids or client.company_id
        if self.env.company not in allowed_companies:
            raise AccessError(_("The active Odoo company is outside this API client's company scope."))
        if "company_id" in model._fields:
            values["company_id"] = self.env.company.id
        return values

    @api.model
    def _normalize_patient_values(self, values):
        return values

    @api.model
    def _normalize_booking_values(self, values):
        values = dict(values)
        if "patient_id" in values:
            patient = self.env["clinic.patient"].browse(int(values["patient_id"])).exists()
            if not patient:
                raise ValidationError(_("Invalid canonical Clinic Patient ID."))
            patient.check_access("read")
            if not patient.partner_id:
                raise ValidationError(_("Clinic Patient has no linked contact for Booking."))
            values["patient_id"] = patient.partner_id.id
        return values

    @api.model
    def _validated_mutation_values(self, resource, payload, mode):
        mutation = self.MUTATION_SPECS.get(resource)
        if not mutation:
            raise AccessError(_("This ClinicOne resource is read-only through the public Integration API."))
        allowed = set(mutation[f"{mode}_fields"])
        unknown = set(payload) - allowed
        if unknown:
            raise ValidationError(_("Unsupported fields for %(resource)s: %(fields)s", resource=resource, fields=", ".join(sorted(unknown))))
        values = {key: payload[key] for key in allowed if key in payload}
        if resource == "bookings":
            values = self._normalize_booking_values(values)
        return values, mutation

    @api.model
    def create_resource(self, client, resource, payload):
        """Create only resources/fields explicitly allowed by MUTATION_SPECS."""
        values, mutation = self._validated_mutation_values(resource, payload, "create")
        self.require_scope(client, mutation["scope"])
        spec = self._spec(resource); Model = self.env[spec["model"]]
        self._force_company_values(client, Model, values)
        record = Model.create(values)
        # The just-created record must also be visible inside the client's narrowed scope.
        visible = Model.search([("id", "=", record.id)] + self._scope_domain(client, spec), limit=1)
        if not visible:
            raise AccessError(_("Created record falls outside the configured API branch/company scope."))
        self.emit_event("api.resource.changed", visible, {"operation": "create", "resource": resource, "record_id": visible.id}, spec=spec)
        return {"resource": resource, "item": self._serialize(resource, visible, spec)}

    @api.model
    def update_resource(self, client, resource, record_id, payload):
        values, mutation = self._validated_mutation_values(resource, payload, "write")
        self.require_scope(client, mutation["scope"])
        spec = self._spec(resource); Model = self.env[spec["model"]]
        record = Model.search([("id", "=", int(record_id))] + self._scope_domain(client, spec), limit=1)
        if not record: raise MissingError(_("Requested ClinicOne resource record was not found in the allowed scope."))
        record.write(values)
        self.emit_event("api.resource.changed", record, {"operation": "update", "resource": resource, "record_id": record.id}, spec=spec)
        return {"resource": resource, "item": self._serialize(resource, record, spec)}

    @api.model
    def run_action(self, client, resource, record_id, action_code):
        mutation = self.MUTATION_SPECS.get(resource) or {}
        action = (mutation.get("actions") or {}).get(action_code)
        if not action:
            raise AccessError(_("This API action is not permitted for the selected resource."))
        scope_code, method_name = action; self.require_scope(client, scope_code)
        spec = self._spec(resource); Model = self.env[spec["model"]]
        record = Model.search([("id", "=", int(record_id))] + self._scope_domain(client, spec), limit=1)
        if not record: raise MissingError(_("Requested ClinicOne resource record was not found in the allowed scope."))
        method = getattr(record, method_name, None)
        if not method:
            raise UserError(_("Configured ClinicOne workflow action is unavailable."))
        method()
        self.emit_event("api.resource.changed", record, {"operation": "action", "resource": resource, "action": action_code, "record_id": record.id}, spec=spec)
        return {"resource": resource, "action": action_code, "item": self._serialize(resource, record, spec)}

    @api.model
    def request_hash(self, method, route, payload):
        canonical = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(f"{method.upper()}|{route}|{canonical}".encode()).hexdigest()

    @api.model
    def begin_idempotency(self, client, key, request_hash, resource):
        return self.env["clinic.api.idempotency"].begin(client, key, request_hash, resource)

    @api.model
    def _event_branch(self, record, spec):
        """Resolve one authoritative branch from the code-owned resource spec."""
        if spec.get("branch_identity") and record._name == "clinic.branch":
            return record
        path = spec.get("branch_path")
        if not path:
            return self.env["clinic.branch"]
        value = record
        for part in path.split("."):
            if not value or part not in value._fields:
                return self.env["clinic.branch"]
            value = value[part]
        if getattr(value, "_name", None) == "clinic.branch" and len(value) == 1:
            return value
        return self.env["clinic.branch"]

    @api.model
    def emit_event(self, code, record, payload, spec=None):
        EventType = self.env["clinic.api.event.type"].sudo()
        event_type = EventType.search([("code", "=", code), ("active", "=", True)], limit=1)
        if not event_type:
            return self.env["clinic.api.event"]
        company = record.company_id if "company_id" in record._fields and record.company_id else self.env.company
        branch = self._event_branch(record, spec or {})
        event = self.env["clinic.api.event"].sudo().create({
            "company_id": company.id,
            "branch_id": branch.id or False,
            "event_type_id": event_type.id,
            "model_name": record._name,
            "res_id": record.id,
            "payload_json": json.dumps(payload, default=str, separators=(",", ":")),
        })
        event._create_deliveries()
        event.state = "queued"
        return event

    @api.model
    def find_provider(self, provider_type, company, branch=None, code=None):
        Provider = self.env["clinic.api.provider"].sudo()
        base_domain = [("provider_type", "=", provider_type), ("company_id", "=", company.id), ("state", "=", "active"), ("active", "=", True)]
        if code: base_domain.append(("code", "=", code))
        if branch:
            exact = Provider.search(base_domain + [("branch_id", "=", branch.id)], order="sequence, id", limit=1)
            if exact: return exact
        # Never fall back to another branch's provider.
        return Provider.search(base_domain + [("branch_id", "=", False)], order="sequence, id", limit=1)
