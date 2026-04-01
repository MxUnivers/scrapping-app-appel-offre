from .base import BaseScraper
import logging
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)

class J360InfoScraper(BaseScraper):
    """Scraper pour j360.info - Appels d'offres Afrique/Côte d'Ivoire"""
    
    def __init__(self):
        super().__init__('J360.info', 'https://www.j360.info')
    
    def scrape(self):
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        all_offres = []
        
        # URLs à scraper avec catégories
        categories = [
            'communication-media',
            'construction',
            'consulting',
            'education',
            'energy',
            'healthcare',
            'it-telecom',
            'transport'
        ]
        
        for cat in categories:
            base_url = f'{self.base_url}/en/tenders/africa/ivory-coast/?cat={cat}'
            offres = self._scrape_category(base_url, cat)
            all_offres.extend(offres)
        
        logger.info(f"📦 Total: {len(all_offres)} appels d'offres trouvés sur {self.site_name}")
        
        if all_offres:
            self.save_to_db(all_offres)
        
        return all_offres
    
    def _scrape_category(self, base_url, category):
        """Scrape une catégorie avec pagination"""
        offres = []
        page = 1
        max_pages = 10  # Limite de sécurité
        
        while page <= max_pages:
            url = f"{base_url}&page={page}" if page > 1 else base_url
            logger.info(f"   📄 Page {page}: {url}")
            
            html = self._make_request(url)
            if not html:
                break
            
            soup = self._parse_html(html)
            if not soup:
                break
            
            # Sélecteurs à adapter selon la structure réelle du site
            items = soup.find_all('article') or soup.find_all('div', class_='tender-item') or \
                   soup.find_all('div', class_='post') or soup.find_all('li')
            
            if not items:
                logger.warning(f"   ⚠️  Aucun élément trouvé avec les sélecteurs connus")
                break
            
            for item in items:
                try:
                    title_elem = item.find('h2') or item.find('h3') or item.find('a', class_='title')
                    if not title_elem:
                        continue
                    
                    title = title_elem.text.strip()
                    
                    # Ignorer si pas un appel d'offre (filtre basique)
                    if not self._is_tender_title(title):
                        continue
                    
                    link_elem = item.find('a')
                    link = link_elem['href'] if link_elem else ''
                    if link and not link.startswith('http'):
                        link = self.base_url + link
                    
                    # Extraire la date
                    date_elem = item.find('time') or item.find('span', class_='date')
                    date_text = date_elem.text.strip() if date_elem else ''
                    date_pub = self._normalize_date(date_text)
                    
                    # Extraire la localisation
                    location = self._extract_location(item)
                    
                    offre = {
                        'title': title,
                        'url': link,
                        'source_url': url,
                        'description': '',
                        'category': category.replace('-', ' ').title(),
                        'location': location or 'Côte d\'Ivoire',
                        'employment_type': 'Appel d\'offre',
                        'date_publication': date_pub,
                        'company_name': '',
                        'tags': [category, 'Afrique', 'tender'],
                        'scraped_at': datetime.utcnow().isoformat()
                    }
                    offres.append(offre)
                    
                except Exception as e:
                    logger.debug(f"   Erreur parsing item: {e}")
                    continue
            
            # Vérifier s'il y a une page suivante
            next_btn = soup.find('a', class_='next') or soup.find('a', rel='next')
            if not next_btn:
                break
            
            page += 1
        
        return offres
    
    def _is_tender_title(self, title):
        """Filtre pour vérifier si c'est un appel d'offre"""
        keywords = ['appel', 'offre', 'tender', 'marché', 'consultance', 'bid', 'rfp', 'rft']
        return any(kw in title.lower() for kw in keywords)
    
    def _extract_location(self, item):
        """Extrait la localisation depuis l'élément"""
        text = item.text.lower()
        locations = ['abidjan', 'bouaké', 'yamoussoukro', 'san-pédro', 'korhogo', 
                    'daloa', 'man', 'gagnoa', 'côte d\'ivoire', 'ivory coast']
        for loc in locations:
            if loc in text:
                return loc.title()
        return None