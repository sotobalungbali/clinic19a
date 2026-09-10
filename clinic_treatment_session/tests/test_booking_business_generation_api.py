# -*- coding: utf-8 -*-
from pathlib import Path
import ast
from odoo.tests.common import TransactionCase

class TestBookingBusinessGenerationAPI(TransactionCase):
    def test_owner_business_api_exists(self):
        Booking = self.env["booking.booking"]
        self.assertTrue(hasattr(Booking, "generate_treatment_sessions"))
        self.assertTrue(hasattr(Booking, "action_generate_treatment_sessions"))

    def test_business_api_has_no_ui_action_access(self):
        path = Path(__file__).resolve().parents[1] / "models/extensions/ext_booking.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        business_node = action_node = None
        for cls in tree.body:
            if isinstance(cls, ast.ClassDef):
                for method in cls.body:
                    if isinstance(method, ast.FunctionDef):
                        if method.name == "generate_treatment_sessions":
                            business_node = method
                        elif method.name == "action_generate_treatment_sessions":
                            action_node = method
        self.assertIsNotNone(business_node)
        self.assertIsNotNone(action_node)
        business = ast.get_source_segment(source, business_node) or ""
        action = ast.get_source_segment(source, action_node) or ""
        self.assertNotIn("action_clinic_treatment_session", business)
        self.assertIn("return created", business)
        self.assertIn("self.generate_treatment_sessions()", action)
        self.assertIn("action_clinic_treatment_session", action)
