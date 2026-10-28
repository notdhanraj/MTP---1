import types
import unittest
from src.classify_waste import HazardClassification
from src.generate_management_plan import ManagementPlan
from src.services import lookup_chemical


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


if __name__ == '__main__':
    unittest.main()
