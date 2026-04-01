from .base import BaseScraper
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class CosoCiScraper(BaseScraper):
    """Scraper pour coso.ci - Conseil des Opérations de Bourse"""
    
    def __init__(self):
        super().__init__('COSO.ci', 'https://coso.ci')
    
    def scrape(self):
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        
        url = f"{self.base_url}/index.php/appel-doffres/appels-doffres-a-telecharger"
        offres = self._scrape_page(url)
        
        logger.info(f"📦 {len(offres)} appels trouvés sur {self.site_name}")
        
        if offres:
            self.save_to_db(offres)
        
        return offres
    
    def _scrape_page(self, url):
        """Scrape la page avec gestion PDF"""
        offres = []
        
        html = self._make_request(url)
        if not html:
            return offres
        
        soup = self._parse_html(html)
        if not soup:
            return offres
        
        # Chercher les liens vers PDF ou pages d'appels d'offres
        items = (soup.find_all('a', href=True) or soup.find_all('li'))
        
        for item in items:
            try:
                text = item.text.strip()
                href = item.get('href', '')
                
                # Filtrer: chercher "appel", "offre", "pdf", "télécharger"
                if not any(k in text.lower() for k in ['appel', 'offre', 'pdf', 'download']):
                    continue
                if len(text) < 10:
                    continue
                
                link = href if href.startswith('http') else self.base_url + '/' + href.lstrip('/')
                
                # Essayer d'extraire une date du texte ou de l'URL
                date_pub = self._extract_date_from_text(text + ' ' + href)
                
                offre = {
                    'title': text[:200],
                    'url': link,
                    'source_url': url,
                    'description': 'Document à télécharger',
                    'category': 'Finance/Bourse',
                    'location': 'Côte d\'Ivoire',
                    'employment_type': 'Appel d\'offre',
                    'date_publication': date_pub,
                    'company_name': 'COSO CI',
                    'tags': ['coso', 'bourse', 'finance', 'pdf'],
                    'is_pdf': '.pdf' in link.lower(),
                    'scraped_at': datetime.utcnow().isoformat()
                }
                offres.append(offre)
                
            except Exception as e:
                logger.debug(f"   Erreur: {e}")
                continue
        
        return offres
    
    def _extract_date_from_text(self, text):
        """Extrait une date depuis un texte ou URL"""
        import re
        # Pattern date FR: 12/03/2024 ou 12 mars 2024
        match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})', text)
        if match:
            return self._normalize_date(match.group(1))
        return datetime.utcnow()