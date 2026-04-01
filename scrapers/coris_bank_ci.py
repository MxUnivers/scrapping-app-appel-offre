from .base import BaseScraper
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class CorisBankCiScraper(BaseScraper):
    """Scraper pour cotedivoire.coris.bank"""
    
    def __init__(self):
        super().__init__('CorisBank.ci', 'https://cotedivoire.coris.bank')
    
    def scrape(self):
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        
        # URL spécifique fournie + recherche générale
        urls = [
            'https://cotedivoire.coris.bank/appel-doffres-pour-selection-fournisseurs-et-prestataires-de-service-2025/',
            f"{self.base_url}/category/appel-doffres/",
            f"{self.base_url}/actualites/",
        ]
        
        all_offres = []
        for url in urls:
            offres = self._scrape_url(url)
            all_offres.extend(offres)
        
        # Supprimer doublons par URL
        seen = set()
        unique_offres = []
        for o in all_offres:
            if o['url'] not in seen:
                seen.add(o['url'])
                unique_offres.append(o)
        
        logger.info(f"📦 {len(unique_offres)} offres uniques sur {self.site_name}")
        
        if unique_offres:
            self.save_to_db(unique_offres)
        
        return unique_offres
    
    def _scrape_url(self, url):
        """Scrape une URL spécifique"""
        offres = []
        
        html = self._make_request(url)
        if not html:
            return offres
        
        soup = self._parse_html(html)
        if not soup:
            return offres
        
        # Contenu principal
        main = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
        
        if main:
            # Chercher les liens d'appels d'offres dans le contenu
            links = main.find_all('a', href=True)
            for link in links:
                text = link.text.strip()
                href = link['href']
                
                if any(k in text.lower() for k in ['appel', 'offre', 'fournisseur', 'prestataire']):
                    full_url = href if href.startswith('http') else self.base_url + '/' + href.lstrip('/')
                    
                    offre = {
                        'title': text[:200],
                        'url': full_url,
                        'source_url': url,
                        'description': '',
                        'category': 'Banque/Services',
                        'location': 'Côte d\'Ivoire',
                        'employment_type': 'Appel d\'offre',
                        'date_publication': datetime.utcnow(),
                        'company_name': 'Coris Bank CI',
                        'tags': ['banque', 'coris', 'fournisseur', 'prestataire'],
                        'scraped_at': datetime.utcnow().isoformat()
                    }
                    offres.append(offre)
        
        # Aussi scraper les articles listés
        articles = soup.find_all('article') or soup.find_all('div', class_='post')
        for article in articles:
            try:
                title_elem = article.find('h2') or article.find('h3')
                if not title_elem:
                    continue
                title = title_elem.text.strip()
                
                if 'appel' not in title.lower() and 'offre' not in title.lower():
                    continue
                
                link_elem = article.find('a')
                link = link_elem['href'] if link_elem else url
                if link and not link.startswith('http'):
                    link = self.base_url + '/' + link.lstrip('/')
                
                offre = {
                    'title': title,
                    'url': link,
                    'source_url': url,
                    'description': '',
                    'category': 'Banque',
                    'location': 'Côte d\'Ivoire',
                    'employment_type': 'Appel d\'offre',
                    'date_publication': datetime.utcnow(),
                    'company_name': 'Coris Bank CI',
                    'tags': ['coris', 'banque'],
                    'scraped_at': datetime.utcnow().isoformat()
                }
                offres.append(offre)
            except:
                continue
        
        return offres