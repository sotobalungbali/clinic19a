# -*- coding: utf-8 -*-

import logging

from odoo import api, models, _
from odoo.exceptions import AccessError

from .tracked_model_catalog import TRACKED_MODEL_NAMES

_logger = logging.getLogger(__name__)


class ClinicAuditRegistryHook(models.AbstractModel):
    """Register bounded suite-wide audit coverage after the full registry exists."""

    _name = "clinic.audit.registry.hook"
    _description = "Clinic Audit Registry Coverage Hook"

    def _register_hook(self):
        result = super()._register_hook()

        patched = {"create": set(), "write": set(), "unlink": set()}

        def patch(model, method_name, method):
            model_name = model._name
            if model_name in patched[method_name]:
                return
            ModelClass = self.env.registry[model_name]
            method.origin = getattr(ModelClass, method_name)
            setattr(ModelClass, method_name, method)
            patched[method_name].add(model_name)

        def make_create():
            @api.model_create_multi
            def create(self, vals_list, **kw):
                if self.env.context.get("clinic_audit_skip"):
                    return create.origin(self, vals_list, **kw)

                # Suppress only the historical ClinicOne audit mixin while the
                # original business create runs.  This prevents duplicate
                # evidence; the authoritative event is emitted immediately
                # afterwards by the #38 service and therefore remains fail-closed.
                business_self = self.with_context(clinic_audit_skip=True)
                records = create.origin(business_self, vals_list, **kw)
                records = records.with_env(self.env)
                self.env["clinic.audit.service"]._after_create(records, vals_list)
                return records
            return create

        def make_write():
            def write(self, vals, **kw):
                if self.env.context.get("clinic_audit_skip") or not self:
                    return write.origin(self, vals, **kw)
                service = self.env["clinic.audit.service"]
                before_map = service._before_write(self, vals)
                business_self = self.with_context(clinic_audit_skip=True)
                result = write.origin(business_self, vals, **kw)
                service._after_write(self, vals, before_map)
                return result
            return write

        def make_unlink():
            def unlink(self, **kw):
                if self.env.context.get("clinic_audit_skip") or not self:
                    return unlink.origin(self, **kw)
                service = self.env["clinic.audit.service"]
                snapshots = service._before_unlink(self)
                business_self = self.with_context(clinic_audit_skip=True)
                result = unlink.origin(business_self, **kw)
                service._after_unlink(snapshots)
                return result
            return unlink

        coverage_count = 0
        mixin_count = 0
        for model_name in TRACKED_MODEL_NAMES:
            Model = self.env.get(model_name)
            if Model is None or model_name.startswith("clinic.audit."):
                continue
            if not getattr(Model, "_auto", True) or getattr(Model, "_transient", False):
                continue

            ModelClass = self.env.registry[model_name]
            if (
                hasattr(ModelClass, "_clinic_audit_logger_model")
                and hasattr(ModelClass, "_clinic_audit_emit")
            ):
                # Manual custom events emitted by the legacy mixin are routed
                # to the authoritative ledger.  Automatic create/write events
                # are suppressed only during origin execution above.
                ModelClass._clinic_audit_logger_model = "clinic.audit.event"
                mixin_count += 1

            patch(Model, "create", make_create())
            patch(Model, "write", make_write())
            patch(Model, "unlink", make_unlink())
            coverage_count += 1

        self._harden_legacy_log_surface(patch)
        _logger.info(
            "Clinic Audit registered fail-closed coverage for %s persistent models "
            "(%s include the historical clinic.mixin.audit contract).",
            coverage_count,
            mixin_count,
        )
        return result

    def _harden_legacy_log_surface(
        self,
        patch,
    ):
        """Protect the final legacy log model after clinic_encounter overrides it."""

        Legacy = self.env.get(
            "clinic.audit.log"
        )
        if Legacy is None:
            return

        def make_legacy_create():
            @api.model_create_multi
            def create(self, vals_list, **kw):
                if not (
                    self.env.su
                    or self.env.context.get(
                        "clinic_audit_legacy_internal"
                    )
                ):
                    raise AccessError(
                        _(
                            "Legacy audit logs can only be created "
                            "by trusted internal audit producers."
                        )
                    )
                return create.origin(
                    self,
                    vals_list,
                    **kw,
                )

            return create

        def make_legacy_write():
            def write(self, vals, **kw):
                if not (
                    self.env.su
                    and self.env.context.get(
                        "clinic_audit_legacy_maintenance"
                    )
                ):
                    raise AccessError(
                        _(
                            "Legacy audit logs are immutable."
                        )
                    )
                return write.origin(
                    self,
                    vals,
                    **kw,
                )

            return write

        def make_legacy_unlink():
            def unlink(self, **kw):
                raise AccessError(
                    _(
                        "Legacy audit logs are immutable "
                        "and cannot be deleted."
                    )
                )

            return unlink

        patch(
            Legacy,
            "create",
            make_legacy_create(),
        )
        patch(
            Legacy,
            "write",
            make_legacy_write(),
        )
        patch(
            Legacy,
            "unlink",
            make_legacy_unlink(),
        )

        # ``clinic_encounter`` historically re-declares ``clinic.audit.log``
        # later in the module graph.  Its final registry class therefore may
        # not contain the compatibility action declared by clinic_audit while
        # this module's XML was loaded.  Install a small navigation helper on
        # the final class so the button remains valid at runtime as well.
        ModelClass = self.env.registry["clinic.audit.log"]

        def action_open_log(records):
            records.ensure_one()
            return {
                "type": "ir.actions.act_window",
                "name": _("Legacy Audit Log"),
                "res_model": "clinic.audit.log",
                "res_id": records.id,
                "view_mode": "form",
            }

        ModelClass.action_open_log = action_open_log

