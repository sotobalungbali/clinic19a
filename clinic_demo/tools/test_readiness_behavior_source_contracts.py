"""Execute validation methods with small recordset doubles, without Odoo."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


def method(path, name, namespace):
    tree = ast.parse((ROOT / path).read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


class Rows(list):
    def __getitem__(self, index):
        value = super().__getitem__(index)
        return Rows(value) if isinstance(index, slice) else value

    def __getattr__(self, name):
        if len(self) != 1:
            raise ValueError('Expected singleton')
        return getattr(self[0], name)

    def filtered(self, predicate):
        return Rows(x for x in self if predicate(x))


class ReadinessBehavior(unittest.TestCase):
    def test_missing_checkpoint_is_failure_not_skipped(self):
        generator = SimpleNamespace(key='management.reports', phase='21', sequence=1)
        registry = SimpleNamespace(validate=lambda: None, all=lambda: [generator])
        fn = method('services/validation_service.py', '_validate_registered_generators',
                    {'GENERATOR_REGISTRY': registry})
        service = SimpleNamespace(_result=lambda *args, **kw: args)
        results = fn(service, SimpleNamespace(checkpoint_ids=Rows()))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][4], 'fail')

    def test_report_zero_blocks_and_positive_passes(self):
        fn = method('generators/management/reports.py', 'validate', {
            'REPORT_SPECS': [('FIN-INS', 'definition', 'AUTH_COUNT', True)],
            'REPORT_SOURCE_GAPS': {'FIN-INS': 'clinic.insurance.authorization'},
            'UserError': ValueError, '_': lambda x: x,
        })
        metric = SimpleNamespace(code='AUTH_COUNT', value=0)
        report = SimpleNamespace(state='ready', metric_ids=Rows([metric]), csv_file=b'csv',
                                 detail_ids=Rows(), date_from='2026-01-01', date_to='2026-12-31')
        service = SimpleNamespace(_resolve=lambda *args: report, _validate_source_journeys=lambda *args: None)
        with self.assertRaisesRegex(ValueError, 'source coverage gap'):
            fn(service, None, None)
        metric.value = 1
        self.assertEqual(fn(service, None, None), [])
        report.csv_file = False
        with self.assertRaisesRegex(ValueError, 'metric/CSV'):
            fn(service, None, None)

    def test_revalidation_replaces_stale_evidence(self):
        written = {}
        record = SimpleNamespace(write=lambda values: written.update(values))
        model = SimpleNamespace(search=lambda *args, **kw: record)
        fn = method('services/validation_service.py', '_result', {
            'GENERATOR_VERSION': '19.0.1.0.61',
            'fields': SimpleNamespace(Datetime=SimpleNamespace(now=lambda: 'test-time')),
        })
        service = SimpleNamespace(env={'clinic.demo.validation.result': model})
        fn(service, SimpleNamespace(id=1), 'key', 'runtime', 'info', 'pass', 'Current check passed')
        self.assertIn('19.0.1.0.61', written['expected_value'])
        self.assertIn('test-time', written['actual_value'])
        self.assertEqual(written['state'], 'pass')


if __name__ == '__main__':
    unittest.main()














