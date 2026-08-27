from odoo import models, _


class ClinicReportEngineOperational(models.AbstractModel):
    """Operational report family for scheduling, queue, rooms and patient programs."""

    _name = "clinic.report.engine.operational"
    _description = "Clinic Reports Operational Engine"

    # Booking has no authoritative branch field in the current baseline; its definition therefore disables Branch.
    def _generate_ops_booking(self):
        self.ensure_one()
        Booking = self.env["booking.booking"]
        bookings = Booking.sudo().search(
            self._report_domain(
                "booking.booking",
                "start_datetime",
                self.date_from,
                self.date_to,
            ),
            order="start_datetime, id",
        )

        done = bookings.filtered(lambda rec: rec.state == "done")
        cancelled = bookings.filtered(lambda rec: rec.state == "cancelled")
        active = bookings.filtered(lambda rec: rec.state in ("confirmed", "in_progress"))
        avg_duration = (
            sum(bookings.mapped("duration_minutes")) / len(bookings)
            if bookings
            else 0.0
        )
        planned_value = sum(bookings.mapped("amount_total"))

        self._add_metric("BOOKING_COUNT", _("Bookings"), len(bookings), "count", 10)
        self._add_metric("BOOKING_DONE", _("Completed Bookings"), len(done), "count", 20)
        self._add_metric("BOOKING_ACTIVE", _("Confirmed / In Progress"), len(active), "count", 30)
        self._add_metric("BOOKING_CANCELLED", _("Cancelled Bookings"), len(cancelled), "count", 40)
        self._add_metric(
            "BOOKING_COMPLETION_RATE",
            _("Booking Completion Rate"),
            self._percentage(len(done), len(bookings)),
            "percentage",
            50,
        )
        self._add_metric(
            "BOOKING_CANCEL_RATE",
            _("Booking Cancellation Rate"),
            self._percentage(len(cancelled), len(bookings)),
            "percentage",
            60,
        )
        self._add_metric("BOOKING_AVG_DURATION", _("Average Planned Duration"), avg_duration, "duration", 70)
        self._add_metric("BOOKING_PLANNED_VALUE", _("Booking Planned Value"), planned_value, "amount", 80)
        self._state_breakdown_metrics(bookings, "BOOKING_STATE", 100)

        for booking in bookings:
            self._add_detail(
                booking,
                _("Booking"),
                event_date=booking.start_datetime,
                reference=booking.name,
                state_label=booking.state,
                partner=booking.patient_id,
                doctor=booking.doctor_id,
                treatment=booking.treatment_id,
                amount=booking.amount_total,
                duration_minutes=booking.duration_minutes,
                note=(
                    booking.room_id.display_name
                    if booking.room_id
                    else ""
                ),
            )

    # Queue SLA metrics reuse stored Queue durations/breach flags rather than introducing a second SLA formula.
    def _generate_ops_queue(self):
        self.ensure_one()
        Queue = self.env["clinic.queue"]
        queues = Queue.sudo().search(
            self._report_domain(
                "clinic.queue",
                "checkin_time",
                self.date_from,
                self.date_to,
            ),
            order="checkin_time, id",
        )

        done = queues.filtered(lambda rec: rec.state == "done")
        no_show = queues.filtered(lambda rec: rec.state == "no_show")
        cancelled = queues.filtered(lambda rec: rec.state == "cancelled")
        wait_values = [
            value for value in queues.mapped("waiting_duration_min")
            if value is not False
        ]
        service_values = [
            value for value in queues.mapped("service_duration_min")
            if value is not False
        ]
        avg_wait = sum(wait_values) / len(wait_values) if wait_values else 0.0
        avg_service = (
            sum(service_values) / len(service_values)
            if service_values
            else 0.0
        )
        sla_breached = len(
            queues.filtered(lambda rec: bool(rec.sla_wait_breached))
        )

        self._add_metric("QUEUE_COUNT", _("Queue Visits"), len(queues), "count", 10)
        self._add_metric("QUEUE_DONE", _("Completed Queue Visits"), len(done), "count", 20)
        self._add_metric("QUEUE_NO_SHOW", _("No Shows"), len(no_show), "count", 30)
        self._add_metric("QUEUE_CANCELLED", _("Cancelled"), len(cancelled), "count", 40)
        self._add_metric("QUEUE_AVG_WAIT", _("Average Waiting Time"), avg_wait, "duration", 50)
        self._add_metric("QUEUE_AVG_SERVICE", _("Average Service Time"), avg_service, "duration", 60)
        self._add_metric("QUEUE_SLA_BREACH", _("Wait SLA Breaches"), sla_breached, "count", 70)
        self._add_metric(
            "QUEUE_SLA_BREACH_RATE",
            _("Wait SLA Breach Rate"),
            self._percentage(sla_breached, len(queues)),
            "percentage",
            80,
        )
        self._state_breakdown_metrics(queues, "QUEUE_STATE", 100)

        for queue in queues:
            self._add_detail(
                queue,
                _("Queue Visit"),
                event_date=queue.checkin_time,
                reference=queue.name,
                state_label=queue.state,
                partner=queue.patient_id,
                treatment=queue.treatment_id,
                room=queue.room_id,
                duration_minutes=queue.waiting_duration_min,
                note=_("Service %.2f min | SLA %s")
                % (
                    queue.service_duration_min or 0.0,
                    _("Breached") if queue.sla_wait_breached else _("OK"),
                ),
            )

    def _generate_ops_room(self):
        self.ensure_one()
        Assignment = self.env["clinic.room.assignment"]
        assignments = Assignment.sudo().search(
            self._report_domain(
                "clinic.room.assignment",
                "assigned_at",
                self.date_from,
                self.date_to,
            ),
            order="assigned_at, id",
        )

        released = assignments.filtered(lambda rec: rec.state == "released")
        active = assignments.filtered(lambda rec: rec.state in ("assigned", "in_service"))
        occupancy = [
            value for value in assignments.mapped("occupancy_duration_min")
            if value is not False
        ]
        service = [
            value for value in assignments.mapped("service_duration_min")
            if value is not False
        ]
        total_occupancy = sum(occupancy)
        avg_occupancy = total_occupancy / len(occupancy) if occupancy else 0.0
        avg_service = sum(service) / len(service) if service else 0.0
        unique_rooms = len(assignments.mapped("room_id"))

        self._add_metric("ROOM_ASSIGNMENTS", _("Room Assignments"), len(assignments), "count", 10)
        self._add_metric("ROOMS_USED", _("Unique Rooms Used"), unique_rooms, "count", 20)
        self._add_metric("ROOM_RELEASED", _("Released Assignments"), len(released), "count", 30)
        self._add_metric("ROOM_ACTIVE", _("Active Assignments"), len(active), "count", 40)
        self._add_metric("ROOM_TOTAL_OCCUPANCY", _("Total Occupancy Minutes"), total_occupancy, "duration", 50)
        self._add_metric("ROOM_AVG_OCCUPANCY", _("Average Occupancy"), avg_occupancy, "duration", 60)
        self._add_metric("ROOM_AVG_SERVICE", _("Average Service Duration"), avg_service, "duration", 70)
        self._state_breakdown_metrics(assignments, "ROOM_STATE", 100)

        for assignment in assignments:
            self._add_detail(
                assignment,
                _("Room Assignment"),
                event_date=assignment.assigned_at,
                reference=assignment.name,
                state_label=assignment.state,
                partner=assignment.patient_id,
                treatment=assignment.treatment_id,
                room=assignment.room_id,
                duration_minutes=assignment.occupancy_duration_min,
                note=_("Service %.2f min | Wait %.2f min")
                % (
                    assignment.service_duration_min or 0.0,
                    assignment.wait_before_service_min or 0.0,
                ),
            )

    # Inventory branch scope follows Warehouse.branch_id, the live Clinic Branch stock contract.
    def _generate_ops_inventory(self):
        self.ensure_one()
        Usage = self.env["clinic.treatment.product.usage"]
        usages = Usage.sudo().search(
            self._report_domain(
                "clinic.treatment.product.usage",
                "date_usage",
                self.date_from,
                self.date_to,
                extra=[("state", "=", "done")],
                branch_path="warehouse_id.branch_id",
            ),
            order="date_usage, id",
        )

        line_count = sum(usages.mapped("total_lines"))
        total_qty = sum(usages.mapped("total_qty"))
        products = usages.mapped("line_ids.product_id")

        self._add_metric("INVENTORY_USAGE_COUNT", _("Completed Usage Documents"), len(usages), "count", 10)
        self._add_metric("INVENTORY_USAGE_LINES", _("Usage Lines"), line_count, "count", 20)
        self._add_metric("INVENTORY_TOTAL_QTY", _("Total Consumed Quantity"), total_qty, "quantity", 30)
        self._add_metric("INVENTORY_PRODUCTS", _("Distinct Products Consumed"), len(products), "count", 40)

        for usage in usages:
            product_summary = ", ".join(
                usage.line_ids.mapped("product_id.display_name")[:5]
            )
            self._add_detail(
                usage,
                _("Clinical Inventory Usage"),
                event_date=usage.date_usage,
                reference=usage.name,
                state_label=usage.state,
                partner=usage.patient_id,
                quantity=usage.total_qty,
                note=product_summary,
            )

    def _generate_ops_membership(self):
        self.ensure_one()
        Contract = self.env["membership.contract"]
        contracts = Contract.sudo().search(
            self._report_domain(
                "membership.contract",
                "start_date",
                self.date_from,
                self.date_to,
            ),
            order="start_date, id",
        )

        active = contracts.filtered(lambda rec: rec.state == "active")
        expired = contracts.filtered(lambda rec: rec.state == "expired")
        cancelled = contracts.filtered(lambda rec: rec.state == "cancelled")
        contract_value = sum(contracts.mapped("contract_value"))
        savings = sum(contracts.mapped("savings_total"))

        self._add_metric("MEMBERSHIP_CONTRACTS", _("Membership Contracts Started"), len(contracts), "count", 10)
        self._add_metric("MEMBERSHIP_ACTIVE", _("Active"), len(active), "count", 20)
        self._add_metric("MEMBERSHIP_EXPIRED", _("Expired"), len(expired), "count", 30)
        self._add_metric("MEMBERSHIP_CANCELLED", _("Cancelled"), len(cancelled), "count", 40)
        self._add_metric("MEMBERSHIP_VALUE", _("Contract Value"), contract_value, "amount", 50)
        self._add_metric("MEMBERSHIP_SAVINGS", _("Member Savings"), savings, "amount", 60)
        self._state_breakdown_metrics(contracts, "MEMBERSHIP_STATE", 100)

        for contract in contracts:
            self._add_detail(
                contract,
                _("Membership Contract"),
                event_date=contract.start_date,
                reference=contract.name,
                state_label=contract.state,
                partner=contract.partner_id,
                patient=contract.patient_id,
                amount=contract.contract_value,
                note=contract.plan_id.display_name if contract.plan_id else "",
            )

    # Wallet reporting summarizes posted ledger movements only; wallet balances are never rewritten here.
    def _generate_ops_wallet(self):
        self.ensure_one()
        Transaction = self.env["clinic.wallet.transaction"]
        transactions = Transaction.sudo().search(
            self._report_domain(
                "clinic.wallet.transaction",
                "date",
                self.date_from,
                self.date_to,
                extra=[("state", "=", "posted")],
            ),
            order="date, id",
        )

        gross = sum(transactions.mapped("amount"))
        net = sum(transactions.mapped("amount_signed"))
        positive = sum(
            rec.amount_signed
            for rec in transactions
            if rec.amount_signed > 0
        )
        negative = abs(
            sum(
                rec.amount_signed
                for rec in transactions
                if rec.amount_signed < 0
            )
        )

        self._add_metric("WALLET_TX_COUNT", _("Posted Wallet Transactions"), len(transactions), "count", 10)
        self._add_metric("WALLET_GROSS", _("Gross Wallet Movement"), gross, "amount", 20)
        self._add_metric("WALLET_INFLOW", _("Wallet Inflow"), positive, "amount", 30)
        self._add_metric("WALLET_OUTFLOW", _("Wallet Outflow"), negative, "amount", 40)
        self._add_metric("WALLET_NET", _("Net Wallet Movement"), net, "amount", 50)

        type_counts = {}
        for transaction in transactions:
            type_counts[transaction.transaction_type] = (
                type_counts.get(transaction.transaction_type, 0) + 1
            )
        for index, tx_type in enumerate(sorted(type_counts)):
            self._add_metric(
                f"WALLET_TYPE_{tx_type}",
                _("Wallet Type: %s") % tx_type.replace("_", " ").title(),
                type_counts[tx_type],
                "count",
                100 + index,
            )

        for transaction in transactions:
            self._add_detail(
                transaction,
                _("Wallet Transaction"),
                event_date=transaction.date,
                reference=transaction.name,
                state_label=transaction.transaction_type,
                partner=transaction.partner_id,
                amount=transaction.amount_signed,
                note=transaction.note or transaction.reference or "",
            )
