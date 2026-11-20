"""Offline contracts of the release. Run: python3 -m unittest test_release -v"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'software/thermal-sweep'))

import audit                                                           # noqa: E402
import extract_ndom                                                    # noqa: E402

RECORDS = extract_ndom.read_csv(HERE / 'software/thermal-sweep/data/project-red-ndom-monthly.csv')

# numbers as printed in the first audit of 19 November 2026 (A14 corrected, see audit.py)
PRINTED = {
    'A1': ['31.97 → 42.66 M gal (+33.4 %)', '346 → 256', '21.2 % → 56.9 %'],
    'A5': ['344 → 332', '24 °F per year'],
    'A6': ['332 → 242', '26.7 → 18.2 M gal (-32 %)', 'July 316 °F at 22.8 M gal'],
    'A9': ['342, 341, 338, 336', '5–11 °F lower'],
    'A10': ['mean of the 18 steady monthly averages is 335'],
    'B1': ['72.7 % by volume (62.5–77.4)', '65.9 % by mass'],
    'B2': ['27.3 %', '26.2 % (2024), 30.7 % (2025), 25.2 % (2026)'],
    'B3': ['+0.2 ± 1.5 points per year by volume', '-0.2 ± 1.4 by mass'],
    'B5': ['28.3, 23.7, 23.3, 23.9, 25.7, 28.4, 27.2, 34.7, 22.7', '27.9 M gal', '2025-09 (37.8 %)'],
    'B6': ['192.9 M gal'],
    'C3': ['106 kg/s', '1,010–1,127 MW', '101–113 MW', '34–38 MW'],
}
VERDICTS = {'A1': 'supported', 'A2': 'contradicted as reservoir cooling', 'A5': 'supported', 'A6': 'supported',
            'A8': 'supported', 'A13': 'supported', 'B2': 'supported (rounded)', 'B4': 'supported'}


class Audit(unittest.TestCase):
    rows = {r['id']: r for r in audit.rows(RECORDS)}

    def test_thirty_three_rows_eighteen_settled(self):
        self.assertEqual(len(self.rows), 33)
        self.assertEqual(audit.settled(list(self.rows.values())), (18, 24))

    def test_printed_numbers_reproduce(self):
        for row_id, fragments in PRINTED.items():
            for fragment in fragments:
                self.assertIn(fragment, self.rows[row_id]['record'], row_id)

    def test_verdicts(self):
        for row_id, verdict in VERDICTS.items():
            self.assertEqual(self.rows[row_id]['verdict'], verdict)
        self.assertTrue(self.rows['A9']['verdict'].startswith('contradicted'))
        self.assertTrue(self.rows['B3']['verdict'].startswith('contradicted to July 2026'))
        self.assertTrue(self.rows['A14']['verdict'].startswith('supported'))

    def test_a_verdict_flips_when_the_record_changes(self):
        changed = [dict(r) for r in RECORDS]
        for r in changed:
            if r['month_end'].startswith('2026-05'):
                r['production_temp_f'] = 343.0
        rows = {r['id']: r for r in audit.rows(changed)}
        self.assertEqual(rows['A5']['verdict'], 'contradicted')

    def test_every_row_has_rule_and_basis(self):
        for r in self.rows.values():
            self.assertTrue(r['verdict_rule'] and r['basis'] in ('workbook', 'arithmetic', 'document'), r['id'])


class Package(unittest.TestCase):
    def test_copied_sources_are_byte_identical_to_the_registered_manifests(self):
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        sweep = json.loads((HERE / 'registered/thermal-sweep/manifest.json').read_text())['sources']
        for name in ('fieldmodel.py', 'sweep.py', 'extract_ndom.py', 'scoring.py', 'svgchart.py', 'data/SOURCES.json', 'data/project-red-ndom-monthly.csv'):
            self.assertEqual(digest(HERE / 'software/thermal-sweep' / name), sweep[name], name)
        water = json.loads((HERE / 'registered/water-retention/manifest.json').read_text())['sources']
        self.assertEqual(digest(HERE / 'software/water-retention/retention.py'), water['retention.py'])

    def test_offline_run_passes_its_checks_without_site_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = subprocess.run([sys.executable, '-I', '-S', str(HERE / 'reproduce.py'), '--offline', '--out', tmp],
                                  capture_output=True, text=True, timeout=120)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            result = json.loads((Path(tmp) / 'results.json').read_text())
            self.assertTrue(result['all_checks_pass'])
            self.assertAlmostEqual(result['fit']['rmse_f']['value'], 0.5085, places=3)
            for block in ('fit', 'water'):
                for value in result[block].values():
                    if isinstance(value, dict) and 'value' in value:
                        self.assertTrue(value['label'] and value['unit'])


if __name__ == '__main__':
    unittest.main()
