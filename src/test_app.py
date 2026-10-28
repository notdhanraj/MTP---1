import types
import unittest
from fastapi.testclient import TestClient
from src.classify_waste import HazardClassification
from src.generate_management_plan import ManagementPlan


class FakeResponses:
    def __init__(self):
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs['text_format'] is HazardClassification:
            return types.SimpleNamespace(output_parsed=HazardClassification(
                flammable=True, carcinogenic=False, infectious=False, toxic=True, corrosive=False
            ))
        return types.SimpleNamespace(output_parsed=ManagementPlan(
            chemical=kwargs.get('input', 'test'),
            identification_and_characterization='Identification desc',
            segregation_and_incompatibilities='Keep away from oxidizers',
            recommended_container='Safety can Type I',
            labeling_requirements='Flammable solvent',
            storage_requirements='Flammable cabinet',
            handling_and_ppe='Nitrile gloves and goggles',
            spill_and_emergency_management='Absorb with pads',
            treatment_framework='Thermal destruction',
            final_disposal_framework='Authorized TSDF',
            usepa_framework='D001',
            indian_framework='HOWM Schedule I',
            prohibited_or_unsafe_actions='No drain disposal',
            verification_required='Flash point check',
        ))


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


class TestApp(unittest.TestCase):
    def setUp(self):
        from src.app import app
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'healthy'})

    def test_root_serves_html(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])
        self.assertIn('HazWaste Studio', response.text)

    def test_lookup_endpoint_success(self):
        import src.services as services
        fake = FakeClient()
        orig_lookup = services.lookup_chemical

        # Test lookup with explicit fake client
        try:
            services.lookup_chemical = lambda chem: orig_lookup(chem, client=fake)
            response = self.client.post('/api/lookup', json={'chemical': 'Methanol'})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['chemical'], 'Methanol')
            self.assertEqual(data['bin'], 'Flammable Solvents')
            self.assertIn('Flammable', data['categories'])
            self.assertFalse(data['review_required'])
            self.assertEqual(data['prohibited'], 'No drain disposal')
        finally:
            services.lookup_chemical = orig_lookup

    def test_lookup_endpoint_empty_payload_validation(self):
        response = self.client.post('/api/lookup', json={})
        self.assertEqual(response.status_code, 422)

    def test_lookup_endpoint_blank_chemical_validation(self):
        response = self.client.post('/api/lookup', json={'chemical': '   '})
        self.assertEqual(response.status_code, 422)


if __name__ == '__main__':
    unittest.main()
