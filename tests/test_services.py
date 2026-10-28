import io
from pathlib import Path
import tempfile
import types
import unittest
import pandas as pd
from src.classify_waste import HazardClassification
from src.generate_management_plan import ManagementPlan
from src.services import detect_waste_column, lookup_chemical, process_excel_batch


class FakeResponses:
    def __init__(self):
        self.calls = []
        self.parsed = None

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return types.SimpleNamespace(output_parsed=self.parsed)


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


class TestServices(unittest.TestCase):
    def test_lookup_chemical_success(self):
        client = FakeClient()
        classification = HazardClassification(
            flammable=True,
            carcinogenic=False,
            infectious=False,
            toxic=True,
            corrosive=False,
        )
        plan = ManagementPlan(
            chemical='Methanol',
            identification_and_characterization='HPLC solvent',
            segregation_and_incompatibilities='Separate from oxidizers',
            recommended_container='Safety can',
            labeling_requirements='Flammable Toxic',
            storage_requirements='Flammable cabinet',
            handling_and_ppe='Nitrile gloves',
            spill_and_emergency_management='Absorb with pads',
            treatment_framework='TSDF thermal oxidation',
            final_disposal_framework='High temp incinerator',
            usepa_framework='D001, U154',
            indian_framework='HOWM Schedule I',
            prohibited_or_unsafe_actions='Never pour down drain',
            verification_required='Verify flash point',
        )

        def side_effect(**kwargs):
            if kwargs['text_format'] is HazardClassification:
                return types.SimpleNamespace(output_parsed=classification)
            return types.SimpleNamespace(output_parsed=plan)

        client.responses.parse = side_effect

        dossier = lookup_chemical('Methanol', client=client)

        self.assertEqual(dossier.chemical, 'Methanol')
        self.assertEqual(dossier.bin, 'Flammable Solvents')
        self.assertEqual(dossier.categories, ['Flammable', 'Toxic'])
        self.assertEqual(dossier.container, 'Safety can')
        self.assertEqual(dossier.recommended_container, 'Safety can')
        self.assertEqual(dossier.prohibited, 'Never pour down drain')
        self.assertFalse(dossier.review_required)

    def test_lookup_chemical_graceful_error_handling(self):
        client = FakeClient()

        def failing_parse(**kwargs):
            raise RuntimeError("API connection timeout")

        client.responses.parse = failing_parse

        dossier = lookup_chemical('Mystery Liquid', client=client)

        self.assertEqual(dossier.chemical, 'Mystery Liquid')
        self.assertEqual(dossier.bin, 'Review Queue')
        self.assertTrue(dossier.review_required)
        self.assertIn("API connection timeout", dossier.review_reason)
        self.assertIn("STRICTLY PROHIBITED", dossier.prohibited)
        self.assertIn("Isolate in chemical fume hood", dossier.storage)


class TestBatchIngestionServices(unittest.TestCase):
    def _create_test_excel(self, column_name: str, values: list[str]) -> bytes:
        df = pd.DataFrame({column_name: values})
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        return output.getvalue()

    def test_detect_waste_column_variations(self):
        # 1. Exact match
        df1 = pd.DataFrame({'Hazardous Waste': ['Acetone']})
        self.assertEqual(detect_waste_column(df1), 'Hazardous Waste')

        # 2. Case-insensitive and trimmed
        df2 = pd.DataFrame({'  hazardous waste  ': ['Acetone']})
        self.assertEqual(detect_waste_column(df2), '  hazardous waste  ')

        # 3. Fallback to 'chemical' or 'waste'
        df3 = pd.DataFrame({'Chemical Name': ['Acetone'], 'Quantity': ['1L']})
        self.assertEqual(detect_waste_column(df3), 'Chemical Name')

        # 4. No matching column raises ValueError
        df4 = pd.DataFrame({'Sample ID': [1, 2], 'Location': ['Lab 4', 'Lab 5']})
        with self.assertRaises(ValueError) as ctx:
            detect_waste_column(df4)
        self.assertIn("must contain a 'Hazardous Waste' or 'Chemical' column", str(ctx.exception))

    def test_process_excel_batch_success_and_deduplication(self):
        excel_bytes = self._create_test_excel(
            'Hazardous Waste',
            ['Methanol', ' methanol ', 'METHANOL', 'Hydrochloric Acid', None, '']
        )
        fake_client = FakeClient()
        classification = HazardClassification(
            flammable=True, carcinogenic=False, infectious=False, toxic=True, corrosive=False
        )
        plan = ManagementPlan(
            chemical='test',
            identification_and_characterization='desc',
            segregation_and_incompatibilities='seg',
            recommended_container='can',
            labeling_requirements='lbl',
            storage_requirements='store',
            handling_and_ppe='ppe',
            spill_and_emergency_management='spill',
            treatment_framework='treat',
            final_disposal_framework='disp',
            usepa_framework='epa',
            indian_framework='india',
            prohibited_or_unsafe_actions='prohibited',
            verification_required='ver',
        )

        def side_effect(**kwargs):
            if kwargs['text_format'] is HazardClassification:
                return types.SimpleNamespace(output_parsed=classification)
            return types.SimpleNamespace(output_parsed=plan)

        fake_client.responses.parse = side_effect

        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            result = process_excel_batch(
                excel_bytes,
                'test_inventory.xlsx',
                runs_dir=runs_path,
                client=fake_client
            )

            # Assert deduplication: 2 unique chemicals ('Methanol' and 'Hydrochloric Acid')
            self.assertEqual(result.total_count, 2)
            self.assertEqual(result.filename, 'test_inventory.xlsx')
            self.assertIn('Flammable Solvents', result.bin_counts)

            # Assert local run directory created
            run_folder = runs_path / result.run_id
            self.assertTrue(run_folder.exists())
            self.assertTrue((run_folder / 'input.xlsx').exists())
            self.assertTrue((run_folder / 'meta.json').exists())

    def test_process_excel_batch_exceeds_safeguard_limit(self):
        chemicals = [f"Chemical_{i}" for i in range(51)]
        excel_bytes = self._create_test_excel('Hazardous Waste', chemicals)

        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ValueError) as ctx:
                process_excel_batch(excel_bytes, 'too_large.xlsx', runs_dir=Path(tmp_dir))
            self.assertIn("exceeds limit of 50 unique chemicals", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
