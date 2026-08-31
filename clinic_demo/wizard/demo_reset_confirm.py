
"""Manager-only explicit confirmation before a demo reset."""

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from ..services.reset_service import DemoResetService


class ClinicDemoResetConfirmWizard(models.TransientModel):
    _name = "clinic.demo.reset.confirm.wizard"
    _description = "Confirm ClinicOne Demo Dataset Reset"

    run_id = fields.Many2one(
        "clinic.demo.run",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    confirmation_text = fields.Char(
        string="Confirmation",
        help="Type the exact confirmation phrase shown below.",
    )
    expected_confirmation = fields.Char(
        compute="_compute_reset_preview",
        string="Expected Confirmation",
    )
    acknowledge_retained_evidence = fields.Boolean(
        string="I understand immutable/reused evidence may be retained",
    )
    dry_run_summary = fields.Text(
        compute="_compute_reset_preview",
        string="Reset Preview",
        readonly=True,
    )

    @api.depends("run_id")
    def _compute_reset_preview(self):
        service = DemoResetService(self.env)
        for wizard in self:
            if not wizard.run_id:
                wizard.expected_confirmation = ""
                wizard.dry_run_summary = ""
                continue

            summary = service.preview_run(wizard.run_id)
            wizard.expected_confirmation = f"RESET {wizard.run_id.name}"
            wizard.dry_run_summary = _(
                "References: %(total)s\n"
                "Delete/Cancel candidates: %(delete)s\n"
                "Deactivate candidates: %(deactivate)s\n"
                "Retained evidence: %(retain)s\n"
                "Already missing: %(missing)s\n"
                "Blocked/unknown policy: %(blocked)s"
            ) % {
                "total": summary["total"],
                "delete": summary["delete_or_cancel"],
                "deactivate": summary["deactivate"],
                "retain": summary["retain"],
                "missing": summary["missing"],
                "blocked": summary["blocked"],
            }

    def action_confirm_reset(self):
        self.ensure_one()
        authorized = (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group("clinic_demo.group_demo_manager")
        )
        if not authorized:
            raise AccessError(
                _("System Administrator or Demo Dataset Manager access is required.")
            )

        if self.confirmation_text != self.expected_confirmation:
            raise UserError(
                _("Confirmation phrase does not match. Type exactly: %s")
                % self.expected_confirmation
            )
        if not self.acknowledge_retained_evidence:
            raise UserError(
                _(
                    "You must acknowledge that immutable, reused, or financial "
                    "evidence can be retained by the source-driven reset policy."
                )
            )

        summary = DemoResetService(self.env).reset_run(self.run_id)

        from ..services.logging_service import DemoLoggingService

        DemoLoggingService(self.env).log(
            run=self.run_id,
            level="error" if summary["errors"] else "warning",
            operation="reset_demo_dataset",
            message=(
                "Reset summary: "
                f"removed={summary['removed']}, "
                f"deactivated={summary['deactivated']}, "
                f"retained={summary['retained']}, "
                f"missing={summary['missing']}, "
                f"errors={summary['errors']}."
            ),
        )
        message = _(
            "Reset completed. Removed: %(removed)s, deactivated: %(deactivated)s, "
            "retained: %(retained)s, already missing: %(missing)s, errors: %(errors)s."
        ) % summary
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Demo Dataset Reset"),
                "message": message,
                "type": "warning" if summary["errors"] else "success",
                "sticky": bool(summary["errors"] or summary["retained"]),
                "next": {
                    "type": "ir.actions.act_window_close",
                },
            },
        }



