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


if __name__ == '__main__':
    unittest.main()
