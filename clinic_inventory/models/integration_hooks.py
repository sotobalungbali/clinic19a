# -*- coding: utf-8 -*-
# File: models/integration_hooks.py
# Module: clinic_inventory
#
# Purpose
#   Provide a lightweight, safe integration layer for ClinicOne addons:
#     - Abstract mixin with helper utilities (model availability checks, safe calls, notifications)
#     - Event Service to register/emit/dispatch cross-module events without circular dependencies
#     - Optional event logging for audit and troubleshooting
#     - Dynamic field guards on core models to attach back-references when bridges are not installed
#
# Design principles
#   - No hard dependency on other clinic_* addons
#   - Use company-safe defaults and existing core keys when adjusting records
#   - Idempotent operations (dynamic fields/handlers)
#
# All user-facing strings are in English.

import json
import logging
from typing import Iterable, List, Optional, Tuple, Dict

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


# =============================================================================
# Abstract integration mixin
# =============================================================================
class ClinicIntegrationMixin(models.AbstractModel):
    _name = "clinic.integration.mixin"
    _description = "Clinic Integration Mixin"

    # ----------------------------- Safe Utilities ----------------------------

    @api.model
    def _clinic_model_available(self, model_name: str) -> bool:
        """Return True if a model is available in the registry (installed)."""
        try:
            return bool(self.env.get(model_name))
        except Exception:
            return False

    @api.model
    def _clinic_method_available(self, model_name: str, method_name: str) -> bool:
        """Return True if a model and method are available."""
        try:
            model = self.env.get(model_name)
            return bool(model and hasattr(model, method_name))
        except Exception:
            return False

    @api.model
    def _clinic_call_if_available(self, model_name: str, method_name: str, *args, **kwargs):
        """Call model.method if available; return (handled: bool, result: any)."""
        try:
            model = self.env.get(model_name)
            if not model or not hasattr(model, method_name):
                return False, None
            res = getattr(model, method_name)(*args, **kwargs)
            return True, res
        except Exception as e:
            _logger.exception("ClinicIntegrationMixin call failed: %s.%s", model_name, method_name)
            return False, e

    @api.model
    def _clinic_notify_success(self, message: str):
        """UI success toast for current user (no-op if client not supporting)."""
        try:
            self.env.user.notify_success(message=message)
        except Exception:
            _logger.info("notify_success unavailable; message: %s", message)

    @api.model
    def _clinic_notify_warning(self, message: str):
        try:
            self.env.user.notify_warning(message=message)
        except Exception:
            _logger.info("notify_warning unavailable; message: %s", message)

    @api.model
    def _clinic_notify_danger(self, message: str):
        try:
            self.env.user.notify_danger(message=message)
        except Exception:
            _logger.warning("notify_danger unavailable; message: %s", message)

    @api.model
    def _clinic_company_defaults(self, company=None) -> Dict:
        """Fetch company-scoped Clinic Inventory defaults via ResConfigSettings helper if present."""
        company = company or self.env.company
        if self._clinic_method_available("res.config.settings", "clinic_get_company_defaults"):
            ok, res = self._clinic_call_if_available("res.config.settings", "clinic_get_company_defaults", company=company)
            if ok and isinstance(res, dict):
                return res
        # Fallback minimal set
        return {
            "expiry_policy": "warn",
            "replenishment_scope": "pharmacy_and_rooms",
            "enforce_fefo": True,
            "min_shelf_life_days": 0,
            "allow_expired_exception": False,
        }

    # ----------------------------- Event Helpers -----------------------------

    @api.model
    def _clinic_emit_event(self, code: str, payload: Dict, model: Optional[str] = None, res_id: Optional[int] = None):
        """Emit an integration event via service (sugar)."""
        return self.env["clinic.integration.service"].emit_event(
            event_code=code, payload=payload or {}, ctx_model=model, ctx_res_id=res_id
        )


# =============================================================================
# Event Log (optional but useful for audit/troubleshooting)
# =============================================================================
class ClinicIntegrationEventLog(models.Model):
    _name = "clinic.integration.event.log"
    _description = "Clinic Integration Event Log"
    _order = "create_date desc, id desc"
    _rec_name = "event_code"

    event_code = fields.Char(string="Event Code", required=True, index=True)
    ctx_model = fields.Char(string="Context Model", help="Model that emitted the event.")
    ctx_res_id = fields.Integer(string="Context Record ID")
    payload_json = fields.Text(string="Payload (JSON)")
    handled_by = fields.Char(string="Handled By", help="Comma-separated list of handler model names.")
    status = fields.Selection(
        selection=[("queued", "Queued"), ("dispatched", "Dispatched"), ("error", "Error")],
        string="Status",
        default="queued",
        index=True,
    )
    message = fields.Char(string="Message")
    company_id = fields.Many2one("res.company", string="Company", default=lambda s: s.env.company, index=True)
    user_id = fields.Many2one("res.users", string="Emitted By", default=lambda s: s.env.user)

    def set_dispatched(self, handlers: Iterable[str]):
        self.write({
            "status": "dispatched",
            "handled_by": ", ".join([h for h in handlers if h]),
        })

    def set_error(self, msg: str):
        self.write({"status": "error", "message": msg[:1024]})


# =============================================================================
# Event Service (registration + dispatch)
# =============================================================================
class ClinicIntegrationService(models.Model):
    _name = "clinic.integration.service"
    _description = "Clinic Integration Service"
    _inherit = "clinic.integration.mixin"

    # --------------- Public API: Registration ----------------

    @api.model
    def register_handler(self, event_code: str, model_name: str) -> bool:
        """Register a model as handler for a given event_code.

        Stored in ir.config_parameter as JSON array per key:
            clinic_integration.handlers.<event_code> = ["model.A", "model.B"]
        """
        if not event_code or not model_name:
            raise UserError(_("Both event_code and model_name are required for registration."))
        ICP = self.env["ir.config_parameter"].sudo()
        key = f"clinic_integration.handlers.{event_code}"
        raw = ICP.get_param(key, default="[]")
        try:
            arr = json.loads(raw) if raw else []
            if model_name not in arr:
                arr.append(model_name)
                ICP.set_param(key, json.dumps(arr))
                _logger.info("[ClinicIntegration] Registered handler %s for event %s", model_name, event_code)
            return True
        except Exception:
            _logger.exception("Failed to register handler: %s for %s", model_name, event_code)
            return False

    @api.model
    def unregister_handler(self, event_code: str, model_name: str) -> bool:
        ICP = self.env["ir.config_parameter"].sudo()
        key = f"clinic_integration.handlers.{event_code}"
        raw = ICP.get_param(key, default="[]")
        try:
            arr = json.loads(raw) if raw else []
            if model_name in arr:
                arr.remove(model_name)
                ICP.set_param(key, json.dumps(arr))
                _logger.info("[ClinicIntegration] Unregistered handler %s for event %s", model_name, event_code)
            return True
        except Exception:
            _logger.exception("Failed to unregister handler: %s for %s", model_name, event_code)
            return False

    @api.model
    def list_handlers(self, event_code: str) -> List[str]:
        ICP = self.env["ir.config_parameter"].sudo()
        key = f"clinic_integration.handlers.{event_code}"
        try:
            raw = ICP.get_param(key, default="[]")
            return json.loads(raw) if raw else []
        except Exception:
            return []

    # --------------- Public API: Emit/Dispatch ---------------

    @api.model
    def emit_event(self, event_code: str, payload: Dict, ctx_model: Optional[str] = None, ctx_res_id: Optional[int] = None):
        """Emit an event and dispatch to registered handlers.

        Handlers must implement:
            - def clinic_handle_event(self, event_code: str, payload: dict, ctx_model: str, ctx_res_id: int) -> bool
          OR
            - def clinic_handle_event_<event_code>(self, payload: dict, ctx_model: str, ctx_res_id: int) -> bool
        Return True from handler if it processed the event; False to ignore.

        Returns a dict: {"dispatched": True/False, "handlers": [..], "results": {model: bool/str}}
        """
        if not event_code:
            raise UserError(_("Event code is required."))

        # Create a log row (best-effort; do not block on failure)
        log_rec = None
        try:
            log_rec = self.env["clinic.integration.event.log"].sudo().create({
                "event_code": event_code,
                "ctx_model": ctx_model or "",
                "ctx_res_id": int(ctx_res_id or 0),
                "payload_json": json.dumps(payload or {}, default=str),
            })
        except Exception:
            _logger.warning("Failed to create event log for %s", event_code)

        handlers = self.list_handlers(event_code)
        results: Dict[str, object] = {}
        dispatched_any = False

        for model_name in handlers:
            handled, result = self._dispatch_to_handler(model_name, event_code, payload, ctx_model, ctx_res_id)
            results[model_name] = (handled if isinstance(result, Exception) else result)
            dispatched_any = dispatched_any or bool(handled)

        # Fallback: discover generic handlers dynamically (opt-in, light scan)
        if not handlers:
            generic_models = self._discover_generic_handlers()
            for model_name in generic_models:
                handled, result = self._dispatch_to_handler(model_name, event_code, payload, ctx_model, ctx_res_id)
                results[model_name] = (handled if isinstance(result, Exception) else result)
                dispatched_any = dispatched_any or bool(handled)
                # We do not auto-register them; discovery is stateless by design.

        # Update log
        try:
            if log_rec:
                if dispatched_any:
                    log_rec.set_dispatched(handlers or list(results.keys()))
                else:
                    log_rec.set_error("No handlers dispatched.")
        except Exception:
            _logger.debug("Cannot update event log for %s", event_code)

        return {"dispatched": dispatched_any, "handlers": handlers or list(results.keys()), "results": results}

    # --------------- Internals --------------------------------

    def _dispatch_to_handler(self, model_name: str, event_code: str, payload: Dict, ctx_model: Optional[str], ctx_res_id: Optional[int]) -> Tuple[bool, object]:
        """Call a model's handler method if available."""
        try:
            model = self.env.get(model_name)
            if not model:
                _logger.debug("Handler model not available: %s", model_name)
                return False, "model_unavailable"

            specific = f"clinic_handle_event_{event_code}"
            if hasattr(model, specific):
                res = getattr(model, specific)(payload or {}, ctx_model, ctx_res_id)
                return bool(res), res

            if hasattr(model, "clinic_handle_event"):
                res = model.clinic_handle_event(event_code, payload or {}, ctx_model, ctx_res_id)
                return bool(res), res

            _logger.debug("No handler method on model %s for event %s", model_name, event_code)
            return False, "method_unavailable"
        except Exception as e:
            _logger.exception("Error dispatching event %s to handler %s", event_code, model_name)
            return False, e

    def _discover_generic_handlers(self) -> List[str]:
        """Lightweight discovery of models implementing clinic_handle_event (not auto-registered)."""
        try:
            imodel = self.env["ir.model"].sudo()
            # Limit scan to models within 'clinic_' namespace to keep it cheap
            rows = imodel.search([("model", "ilike", "clinic_%")], limit=300)
            res = []
            for r in rows:
                model = self.env.get(r.model)
                if model and hasattr(model, "clinic_handle_event"):
                    res.append(r.model)
            return res
        except Exception:
            return []


# =============================================================================
# Suggested Event Codes (for consistency across addons)
# =============================================================================
class ClinicIntegrationEventCatalog(models.AbstractModel):
    _name = "clinic.integration.event.catalog"
    _description = "Clinic Integration Event Catalog"

    # The class only acts as a namespaced place for constants.
    # Usage: self.env['clinic.integration.service'].register_handler(
    #           self.env['clinic.integration.event.catalog'].EV_TREATMENT_CONSUME_PRE, 'clinic_xyz.bridge')
    EV_TREATMENT_CONSUME_PRE = "treatment.consume.pre"
    EV_TREATMENT_CONSUME_POST = "treatment.consume.post"
    EV_SCRAP_VALIDATE_PRE = "inventory.scrap.validate.pre"
    EV_SCRAP_VALIDATE_POST = "inventory.scrap.validate.post"
    EV_ADJUSTMENT_APPLY_POST = "inventory.adjustment.apply.post"
    EV_PRODUCT_EXPIRY_CHANGED = "product.expiry.changed"
    EV_REORDER_SUGGEST = "reorder.suggest"
    EV_PURCHASE_CREATED = "purchase.created"
    EV_INTERNAL_TRANSFER_CREATED = "stock.internal.created"


# =============================================================================
# Dynamic field guards (idempotent): back-references on stock.move / stock.picking
# =============================================================================
def _ensure_dynamic_fields(env):
    """Add optional back-reference fields safely if they don't exist.

    - stock.move.clinic_usage_id -> clinic.treatment.product.usage
    - stock.move.clinic_adjustment_id -> clinic.inventory.adjustment
    - stock.picking.clinic_is_quarantine_transfer -> Boolean tag (UI hint)
    """
    from odoo.fields import Many2one, Boolean

    Move = env["stock.move"]
    if "clinic_usage_id" not in Move._fields:
        Move._add_field(
            "clinic_usage_id",
            Many2one(
                comodel_name="clinic.treatment.product.usage",
                string="Treatment Usage",
                help="Back-reference to the treatment usage document that generated this move.",
                ondelete="set null",
            ),
        )
        _logger.info("Added dynamic field stock.move.clinic_usage_id")

    if "clinic_adjustment_id" not in Move._fields:
        Move._add_field(
            "clinic_adjustment_id",
            Many2one(
                comodel_name="clinic.inventory.adjustment",
                string="Clinical Adjustment",
                help="Back-reference to the clinical inventory adjustment document.",
                ondelete="set null",
            ),
        )
        _logger.info("Added dynamic field stock.move.clinic_adjustment_id")

    Picking = env["stock.picking"]
    if "clinic_is_quarantine_transfer" not in Picking._fields:
        Picking._add_field(
            "clinic_is_quarantine_transfer",
            Boolean(
                string="Quarantine Transfer",
                help="True if this transfer was intended to move items into a quarantine area.",
            ),
        )
        _logger.info("Added dynamic field stock.picking.clinic_is_quarantine_transfer")


# Odoo will call this on module registry load
def _register_hook(env):
    _ensure_dynamic_fields(env)




