# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestQueueStageDomainOdoo19(TransactionCase):
    """Regression for Odoo 19 queue-stage domain parsing."""

    def test_stage_lookup_executes_without_tuple_operator_failure(self):
        Stage = self.env["clinic.queue.stage"]
        stage = Stage.search(
            [
                ("company_id", "=", self.env.company.id),
                ("queue_type", "=", "general"),
                ("active", "=", True),
            ],
            limit=1,
        )
        if stage:
            queue = self.env["clinic.queue"].create(
                {
                    "company_id": self.env.company.id,
                    "queue_type": "general",
                    "channel": "walkin",
                    "stage_id": stage.id,
                }
            )
            queue._find_stage_by_mapped_state("in_progress")
