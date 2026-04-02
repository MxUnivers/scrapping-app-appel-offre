from .base import BaseScraper
import logging
import time
import random
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Try to import Playwright (optional dependency)
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("⚠️  Playwright non installé - LinkedIn scraper en mode limité")


class LinkedInCiScraper(BaseScraper):
    """
    Scraper pour LinkedIn - Recherche "appel d'offre Côte d'Ivoire"
    
    ⚠️  Ce scraper utilise Playwright pour gérer le JavaScript de LinkedIn.
    Il inclut des délais importants pour éviter les blocages.
    
    Alternative recommandée : LinkedIn API officielle
    https://learn.microsoft.com/en-us/linkedin/
    """
    
    def __init__(self):
        super().__init__('LinkedIn CI', 'https://www.linkedin.com')
        self.search_url = (
            "https://www.linkedin.com/search/results/all/"
            "?keywords=appel%20d%27offre%20C%C3%B4te%20d%27ivoire"
            "&origin=GLOBAL_SEARCH_HEADER"
        )
        # Délais pour éviter les blocages (en secondes)
        self.delay_between_requests = random.uniform(8, 15)
        self.delay_between_scrolls = random.uniform(3, 6)
        self.max_scroll_attempts = 5  # Limite le scroll infini
        
    def scrape(self) -> List[Dict]:
        """Scrape LinkedIn avec Playwright pour le rendu JavaScript"""
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        
        # Si Playwright n'est pas disponible, retourne un fallback
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("⚠️  Playwright non disponible - mode fallback")
            return self._get_fallback_notice()
        
        all_offres = []
        
        try:
            with sync_playwright() as p:
                # Lancer Chromium en mode "humain"
                browser = p.chromium.launch(
                    headless=True,  # Mettre à False pour debug visuel
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-blink-features=AutomationControlled'
                    ]
                )
                
                # Créer un contexte avec fingerprinting réaliste
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=self._get_realistic_user_agent(),
                    locale='fr-FR',
                    timezone_id='Africa/Abidjan'
                )
                
                # Ajouter des headers supplémentaires
                context.set_extra_http_headers({
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                })
                
                page = context.new_page()
                
                # Éviter la détection de bot
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)
                
                # Naviguer vers la page de recherche
                logger.info(f"   🌐 Navigation vers LinkedIn...")
                try:
                    page.goto(self.search_url, wait_until='networkidle', timeout=60000)
                except PlaywrightTimeout:
                    logger.warning("⚠️  Timeout lors du chargement LinkedIn")
                    return self._get_fallback_notice()
                
                # Attendre que le contenu soit chargé
                page.wait_for_selector('div.search-results-container', timeout=30000)
                
                # Scroll progressif pour charger plus de résultats
                offres = self._scroll_and_extract(page)
                
                browser.close()
                
        except Exception as e:
            logger.error(f"❌ Erreur LinkedIn scraping: {e}")
            return self._get_fallback_notice()
        
        logger.info(f"📦 {len(all_offres)} offres trouvées sur {self.site_name}")
        
        if all_offres:
            self.save_to_db(all_offres)
        
        return all_offres
    
    def _scroll_and_extract(self, page) -> List[Dict]:
        """Scroll la page et extrait les offres"""
        offres = []
        seen_urls = set()
        
        for scroll_num in range(self.max_scroll_attempts):
            logger.info(f"   📜 Scroll #{scroll_num + 1}")
            
            # Extraire les éléments visibles
            items = page.locator('div.search-result__wrapper').all()
            
            for item in items:
                try:
                    offre_data = self._parse_linkedin_item(item)
                    if offre_data and offre_data['url'] not in seen_urls:
                        seen_urls.add(offre_data['url'])
                        offres.append(offre_data)
                except Exception as e:
                    logger.debug(f"   Erreur parsing item: {e}")
                    continue
            
            # Si on a assez d'offres, on arrête
            if len(offres) >= 20:
                break
            
            # Scroll vers le bas
            page.evaluate('window.scrollBy(0, document.body.scrollHeight)')
            time.sleep(self.delay_between_scrolls)
            
            # Vérifier si on est en bas de page
            if self._is_at_bottom(page):
                logger.info("   ✅ Bas de page atteint")
                break
        
        return offres
    
    def _parse_linkedin_item(self, item) -> Optional[Dict]:
        """Parse un élément de résultat LinkedIn"""
        try:
            # Extraire le titre (texte principal)
            title_elem = item.locator('span.entity-result__title-text').first
            title = title_elem.text_content().strip() if title_elem else ''
            
            # Filtrer: doit contenir des mots-clés pertinents
            if not self._is_relevant_title(title):
                return None
            
            # Extraire le lien
            link_elem = item.locator('a.entity-result__title-link').first
            link = link_elem.get_attribute('href') if link_elem else ''
            if link and not link.startswith('http'):
                link = self.base_url + link
            
            # Éviter les liens non pertinents (personnes, entreprises)
            if any(skip in link for skip in ['/in/', '/company/', '/school/']):
                return None
            
            # Extraire la description/snippet
            desc_elem = item.locator('div.entity-result__snippet').first
            description = desc_elem.text_content().strip() if desc_elem else ''
            
            # Extraire les métadonnées (date, localisation, type)
            metadata_text = item.text_content()
            
            # Extraire la localisation
            location = self._extract_location(metadata_text)
            
            # Extraire la date (approximative)
            date_pub = self._extract_date_from_text(metadata_text)
            
            # Déterminer le type d'offre
            employment_type = self._classify_offer_type(title + ' ' + description)
            
            return {
                'title': title[:200],  # Limite de longueur
                'url': link,
                'source_url': self.search_url,
                'description': description[:500],
                'category': 'Appel d\'offre / Marché',
                'location': location or 'Côte d\'Ivoire',
                'employment_type': employment_type,
                'date_publication': date_pub,
                'company_name': self._extract_company(metadata_text),
                'tags': ['linkedin', 'appel d\'offre', 'côte d\'ivoire'],
                'platform': 'LinkedIn',
                'scraped_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.debug(f"   Erreur parse item: {e}")
            return None
    
    def _is_relevant_title(self, title: str) -> bool:
        """Filtre pour vérifier si le titre concerne un appel d'offre"""
        if not title or len(title) < 10:
            return False
        
        title_lower = title.lower()
        
        # Mots-clés positifs
        positive_keywords = [
            'appel d\'offre', 'appel d\'offres', 'marché public', 'consultance',
            'consulting', 'tender', 'bid', 'rfp', 'rft', 'soumission',
            'prestataire', 'fournisseur', 'contrat', 'marché'
        ]
        
        # Mots-clés négatifs (à exclure)
        negative_keywords = [
            'recrute', 'hiring', 'emploi', 'job', 'stage', 'cdi', 'cdd',
            'rejoignez', 'candidatez', 'postulez'
        ]
        
        # Doit contenir au moins un mot positif
        has_positive = any(kw in title_lower for kw in positive_keywords)
        
        # Ne doit pas être une offre d'emploi classique
        has_negative = any(kw in title_lower for kw in negative_keywords)
        
        return has_positive and not has_negative
    
    def _extract_location(self, text: str) -> Optional[str]:
        """Extrait la localisation depuis le texte"""
        locations_ci = [
            'Abidjan', 'Bouaké', 'Yamoussoukro', 'San-Pédro', 'Korhogo',
            'Daloa', 'Man', 'Gagnoa', 'Divo', 'Bondoukou',
            'Côte d\'Ivoire', 'Cote d\'Ivoire', 'Ivory Coast'
        ]
        
        for loc in locations_ci:
            if loc.lower() in text.lower():
                return loc
        return None
    
    def _extract_date_from_text(self, text: str) -> datetime:
        """Extrait une date approximative depuis le texte LinkedIn"""
        # LinkedIn affiche souvent "Il y a X jours/semaines"
        patterns = [
            (r'il y a\s+(\d+)\s+jours?', lambda x: datetime.utcnow() - timedelta(days=int(x))),
            (r'il y a\s+(\d+)\s+semaines?', lambda x: datetime.utcnow() - timedelta(weeks=int(x))),
            (r'il y a\s+(\d+)\s+mois?', lambda x: datetime.utcnow() - timedelta(days=int(x)*30)),
            (r'(\d{1,2}/\d{1,2}/\d{4})', lambda x: self._normalize_date(x)),
            (r'(\d{4}-\d{1,2}-\d{1,2})', lambda x: self._normalize_date(x)),
        ]
        
        for pattern, converter in patterns:
            match = re.search(pattern, text.lower())
            if match:
                try:
                    return converter(match.group(1))
                except:
                    continue
        
        # Date par défaut: aujourd'hui
        return datetime.utcnow()
    
    def _classify_offer_type(self, text: str) -> str:
        """Classifie le type d'offre"""
        text_lower = text.lower()
        
        if any(kw in text_lower for kw in ['travaux', 'construction', 'btp', 'infrastructure']):
            return 'Appel d\'offre - Travaux'
        elif any(kw in text_lower for kw in ['fourniture', 'équipement', 'matériel']):
            return 'Appel d\'offre - Fournitures'
        elif any(kw in text_lower for kw in ['consultance', 'consulting', 'étude', 'expertise']):
            return 'Appel d\'offre - Consultance'
        elif any(kw in text_lower for kw in ['service', 'prestation', 'maintenance']):
            return 'Appel d\'offre - Services'
        else:
            return 'Appel d\'offre'
    
    def _extract_company(self, text: str) -> str:
        """Tente d'extraire le nom de l'entreprise/organisme"""
        # LinkedIn met souvent le nom après "·" ou "•"
        parts = re.split(r'[·•|]', text)
        if len(parts) >= 2:
            candidate = parts[1].strip()
            # Filtrer les résultats trop courts ou génériques
            if len(candidate) > 3 and candidate.lower() not in ['ci', 'fr', 'en']:
                return candidate
        return ''
    
    def _is_at_bottom(self, page) -> bool:
        """Vérifie si on est en bas de la page"""
        return page.evaluate("""
            () => {
                const scrollTop = window.scrollY;
                const windowHeight = window.innerHeight;
                const documentHeight = document.documentElement.scrollHeight;
                return scrollTop + windowHeight >= documentHeight - 100;
            }
        """)
    
    def _get_realistic_user_agent(self) -> str:
        """Retourne un User-Agent réaliste pour Firefox/Chrome récent"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        return random.choice(user_agents)
    
    def _get_fallback_notice(self) -> List[Dict]:
        """Retourne une notice de consultation manuelle en cas d'échec"""
        logger.warning("🔄 Retour fallback pour LinkedIn")
        return [{
            'title': '🔍 Appels d\'offre Côte d\'Ivoire - LinkedIn',
            'url': self.search_url,
            'source_url': self.search_url,
            'description': 'LinkedIn restreint l\'accès automatisé à ses données. '
                          'Pour consulter les derniers appels d\'offre, '
                          'veuillez visiter directement ce lien de recherche LinkedIn. '
                          'Connectez-vous pour voir tous les résultats.',
            'category': 'Appel d\'offre / Marché',
            'location': 'Côte d\'Ivoire',
            'employment_type': 'Appel d\'offre',
            'date_publication': datetime.utcnow(),
            'company_name': 'Divers (via LinkedIn)',
            'tags': ['linkedin', 'manuel', 'recherche'],
            'platform': 'LinkedIn',
            'scraped_at': datetime.utcnow().isoformat(),
            'requires_manual_check': True,
            'scraping_method': 'fallback_notification',
            'warning': 'LinkedIn bloque le scraping - consultation manuelle requise'
        }]