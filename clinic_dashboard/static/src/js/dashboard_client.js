/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";


export class ClinicDashboardClient extends Component {
    static template = "clinic_dashboard.ClientAction";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");

        const params = this.props.action?.params || {};
        this.state = useState({
            loading: true,
            error: false,
            boards: [],
            branches: [],
            selectedBoardId: params.board_id || false,
            branchId: params.branch_id || false,
            dateFrom: params.date_from || false,
            dateTo: params.date_to || false,
            canRefresh: false,
            canManage: false,
            payload: false,
        });

        onWillStart(async () => {
            await this.loadBootstrap();
        });
    }

    async loadBootstrap() {
        this.state.loading = true;
        this.state.error = false;
        try {
            const bootstrap = await this.orm.call(
                "clinic.dashboard.board",
                "get_dashboard_bootstrap",
                [],
                { board_id: this.state.selectedBoardId || false }
            );

            this.state.boards = bootstrap.boards || [];
            this.state.branches = bootstrap.branches || [];
            this.state.selectedBoardId =
                this.state.selectedBoardId || bootstrap.selected_board_id || false;
            this.state.branchId =
                this.state.branchId || bootstrap.branch_id || false;
            this.state.dateFrom = this.state.dateFrom || bootstrap.date_from;
            this.state.dateTo = this.state.dateTo || bootstrap.date_to;
            this.state.canRefresh = Boolean(bootstrap.can_refresh);
            this.state.canManage = Boolean(bootstrap.can_manage);

            if (this.state.selectedBoardId) {
                await this.loadPayload(false);
            }
        } catch (error) {
            this.state.error = error.message || String(error);
        } finally {
            this.state.loading = false;
        }
    }

    async loadPayload(forceRefresh = false) {
        if (!this.state.selectedBoardId) {
            this.state.payload = false;
            return;
        }

        this.state.loading = true;
        this.state.error = false;
        try {
            this.state.payload = await this.orm.call(
                "clinic.dashboard.board",
                "get_dashboard_payload",
                [Number(this.state.selectedBoardId)],
                {
                    date_from: this.state.dateFrom,
                    date_to: this.state.dateTo,
                    branch_id: this.state.branchId
                        ? Number(this.state.branchId)
                        : false,
                    force_refresh: forceRefresh,
                }
            );
        } catch (error) {
            this.state.error = error.message || String(error);
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    async onBoardChange(event) {
        this.state.selectedBoardId = Number(event.target.value) || false;
        this.state.branchId = false;
        this.state.dateFrom = false;
        this.state.dateTo = false;

        const bootstrap = await this.orm.call(
            "clinic.dashboard.board",
            "get_dashboard_bootstrap",
            [],
            { board_id: this.state.selectedBoardId }
        );
        this.state.branchId = bootstrap.branch_id || false;
        this.state.dateFrom = bootstrap.date_from;
        this.state.dateTo = bootstrap.date_to;
        await this.loadPayload(false);
    }

    async applyScope() {
        await this.loadPayload(false);
    }

    async refreshDashboard() {
        if (!this.state.canRefresh) {
            this.notification.add(
                "Dashboard Analyst access is required to refresh KPI snapshots.",
                { type: "warning" }
            );
            return;
        }

        try {
            await this.loadPayload(true);
            this.notification.add(
                "Dashboard snapshot refreshed from Clinic Reports.",
                { type: "success" }
            );
        } catch {
            this.notification.add(
                "Dashboard refresh failed. Review the generated error and source Report Runs.",
                { type: "danger" }
            );
        }
    }

    openReport(card) {
        if (!card.report_run_id) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: card.name,
            res_model: "clinic.report.run",
            view_mode: "form",
            views: [[false, "form"]],
            res_id: card.report_run_id,
        });
    }

    openMetric(card) {
        if (!card.metric_id) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: card.name,
            res_model: "clinic.report.metric",
            view_mode: "form",
            views: [[false, "form"]],
            res_id: card.metric_id,
        });
    }

    openBoard() {
        if (!this.state.selectedBoardId) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Dashboard Board",
            res_model: "clinic.dashboard.board",
            view_mode: "form",
            views: [[false, "form"]],
            res_id: Number(this.state.selectedBoardId),
        });
    }

    openSnapshots() {
        if (!this.state.selectedBoardId) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Dashboard Snapshots",
            res_model: "clinic.dashboard.snapshot",
            view_mode: "kanban,list,form",
            views: [
                [false, "kanban"],
                [false, "list"],
                [false, "form"],
            ],
            domain: [["board_id", "=", Number(this.state.selectedBoardId)]],
        });
    }

    trendClass(card) {
        if (!card.has_trend) {
            return "text-muted";
        }
        if (card.trend_direction === "up") {
            return "text-success";
        }
        if (card.trend_direction === "down") {
            return "text-danger";
        }
        return "text-muted";
    }

    statusClass(card) {
        if (card.status === "critical" || card.status === "error") {
            return "o_clinic_dashboard_card--critical";
        }
        if (card.status === "warning") {
            return "o_clinic_dashboard_card--warning";
        }
        if (card.status === "normal") {
            return "o_clinic_dashboard_card--normal";
        }
        return "o_clinic_dashboard_card--nodata";
    }
}

registry.category("actions").add(
    "clinic_dashboard.main",
    ClinicDashboardClient
);
