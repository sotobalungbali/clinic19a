from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class TestClinicBranchSourceContracts(unittest.TestCase):
    def test_odoo19_constraint_api(self):
        branch = (ROOT / "models/branch.py").read_text()
        location = (ROOT / "models/branch_location.py").read_text()
        self.assertNotIn("_sql_constraints", branch)
        self.assertNotIn("_sql_constraints", location)
        self.assertIn("models.Constraint", branch)
        self.assertIn("models.Constraint", location)

    def test_branch_contracts_preserved(self):
        self.assertIn("_name = 'clinic.branch'", (ROOT / "models/branch.py").read_text())
        users = (ROOT / "models/res_users_inherit.py").read_text()
        self.assertIn("allowed_branch_ids = fields.Many2many", users)
        self.assertIn("working_branch_id = fields.Many2one", users)

    def test_search_views_exist(self):
        self.assertIn("<search", (ROOT / "views/branch_views.xml").read_text())
        self.assertIn("<search", (ROOT / "views/branch_location_views.xml").read_text())

if __name__ == "__main__":
    unittest.main()
