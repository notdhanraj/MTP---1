import unittest
from src.models import WasteManagementDossier, assign_segregation_bin


class TestModels(unittest.TestCase):
    def test_assign_segregation_bin_rules(self):
        # 1. Review required items
        self.assertEqual(assign_segregation_bin([], 'Unknown Liquid', review_required=True), 'Review Queue')

        # 2. Infectious items
        self.assertEqual(assign_segregation_bin(['Infectious'], 'Bacterial Culture Broth'), 'Biohazard & Infectious')

        # 3. Flammable solvents
        self.assertEqual(assign_segregation_bin(['Flammable', 'Toxic'], 'Methanol'), 'Flammable Solvents')

        # 4. Inorganic Bases
        self.assertEqual(assign_segregation_bin(['Corrosive'], 'Sodium Hydroxide 10M'), 'Inorganic Bases')
        self.assertEqual(assign_segregation_bin(['Corrosive'], 'Ammonium Hydroxide 28%'), 'Inorganic Bases')

        # 5. Inorganic Acids
        self.assertEqual(assign_segregation_bin(['Corrosive', 'Toxic'], 'Hydrochloric Acid 37%'), 'Inorganic Acids')
        self.assertEqual(assign_segregation_bin(['Corrosive'], 'Sulfuric Acid 98%'), 'Inorganic Acids')

        # 6. Carcinogenic & Toxic Organics
        self.assertEqual(assign_segregation_bin(['Toxic', 'Carcinogenic'], 'Ethidium Bromide Solution'), 'Carcinogenic & Toxic Organics')
        self.assertEqual(assign_segregation_bin(['Toxic'], 'Potassium Cyanide'), 'Carcinogenic & Toxic Organics')

    def test_waste_management_dossier_serialization(self):
        dossier = WasteManagementDossier(
            chemical='Methanol',
            bin='Flammable Solvents',
            categories=['Flammable', 'Toxic'],
            container='Type I safety can',
            storage='Flammable cabinet',
            ppe='Nitrile gloves, goggles',
            segregation='Isolate from oxidizers',
            labeling='Flammable Liquid',
            spill='Absorb with pads',
            identification='HPLC solvent',
            prohibited='No drain disposal',
            verification='Check flash point',
            usepa='D001, U154',
            india='HOWM Schedule I',
            treatment='TSDF incineration',
            disposal='Authorized TSDF',
            review_required=False,
            review_reason=None,
        )
        data = dossier.model_dump()
        self.assertEqual(data['chemical'], 'Methanol')
        self.assertEqual(data['bin'], 'Flammable Solvents')
        self.assertFalse(data['review_required'])

    def test_batch_run_response_serialization(self):
        from src.models import BatchRunResponse

        dossier = WasteManagementDossier(
            chemical='Methanol',
            bin='Flammable Solvents',
            categories=['Flammable', 'Toxic'],
            container='Type I safety can',
            storage='Flammable cabinet',
            ppe='Nitrile gloves, goggles',
            segregation='Isolate from oxidizers',
            labeling='Flammable Liquid',
            spill='Absorb with pads',
            identification='HPLC solvent',
            prohibited='No drain disposal',
            verification='Check flash point',
            usepa='D001, U154',
            india='HOWM Schedule I',
            treatment='TSDF incineration',
            disposal='Authorized TSDF',
            review_required=False,
            review_reason=None,
        )

        batch = BatchRunResponse(
            run_id='2026-10-29_010000',
            filename='inventory.xlsx',
            total_count=1,
            bin_counts={'Flammable Solvents': 1},
            items=[dossier],
        )

        data = batch.model_dump()
        self.assertEqual(data['run_id'], '2026-10-29_010000')
        self.assertEqual(data['filename'], 'inventory.xlsx')
        self.assertEqual(data['total_count'], 1)
        self.assertEqual(data['bin_counts']['Flammable Solvents'], 1)
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['items'][0]['chemical'], 'Methanol')

    def test_batch_queued_response_schema(self):
        from src.models import BatchQueuedResponse

        queued = BatchQueuedResponse(
            run_id="2026-10-29_020000_123456",
            filename="lab_inventory.xlsx",
            total_count=3,
            chemicals=["Methanol", "Acetone", "Hydrochloric Acid"],
            pause_after_classification=True,
            status="queued"
        )
        self.assertEqual(queued.run_id, "2026-10-29_020000_123456")
        self.assertEqual(queued.total_count, 3)
        self.assertTrue(queued.pause_after_classification)
        self.assertEqual(queued.status, "queued")

        # Verify defaults
        minimal = BatchQueuedResponse(
            run_id="2026-10-29_020000_999999",
            filename="sample.xlsx",
            total_count=1,
            chemicals=["Toluene"]
        )
        self.assertFalse(minimal.pause_after_classification)
        self.assertEqual(minimal.status, "queued")

    def test_retry_models_schema(self):
        from src.models import RetryItemRequest, RetryItemResponse, WasteManagementDossier

        req = RetryItemRequest(original_name="Mystery Acid", new_name="Hydrochloric Acid")
        self.assertEqual(req.original_name, "Mystery Acid")
        self.assertEqual(req.new_name, "Hydrochloric Acid")

        dossier = WasteManagementDossier(
            chemical="Hydrochloric Acid",
            flammable=False,
            carcinogenic=False,
            infectious=False,
            toxic=False,
            corrosive=True,
            segregation_bin="Inorganic Acids",
            identification="HCl",
            segregation="Keep away from bases",
            container="Polyethylene drum",
            labeling="CORROSIVE",
            storage="Acid cabinet",
            ppe="Gloves, goggles",
            spill="Neutralize with sodium bicarbonate",
            treatment="Neutralization",
            disposal="TSDF inorganic acid stream",
            usepa="D002",
            india="Schedule II",
            prohibited="Do not pour into sink",
            verification="Verify pH",
            review_required=False,
            review_reason=None
        )
        resp = RetryItemResponse(
            status="success",
            chemical="Hydrochloric Acid",
            original_name="Mystery Acid",
            dossier=dossier,
            bin_counts={"Inorganic Acids": 1, "Review Queue": 0}
        )
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.dossier.chemical, "Hydrochloric Acid")



if __name__ == '__main__':
    unittest.main()
