import importlib.util
import os
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path('/mnt/data')


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


def import_script(path, module_name, monkeypatch, api_key='test-key'):
    fake_openai = types.ModuleType('openai')
    fake_openai.OpenAI = FakeClient
    monkeypatch.setitem(sys.modules, 'openai', fake_openai)
    monkeypatch.setenv('OPENAI_API_KEY', api_key)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)

    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_classify_uses_luna_medium_and_pydantic_schema(monkeypatch):
    module = import_script(ROOT / 'classify_waste.py', 'classify_mod', monkeypatch)
    expected = module.HazardClassification(
        flammable=True,
        carcinogenic=False,
        infectious=False,
        toxic=True,
        corrosive=False,
    )
    module.client.responses.parsed = expected

    result = module.classify_chemical('Methanol')

    assert result is expected
    call = module.client.responses.calls[-1]
    assert call['model'] == 'gpt-6-luna'
    assert call['reasoning'] == {'effort': 'medium'}
    assert call['text_format'] is module.HazardClassification
    assert 'Methanol' in call['input']
    assert 'temperature' not in call


def test_management_plan_uses_luna_medium_and_pydantic_schema(monkeypatch):
    module = import_script(ROOT / 'generate_management_plan.py', 'plan_mod', monkeypatch)
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

    assert result is expected
    call = module.client.responses.calls[-1]
    assert call['model'] == 'gpt-6-luna'
    assert call['reasoning'] == {'effort': 'medium'}
    assert call['text_format'] is module.ManagementPlan
    assert 'Methanol' in call['input']
    assert 'Flammable, Toxic' in call['input']
    assert 'temperature' not in call


def test_env_loader_does_not_overwrite_existing_value(monkeypatch, tmp_path):
    module = import_script(ROOT / 'classify_waste.py', 'classify_env_mod', monkeypatch)
    env_file = tmp_path / '.env'
    env_file.write_text('OPENAI_API_KEY=file-key\n', encoding='utf-8')
    monkeypatch.setenv('OPENAI_API_KEY', 'existing-key')

    module.load_env_file(env_file)

    assert os.environ['OPENAI_API_KEY'] == 'existing-key'


def test_management_script_has_same_env_loader_behavior(monkeypatch, tmp_path):
    module = import_script(ROOT / 'generate_management_plan.py', 'plan_env_mod', monkeypatch)
    env_file = tmp_path / '.env'
    env_file.write_text('OPENAI_API_KEY="file-key"\n', encoding='utf-8')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)

    module.load_env_file(env_file)

    assert os.environ['OPENAI_API_KEY'] == 'file-key'


def test_normalize_chemical_name_is_unchanged(monkeypatch):
    module = import_script(ROOT / 'classify_waste.py', 'classify_norm_mod', monkeypatch)
    assert module.normalize_chemical_name('  Sodium   Hydroxide  ') == 'Sodium Hydroxide'


def test_unique_chemicals_remain_case_insensitive_and_merge_categories(monkeypatch):
    module = import_script(ROOT / 'generate_management_plan.py', 'plan_unique_mod', monkeypatch)
    df = pd.DataFrame({
        'Flammable': ['Methanol', None],
        'Carcinogenic': [None, None],
        'Infectious': [None, None],
        'Toxic': ['methanol', 'Benzene'],
        'Corrosive': [None, None],
    })

    records = module.get_unique_chemicals(df)

    assert records == [
        {'name': 'Methanol', 'categories': ['Flammable', 'Toxic']},
        {'name': 'Benzene', 'categories': ['Toxic']},
    ]


def test_classification_main_keeps_deduplication_and_excel_shape(monkeypatch, tmp_path):
    module = import_script(ROOT / 'classify_waste.py', 'classify_main_mod', monkeypatch)
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

    monkeypatch.setattr(module, 'INPUT_FILE', str(input_file))
    monkeypatch.setattr(module, 'OUTPUT_FILE', str(output_file))
    monkeypatch.setattr(module, 'classify_chemical', fake_classify)
    monkeypatch.setattr(module.time, 'sleep', lambda _: None)

    module.main()

    assert calls == ['Methanol', 'Hydrochloric Acid']
    result = pd.read_excel(output_file, sheet_name='Classification')
    assert list(result.columns) == ['Flammable', 'Carcinogenic', 'Infectious', 'Toxic', 'Corrosive']
    assert result['Flammable'].dropna().tolist() == ['Methanol']
    assert result['Toxic'].dropna().tolist() == ['Methanol', 'Hydrochloric Acid']
    assert result['Corrosive'].dropna().tolist() == ['Hydrochloric Acid']


def test_management_main_keeps_excel_output_columns(monkeypatch, tmp_path):
    module = import_script(ROOT / 'generate_management_plan.py', 'plan_main_mod', monkeypatch)
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

    monkeypatch.setattr(module, 'INPUT_FILE', str(input_file))
    monkeypatch.setattr(module, 'OUTPUT_FILE', str(output_file))
    monkeypatch.setattr(module, 'make_plan', lambda chemical, categories: plan)
    monkeypatch.setattr(module.time, 'sleep', lambda _: None)

    module.main()

    result = pd.read_excel(output_file, sheet_name='Management Plan')
    assert result.loc[0, 'Chemical'] == 'Methanol'
    assert result.loc[0, 'Hazard Categories'] == 'Flammable, Toxic'
    assert result.loc[0, 'Treatment Framework'] == 'treat'
    assert result.loc[0, 'Indian HOWM / CPCB Framework'] == 'india'


def test_missing_parsed_classification_raises_clear_error(monkeypatch):
    module = import_script(ROOT / 'classify_waste.py', 'classify_none_mod', monkeypatch)
    module.client.responses.parsed = None
    with pytest.raises(RuntimeError, match='no parsed classification output'):
        module.classify_chemical('Unknown')


def test_missing_parsed_management_plan_raises_clear_error(monkeypatch):
    module = import_script(ROOT / 'generate_management_plan.py', 'plan_none_mod', monkeypatch)
    module.client.responses.parsed = None
    with pytest.raises(RuntimeError, match='no parsed management-plan output'):
        module.make_plan('Unknown', ['Toxic'])
