import io
import json
from pathlib import Path
import tempfile
import types
import unittest
import pandas as pd
from src.classify_waste import HazardClassification
from src.generate_management_plan import ManagementPlan
from src.services import (
    detect_waste_column,
    initialize_batch_run,
    lookup_chemical,
    process_excel_batch,
    remediate_batch_item,
    stream_batch_events,
    generate_batch_excel,
    list_runs,
    get_run_details,
)


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

    def test_initialize_batch_run_creates_run_dir_and_meta(self):
        excel_bytes = self._create_test_excel('Hazardous Waste', ['Methanol', 'Acetone'])
        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            queued = initialize_batch_run(
                excel_bytes,
                'test.xlsx',
                pause_after_classification=True,
                runs_dir=runs_path
            )
            self.assertEqual(queued.total_count, 2)
            self.assertTrue(queued.pause_after_classification)
            self.assertEqual(queued.status, "queued")

            run_folder = runs_path / queued.run_id
            self.assertTrue(run_folder.exists())
            self.assertTrue((run_folder / 'input.xlsx').exists())
            self.assertTrue((run_folder / 'meta.json').exists())

            with open(run_folder / 'meta.json', 'r', encoding='utf-8') as f:
                meta = json.load(f)
            self.assertEqual(meta['status'], 'queued')
            self.assertEqual(meta['chemicals'], ['Methanol', 'Acetone'])
            self.assertTrue(meta['pause_after_classification'])
            self.assertEqual(meta['total_count'], 2)
            self.assertIn('Flammable Solvents', meta['bin_counts'])
            self.assertEqual(meta['bin_counts']['Flammable Solvents'], 0)
            self.assertEqual(meta['classifications'], {})
            self.assertEqual(meta['dossiers'], {})

    def test_stream_batch_events_full_flow_straight_through(self):
        excel_bytes = self._create_test_excel('Hazardous Waste', ['Methanol'])
        fake_client = FakeClient()
        classification = HazardClassification(
            flammable=True, carcinogenic=False, infectious=False, toxic=False, corrosive=False
        )
        plan = ManagementPlan(
            chemical='Methanol',
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
            queued = initialize_batch_run(
                excel_bytes, 'test.xlsx', pause_after_classification=False, runs_dir=runs_path
            )

            events = list(stream_batch_events(queued.run_id, runs_dir=runs_path, client=fake_client))
            event_types = [e['type'] for e in events]

            # Straight-through sequence: stage_start(classification) -> item_progress -> stage_complete -> stage_start(planning) -> item_progress -> complete
            self.assertIn('stage_start', event_types)
            self.assertIn('stage_complete', event_types)
            self.assertIn('complete', event_types)
            self.assertNotIn('stage_paused', event_types)

            # Check final complete event
            complete_event = [e for e in events if e['type'] == 'complete'][0]
            self.assertEqual(complete_event['total_count'], 1)
            self.assertIn('Flammable Solvents', complete_event['bin_counts'])
            self.assertEqual(len(complete_event['items']), 1)
            self.assertEqual(complete_event['items'][0]['chemical'], 'Methanol')

            # Verify meta.json updated to completed
            meta_path = runs_path / queued.run_id / 'meta.json'
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_completed = json.load(f)
            self.assertEqual(meta_completed['status'], 'completed')
            self.assertIn('Methanol', meta_completed['dossiers'])

    def test_stream_batch_events_pause_and_resumption(self):
        excel_bytes = self._create_test_excel('Hazardous Waste', ['Methanol'])
        fake_client = FakeClient()
        classification = HazardClassification(
            flammable=True, carcinogenic=False, infectious=False, toxic=False, corrosive=False
        )
        plan = ManagementPlan(
            chemical='Methanol',
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
            queued = initialize_batch_run(
                excel_bytes, 'test.xlsx', pause_after_classification=True, runs_dir=runs_path
            )

            # Stream Stage 1 (Classification)
            stage1_events = list(stream_batch_events(queued.run_id, runs_dir=runs_path, client=fake_client))
            stage1_types = [e['type'] for e in stage1_events]
            self.assertIn('stage_paused', stage1_types)
            self.assertNotIn('complete', stage1_types)

            # Check meta.json reflects paused_for_review
            meta_path = runs_path / queued.run_id / 'meta.json'
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            self.assertEqual(meta['status'], 'paused_for_review')
            self.assertIn('Methanol', meta['classifications'])
            self.assertNotIn('Methanol', meta.get('dossiers', {}))

            # Stream Stage 2 (Planning Resume)
            stage2_events = list(stream_batch_events(queued.run_id, stage='planning', runs_dir=runs_path, client=fake_client))
            stage2_types = [e['type'] for e in stage2_events]
            self.assertIn('stage_start', stage2_types)
            self.assertIn('complete', stage2_types)

            # Verify meta.json updated to completed
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_completed = json.load(f)
            self.assertEqual(meta_completed['status'], 'completed')
            self.assertIn('Methanol', meta_completed['dossiers'])

    def test_stream_batch_events_chemical_error_fallback(self):
        excel_bytes = self._create_test_excel('Hazardous Waste', ['FaultyChem', 'ValidChem'])
        fake_client = FakeClient()
        valid_classification = HazardClassification(
            flammable=True, carcinogenic=False, infectious=False, toxic=False, corrosive=False
        )
        valid_plan = ManagementPlan(
            chemical='ValidChem',
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
            inp = kwargs.get('input', '')
            if 'FaultyChem' in inp:
                raise RuntimeError("LLM failure for FaultyChem")
            if kwargs['text_format'] is HazardClassification:
                return types.SimpleNamespace(output_parsed=valid_classification)
            return types.SimpleNamespace(output_parsed=valid_plan)

        fake_client.responses.parse = side_effect

        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            queued = initialize_batch_run(
                excel_bytes, 'test_fallback.xlsx', pause_after_classification=False, runs_dir=runs_path
            )

            events = list(stream_batch_events(queued.run_id, runs_dir=runs_path, client=fake_client))
            event_types = [e['type'] for e in events]
            self.assertIn('complete', event_types)

            complete_event = [e for e in events if e['type'] == 'complete'][0]
            self.assertEqual(complete_event['total_count'], 2)
            self.assertEqual(complete_event['bin_counts']['Review Queue'], 1)
            self.assertEqual(complete_event['bin_counts']['Flammable Solvents'], 1)

            # FaultyChem dossier is fallback
            faulty_dossier = [item for item in complete_event['items'] if item['chemical'] == 'FaultyChem'][0]
            self.assertEqual(faulty_dossier['bin'], 'Review Queue')
            self.assertTrue(faulty_dossier['review_required'])

            # ValidChem dossier is normal
            valid_dossier = [item for item in complete_event['items'] if item['chemical'] == 'ValidChem'][0]
            self.assertEqual(valid_dossier['bin'], 'Flammable Solvents')
            self.assertFalse(valid_dossier['review_required'])

    def test_remediate_batch_item_success(self):
        fake_client = FakeClient()
        classification = HazardClassification(
            flammable=True, carcinogenic=False, infectious=False, toxic=False, corrosive=False
        )
        plan = ManagementPlan(
            chemical='Acetone',
            identification_and_characterization='Ketone solvent',
            segregation_and_incompatibilities='Keep away from oxidizers',
            recommended_container='Safety can',
            labeling_requirements='FLAMMABLE',
            storage_requirements='Flammables cabinet',
            handling_and_ppe='Nitrile gloves',
            spill_and_emergency_management='Absorb with vermiculite',
            treatment_framework='Thermal oxidation',
            final_disposal_framework='Incineration at TSDF',
            usepa_framework='D001',
            indian_framework='HOWM Schedule II',
            prohibited_or_unsafe_actions='No drain disposal',
            verification_required='Verify flash point',
        )
        def side_effect(**kwargs):
            if kwargs['text_format'] is HazardClassification:
                return types.SimpleNamespace(output_parsed=classification)
            return types.SimpleNamespace(output_parsed=plan)
        fake_client.responses.parse = side_effect

        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            run_id = "test_remediation_run"
            run_folder = runs_path / run_id
            run_folder.mkdir(parents=True, exist_ok=True)

            initial_meta = {
                "run_id": run_id,
                "filename": "test.xlsx",
                "chemicals": ["Mystery Liquid", "Toluene"],
                "status": "completed",
                "bin_counts": {
                    "Flammable Solvents": 1,
                    "Inorganic Acids": 0,
                    "Inorganic Bases": 0,
                    "Carcinogenic & Toxic Organics": 0,
                    "Biohazard & Infectious": 0,
                    "Review Queue": 1,
                },
                "classifications": {
                    "Mystery Liquid": {"classification": {}, "bin": "Review Queue"},
                    "Toluene": {"classification": {"flammable": True}, "bin": "Flammable Solvents"}
                },
                "dossiers": {
                    "Mystery Liquid": {
                        "chemical": "Mystery Liquid",
                        "flammable": False,
                        "carcinogenic": False,
                        "infectious": False,
                        "toxic": False,
                        "corrosive": False,
                        "segregation_bin": "Review Queue",
                        "identification": "",
                        "segregation": "",
                        "container": "",
                        "labeling": "",
                        "storage": "",
                        "ppe": "",
                        "spill": "",
                        "treatment": "",
                        "disposal": "",
                        "usepa": "",
                        "india": "",
                        "prohibited": "",
                        "verification": "",
                        "review_required": True,
                        "review_reason": "API timeout"
                    },
                    "Toluene": {
                        "chemical": "Toluene",
                        "flammable": True,
                        "carcinogenic": False,
                        "infectious": False,
                        "toxic": False,
                        "corrosive": False,
                        "segregation_bin": "Flammable Solvents",
                        "identification": "",
                        "segregation": "",
                        "container": "",
                        "labeling": "",
                        "storage": "",
                        "ppe": "",
                        "spill": "",
                        "treatment": "",
                        "disposal": "",
                        "usepa": "",
                        "india": "",
                        "prohibited": "",
                        "verification": "",
                        "review_required": False,
                        "review_reason": None
                    }
                },
                "remediated_from": {}
            }
            with open(run_folder / "meta.json", "w", encoding="utf-8") as f:
                json.dump(initial_meta, f, indent=2)

            dossier, bin_counts = remediate_batch_item(
                run_id=run_id,
                original_name="Mystery Liquid",
                new_name="Acetone",
                runs_dir=runs_path,
                client=fake_client
            )

            self.assertEqual(dossier.chemical, "Acetone")
            self.assertFalse(dossier.review_required)
            self.assertEqual(dossier.segregation_bin, "Flammable Solvents")
            self.assertEqual(bin_counts["Review Queue"], 0)
            self.assertEqual(bin_counts["Flammable Solvents"], 2)

            with open(run_folder / "meta.json", "r", encoding="utf-8") as f:
                meta = json.load(f)
            self.assertIn("Acetone", meta["chemicals"])
            self.assertNotIn("Mystery Liquid", meta["chemicals"])
            self.assertEqual(meta["remediated_from"]["Acetone"], "Mystery Liquid")

    def test_remediate_batch_item_collision_guard(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            run_id = "collision_run"
            run_folder = runs_path / run_id
            run_folder.mkdir(parents=True, exist_ok=True)

            meta = {
                "run_id": run_id,
                "chemicals": ["Mystery Liquid", "Acetone"],
                "dossiers": {"Mystery Liquid": {}, "Acetone": {}},
                "bin_counts": {}
            }
            with open(run_folder / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f)

            with self.assertRaises(ValueError) as ctx:
                remediate_batch_item(
                    run_id=run_id,
                    original_name="Mystery Liquid",
                    new_name="Acetone",
                    runs_dir=runs_path
                )
            self.assertIn("already present in this batch", str(ctx.exception))

    def test_remediate_batch_item_empty_name(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            run_id = "empty_run"
            run_folder = runs_path / run_id
            run_folder.mkdir(parents=True, exist_ok=True)

            meta = {
                "run_id": run_id,
                "chemicals": ["Mystery Liquid"],
                "dossiers": {"Mystery Liquid": {}},
                "bin_counts": {}
            }
            with open(run_folder / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f)

            with self.assertRaises(ValueError) as ctx:
                remediate_batch_item(
                    run_id=run_id,
                    original_name="Mystery Liquid",
                    new_name="   ",
                    runs_dir=runs_path
                )
            self.assertIn("Chemical name cannot be empty", str(ctx.exception))

    def test_remediate_batch_item_run_not_found(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            with self.assertRaises(FileNotFoundError):
                remediate_batch_item(
                    run_id="non_existent_run",
                    original_name="Mystery Liquid",
                    new_name="Acetone",
                    runs_dir=runs_path
                )

    def test_remediate_batch_item_chemical_not_found(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            run_id = "chem_not_found_run"
            run_folder = runs_path / run_id
            run_folder.mkdir(parents=True, exist_ok=True)

            meta = {
                "run_id": run_id,
                "chemicals": ["Toluene"],
                "dossiers": {"Toluene": {}},
                "bin_counts": {}
            }
            with open(run_folder / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f)

            with self.assertRaises(ValueError) as ctx:
                remediate_batch_item(
                    run_id=run_id,
                    original_name="Ghost Chemical",
                    new_name="Acetone",
                    runs_dir=runs_path
                )
            self.assertIn("Ghost Chemical", str(ctx.exception))

    def test_remediate_batch_item_same_name_retry(self):
        fake_client = FakeClient()
        classification = HazardClassification(
            flammable=True, carcinogenic=False, infectious=False, toxic=False, corrosive=False
        )
        plan = ManagementPlan(
            chemical='Acetone',
            identification_and_characterization='Ketone solvent',
            segregation_and_incompatibilities='Keep away from oxidizers',
            recommended_container='Safety can',
            labeling_requirements='FLAMMABLE',
            storage_requirements='Flammables cabinet',
            handling_and_ppe='Nitrile gloves',
            spill_and_emergency_management='Absorb with vermiculite',
            treatment_framework='Thermal oxidation',
            final_disposal_framework='Incineration at TSDF',
            usepa_framework='D001',
            indian_framework='HOWM Schedule II',
            prohibited_or_unsafe_actions='No drain disposal',
            verification_required='Verify flash point',
        )
        def side_effect(**kwargs):
            if kwargs['text_format'] is HazardClassification:
                return types.SimpleNamespace(output_parsed=classification)
            return types.SimpleNamespace(output_parsed=plan)
        fake_client.responses.parse = side_effect

        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            run_id = "same_name_run"
            run_folder = runs_path / run_id
            run_folder.mkdir(parents=True, exist_ok=True)

            meta = {
                "run_id": run_id,
                "chemicals": ["Acetone"],
                "dossiers": {"Acetone": {"review_required": True, "bin": "Review Queue", "segregation_bin": "Review Queue"}},
                "bin_counts": {"Review Queue": 1}
            }
            with open(run_folder / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f)

            dossier, bin_counts = remediate_batch_item(
                run_id=run_id,
                original_name="Acetone",
                new_name="Acetone",
                runs_dir=runs_path,
                client=fake_client
            )
            self.assertEqual(dossier.chemical, "Acetone")
            self.assertFalse(dossier.review_required)
            self.assertEqual(bin_counts["Flammable Solvents"], 1)
            self.assertEqual(bin_counts["Review Queue"], 0)



class TestBatchExcelExportAndRunHistoryServices(unittest.TestCase):
    def test_generate_batch_excel_creates_3_sheet_workbook(self):
        import openpyxl

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            run_id = "test_run_excel"
            run_dir = tmp_path / run_id
            run_dir.mkdir(parents=True)

            meta_data = {
                "run_id": run_id,
                "filename": "lab_chemicals.xlsx",
                "timestamp": "2026-10-29T10:00:00",
                "status": "completed",
                "chemicals": ["Methanol", "Hydrochloric Acid", "Mystery Chem"],
                "bin_counts": {
                    "Flammable Solvents": 1,
                    "Inorganic Acids": 1,
                    "Review Queue": 1,
                },
                "classifications": {
                    "Methanol": {"categories": ["Flammable", "Toxic"], "bin": "Flammable Solvents"},
                    "Hydrochloric Acid": {"categories": ["Corrosive"], "bin": "Inorganic Acids"},
                    "Mystery Chem": {"categories": [], "bin": "Review Queue"},
                },
                "dossiers": {
                    "Methanol": {
                        "chemical": "Methanol",
                        "bin": "Flammable Solvents",
                        "categories": ["Flammable", "Toxic"],
                        "container": "Glass Bottle",
                        "storage": "Flammables cabinet",
                        "ppe": "Nitrile gloves",
                        "segregation": "Keep away from oxidizers",
                        "labeling": "Flammable Liquid",
                        "spill": "Absorb with inert pads",
                        "identification": "Solvent waste",
                        "prohibited": "Do not pour down drain",
                        "verification": "Check pH",
                        "usepa": "D001",
                        "india": "Schedule II",
                        "treatment": "Incineration",
                        "disposal": "Authorized TSDF",
                        "review_required": False,
                    },
                    "Hydrochloric Acid": {
                        "chemical": "Hydrochloric Acid",
                        "bin": "Inorganic Acids",
                        "categories": ["Corrosive"],
                        "container": "Acid-resistant HDPE container",
                        "storage": "Dedicated acid locker",
                        "ppe": "Acid apron and faceshield",
                        "segregation": "Isolate from bases and cyanide",
                        "labeling": "Corrosive Acid Waste",
                        "spill": "Neutralize with sodium bicarbonate",
                        "identification": "Mineral acid stream",
                        "prohibited": "Do not mix with flammables",
                        "verification": "Test with pH paper",
                        "usepa": "D002",
                        "india": "Schedule II",
                        "treatment": "Neutralization",
                        "disposal": "Permitted facility",
                        "review_required": False,
                    },
                    "Mystery Chem": {
                        "chemical": "Mystery Chem",
                        "bin": "Review Queue",
                        "categories": [],
                        "container": "Secondary containment bin",
                        "storage": "Quarantine bench",
                        "ppe": "Standard PPE",
                        "segregation": "Do not mix",
                        "labeling": "Unidentified Chemical",
                        "spill": "Contain immediately",
                        "identification": "Unknown compound",
                        "prohibited": "Do not discard",
                        "verification": "EHS Characterization required",
                        "usepa": "Pending",
                        "india": "Pending",
                        "treatment": "Hold for testing",
                        "disposal": "Hold for testing",
                        "review_required": True,
                        "review_reason": "Classification failed or requires human review",
                    },
                },
            }

            with open(run_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta_data, f, indent=2)

            excel_path = generate_batch_excel(run_id, runs_dir=tmp_path)
            self.assertTrue(excel_path.exists())
            self.assertEqual(excel_path.name, "output.xlsx")

            wb = openpyxl.load_workbook(excel_path)
            self.assertEqual(wb.sheetnames, ["Management Plan", "Classification", "Review Required"])

            ws_mp = wb["Management Plan"]
            headers = [cell.value for cell in ws_mp[1]]
            self.assertEqual(len(headers), 14)
            self.assertEqual(headers[0], "Chemical")
            self.assertEqual(headers[1], "Recommended Container")
            self.assertEqual(headers[13], "Verification Required")
            self.assertEqual(ws_mp.max_row, 4)  # header + 3 chemicals

            ws_clf = wb["Classification"]
            clf_headers = [cell.value for cell in ws_clf[1]]
            self.assertEqual(clf_headers, ["Flammable", "Carcinogenic", "Infectious", "Toxic", "Corrosive"])

            ws_rev = wb["Review Required"]
            rev_headers = [cell.value for cell in ws_rev[1]]
            self.assertEqual(rev_headers, ["Chemical", "Review Reason"])
            self.assertEqual(ws_rev.max_row, 2)  # header + Mystery Chem
            self.assertEqual(ws_rev.cell(row=2, column=1).value, "Mystery Chem")

    def test_list_runs_and_get_run_details(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            run_id = "run_2026-10-29_090000"
            run_dir = tmp_path / run_id
            run_dir.mkdir(parents=True)

            meta_data = {
                "run_id": run_id,
                "filename": "inventory.xlsx",
                "timestamp": "2026-10-29T09:00:00",
                "status": "completed",
                "total_count": 1,
                "chemicals": ["Methanol"],
                "bin_counts": {"Flammable Solvents": 1},
                "dossiers": {
                    "Methanol": {
                        "chemical": "Methanol",
                        "bin": "Flammable Solvents",
                        "categories": ["Flammable"],
                        "container": "Glass Bottle",
                        "storage": "Cabinet",
                        "ppe": "Gloves",
                        "segregation": "Separate",
                        "labeling": "Flammable",
                        "spill": "Pads",
                        "identification": "Solvent",
                        "prohibited": "Drain",
                        "verification": "None",
                        "usepa": "D001",
                        "india": "Sched II",
                        "treatment": "Incineration",
                        "disposal": "TSDF",
                    }
                },
            }
            with open(run_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta_data, f, indent=2)

            runs = list_runs(runs_dir=tmp_path)
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["run_id"], run_id)
            self.assertEqual(runs[0]["filename"], "inventory.xlsx")
            self.assertEqual(runs[0]["total_count"], 1)

            details = get_run_details(run_id, runs_dir=tmp_path)
            self.assertEqual(details.run_id, run_id)
            self.assertEqual(len(details.items), 1)
            self.assertEqual(details.items[0].chemical, "Methanol")

    def test_generate_batch_excel_errors(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Run not found
            with self.assertRaises(FileNotFoundError):
                generate_batch_excel("nonexistent_run", runs_dir=tmp_path)

            # Run in progress
            in_progress_dir = tmp_path / "in_progress_run"
            in_progress_dir.mkdir()
            with open(in_progress_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump({"status": "classifying"}, f)

            with self.assertRaises(ValueError) as ctx:
                generate_batch_excel("in_progress_run", runs_dir=tmp_path)
            self.assertIn("still in progress", str(ctx.exception))

    def test_list_runs_nonexistent_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "missing_folder"
            self.assertEqual(list_runs(runs_dir=tmp_path), [])

    def test_stream_batch_events_creates_output_excel(self):
        fake_client = FakeClient()
        classification = HazardClassification(
            flammable=True, carcinogenic=False, infectious=False, toxic=False, corrosive=False
        )
        plan = ManagementPlan(
            chemical='Ethanol',
            identification_and_characterization='Alcohol solvent',
            segregation_and_incompatibilities='Keep away from oxidizers',
            recommended_container='Glass Bottle',
            labeling_requirements='FLAMMABLE',
            storage_requirements='Flammables cabinet',
            handling_and_ppe='Nitrile gloves',
            spill_and_emergency_management='Absorb with pads',
            treatment_framework='Thermal oxidation',
            final_disposal_framework='Incineration at TSDF',
            usepa_framework='D001',
            indian_framework='HOWM Schedule II',
            prohibited_or_unsafe_actions='No drain disposal',
            verification_required='Verify flash point',
        )
        def side_effect(**kwargs):
            if kwargs['text_format'] is HazardClassification:
                return types.SimpleNamespace(output_parsed=classification)
            return types.SimpleNamespace(output_parsed=plan)
        fake_client.responses.parse = side_effect

        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            df = pd.DataFrame({"Hazardous Waste": ["Ethanol"]})
            excel_bytes = io.BytesIO()
            df.to_excel(excel_bytes, index=False)
            excel_bytes = excel_bytes.getvalue()

            queued = initialize_batch_run(
                excel_bytes, 'test_ethanol.xlsx', pause_after_classification=False, runs_dir=runs_path
            )

            events = list(stream_batch_events(queued.run_id, runs_dir=runs_path, client=fake_client))
            complete_event = [e for e in events if e['type'] == 'complete']
            self.assertTrue(len(complete_event) > 0)

            excel_path = runs_path / queued.run_id / "output.xlsx"
            self.assertTrue(excel_path.exists())

    def test_remediate_batch_item_refreshes_output_excel(self):
        fake_client = FakeClient()
        classification = HazardClassification(
            flammable=True, carcinogenic=False, infectious=False, toxic=False, corrosive=False
        )
        plan = ManagementPlan(
            chemical='Acetone',
            identification_and_characterization='Ketone solvent',
            segregation_and_incompatibilities='Keep away from oxidizers',
            recommended_container='Safety can',
            labeling_requirements='FLAMMABLE',
            storage_requirements='Flammables cabinet',
            handling_and_ppe='Nitrile gloves',
            spill_and_emergency_management='Absorb with pads',
            treatment_framework='Thermal oxidation',
            final_disposal_framework='Incineration at TSDF',
            usepa_framework='D001',
            indian_framework='HOWM Schedule II',
            prohibited_or_unsafe_actions='No drain disposal',
            verification_required='Verify flash point',
        )
        def side_effect(**kwargs):
            if kwargs['text_format'] is HazardClassification:
                return types.SimpleNamespace(output_parsed=classification)
            return types.SimpleNamespace(output_parsed=plan)
        fake_client.responses.parse = side_effect

        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            run_id = "remediate_excel_test"
            run_folder = runs_path / run_id
            run_folder.mkdir(parents=True, exist_ok=True)

            meta = {
                "run_id": run_id,
                "chemicals": ["Unknown"],
                "status": "completed",
                "dossiers": {
                    "Unknown": {
                        "chemical": "Unknown",
                        "review_required": True,
                        "bin": "Review Queue",
                        "segregation_bin": "Review Queue",
                        "container": "Bottle",
                        "storage": "Hood",
                        "ppe": "Gloves",
                        "segregation": "None",
                        "labeling": "Unknown",
                        "spill": "Absorb",
                        "identification": "Unknown",
                        "prohibited": "None",
                        "verification": "Check",
                        "usepa": "None",
                        "india": "None",
                        "treatment": "None",
                        "disposal": "None",
                    }
                },
                "bin_counts": {"Review Queue": 1}
            }
            with open(run_folder / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f)

            generate_batch_excel(run_id, runs_dir=runs_path)
            excel_path = run_folder / "output.xlsx"
            self.assertTrue(excel_path.exists())

            # Remediate item
            remediate_batch_item(
                run_id=run_id,
                original_name="Unknown",
                new_name="Acetone",
                runs_dir=runs_path,
                client=fake_client
            )

            # Check that output.xlsx was updated
            import openpyxl
            wb = openpyxl.load_workbook(excel_path)
            ws_mp = wb["Management Plan"]
            self.assertEqual(ws_mp.cell(row=2, column=1).value, "Acetone")
            ws_rev = wb["Review Required"]
            self.assertEqual(ws_rev.max_row, 1)  # Only header remaining!

    def test_generate_classification_excel_creates_2_sheet_workbook(self):
        from src.services import generate_classification_excel
        import openpyxl

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            run_id = "test_run_clf_excel"
            run_dir = tmp_path / run_id
            run_dir.mkdir(parents=True)

            meta_data = {
                "run_id": run_id,
                "filename": "lab_chemicals.xlsx",
                "timestamp": "2026-10-29T10:00:00",
                "status": "paused_for_review",
                "chemicals": ["Methanol", "Hydrochloric Acid", "Mystery Chem"],
                "bin_counts": {
                    "Flammable Solvents": 1,
                    "Inorganic Acids": 1,
                    "Review Queue": 1,
                },
                "classifications": {
                    "Methanol": {"categories": ["Flammable", "Toxic"], "bin": "Flammable Solvents"},
                    "Hydrochloric Acid": {"categories": ["Corrosive"], "bin": "Inorganic Acids"},
                    "Mystery Chem": {"categories": [], "bin": "Review Queue", "review_reason": "Ambiguous chemical"},
                },
            }

            with open(run_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta_data, f, indent=2)

            excel_path = generate_classification_excel(run_id, runs_dir=tmp_path)
            self.assertTrue(excel_path.exists())
            self.assertEqual(excel_path.name, "classified.xlsx")

            wb = openpyxl.load_workbook(excel_path)
            self.assertEqual(wb.sheetnames, ["Classification", "Review Required"])

            ws_clf = wb["Classification"]
            clf_headers = [cell.value for cell in ws_clf[1]]
            self.assertEqual(clf_headers, ["Flammable", "Carcinogenic", "Infectious", "Toxic", "Corrosive"])

            ws_rev = wb["Review Required"]
            rev_headers = [cell.value for cell in ws_rev[1]]
            self.assertEqual(rev_headers, ["Chemical", "Review Reason"])
            self.assertEqual(ws_rev.max_row, 2)
            self.assertEqual(ws_rev.cell(row=2, column=1).value, "Mystery Chem")

    def test_generate_classification_excel_errors(self):
        from src.services import generate_classification_excel

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with self.assertRaises(FileNotFoundError):
                generate_classification_excel("non_existent_run", runs_dir=tmp_path)

            empty_run = tmp_path / "empty_run"
            empty_run.mkdir()
            with open(empty_run / "meta.json", "w", encoding="utf-8") as f:
                json.dump({"run_id": "empty_run", "status": "queued"}, f)

            with self.assertRaises(ValueError):
                generate_classification_excel("empty_run", runs_dir=tmp_path)


if __name__ == '__main__':
    unittest.main()

