import requests
from bs4 import BeautifulSoup
import logging
from typing import Dict, Optional
import time

class ProductScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def get_product_info(self, sap_number: str) -> Dict:
        """
        Získá informace o produktu z obou webů podle SAP čísla
        """
        result = {
            'fastcr': self._scrape_fastcr(sap_number),
            'planeo': self._scrape_planeo(sap_number)
        }
        return result

    def _scrape_fastcr(self, sap_number: str) -> Optional[Dict]:
        """
        Scrape produktových informací z FastCR
        """
        try:
            # Nejdřív vyhledáme produkt
            search_url = f"https://katalog.fastcr.cz/katalog/?f_search={sap_number}"
            search_response = self.session.get(search_url)
            search_response.raise_for_status()
            
            soup = BeautifulSoup(search_response.text, 'html.parser')
            
            # Najít odkaz na detail produktu
            product_link = soup.find('a', href=lambda x: x and 'katalog' in x and '.html' in x)
            if not product_link:
                return None
                
            # Získat detail produktu
            detail_url = f"https://katalog.fastcr.cz{product_link['href']}"
            detail_response = self.session.get(detail_url)
            detail_response.raise_for_status()
            
            detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
            
            # Získat specifikace produktu
            specs = {}
            specs_table = detail_soup.find('table', class_='specifications')
            if specs_table:
                for row in specs_table.find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) == 2:
                        specs[cols[0].text.strip()] = cols[1].text.strip()
            
            # Získat popis produktu
            description = detail_soup.find('div', class_='product-description')
            description_text = description.text.strip() if description else ''
            
            return {
                'specifications': specs,
                'description': description_text,
                'url': detail_url
            }
            
        except Exception as e:
            logging.error(f"Chyba při scrapování FastCR: {str(e)}")
            return None

    def _scrape_planeo(self, sap_number: str) -> Optional[Dict]:
        """
        Scrape produktových informací z Planeo
        """
        try:
            # Vyhledání produktu
            search_url = f"https://www.planeo.cz/vyhledavani$a1013-search?query={sap_number}"
            search_response = self.session.get(search_url)
            search_response.raise_for_status()
            
            soup = BeautifulSoup(search_response.text, 'html.parser')
            
            # Najít odkaz na detail produktu
            product_link = soup.find('a', href=lambda x: x and 'planeo.cz' in x and sap_number in x)
            if not product_link:
                return None
                
            # Získat detail produktu
            detail_url = product_link['href']
            detail_response = self.session.get(detail_url)
            detail_response.raise_for_status()
            
            detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
            
            # Získat specifikace produktu
            specs = {}
            specs_section = detail_soup.find('section', class_='product-parameters')
            if specs_section:
                for item in specs_section.find_all('dl'):
                    key = item.find('dt')
                    value = item.find('dd')
                    if key and value:
                        specs[key.text.strip()] = value.text.strip()
            
            # Získat popis produktu
            description = detail_soup.find('div', class_='product-description')
            description_text = description.text.strip() if description else ''
            
            return {
                'specifications': specs,
                'description': description_text,
                'url': detail_url
            }
            
        except Exception as e:
            logging.error(f"Chyba při scrapování Planeo: {str(e)}")
            return None
