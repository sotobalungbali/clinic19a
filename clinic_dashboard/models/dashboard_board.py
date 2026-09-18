from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .dashboard_defaults import DEFAULT_DASHBOARDS, DASHBOARD_TYPE_SELECTION


PERIOD_SELECTION = [
    ("today", "Today"),
    ("7d", "Last 7 Days"),
    ("30d", "Last 30 Days"),
    ("90d", "Last 90 Days"),
    ("month", "Current Month"),
    ("ytd", "Year to Date"),
]


class ClinicDashboardBoard(models.Model):
    """Company-scoped dashboard configuration consuming Clinic Reports output."""

    _name = "clinic.dashboard.board"
    _description = "Clinic Dashboard Board"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"
    _check_company_auto = True

    _code_company_unique = models.Constraint(
        "UNIQUE(company_id, code)",
        "Dashboard code must be unique per company.",
    )
    _refresh_positive = models.Constraint(
        "CHECK(refresh_interval_hours >= 1)",
        "Dashboard refresh interval must be at least one hour.",
    )
    _company_state_idx = models.Index("(company_id, state, dashboard_type, sequence)")

    name = fields.Char(required=True, tracking=True, index=True)
    code = fields.Char(required=True, tracking=True, index=True)
    sequence = fields.Integer(default=10)
    dashboard_type = fields.Selection(
        DASHBOARD_TYPE_SELECTION,
        required=True,
        default="executive",
        tracking=True,
        index=True,
    )
    description = fields.Text()

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    default_branch_id = fields.Many2one(
        "clinic.branch",
        string="Default Branch",
        domain="[('company_id', '=', company_id)]",
        ondelete="set null",
    )

    default_period = fields.Selection(
        PERIOD_SELECTION,
        required=True,
        default="month",
        tracking=True,
    )
    auto_generate_missing_reports = fields.Boolean(
        default=True,
        help=(
            "When refreshing, create missing exact-scope Report Runs through "
            "clinic_reports instead of duplicating KPI formulas in Dashboard."
        ),
    )
    auto_refresh = fields.Boolean(
        string="Automatic Refresh",
        default=False,
        tracking=True,
    )
    refresh_interval_hours = fields.Integer(default=24)
    next_refresh_at = fields.Datetime(index=True)
    owner_user_id = fields.Many2one(
        "res.users",
        string="Automatic Refresh Owner",
        help="Must have Dashboard Analyst access when Automatic Refresh is enabled.",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True)

    widget_ids = fields.One2many(
        "clinic.dashboard.widget",
        "board_id",
        string="Dashboard Widgets",
        copy=True,
    )
    snapshot_ids = fields.One2many(
        "clinic.dashboard.snapshot",
        "board_id",
        string="Dashboard Snapshots",
        copy=False,
    )
    widget_count = fields.Integer(compute="_compute_counts")
    snapshot_count = fields.Integer(compute="_compute_counts")
    latest_snapshot_id = fields.Many2one(
        "clinic.dashboard.snapshot",
        compute="_compute_counts",
        string="Latest Snapshot",
    )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            if vals.get("code"):
                vals["code"] = vals["code"].strip().upper()
            if vals.get("auto_refresh") and not vals.get("next_refresh_at"):
                vals["next_refresh_at"] = fields.Datetime.now()
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        if "state" in vals and not self.env.context.get("dashboard_board_transition"):
            raise AccessError(
                _("Use Dashboard Board workflow actions to change status.")
            )
        vals = dict(vals)
        if "code" in vals and vals["code"]:
            vals["code"] = vals["code"].strip().upper()
        if vals.get("auto_refresh") and not vals.get("next_refresh_at"):
            if not all(record.next_refresh_at for record in self):
                vals["next_refresh_at"] = fields.Datetime.now()
        return super().write(vals)

    @api.constrains("company_id", "default_branch_id")
    def _check_default_branch_company(self):
        for board in self:
            if (
                board.default_branch_id
                and board.default_branch_id.company_id != board.company_id
            ):
                raise ValidationError(
                    _("Default Branch must belong to the Dashboard company.")
                )

    @api.constrains("auto_refresh", "owner_user_id")
    def _check_refresh_owner(self):
        for board in self:
            if not board.auto_refresh:
                continue
            if not board.owner_user_id:
                raise ValidationError(
                    _("Automatic Refresh requires a Dashboard Refresh Owner.")
                )
            if not board.owner_user_id.has_group(
                "clinic_dashboard.group_dashboard_analyst"
            ):
                raise ValidationError(
                    _("Automatic Refresh Owner must be a Dashboard Analyst or Manager.")
                )

    @api.depends("widget_ids", "snapshot_ids", "snapshot_ids.generated_at")
    def _compute_counts(self):
        for board in self:
            board.widget_count = len(board.widget_ids)
            board.snapshot_count = len(board.snapshot_ids)
            board.latest_snapshot_id = board.snapshot_ids.sorted(
                key=lambda snap: (snap.generated_at or datetime.min, snap.id),
                reverse=True,
            )[:1]

    def _require_group(self, xmlid, message):
        if self.env.su:
            return True
        if not self.env.user.has_group(xmlid):
            raise AccessError(message)
        return True

    # Period resolution is centralized so UI, cron and backend actions use identical date boundaries.
    def _resolve_period(self, period=None):
        self.ensure_one()
        period = period or self.default_period or "month"
        today = fields.Date.context_today(self)

        if period == "today":
            return today, today
        if period == "7d":
            return today - timedelta(days=6), today
        if period == "30d":
            return today - timedelta(days=29), today
        if period == "90d":
            return today - timedelta(days=89), today
        if period == "ytd":
            return today.replace(month=1, day=1), today
        return today.replace(day=1), today

    # Runtime scope is validated again in Python; the Branch selector is never trusted as UI-only security.
    def _validate_runtime_scope(self, date_from, date_to, branch):
        self.ensure_one()
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        if not date_from or not date_to:
            raise ValidationError(_("Dashboard Date From and Date To are required."))
        if date_from > date_to:
            raise ValidationError(_("Dashboard Date From cannot be after Date To."))
        if branch:
            if branch.company_id != self.company_id:
                raise ValidationError(
                    _("Dashboard Branch must belong to the selected company.")
                )
            if (
                "policy_branch_scope_reports" in self.company_id._fields
                and not self.company_id.policy_branch_scope_reports
            ):
                raise ValidationError(
                    _("Branch reporting is disabled by the Clinic Branch company policy.")
                )
        return date_from, date_to

    # Trend comparison uses the immediately preceding period with exactly the same number of calendar days.
    def _previous_period(self, date_from, date_to):
        self.ensure_one()
        window = (date_to - date_from).days + 1
        previous_to = date_from - timedelta(days=1)
        previous_from = previous_to - timedelta(days=window - 1)
        return previous_from, previous_to

    # Dashboard accepts only exact-scope ready/finalized/archived Report Runs to avoid mixed-period KPI cards.
    def _find_report_run(self, definition, date_from, date_to, branch):
        self.ensure_one()
        domain = [
            ("definition_id", "=", definition.id),
            ("company_id", "=", self.company_id.id),
            ("date_from", "=", date_from),
            ("date_to", "=", date_to),
            ("state", "in", ("ready", "finalized", "archived")),
        ]
        domain.append(("branch_id", "=", branch.id if branch else False))
        return self.env["clinic.report.run"].sudo().search(
            domain,
            order="finalized_at desc, generated_at desc, id desc",
            limit=1,
        )

    # Missing KPI data is delegated to clinic_reports; Dashboard never reimplements the underlying KPI formula.
    def _ensure_report_run(self, definition, date_from, date_to, branch):
        """Reuse an exact-scope Report Run, or delegate generation to clinic_reports."""
        self.ensure_one()

        if branch and not definition.allow_branch_filter:
            return self.env["clinic.report.run"], "unsupported_scope"

        run = self._find_report_run(definition, date_from, date_to, branch)
        if run:
            return run, "available"

        if not self.auto_generate_missing_reports:
            return self.env["clinic.report.run"], "no_data"

        self._require_group(
            "clinic_dashboard.group_dashboard_analyst",
            _("Only a Dashboard Analyst can generate missing Report Runs."),
        )

        # Dashboard never owns KPI formulas. Missing source snapshots are
        # generated through the existing clinic_reports engine.
        run = self.env["clinic.report.run"].create({
            "definition_id": definition.id,
            "company_id": self.company_id.id,
            "branch_id": branch.id if branch else False,
            "date_from": date_from,
            "date_to": date_to,
            "include_details": False,
            "detail_limit": max(definition.default_detail_limit or 1, 1),
        })
        run.action_generate()
        run.invalidate_recordset(["state", "metric_ids"])
        if run.state not in ("ready", "finalized", "archived"):
            return run, "generation_failed"
        return run, "available"

    # Previous-period trend is observational only; Dashboard does not auto-generate historical comparisons.
    def _find_previous_metric(self, widget, date_from, date_to, branch):
        self.ensure_one()
        previous_from, previous_to = self._previous_period(date_from, date_to)
        previous_run = self._find_report_run(
            widget.definition_id,
            previous_from,
            previous_to,
            branch,
        )
        if not previous_run:
            return self.env["clinic.report.metric"]
        return previous_run.metric_ids.filtered(
            lambda metric: metric.code == widget.metric_code
        )[:1]

    # One refresh creates one immutable Dashboard Snapshot that records full Report provenance per card.
    def _refresh_snapshot(self, date_from, date_to, branch=None, snapshot_name=None, existing_snapshot=None):
        self.ensure_one()
        self._require_group(
            "clinic_dashboard.group_dashboard_analyst",
            _("Only a Dashboard Analyst can refresh Dashboard snapshots."),
        )

        date_from, date_to = self._validate_runtime_scope(
            date_from,
            date_to,
            branch,
        )

        Snapshot = self.env["clinic.dashboard.snapshot"].sudo().with_context(
            dashboard_generation=True
        )
        snapshot_values = {
            "name": snapshot_name or "/",
            "board_id": self.id,
            "company_id": self.company_id.id,
            "branch_id": branch.id if branch else False,
            "date_from": date_from,
            "date_to": date_to,
            "state": "refreshing",
            "generated_by_id": self.env.user.id,
        }
        if existing_snapshot is not None:
            existing_snapshot.ensure_one()
            existing_snapshot.check_access("read")
            if (not snapshot_name or not snapshot_name.startswith("DEMO-")
                    or existing_snapshot.board_id != self or existing_snapshot.company_id != self.company_id
                    or existing_snapshot.name != snapshot_name
                    or existing_snapshot.branch_id.id != (branch.id if branch else False)):
                raise UserError(_("Snapshot refresh must preserve board, company, branch and identity."))
            snapshot = Snapshot.browse(existing_snapshot.id)
            snapshot.line_ids.with_context(dashboard_generation=True).unlink()
            snapshot.write(snapshot_values)
        else:
            snapshot = Snapshot.create(snapshot_values)

        line_commands = []
        report_cache = {}

        try:
            for widget in self.widget_ids.filtered("active").sorted(
                key=lambda rec: (rec.sequence, rec.id)
            ):
                try:
                    # A broken/missing source Report for one KPI must not blank
                    # the entire enterprise Dashboard. Each card is isolated.
                    with self.env.cr.savepoint():
                        if branch and not widget.definition_id.allow_branch_filter:
                            line_commands.append(
                                snapshot._line_vals_unsupported(widget)
                            )
                            continue

                        cache_key = widget.definition_id.id
                        if cache_key not in report_cache:
                            report_cache[cache_key] = self._ensure_report_run(
                                widget.definition_id,
                                date_from,
                                date_to,
                                branch,
                            )

                        run, availability = report_cache[cache_key]
                        if availability != "available":
                            line_commands.append(
                                snapshot._line_vals_no_data(
                                    widget,
                                    run=run,
                                    status=availability,
                                )
                            )
                            continue

                        metric = run.metric_ids.filtered(
                            lambda rec: rec.code == widget.metric_code
                        )[:1]
                        if not metric:
                            line_commands.append(
                                snapshot._line_vals_no_data(
                                    widget,
                                    run=run,
                                    status="no_data",
                                    note=_(
                                        "Metric code was not produced by this Report Run."
                                    ),
                                )
                            )
                            continue

                        previous_metric = self._find_previous_metric(
                            widget,
                            date_from,
                            date_to,
                            branch,
                        )
                        line_commands.append(
                            snapshot._line_vals_metric(
                                widget,
                                run,
                                metric,
                                previous_metric,
                            )
                        )
                except Exception as widget_error:
                    line_commands.append(
                        snapshot._line_vals_no_data(
                            widget,
                            status="generation_failed",
                            note=str(widget_error),
                        )
                    )

            snapshot.with_context(dashboard_generation=True).write({
                "line_ids": [(0, 0, vals) for vals in line_commands],
                "state": "ready",
                "generated_at": fields.Datetime.now(),
                "error_message": False,
            })
        except Exception as exc:
            snapshot.with_context(dashboard_generation=True).write({
                "state": "failed",
                "generated_at": fields.Datetime.now(),
                "error_message": str(exc),
            })
            raise

        return snapshot

    def action_refresh(self):
        self.ensure_one()
        if self.state != "active":
            raise UserError(_("Only Active Dashboard Boards can be refreshed."))
        date_from, date_to = self._resolve_period()
        snapshot = self._refresh_snapshot(
            date_from,
            date_to,
            self.default_branch_id,
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Dashboard Snapshot"),
            "res_model": "clinic.dashboard.snapshot",
            "view_mode": "form",
            "res_id": snapshot.id,
        }

    def action_activate(self):
        self._require_group(
            "clinic_dashboard.group_dashboard_manager",
            _("Only a Dashboard Manager can activate Dashboard Boards."),
        )
        self.with_context(dashboard_board_transition=True).write({"state": "active"})
        return True

    def action_archive(self):
        self._require_group(
            "clinic_dashboard.group_dashboard_manager",
            _("Only a Dashboard Manager can archive Dashboard Boards."),
        )
        self.with_context(dashboard_board_transition=True).write({
            "state": "archived",
            "active": False,
        })
        return True

    def action_reset_to_draft(self):
        self._require_group(
            "clinic_dashboard.group_dashboard_manager",
            _("Only a Dashboard Manager can reset Dashboard Boards."),
        )
        self.with_context(dashboard_board_transition=True).write({
            "state": "draft",
            "active": True,
        })
        return True

    def action_open_live_dashboard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "clinic_dashboard.main",
            "target": "main",
            "params": {"board_id": self.id},
        }

    def action_view_widgets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Dashboard Widgets"),
            "res_model": "clinic.dashboard.widget",
            "view_mode": "list,form",
            "domain": [("board_id", "=", self.id)],
            "context": {"default_board_id": self.id},
        }

    def action_view_snapshots(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Dashboard Snapshots"),
            "res_model": "clinic.dashboard.snapshot",
            "view_mode": "kanban,list,form",
            "domain": [("board_id", "=", self.id)],
            "context": {"default_board_id": self.id},
        }

    def action_view_report_runs(self):
        self.ensure_one()
        definition_ids = self.widget_ids.mapped("definition_id").ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Source Report Runs"),
            "res_model": "clinic.report.run",
            "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("definition_id", "in", definition_ids),
            ],
        }

    @api.model
    # Built-in setup is idempotent so install, new-company setup and manual repair use the same safe path.
    def _ensure_default_boards(self, company):
        """Idempotently seed company-specific board/widget configuration."""
        company = self.env["res.company"].browse(company.id).exists()
        if not company:
            return self.browse()

        created_or_found = self.browse()
        Definition = self.env["clinic.report.definition"].sudo()

        for blueprint in DEFAULT_DASHBOARDS:
            board = self.sudo().search([
                ("company_id", "=", company.id),
                ("code", "=", blueprint["code"]),
            ], limit=1)

            if not board:
                board = self.sudo().with_context(
                    dashboard_board_transition=True
                ).create({
                    "name": blueprint["name"],
                    "code": blueprint["code"],
                    "sequence": blueprint["sequence"],
                    "dashboard_type": blueprint["dashboard_type"],
                    "description": blueprint["description"],
                    "company_id": company.id,
                    "default_period": blueprint["default_period"],
                    "auto_generate_missing_reports": True,
                    "state": "active",
                })

            created_or_found |= board

            for index, widget_data in enumerate(
                blueprint["widgets"],
                start=1,
            ):
                (
                    report_key,
                    metric_code,
                    widget_name,
                    icon,
                    display_style,
                    direction,
                    col_span,
                    target_value,
                    warning_threshold,
                    critical_threshold,
                ) = widget_data

                definition = Definition.search([
                    ("report_key", "=", report_key),
                    ("state", "=", "active"),
                ], limit=1)
                if not definition:
                    continue

                existing = self.env["clinic.dashboard.widget"].sudo().search([
                    ("board_id", "=", board.id),
                    ("definition_id", "=", definition.id),
                    ("metric_code", "=", metric_code),
                ], limit=1)
                if existing:
                    continue

                self.env["clinic.dashboard.widget"].sudo().create({
                    "board_id": board.id,
                    "sequence": index * 10,
                    "name": widget_name,
                    "definition_id": definition.id,
                    "metric_code": metric_code,
                    "icon": icon,
                    "display_style": display_style,
                    "direction": direction,
                    "column_span": str(col_span),
                    "target_value": target_value or 0.0,
                    "has_target": target_value is not False,
                    "warning_threshold": warning_threshold or 0.0,
                    "has_warning_threshold": warning_threshold is not False,
                    "critical_threshold": critical_threshold or 0.0,
                    "has_critical_threshold": critical_threshold is not False,
                    "active": True,
                })

        if not company.clinic_dashboard_default_board_id:
            executive = created_or_found.filtered(
                lambda rec: rec.code == "EXECUTIVE"
            )[:1]
            if executive:
                company.sudo().clinic_dashboard_default_board_id = executive.id

        return created_or_found

    @api.model
    # The client bootstrap returns only current-company board/branch navigation and capability flags.
    def get_dashboard_bootstrap(self, board_id=None):
        company = self.env.company
        boards = self.search([
            ("company_id", "=", company.id),
            ("state", "=", "active"),
            ("active", "=", True),
        ], order="sequence, name")

        if not boards:
            boards = self._ensure_default_boards(company).filtered(
                lambda rec: rec.state == "active"
            )

        selected = self.browse(board_id).exists() if board_id else self.browse()
        if not selected or selected.company_id != company or selected not in boards:
            selected = (
                company.clinic_dashboard_default_board_id
                if company.clinic_dashboard_default_board_id in boards
                else boards[:1]
            )

        branches = self.env["clinic.branch"].search([
            ("company_id", "=", company.id),
        ], order="name")

        date_from = date_to = fields.Date.context_today(self)
        if selected:
            date_from, date_to = selected._resolve_period()

        return {
            "boards": [
                {
                    "id": board.id,
                    "name": board.name,
                    "code": board.code,
                    "type": board.dashboard_type,
                    "default_period": board.default_period,
                }
                for board in boards
            ],
            "branches": [
                {"id": branch.id, "name": branch.display_name}
                for branch in branches
            ],
            "selected_board_id": selected.id if selected else False,
            "branch_id": (
                selected.default_branch_id.id
                if selected and selected.default_branch_id
                else False
            ),
            "date_from": fields.Date.to_string(date_from),
            "date_to": fields.Date.to_string(date_to),
            "can_refresh": self.env.user.has_group(
                "clinic_dashboard.group_dashboard_analyst"
            ),
            "can_manage": self.env.user.has_group(
                "clinic_dashboard.group_dashboard_manager"
            ),
        }

    @api.model
    # The Owl client receives a DTO payload; it never reads transactional models directly from JavaScript.
    def get_dashboard_payload(
        self,
        board_id,
        date_from=None,
        date_to=None,
        branch_id=None,
        force_refresh=False,
    ):
        board = self.browse(board_id).exists()
        if not board:
            raise AccessError(_("Dashboard Board is not available."))
        if hasattr(board, "check_access"):
            board.check_access("read")
        if board.company_id != self.env.company:
            raise AccessError(_("Dashboard Board is not available in the current company."))

        branch = (
            self.env["clinic.branch"].browse(branch_id).exists()
            if branch_id
            else self.env["clinic.branch"]
        )
        if branch and hasattr(branch, "check_access"):
            branch.check_access("read")
        if not date_from or not date_to:
            date_from, date_to = board._resolve_period()

        date_from, date_to = board._validate_runtime_scope(
            date_from,
            date_to,
            branch,
        )

        snapshot = self.env["clinic.dashboard.snapshot"].search([
            ("board_id", "=", board.id),
            ("company_id", "=", board.company_id.id),
            ("branch_id", "=", branch.id if branch else False),
            ("date_from", "=", date_from),
            ("date_to", "=", date_to),
            ("state", "=", "ready"),
        ], order="generated_at desc, id desc", limit=1)

        if force_refresh:
            snapshot = board._refresh_snapshot(
                date_from,
                date_to,
                branch,
            )

        return board._payload_from_snapshot(
            snapshot,
            date_from,
            date_to,
            branch,
        )

    # Payload composition preserves card ordering from Widget governance rather than sorting by volatile values.
    def _payload_from_snapshot(self, snapshot, date_from, date_to, branch):
        self.ensure_one()
        line_by_widget = {
            line.widget_id.id: line
            for line in snapshot.line_ids
        } if snapshot else {}

        cards = []
        for widget in self.widget_ids.filtered("active").sorted(
            key=lambda rec: (rec.sequence, rec.id)
        ):
            line = line_by_widget.get(widget.id)
            cards.append(
                line._as_dashboard_card()
                if line
                else widget._empty_dashboard_card()
            )

        return {
            "board": {
                "id": self.id,
                "name": self.name,
                "code": self.code,
                "type": self.dashboard_type,
                "description": self.description or "",
            },
            "scope": {
                "company": self.company_id.display_name,
                "branch": branch.display_name if branch else _("All / Company Scope"),
                "date_from": fields.Date.to_string(date_from),
                "date_to": fields.Date.to_string(date_to),
            },
            "snapshot": {
                "id": snapshot.id if snapshot else False,
                "generated_at": fields.Datetime.to_string(snapshot.generated_at)
                if snapshot and snapshot.generated_at
                else False,
                "state": snapshot.state if snapshot else "no_data",
                "critical_count": snapshot.critical_count if snapshot else 0,
                "warning_count": snapshot.warning_count if snapshot else 0,
                "no_data_count": snapshot.no_data_count if snapshot else len(cards),
            },
            "cards": cards,
            "can_refresh": self.env.user.has_group(
                "clinic_dashboard.group_dashboard_analyst"
            ),
        }

    @api.model
    # Each due Board runs in a savepoint-equivalent guarded loop so one failure never becomes an endless retry engine.
    def _cron_refresh_due_boards(self):
        now = fields.Datetime.now()
        boards = self.sudo().search([
            ("state", "=", "active"),
            ("active", "=", True),
            ("auto_refresh", "=", True),
            ("next_refresh_at", "<=", now),
        ])

        for board in boards:
            next_refresh = now + timedelta(
                hours=max(board.refresh_interval_hours, 1)
            )
            try:
                if not board.owner_user_id:
                    board.message_post(
                        body=_("Automatic Dashboard refresh skipped: no Refresh Owner.")
                    )
                    continue

                board_user = board.with_user(board.owner_user_id)
                date_from, date_to = board_user._resolve_period()
                with self.env.cr.savepoint():
                    board_user._refresh_snapshot(
                        date_from,
                        date_to,
                        board.default_branch_id,
                    )
            except Exception as exc:
                board.message_post(
                    body=_("Automatic Dashboard refresh failed: %s") % str(exc)
                )
            finally:
                board.next_refresh_at = next_refresh

        return True

