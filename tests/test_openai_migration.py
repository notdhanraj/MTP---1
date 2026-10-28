import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent / 'src'


class FakeResponses:
    def __init__(self):
        self.calls = []
        self.parsed = None

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return types.SimpleNamespace(output_parsed=self.parsed)


class FakeClient:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.responses = FakeResponses()


class TestOpenAIMigration(unittest.TestCase):
    def import_script(self, path, module_name, api_key='test-key'):
        fake_openai = types.ModuleType('openai')
        fake_openai.OpenAI = FakeClient

        orig_openai = sys.modules.get('openai')
        orig_env = os.environ.copy()

        def cleanup():
            if orig_openai is not None:
                sys.modules['openai'] = orig_openai
            else:
                sys.modules.pop('openai', None)
            os.environ.clear()
            os.environ.update(orig_env)

        self.addCleanup(cleanup)

        sys.modules['openai'] = fake_openai
        os.environ['OPENAI_API_KEY'] = api_key
        os.environ.pop('GEMINI_API_KEY', None)

        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_classify_uses_luna_medium_and_pydantic_schema(self):
        module = self.import_script(ROOT / 'classify_waste.py', 'classify_mod')
        expected = module.HazardClassification(
            flammable=True,
            carcinogenic=False,
            infectious=False,
            toxic=True,
            corrosive=False,
        )
        module.client.responses.parsed = expected

        result = module.classify_chemical('Methanol')

        self.assertIs(result, expected)
        call = module.client.responses.calls[-1]
        self.assertEqual(call['model'], 'gpt-6-luna')
        self.assertEqual(call['reasoning'], {'effort': 'medium'})
        self.assertIs(call['text_format'], module.HazardClassification)
        self.assertIn('Methanol', call['input'])
        self.assertNotIn('temperature', call)

    def test_classify_chemical_accepts_explicit_client(self):
        module = self.import_script(ROOT / 'classify_waste.py', 'classify_explicit_mod')
        custom_client = FakeClient()
        expected = module.HazardClassification(
            flammable=True,
            carcinogenic=False,
            infectious=False,
            toxic=False,
            corrosive=False,
        )
        custom_client.responses.parsed = expected

        result = module.classify_chemical('Ethanol', client=custom_client)

        self.assertIs(result, expected)
        self.assertEqual(len(custom_client.responses.calls), 1)
        self.assertIn('Ethanol', custom_client.responses.calls[0]['input'])

    def test_management_plan_uses_luna_medium_and_pydantic_schema(self):
        module = self.import_script(ROOT / 'generate_management_plan.py', 'plan_mod')
        expected = module.ManagementPlan(
            chemical='Methanol',
            identification_and_characterization='x',
            segregation_and_incompatibilities='x',
            recommended_container='x',
            labeling_requirements='x',
            storage_requirements='x',
            handling_and_ppe='x',
            spill_and_emergency_management='x',
            treatment_framework='x',
            final_disposal_framework='x',
            usepa_framework='x',
            indian_framework='x',
            prohibited_or_unsafe_actions='x',
            verification_required='x',
        )
        module.client.responses.parsed = expected

        result = module.make_plan('Methanol', ['Flammable', 'Toxic'])

        self.assertIs(result, expected)
        call = module.client.responses.calls[-1]
        self.assertEqual(call['model'], 'gpt-6-luna')
        self.assertEqual(call['reasoning'], {'effort': 'medium'})
        self.assertIs(call['text_format'], module.ManagementPlan)
        self.assertIn('Methanol', call['input'])
        self.assertIn('Flammable, Toxic', call['input'])
        self.assertNotIn('temperature', call)

    def test_make_plan_accepts_explicit_client(self):
        module = self.import_script(ROOT / 'generate_management_plan.py', 'plan_explicit_mod')
        custom_client = FakeClient()
        expected = module.ManagementPlan(
            chemical='Acetone',
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
            prohibited_or_unsafe_actions='none',
            verification_required='ver',
        )
        custom_client.responses.parsed = expected

        result = module.make_plan('Acetone', ['Flammable'], client=custom_client)

        self.assertIs(result, expected)
        self.assertEqual(len(custom_client.responses.calls), 1)
        self.assertIn('Acetone', custom_client.responses.calls[0]['input'])

    def test_env_loader_does_not_overwrite_existing_value(self):
        module = self.import_script(ROOT / 'classify_waste.py', 'classify_env_mod')
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / '.env'
            env_file.write_text('OPENAI_API_KEY=file-key\n', encoding='utf-8')
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'existing-key'}):
                module.load_env_file(env_file)
                self.assertEqual(os.environ['OPENAI_API_KEY'], 'existing-key')

    def test_management_script_has_same_env_loader_behavior(self):
        module = self.import_script(ROOT / 'generate_management_plan.py', 'plan_env_mod')
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / '.env'
            env_file.write_text('OPENAI_API_KEY="file-key"\n', encoding='utf-8')
            env_copy = os.environ.copy()
            env_copy.pop('OPENAI_API_KEY', None)
            with patch.dict(os.environ, env_copy, clear=True):
                module.load_env_file(env_file)
                self.assertEqual(os.environ['OPENAI_API_KEY'], 'file-key')

    def test_normalize_chemical_name_is_unchanged(self):
        module = self.import_script(ROOT / 'classify_waste.py', 'classify_norm_mod')
        self.assertEqual(module.normalize_chemical_name('  Sodium   Hydroxide  '), 'Sodium Hydroxide')

    def test_unique_chemicals_remain_case_insensitive_and_merge_categories(self):
        module = self.import_script(ROOT / 'generate_management_plan.py', 'plan_unique_mod')
        df = pd.DataFrame({
            'Flammable': ['Methanol', None],
            'Carcinogenic': [None, None],
            'Infectious': [None, None],
            'Toxic': ['methanol', 'Benzene'],
            'Corrosive': [None, None],
        })

        records = module.get_unique_chemicals(df)

        self.assertEqual(records, [
            {'name': 'Methanol', 'categories': ['Flammable', 'Toxic']},
            {'name': 'Benzene', 'categories': ['Toxic']},
        ])

    def test_classification_main_keeps_deduplication_and_excel_shape(self):
        module = self.import_script(ROOT / 'classify_waste.py', 'classify_main_mod')
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_file = tmp_path / 'hazardous.xlsx'
            output_file = tmp_path / 'classified.xlsx'
            pd.DataFrame({
                'Hazardous Waste': ['Methanol', ' methanol ', 'Hydrochloric Acid', None]
            }).to_excel(input_file, index=False)

            answers = {
                'Methanol': module.HazardClassification(
                    flammable=True, carcinogenic=False, infectious=False, toxic=True, corrosive=False
                ),
                'Hydrochloric Acid': module.HazardClassification(
                    flammable=False, carcinogenic=False, infectious=False, toxic=True, corrosive=True
                ),
            }
            calls = []

            def fake_classify(name):
                calls.append(name)
                return answers[name]

            with patch.object(module, 'INPUT_FILE', str(input_file)), \
                 patch.object(module, 'OUTPUT_FILE', str(output_file)), \
                 patch.object(module, 'classify_chemical', fake_classify), \
                 patch.object(module.time, 'sleep', lambda _: None):
                module.main()

            self.assertEqual(calls, ['Methanol', 'Hydrochloric Acid'])
            result = pd.read_excel(output_file, sheet_name='Classification')
            self.assertEqual(list(result.columns), ['Flammable', 'Carcinogenic', 'Infectious', 'Toxic', 'Corrosive'])
            self.assertEqual(result['Flammable'].dropna().tolist(), ['Methanol'])
            self.assertEqual(result['Toxic'].dropna().tolist(), ['Methanol', 'Hydrochloric Acid'])
            self.assertEqual(result['Corrosive'].dropna().tolist(), ['Hydrochloric Acid'])

    def test_management_main_keeps_excel_output_columns(self):
        module = self.import_script(ROOT / 'generate_management_plan.py', 'plan_main_mod')
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_file = tmp_path / 'classified.xlsx'
            output_file = tmp_path / 'management.xlsx'
            pd.DataFrame({
                'Flammable': ['Methanol'],
                'Carcinogenic': [None],
                'Infectious': [None],
                'Toxic': ['Methanol'],
                'Corrosive': [None],
            }).to_excel(input_file, sheet_name='Classification', index=False)

            plan = module.ManagementPlan(
                chemical='Methanol',
                identification_and_characterization='identify',
                segregation_and_incompatibilities='segregate',
                recommended_container='container',
                labeling_requirements='label',
                storage_requirements='store',
                handling_and_ppe='ppe',
                spill_and_emergency_management='spill',
                treatment_framework='treat',
                final_disposal_framework='dispose',
                usepa_framework='usepa',
                indian_framework='india',
                prohibited_or_unsafe_actions='avoid',
                verification_required='verify',
            )

            with patch.object(module, 'INPUT_FILE', str(input_file)), \
                 patch.object(module, 'OUTPUT_FILE', str(output_file)), \
                 patch.object(module, 'make_plan', lambda chemical, categories: plan), \
                 patch.object(module.time, 'sleep', lambda _: None):
                module.main()

            result = pd.read_excel(output_file, sheet_name='Management Plan')
            self.assertEqual(result.loc[0, 'Chemical'], 'Methanol')
            self.assertEqual(result.loc[0, 'Hazard Categories'], 'Flammable, Toxic')
            self.assertEqual(result.loc[0, 'Treatment Framework'], 'treat')
            self.assertEqual(result.loc[0, 'Indian HOWM / CPCB Framework'], 'india')

    def test_missing_parsed_classification_raises_clear_error(self):
        module = self.import_script(ROOT / 'classify_waste.py', 'classify_none_mod')
        module.client.responses.parsed = None
        with self.assertRaises(RuntimeError) as cm:
            module.classify_chemical('Unknown')
        self.assertIn('no parsed classification output', str(cm.exception))

    def test_missing_parsed_management_plan_raises_clear_error(self):
        module = self.import_script(ROOT / 'generate_management_plan.py', 'plan_none_mod')
        module.client.responses.parsed = None
        with self.assertRaises(RuntimeError) as cm:
            module.make_plan('Unknown', ['Toxic'])
        self.assertIn('no parsed management-plan output', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
