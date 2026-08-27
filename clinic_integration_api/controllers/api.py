# -*- coding: utf-8 -*-
import logging
import time

from odoo import http, _
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)
MAX_BODY_BYTES = 1024 * 1024


class ClinicIntegrationApiController(http.Controller):
    """Bearer-only REST surface backed by fixed resource adapters."""

    def _require_explicit_bearer(self):
        # Odoo bearer auth can fall back to an authenticated browser session when
        # the header is missing. ClinicOne deliberately rejects that fallback.
        header = request.httprequest.headers.get("Authorization", "")
        if not header.lower().startswith("bearer ") or not header[7:].strip():
            raise AccessError(_("A Bearer Authorization header is required."))

    def _body(self):
        length = request.httprequest.content_length or 0
        if length > MAX_BODY_BYTES:
            raise ValidationError(_("JSON request body exceeds the 1 MiB API limit."))
        payload = request.httprequest.get_json(silent=True)
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise ValidationError(_("JSON request body must be an object."))
        return payload

    def _error_response(self, request_id, exc):
        if isinstance(exc, AccessError):
            status, code = 403, "access_denied"
        elif isinstance(exc, MissingError):
            status, code = 404, "not_found"
        elif isinstance(exc, (ValidationError, UserError, ValueError, TypeError)):
            status, code = 400, "invalid_request"
        else:
            status, code = 500, "internal_error"
        message = str(exc) if status < 500 else _("Internal server error.")
        return status, {"ok": False, "request_id": request_id, "error": {"code": code, "message": message}}

    def _execute(self, resource, callback):
        started = time.monotonic()
        service = request.env["clinic.api.service"]
        request_id = service.new_request_id()
        client = None
        status = 500
        error_code = error_message = False
        try:
            self._require_explicit_bearer()
            client = service.get_active_client()
            service.enforce_rate_limit(client)
            status, payload = callback(service, client, request_id)
        except Exception as exc:
            status, payload = self._error_response(request_id, exc)
            error_code = payload["error"]["code"]
            error_message = payload["error"]["message"]
            if status >= 500:
                _logger.exception("Clinic Integration API request failed: %s", request_id)
        finally:
            if client:
                duration = int((time.monotonic() - started) * 1000)
                request.env["clinic.api.request.log"].log_request({
                    "client_id": client.id,
                    "company_id": request.env.company.id,
                    "user_id": request.env.user.id,
                    "request_id": request_id,
                    "method": request.httprequest.method,
                    "route": request.httprequest.path,
                    "resource": resource,
                    "status_code": status,
                    "duration_ms": duration,
                    "remote_addr": request.httprequest.remote_addr,
                    "error_code": error_code,
                    "error_message": error_message,
                })
        return request.make_json_response(payload, status=status)

    def _mutation(self, service, client, request_id, resource, payload, callback, success_status=200):
        key = request.httprequest.headers.get("Idempotency-Key", "").strip()
        req_hash = service.request_hash(request.httprequest.method, request.httprequest.path, payload)
        idem, replay = service.begin_idempotency(client, key, req_hash, resource)
        if replay is not None:
            return idem.response_code or success_status, replay
        try:
            with request.env.cr.savepoint():
                data = callback()
            response = {"ok": True, "request_id": request_id, "data": data}
            idem.mark_done(success_status, response)
            return success_status, response
        except Exception as exc:
            idem.mark_failed(exc)
            raise

    @http.route("/api/clinic/v1/health", type="http", auth="bearer", methods=["GET"], csrf=False, save_session=False)
    def health(self, **kwargs):
        return self._execute("health", lambda service, client, rid: (200, {
            "ok": True, "request_id": rid,
            "data": {"service": "clinic_integration_api", "version": "19.0.1.0.0", "client": client.code},
        }))

    @http.route("/api/clinic/v1/resources/<string:resource>", type="http", auth="bearer", methods=["GET"], csrf=False, save_session=False)
    def list_resource(self, resource, **kwargs):
        def run(service, client, rid):
            args = request.httprequest.args
            data = service.list_resource(client, resource, query=args.get("q"), limit=args.get("limit", 50), offset=args.get("offset", 0))
            return 200, {"ok": True, "request_id": rid, "data": data}
        return self._execute(resource, run)

    @http.route("/api/clinic/v1/resources/<string:resource>/<int:record_id>", type="http", auth="bearer", methods=["GET"], csrf=False, save_session=False)
    def get_resource(self, resource, record_id, **kwargs):
        return self._execute(resource, lambda service, client, rid: (200, {"ok": True, "request_id": rid, "data": service.get_resource(client, resource, record_id)}))

    @http.route("/api/clinic/v1/resources/<string:resource>", type="http", auth="bearer", methods=["POST"], csrf=False, save_session=False)
    def create_resource(self, resource, **kwargs):
        def run(service, client, rid):
            payload = self._body()
            return self._mutation(service, client, rid, resource, payload, lambda: service.create_resource(client, resource, payload), success_status=201)
        return self._execute(resource, run)

    @http.route("/api/clinic/v1/resources/<string:resource>/<int:record_id>", type="http", auth="bearer", methods=["PATCH"], csrf=False, save_session=False)
    def update_resource(self, resource, record_id, **kwargs):
        def run(service, client, rid):
            payload = self._body()
            return self._mutation(service, client, rid, resource, payload, lambda: service.update_resource(client, resource, record_id, payload))
        return self._execute(resource, run)

    @http.route("/api/clinic/v1/resources/<string:resource>/<int:record_id>/actions/<string:action_code>", type="http", auth="bearer", methods=["POST"], csrf=False, save_session=False)
    def run_action(self, resource, record_id, action_code, **kwargs):
        def run(service, client, rid):
            payload = self._body()
            if payload:
                raise ValidationError(_("Workflow action endpoints do not accept arbitrary payload fields."))
            return self._mutation(service, client, rid, resource, {}, lambda: service.run_action(client, resource, record_id, action_code))
        return self._execute(resource, run)
