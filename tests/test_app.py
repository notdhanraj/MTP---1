import io
import json
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

    def test_template_contains_in_batch_search_and_hazard_filter_pills(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.text

        # In-batch search input and clear button
        self.assertIn("batchSearchQuery", html)
        self.assertIn("Filter chemicals in batch", html)

        # Multi-hazard filter pills with live counts
        self.assertIn("activeHazardFilters", html)
        self.assertIn("toggleHazardFilter", html)
        self.assertIn("filteredItems", html)
        self.assertIn("Flammable", html)
        self.assertIn("Toxic", html)
        self.assertIn("Corrosive", html)
        self.assertIn("Infectious", html)
        self.assertIn("Carcinogenic", html)
        self.assertIn("Review Required", html)

    def test_template_contains_cabinet_swimlanes_and_layout_toggle(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.text

        # Segmented view layout toggle
        self.assertIn("activeViewMode", html)
        self.assertIn("Card Grid", html)
        self.assertIn("Cabinet Swimlanes", html)

        # 6 Containment Zones in Swimlane View
        self.assertIn("cabinetZones", html)
        self.assertIn("expandedZones", html)
        self.assertIn("toggleZone", html)
        self.assertIn("toggleAllZones", html)
        self.assertIn("Flammable Solvents Cabinet", html)
        self.assertIn("Inorganic Acid Storage", html)
        self.assertIn("Inorganic Base Storage", html)
        self.assertIn("Carcinogenic & Toxic Organics", html)
        self.assertIn("Biohazard & Infectious Holding", html)
        self.assertIn("Safety Review Queue", html)

    def test_template_contains_zero_result_empty_state_and_reset_button(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.text

        # Zero-result empty state card & reset button
        self.assertIn("No chemicals match active filters", html)
        self.assertIn("resetFilters", html)
        self.assertIn("Reset Filters", html)

    def test_template_contains_inline_editing_and_retry_controls(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.text

        # Review card inline edit and retry bindings
        self.assertIn("startEditing", html)
        self.assertIn("cancelEditing", html)
        self.assertIn("retryChemical", html)
        self.assertIn("editingChemical", html)
        self.assertIn("editNameInput", html)
        self.assertIn("retryingChemical", html)
        self.assertIn("retryError", html)
        self.assertIn("Save &amp; Retry", html)
        self.assertIn("Retry Chemical", html)
        self.assertIn("Reason:", html)


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

    def _create_test_excel(self, chemicals: list[str]) -> io.BytesIO:
        return self._create_excel("Hazardous Waste", chemicals)

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

    def test_e2e_live_sse_batch_processing_and_review_pause(self):
        import src.services as services
        from src.app import app

        sample_path = Path(__file__).resolve().parent.parent / "src" / "Hazardous Waste.xlsx"
        if not sample_path.exists():
            sample_path = Path("src/Hazardous Waste.xlsx")
        self.assertTrue(sample_path.exists(), "Sample workbook src/Hazardous Waste.xlsx must exist")

        with open(sample_path, "rb") as f:
            file_bytes = f.read()

        app.state.client = FakeClient()

        # 1. Upload workbook with pause_after_classification=True
        upload_resp = self.client.post(
            "/api/upload",
            files={"file": ("Hazardous Waste.xlsx", io.BytesIO(file_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"pause_after_classification": "true"}
        )
        self.assertEqual(upload_resp.status_code, 200)
        queued = upload_resp.json()
        run_id = queued["run_id"]
        self.assertGreater(queued["total_count"], 0)
        self.assertTrue(queued["pause_after_classification"])
        self.assertEqual(queued["status"], "queued")

        # 2. Connect to SSE stream for Stage 1 (Classification)
        stream_stage1 = self.client.get(f"/api/runs/{run_id}/stream")
        self.assertEqual(stream_stage1.status_code, 200)
        self.assertEqual(stream_stage1.headers["content-type"], "text/event-stream; charset=utf-8")
        body1 = stream_stage1.text

        # Verify Stage 1 emitted classification events and paused cleanly
        self.assertIn('"stage": "classification"', body1)
        self.assertIn('"type": "stage_paused"', body1)
        self.assertNotIn('"type": "complete"', body1)

        # 3. Resume Stage 2 (Planning)
        stream_stage2 = self.client.get(f"/api/runs/{run_id}/stream?stage=planning")
        self.assertEqual(stream_stage2.status_code, 200)
        self.assertEqual(stream_stage2.headers["content-type"], "text/event-stream; charset=utf-8")
        body2 = stream_stage2.text

        # Verify Stage 2 emitted planning events and completed
        self.assertIn('"stage": "planning"', body2)
        self.assertIn('"type": "complete"', body2)
        self.assertIn('"status": "completed"', body2)

        # 4. Verify data/runs/<run_id>/meta.json
        meta_file = services.DEFAULT_RUNS_DIR / run_id / "meta.json"
        self.assertTrue(meta_file.exists(), f"Meta file {meta_file} must exist")
        with open(meta_file, "r", encoding="utf-8") as f:
            meta_data = json.load(f)
        self.assertEqual(meta_data["status"], "completed")
        self.assertIsInstance(meta_data["dossiers"], dict)
        self.assertGreater(len(meta_data["dossiers"]), 0)

    def test_retry_endpoint_success_and_bin_recalculation(self):
        from src.app import app
        app.state.client = FakeClient()
        excel_bytes = self._create_test_excel(['Mystery Chemical'])
        upload_resp = self.client.post(
            "/api/upload",
            files={"file": ("inventory.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"pause_after_classification": "false"}
        )
        run_id = upload_resp.json()["run_id"]

        # Run stream to completion so dossiers are saved
        self.client.get(f"/api/runs/{run_id}/stream")

        retry_resp = self.client.post(
            f"/api/runs/{run_id}/retry",
            json={"original_name": "Mystery Chemical", "new_name": "Acetone"}
        )
        self.assertEqual(retry_resp.status_code, 200)
        data = retry_resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["chemical"], "Acetone")
        self.assertEqual(data["original_name"], "Mystery Chemical")
        self.assertIn("dossier", data)
        self.assertIn("bin_counts", data)

    def test_retry_endpoint_duplicate_collision_returns_422(self):
        from src.app import app
        app.state.client = FakeClient()
        excel_bytes = self._create_test_excel(['Acetone', 'Mystery Chemical'])
        upload_resp = self.client.post(
            "/api/upload",
            files={"file": ("inventory.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        run_id = upload_resp.json()["run_id"]
        self.client.get(f"/api/runs/{run_id}/stream")

        retry_resp = self.client.post(
            f"/api/runs/{run_id}/retry",
            json={"original_name": "Mystery Chemical", "new_name": "Acetone"}
        )
        self.assertEqual(retry_resp.status_code, 422)
        self.assertIn("already present in this batch", retry_resp.json()["detail"])

    def test_retry_endpoint_empty_name_returns_422(self):
        retry_resp = self.client.post(
            "/api/runs/any_run_id/retry",
            json={"original_name": "Acetone", "new_name": "   "}
        )
        self.assertEqual(retry_resp.status_code, 422)

    def test_retry_endpoint_unknown_run_returns_404(self):
        retry_resp = self.client.post(
            "/api/runs/nonexistent_run_99999/retry",
            json={"original_name": "Acetone", "new_name": "Methanol"}
        )
        self.assertEqual(retry_resp.status_code, 404)


def __getattr__(name: str):
    if name == "TestAppRoutes":
        return TestAppUploadEndpoint
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == '__main__':
    unittest.main()

