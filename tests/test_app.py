import io
import json
from pathlib import Path
import shutil
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
        inp = kwargs.get('input', '')
        if kwargs['text_format'] is HazardClassification:
            if 'Hydrochloric Acid' in inp:
                return types.SimpleNamespace(output_parsed=HazardClassification(
                    flammable=False, carcinogenic=False, infectious=False, toxic=True, corrosive=True
                ))
            if 'Mystery' in inp or 'Unknown' in inp:
                return types.SimpleNamespace(output_parsed=HazardClassification(
                    flammable=False, carcinogenic=False, infectious=False, toxic=False, corrosive=False
                ))
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
        self.assertIn('Hazardous Waste Management', response.text)
        self.assertIn('M.Tech Project I', response.text)

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
        self.assertIn("streamStage === 'completed'", html)
        self.assertIn('streamPaused', html)
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

    def test_template_contains_run_history_archive_and_export_buttons(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.text

        # Header Run History button
        self.assertIn("Run History", html)
        self.assertIn("openRunHistory", html)

        # Run History left drawer
        self.assertIn("historyDrawerOpen", html)
        self.assertIn("Run History Archive", html)
        self.assertIn("loadRun", html)

        # Batch summary export buttons
        self.assertIn("Export Excel (.xlsx)", html)
        self.assertIn("Export Classification (.xlsx)", html)
        self.assertIn("exportFilteredCsv", html)
        self.assertIn("Export Filtered CSV", html)

        # Alpine JS methods
        self.assertIn("fetchRunHistory", html)
        self.assertIn("exportFilteredCsv()", html)


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

        # Verify standalone classified.xlsx was created on disk and is exportable while paused!
        clf_file = services.DEFAULT_RUNS_DIR / run_id / "classified.xlsx"
        self.assertTrue(clf_file.exists(), f"Classified file {clf_file} must exist after stage 1")

        clf_export_resp = self.client.get(f"/api/runs/{run_id}/export-classification")
        self.assertEqual(clf_export_resp.status_code, 200)
        self.assertIn(f"hazardous_waste_classification_{run_id}.xlsx", clf_export_resp.headers["content-disposition"])

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

    def test_e2e_remediation_and_cabinet_graduation(self):
        from src.app import app
        app.state.client = FakeClient()

        # 1. Create a workbook with an unknown ambiguous chemical
        excel_bytes = self._create_test_excel(['Mystery Chemical Mix', 'Methanol'])
        upload_resp = self.client.post(
            "/api/upload",
            files={"file": ("inventory.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        self.assertEqual(upload_resp.status_code, 200)
        run_id = upload_resp.json()["run_id"]

        # 2. Stream to completion
        stream_resp = self.client.get(f"/api/runs/{run_id}/stream")
        self.assertEqual(stream_resp.status_code, 200)

        # 3. Verify Mystery Chemical Mix is initially in Review Queue
        meta_path = Path("data/runs") / run_id / "meta.json"
        with open(meta_path, "r", encoding="utf-8") as f:
            meta_before = json.load(f)
        self.assertIn("Mystery Chemical Mix", meta_before["dossiers"])
        self.assertTrue(meta_before["dossiers"]["Mystery Chemical Mix"]["review_required"])
        self.assertEqual(meta_before["dossiers"]["Mystery Chemical Mix"]["segregation_bin"], "Review Queue")
        initial_review_count = meta_before["bin_counts"]["Review Queue"]

        # 4. Remediate 'Mystery Chemical Mix' -> 'Hydrochloric Acid'
        retry_resp = self.client.post(
            f"/api/runs/{run_id}/retry",
            json={"original_name": "Mystery Chemical Mix", "new_name": "Hydrochloric Acid"}
        )
        self.assertEqual(retry_resp.status_code, 200)
        result = retry_resp.json()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["chemical"], "Hydrochloric Acid")
        self.assertFalse(result["dossier"]["review_required"])
        self.assertEqual(result["dossier"]["segregation_bin"], "Inorganic Acids")

        # 5. Verify graduation in metadata
        with open(meta_path, "r", encoding="utf-8") as f:
            meta_after = json.load(f)
        self.assertIn("Hydrochloric Acid", meta_after["chemicals"])
        self.assertNotIn("Mystery Chemical Mix", meta_after["chemicals"])
        self.assertEqual(meta_after["bin_counts"]["Review Queue"], initial_review_count - 1)
        self.assertEqual(meta_after["bin_counts"]["Inorganic Acids"], 1)
        self.assertEqual(meta_after["remediated_from"]["Hydrochloric Acid"], "Mystery Chemical Mix")

    def test_list_runs_endpoint(self):
        # Create a mock run directory
        from src.services import DEFAULT_RUNS_DIR
        mock_id = "test_run_list_endpoint"
        mock_dir = DEFAULT_RUNS_DIR / mock_id
        mock_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(mock_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump({
                    "run_id": mock_id,
                    "filename": "test.xlsx",
                    "timestamp": "2026-10-29T12:00:00",
                    "total_count": 2,
                    "bin_counts": {"Flammable Solvents": 2},
                    "status": "completed",
                }, f)

            response = self.client.get("/api/runs")
            self.assertEqual(response.status_code, 200)
            runs = response.json()
            self.assertIsInstance(runs, list)
            match = next((r for r in runs if r["run_id"] == mock_id), None)
            self.assertIsNotNone(match)
            self.assertEqual(match["filename"], "test.xlsx")
            self.assertEqual(match["total_count"], 2)
        finally:
            shutil.rmtree(mock_dir, ignore_errors=True)

    def test_get_run_endpoint_success_and_not_found(self):
        from src.services import DEFAULT_RUNS_DIR
        mock_id = "test_run_get_details"
        mock_dir = DEFAULT_RUNS_DIR / mock_id
        mock_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(mock_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump({
                    "run_id": mock_id,
                    "filename": "lab.xlsx",
                    "timestamp": "2026-10-29T12:00:00",
                    "total_count": 1,
                    "bin_counts": {"Flammable Solvents": 1},
                    "status": "completed",
                    "chemicals": ["Ethanol"],
                    "dossiers": {
                        "Ethanol": {
                            "chemical": "Ethanol",
                            "bin": "Flammable Solvents",
                            "categories": ["Flammable"],
                            "container": "Glass",
                            "storage": "Cabinet",
                            "ppe": "Gloves",
                            "segregation": "Oxidizers",
                            "labeling": "Flammable",
                            "spill": "Absorb",
                            "identification": "Alcohol",
                            "prohibited": "Drain",
                            "verification": "None",
                            "usepa": "D001",
                            "india": "Sched II",
                            "treatment": "Thermal",
                            "disposal": "TSDF",
                        }
                    }
                }, f)

            response = self.client.get(f"/api/runs/{mock_id}")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["run_id"], mock_id)
            self.assertEqual(len(data["items"]), 1)
            self.assertEqual(data["items"][0]["chemical"], "Ethanol")

            # 404 for unknown run
            resp_404 = self.client.get("/api/runs/non_existent_run_12345")
            self.assertEqual(resp_404.status_code, 404)
        finally:
            shutil.rmtree(mock_dir, ignore_errors=True)

    def test_export_run_excel_endpoint_success_and_in_progress_guard(self):
        from src.services import DEFAULT_RUNS_DIR
        mock_id = "test_run_export_excel"
        mock_dir = DEFAULT_RUNS_DIR / mock_id
        mock_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(mock_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump({
                    "run_id": mock_id,
                    "filename": "sample.xlsx",
                    "timestamp": "2026-10-29T12:00:00",
                    "total_count": 1,
                    "bin_counts": {"Flammable Solvents": 1},
                    "status": "completed",
                    "chemicals": ["Ethanol"],
                    "dossiers": {
                        "Ethanol": {
                            "chemical": "Ethanol",
                            "bin": "Flammable Solvents",
                            "categories": ["Flammable"],
                            "container": "Glass",
                            "storage": "Cabinet",
                            "ppe": "Gloves",
                            "segregation": "Oxidizers",
                            "labeling": "Flammable",
                            "spill": "Absorb",
                            "identification": "Alcohol",
                            "prohibited": "Drain",
                            "verification": "None",
                            "usepa": "D001",
                            "india": "Sched II",
                            "treatment": "Thermal",
                            "disposal": "TSDF",
                        }
                    }
                }, f)

            response = self.client.get(f"/api/runs/{mock_id}/export")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.headers.get("content-type"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            self.assertIn("hazardous_waste_management_plan_test_run_export_excel.xlsx", response.headers.get("content-disposition", ""))
            self.assertGreater(len(response.content), 1000)

            # 409 guard for in-progress run
            with open(mock_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump({"run_id": mock_id, "status": "planning"}, f)

            resp_in_progress = self.client.get(f"/api/runs/{mock_id}/export")
            self.assertEqual(resp_in_progress.status_code, 409)

            # 404 guard for non-existent run
            resp_404 = self.client.get("/api/runs/non_existent_run_export_99999/export")
            self.assertEqual(resp_404.status_code, 404)
        finally:
            shutil.rmtree(mock_dir, ignore_errors=True)

    def test_export_run_classification_excel_endpoint(self):
        from src.services import DEFAULT_RUNS_DIR
        mock_id = "test_run_export_clf_excel"
        mock_dir = DEFAULT_RUNS_DIR / mock_id
        mock_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(mock_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump({
                    "run_id": mock_id,
                    "filename": "sample.xlsx",
                    "timestamp": "2026-10-29T12:00:00",
                    "total_count": 1,
                    "bin_counts": {"Flammable Solvents": 1},
                    "status": "paused_for_review",
                    "chemicals": ["Ethanol"],
                    "classifications": {
                        "Ethanol": {
                            "classification": {"flammable": True, "toxic": False},
                            "bin": "Flammable Solvents"
                        }
                    }
                }, f)

            response = self.client.get(f"/api/runs/{mock_id}/export-classification")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.headers.get("content-type"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            self.assertIn(f"hazardous_waste_classification_{mock_id}.xlsx", response.headers.get("content-disposition", ""))
            self.assertGreater(len(response.content), 1000)

            # Standalone file should now exist on disk!
            self.assertTrue((mock_dir / "classified.xlsx").exists())

            # 409 guard if classification has not been run
            with open(mock_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump({"run_id": mock_id, "status": "queued"}, f)

            resp_queued = self.client.get(f"/api/runs/{mock_id}/export-classification")
            self.assertEqual(resp_queued.status_code, 409)

            # 404 guard for non-existent run
            resp_404 = self.client.get("/api/runs/non_existent_run_clf_99999/export-classification")
            self.assertEqual(resp_404.status_code, 404)
        finally:
            shutil.rmtree(mock_dir, ignore_errors=True)

    def test_e2e_archive_indexing_and_excel_export_parity(self):
        import openpyxl
        from unittest.mock import patch
        from src.classify_waste import HazardClassification
        from src.generate_management_plan import ManagementPlan
        from src.services import DEFAULT_RUNS_DIR

        # 1. Create a sample batch workbook with 2 chemicals
        buf = io.BytesIO()
        df = pd.DataFrame({"Chemical": ["Toluene", "Nitric Acid"]})
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)

        # 2. Upload batch and process
        with patch("src.services.classify_chemical") as mock_clf, \
             patch("src.services.make_plan") as mock_plan:

            mock_clf.side_effect = lambda chem, client=None: (
                HazardClassification(flammable=True, carcinogenic=False, infectious=False, toxic=True, corrosive=False)
                if chem == "Toluene" else
                HazardClassification(flammable=False, carcinogenic=False, infectious=False, toxic=False, corrosive=True)
            )

            mock_plan.side_effect = lambda chem, cats, client=None: (
                ManagementPlan(
                    chemical="Toluene",
                    recommended_container="Safety can",
                    storage_requirements="Flammable cabinet",
                    handling_and_ppe="Nitrile gloves",
                    segregation_and_incompatibilities="Avoid oxidizers",
                    labeling_requirements="Flammable Liquid",
                    spill_and_emergency_management="Absorb with pads",
                    identification_and_characterization="Aromatic hydrocarbon",
                    prohibited_or_unsafe_actions="Do not pour in sink",
                    verification_required="Visual check",
                    usepa_framework="D001",
                    indian_framework="HOWM Schedule II",
                    treatment_framework="Incineration",
                    final_disposal_framework="Licensed TSDF",
                ) if chem == "Toluene" else
                ManagementPlan(
                    chemical="Nitric Acid",
                    recommended_container="Acid bottle",
                    storage_requirements="Acid locker",
                    handling_and_ppe="Acid suit",
                    segregation_and_incompatibilities="Avoid bases",
                    labeling_requirements="Corrosive",
                    spill_and_emergency_management="Neutralize",
                    identification_and_characterization="Inorganic acid",
                    prohibited_or_unsafe_actions="Do not mix with organic",
                    verification_required="pH strip",
                    usepa_framework="D002",
                    indian_framework="HOWM Schedule II",
                    treatment_framework="Neutralization",
                    final_disposal_framework="Licensed facility",
                )
            )

            upload_resp = self.client.post(
                "/api/upload",
                files={"file": ("e2e_archive_test.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            self.assertEqual(upload_resp.status_code, 200)
            run_id = upload_resp.json()["run_id"]

            try:
                # Consume stream to completion
                stream_resp = self.client.get(f"/api/runs/{run_id}/stream")
                self.assertEqual(stream_resp.status_code, 200)
                events = [line for line in stream_resp.iter_lines() if line]
                self.assertTrue(any("complete" in e for e in events))

                # 3. Verify run appears in GET /api/runs
                runs_resp = self.client.get("/api/runs")
                self.assertEqual(runs_resp.status_code, 200)
                run_ids = [r["run_id"] for r in runs_resp.json()]
                self.assertIn(run_id, run_ids)

                # 4. Verify run details in GET /api/runs/{run_id}
                details_resp = self.client.get(f"/api/runs/{run_id}")
                self.assertEqual(details_resp.status_code, 200)
                data = details_resp.json()
                self.assertEqual(data["run_id"], run_id)
                self.assertEqual(len(data["items"]), 2)

                # 5. Verify Excel export parity in GET /api/runs/{run_id}/export
                export_resp = self.client.get(f"/api/runs/{run_id}/export")
                self.assertEqual(export_resp.status_code, 200)
                self.assertEqual(
                    export_resp.headers["content-type"],
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                self.assertIn(f"hazardous_waste_management_plan_{run_id}.xlsx", export_resp.headers["content-disposition"])

                wb = openpyxl.load_workbook(io.BytesIO(export_resp.content))
                self.assertEqual(wb.sheetnames, ["Management Plan", "Classification", "Review Required"])

                ws_mp = wb["Management Plan"]
                self.assertEqual(ws_mp.max_row, 3)  # header + 2 chemicals
                self.assertEqual(ws_mp.cell(row=1, column=1).value, "Chemical")
                self.assertEqual(ws_mp.cell(row=1, column=14).value, "Verification Required")

                ws_clf = wb["Classification"]
                self.assertEqual([c.value for c in ws_clf[1]], ["Flammable", "Carcinogenic", "Infectious", "Toxic", "Corrosive"])

                ws_rev = wb["Review Required"]
                self.assertEqual([c.value for c in ws_rev[1]], ["Chemical", "Review Reason"])
            finally:
                shutil.rmtree(DEFAULT_RUNS_DIR / run_id, ignore_errors=True)


def __getattr__(name: str):
    if name == "TestAppRoutes":
        return TestAppUploadEndpoint
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == '__main__':
    unittest.main()

