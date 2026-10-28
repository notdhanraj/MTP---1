import io
from pathlib import Path
import types
import unittest
from fastapi.testclient import TestClient
import pandas as pd
from src.classify_waste import HazardClassification
from src.generate_management_plan import ManagementPlan
from src.models import BatchRunResponse


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

    def test_root_template_contains_upload_modal_and_grid_elements(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.text
        # Header upload button
        self.assertIn('Upload Batch (.xlsx)', html)
        # Upload modal container and dropzone
        self.assertIn('uploadModalOpen', html)
        self.assertIn('handleDrop', html)
        self.assertIn('uploadFile', html)
        # Batch summary bar
        self.assertIn('activeBatch', html)
        self.assertIn('Upload New Batch', html)
        # 3-column card grid
        self.assertIn('grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3', html)
        self.assertIn('View Full Plan →', html)

    def test_template_contains_sse_stepper_and_pause_checkbox(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn('pauseAfterClassification', html)
        self.assertIn('streamActive', html)
        self.assertIn('streamProgress', html)
        self.assertIn('Proceed to Plan Generation', html)
        self.assertIn('EventSource', html)

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


class TestAppUploadEndpoint(unittest.TestCase):
    def setUp(self):
        from src.app import app
        app.state.client = None
        self.client = TestClient(app)

    def _create_excel(self, col: str, rows: list[str]) -> io.BytesIO:
        buf = io.BytesIO()
        df = pd.DataFrame({col: rows})
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)
        return buf

    def test_upload_valid_excel_success(self):
        import src.services as services
        fake_client = FakeClient()
        orig_batch = services.process_excel_batch

        try:
            # Inject fake client into process_excel_batch
            services.process_excel_batch = lambda b, fn, **kwargs: orig_batch(b, fn, client=fake_client, **kwargs)

            buf = self._create_excel('Hazardous Waste', ['Methanol', 'Hydrochloric Acid'])
            response = self.client.post(
                '/api/upload?sync=true',
                files={'file': ('inventory.xlsx', buf, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['filename'], 'inventory.xlsx')
            self.assertEqual(data['total_count'], 2)
            self.assertIn('items', data)
            self.assertEqual(len(data['items']), 2)
        finally:
            services.process_excel_batch = orig_batch

    def test_upload_endpoint_returns_batch_queued_response(self):
        buf = self._create_excel('Hazardous Waste', ['Acetone', 'Toluene'])
        response = self.client.post(
            "/api/upload",
            files={"file": ("inventory.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"pause_after_classification": "true"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("run_id", data)
        self.assertEqual(data["total_count"], 2)
        self.assertTrue(data["pause_after_classification"])
        self.assertEqual(data["status"], "queued")
        self.assertEqual(data["chemicals"], ["Acetone", "Toluene"])

    def test_upload_endpoint_backward_compatible_sync_param(self):
        buf = self._create_excel('Hazardous Waste', ['Acetone'])
        fake_client = FakeClient()
        import src.services as services
        orig_batch = services.process_excel_batch
        try:
            services.process_excel_batch = lambda b, fn, **kwargs: orig_batch(b, fn, client=fake_client, **kwargs)
            response = self.client.post(
                "/api/upload?sync=true",
                files={"file": ("inventory.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("items", data)
            self.assertEqual(len(data["items"]), 1)
            self.assertEqual(data["items"][0]["chemical"], "Acetone")
        finally:
            services.process_excel_batch = orig_batch

    def test_stream_endpoint_returns_sse_event_stream(self):
        buf = self._create_excel('Hazardous Waste', ['Acetone'])
        upload_resp = self.client.post(
            "/api/upload",
            files={"file": ("inventory.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"pause_after_classification": "false"}
        )
        self.assertEqual(upload_resp.status_code, 200)
        run_id = upload_resp.json()["run_id"]

        from src.app import app
        app.state.client = FakeClient()

        stream_resp = self.client.get(f"/api/runs/{run_id}/stream")
        self.assertEqual(stream_resp.status_code, 200)
        self.assertEqual(stream_resp.headers["content-type"], "text/event-stream; charset=utf-8")

        body_text = stream_resp.text
        self.assertIn("data: {", body_text)
        self.assertIn('"type": "stage_start"', body_text)
        self.assertIn('"type": "complete"', body_text)

    def test_stream_endpoint_handles_pause_and_planning_resume(self):
        buf = self._create_excel('Hazardous Waste', ['Acetone'])
        upload_resp = self.client.post(
            "/api/upload",
            files={"file": ("inventory.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"pause_after_classification": "true"}
        )
        self.assertEqual(upload_resp.status_code, 200)
        run_id = upload_resp.json()["run_id"]

        from src.app import app
        app.state.client = FakeClient()

        # 1. First stream stops at stage_paused
        stream1 = self.client.get(f"/api/runs/{run_id}/stream")
        self.assertEqual(stream1.status_code, 200)
        self.assertIn('"type": "stage_paused"', stream1.text)
        self.assertNotIn('"type": "complete"', stream1.text)

        # 2. Resume planning stage
        stream2 = self.client.get(f"/api/runs/{run_id}/stream?stage=planning")
        self.assertEqual(stream2.status_code, 200)
        self.assertIn('"stage": "planning"', stream2.text)
        self.assertIn('"type": "complete"', stream2.text)

    def test_stream_endpoint_returns_404_for_unknown_run(self):
        resp = self.client.get("/api/runs/nonexistent_run_id/stream")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json(), {"detail": "Run 'nonexistent_run_id' not found."})

    def test_upload_missing_column_returns_422(self):
        buf = self._create_excel('Invalid Header', ['Item 1'])
        response = self.client.post(
            '/api/upload',
            files={'file': ('bad.xlsx', buf, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("must contain a 'Hazardous Waste' or 'Chemical' column", response.json()['detail'])

    def test_upload_non_excel_extension_returns_422(self):
        response = self.client.post(
            '/api/upload',
            files={'file': ('notes.txt', io.BytesIO(b'hello'), 'text/plain')}
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("Only .xlsx and .xls Excel files are accepted", response.json()['detail'])

    def test_e2e_real_sample_workbook_ingestion(self):
        import src.services as services
        sample_path = Path(__file__).resolve().parent.parent / "src" / "Hazardous Waste.xlsx"
        self.assertTrue(sample_path.exists(), "Sample file src/Hazardous Waste.xlsx must exist")

        fake_client = FakeClient()
        orig_batch = services.process_excel_batch

        try:
            services.process_excel_batch = lambda b, fn, **kwargs: orig_batch(b, fn, client=fake_client, **kwargs)

            with open(sample_path, 'rb') as f:
                content = f.read()

            response = self.client.post(
                '/api/upload?sync=true',
                files={'file': ('Hazardous Waste.xlsx', io.BytesIO(content), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['filename'], 'Hazardous Waste.xlsx')
            self.assertGreater(data['total_count'], 0)
            self.assertEqual(len(data['items']), data['total_count'])
            # Verify every item has required dossier fields
            for item in data['items']:
                self.assertTrue(bool(item['chemical']))
                self.assertTrue(bool(item['bin']))
                self.assertIsInstance(item['categories'], list)
                self.assertTrue(bool(item['container']))
        finally:
            services.process_excel_batch = orig_batch


if __name__ == '__main__':
    unittest.main()

