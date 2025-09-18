import unittest
from scraper import ProductScraper

class TestProductScraper(unittest.TestCase):
    def setUp(self):
        self.scraper = ProductScraper()
        self.test_sap = "41018314"  # SAP číslo pro testování
        
    def test_get_product_info(self):
        result = self.scraper.get_product_info(self.test_sap)
        
        # Test, že vrací výsledky pro oba weby
        self.assertIn('fastcr', result)
        self.assertIn('planeo', result)
        
        # Test FastCR výsledků
        if result['fastcr']:
            self.assertIn('specifications', result['fastcr'])
            self.assertIn('description', result['fastcr'])
            self.assertIn('url', result['fastcr'])
            
        # Test Planeo výsledků
        if result['planeo']:
            self.assertIn('specifications', result['planeo'])
            self.assertIn('description', result['planeo'])
            self.assertIn('url', result['planeo'])
            
    def test_invalid_sap(self):
        result = self.scraper.get_product_info("999999999")
        self.assertIsNone(result['fastcr'])
        self.assertIsNone(result['planeo'])

if __name__ == '__main__':
    unittest.main()