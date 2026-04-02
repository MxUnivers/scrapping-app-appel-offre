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
    logger.warning("⚠️ Playwright non installé - LinkedIn scraper en mode limité")


class LinkedInCiScraper(BaseScraper):
    """
    Scraper pour LinkedIn - Recherche "appel d'offre Côte d'Ivoire"
    
    ⚠️  LinkedIn bloque activement le scraping. Ce code inclut:
    - Détection anti-bot basique
    - Fallback gracieux en cas d'échec
    - Delays réalistes pour minimiser les blocages
    
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
        # Délais réalistes (en secondes) - NE PAS RÉDUIRE
        self.delay_page_load = random.uniform(4, 8)
        self.delay_between_scrolls = random.uniform(3, 7)
        self.delay_between_actions = random.uniform(2, 5)
        self.max_scroll_attempts = 3  # Limite pour éviter la détection
        
    def scrape(self) -> List[Dict]:
        """Scrape LinkedIn avec Playwright - Version robuste"""
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("⚠️ Playwright non disponible - fallback")
            return self._get_fallback_notice()
        
        try:
            with sync_playwright() as p:
                # Lancer Chromium avec options anti-détection
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                    ]
                )
                
                # Contexte réaliste
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=self._get_realistic_user_agent(),
                    locale='fr-FR',
                    timezone_id='Africa/Abidjan',
                    accept_downloads=False,
                )
                
                context.set_extra_http_headers({
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0',
                })
                
                page = context.new_page()
                
                # Script anti-détection (SYNCHRONE - pas de await!)
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr', 'en'] });
                    window.chrome = { runtime: {} };
                """)
                
                # Navigation avec gestion d'erreurs
                logger.info(f"   🌐 Navigation vers LinkedIn...")
                try:
                    response = page.goto(
                        self.search_url, 
                        wait_until='domcontentloaded', 
                        timeout=45000
                    )
                    
                    # Vérifier le statut HTTP
                    if response and response.status >= 400:
                        logger.warning(f"⚠️  HTTP {response.status} - Accès potentiellement bloqué")
                        browser.close()
                        return self._get_fallback_notice()
                        
                except PlaywrightTimeout:
                    logger.warning("⚠️  Timeout navigation LinkedIn")
                    browser.close()
                    return self._get_fallback_notice()
                
                # Attendre que la page charge (delay humain)
                time.sleep(self.delay_page_load)
                
                # Vérifier si redirigé vers login
                if 'login' in page.url.lower() or 'checkpoint' in page.url.lower():
                    logger.warning("⚠️  Redirigé vers login LinkedIn - accès refusé")
                    browser.close()
                    return self._get_fallback_notice()
                
                # Attendre le contenu avec sélecteurs multiples (fallback)
                content_loaded = self._wait_for_content(page)
                if not content_loaded:
                    logger.warning("⚠️  Contenu non chargé - fallback")
                    browser.close()
                    return self._get_fallback_notice()
                
                # Petit delay supplémentaire avant extraction
                time.sleep(random.uniform(1, 3))
                
                # Extraire les résultats
                offres = self._scroll_and_extract(page)
                
                browser.close()
                
        except Exception as e:
            logger.error(f"❌ Erreur LinkedIn scraping: {e}")
            return self._get_fallback_notice()
        
        # Filtrer pour ne garder que les pertinents
        filtered = [o for o in offres if self._is_relevant_offre(o)]
        logger.info(f"📦 {len(offres)} trouvés → {len(filtered)} pertinents sur {self.site_name}")
        
        if filtered:
            self.save_to_db(filtered)
        
        return filtered
    
    def _wait_for_content(self, page, timeout=25000) -> bool:
        """Attendre le contenu avec plusieurs sélecteurs fallback"""
        selectors = [
            'div.search-results-container',
            'ul.search-results__list',
            'div.results-container',
            'div.search-result__wrapper',
            'article',
        ]
        
        for selector in selectors:
            try:
                page.wait_for_selector(selector, timeout=timeout, state='attached')
                logger.debug(f"✅ Contenu trouvé avec: {selector}")
                return True
            except PlaywrightTimeout:
                logger.debug(f"⏳ Timeout pour: {selector}")
                continue
        
        # Dernière tentative: vérifier si la page a du texte
        try:
            content = page.content()
            if len(content) > 10000 and 'linkedin' in content.lower():
                logger.debug("✅ Page chargée (fallback par contenu)")
                return True
        except:
            pass
        
        return False
    
    def _scroll_and_extract(self, page) -> List[Dict]:
        """Scroll progressif et extraction des offres"""
        offres = []
        seen_urls = set()
        
        for scroll_num in range(self.max_scroll_attempts):
            logger.info(f"   📜 Scroll #{scroll_num + 1}/{self.max_scroll_attempts}")
            
            # Extraire avec plusieurs sélecteurs possibles
            items = []
            selectors = [
                'div.search-result__wrapper',
                'div.search-results-container > div',
                'ul.search-results__list > li',
                'article',
            ]
            
            for selector in selectors:
                try:
                    items = page.locator(selector).all()
                    if items:
                        logger.debug(f"✅ {len(items)} éléments avec: {selector}")
                        break
                except:
                    continue
            
            if not items:
                logger.warning("⚠️  Aucun élément trouvé avec les sélecteurs connus")
                break
            
            for item in items:
                try:
                    offre_data = self._parse_linkedin_item(item, page)
                    if offre_data and offre_data['url'] not in seen_urls:
                        seen_urls.add(offre_data['url'])
                        offres.append(offre_data)
                except Exception as e:
                    logger.debug(f"   Erreur parsing item: {e}")
                    continue
            
            # Stop si on a assez
            if len(offres) >= 15:
                logger.info(f"✅ Assez d'offres ({len(offres)}), arrêt du scroll")
                break
            
            # Scroll humain-like
            try:
                page.evaluate('window.scrollBy(0, window.innerHeight * 0.8)')
                time.sleep(self.delay_between_scrolls)
            except:
                break
        
        return offres
    
    def _parse_linkedin_item(self, item, page) -> Optional[Dict]:
        """Parse un élément de résultat LinkedIn - Version flexible"""
        try:
            # Extraire le titre avec fallbacks
            title = ''
            title_selectors = [
                'span.entity-result__title-text',
                'a.app-aware-link',
                'h3',
                'span.t-16',
                '[data-test-text="title"]',
            ]
            for selector in title_selectors:
                try:
                    elem = item.locator(selector).first
                    if elem.count() > 0:
                        title = elem.text_content().strip()
                        break
                except:
                    continue
            
            if not title or len(title) < 10:
                # Fallback: texte brut de l'item
                title = item.text_content().strip()[:100]
            
            if not self._is_relevant_title(title):
                return None
            
            # Extraire le lien
            link = ''
            link_elem = item.locator('a').first
            if link_elem.count() > 0:
                href = link_elem.get_attribute('href')
                if href:
                    link = href if href.startswith('http') else self.base_url + href
            
            # Filtrer liens non pertinents
            if any(skip in link for skip in ['/in/', '/company/', '/school/', '/learning/']):
                return None
            
            # Extraire description
            description = ''
            desc_selectors = [
                'div.entity-result__snippet',
                'div.t-14',
                '[data-test-text="description"]',
            ]
            for selector in desc_selectors:
                try:
                    elem = item.locator(selector).first
                    if elem.count() > 0:
                        description = elem.text_content().strip()
                        break
                except:
                    continue
            
            # Métadonnées
            metadata_text = item.text_content()
            location = self._extract_location(metadata_text)
            date_pub = self._extract_date_from_text(metadata_text)
            employment_type = self._classify_offer_type(title + ' ' + description)
            company = self._extract_company(metadata_text)
            
            return {
                'title': title[:200],
                'url': link or self.search_url,
                'source_url': self.search_url,
                'description': description[:500],
                'category': 'Appel d\'offre / Marché',
                'location': location or 'Côte d\'Ivoire',
                'employment_type': employment_type,
                'date_publication': date_pub,
                'company_name': company or 'Via LinkedIn',
                'tags': ['linkedin', 'appel d\'offre', 'côte d\'ivoire'],
                'platform': 'LinkedIn',
                'scraped_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.debug(f"   Erreur parse item: {e}")
            return None
    
    def _is_relevant_title(self, title: str) -> bool:
        """Filtre intelligent pour appels d'offres"""
        if not title or len(title) < 10:
            return False
        
        title_lower = title.lower()
        
        # Positif: doit contenir au moins un
        positive = [
            'appel d\'offre', 'appel d\'offres', 'marché public', 'consultance',
            'consulting', 'tender', 'bid', 'rfp', 'rft', 'soumission',
            'prestataire', 'fournisseur', 'contrat', 'marché', 'avis d\'appel'
        ]
        
        # Négatif: exclure si contient (offres d'emploi classiques)
        negative = [
            'recrute', 'hiring', 'nous recherchons', 'poste à pourvoir',
            'candidat', 'cv', 'entretien', 'salaire', 'rejoignez',
            'offre d\'emploi', 'job offer', 'career'
        ]
        
        has_positive = any(kw in title_lower for kw in positive)
        has_negative = any(kw in title_lower for kw in negative)
        
        return has_positive and not has_negative
    
    def _is_relevant_offre(self, offre: Dict) -> bool:
        """Filtre secondaire sur l'offre complète"""
        text = (
            offre.get('title', '') + ' ' + 
            offre.get('description', '') + ' ' + 
            offre.get('company_name', '')
        ).lower()
        
        # Exclure si trop générique
        if len(text) < 30:
            return False
        
        # Exclure si contient des mots d'emploi classique
        exclude = ['recrute', 'hiring', 'poste', 'candidat', 'cv', 'salaire']
        if any(kw in text for kw in exclude):
            return False
        
        # Inclure si contient mots-clés appel d'offre
        include = ['appel d\'offre', 'marché', 'consultance', 'tender', 'soumission']
        return any(kw in text for kw in include)
    
    def _extract_location(self, text: str) -> Optional[str]:
        """Extraction robuste de localisation"""
        locations = {
            'abidjan': 'Abidjan',
            'bouaké': 'Bouaké',
            'bouake': 'Bouaké',
            'yamoussoukro': 'Yamoussoukro',
            'san-pédro': 'San-Pédro',
            'san pedro': 'San-Pédro',
            'korhogo': 'Korhogo',
            'daloa': 'Daloa',
            'man': 'Man',
            'gagnoa': 'Gagnoa',
            'côte d\'ivoire': 'Côte d\'Ivoire',
            'cote d\'ivoire': 'Côte d\'Ivoire',
            'ivory coast': 'Côte d\'Ivoire',
            'abidjan, côte d\'ivoire': 'Abidjan, Côte d\'Ivoire',
        }
        
        text_lower = text.lower()
        for key, value in locations.items():
            if key in text_lower:
                return value
        return None
    
    def _extract_date_from_text(self, text: str) -> datetime:
        """Extraction de date avec multiples formats"""
        patterns = [
            # Français
            (r'il y a\s+(\d+)\s+jours?', lambda x: datetime.utcnow() - timedelta(days=int(x))),
            (r'il y a\s+(\d+)\s+semaines?', lambda x: datetime.utcnow() - timedelta(weeks=int(x))),
            (r'il y a\s+(\d+)\s+mois?', lambda x: datetime.utcnow() - timedelta(days=int(x)*30)),
            # Formats date
            (r'(\d{1,2}/\d{1,2}/\d{4})', lambda x: self._normalize_date(x)),
            (r'(\d{4}-\d{1,2}-\d{1,2})', lambda x: self._normalize_date(x)),
            (r'(\d{1,2}\s+[a-zA-Z]+\s+\d{4})', lambda x: self._normalize_date(x)),
            # LinkedIn format relatif
            (r'(\d+)d', lambda x: datetime.utcnow() - timedelta(days=int(x))),
            (r'(\d+)w', lambda x: datetime.utcnow() - timedelta(weeks=int(x))),
        ]
        
        for pattern, converter in patterns:
            match = re.search(pattern, text.lower())
            if match:
                try:
                    return converter(match.group(1))
                except:
                    continue
        
        return datetime.utcnow()
    
    def _classify_offer_type(self, text: str) -> str:
        """Classification intelligente du type d'offre"""
        text_lower = text.lower()
        
        classifications = [
            (['travaux', 'construction', 'btp', 'infrastructure', 'génie civil'], 'Appel d\'offre - Travaux'),
            (['fourniture', 'équipement', 'matériel', 'achat', 'supply'], 'Appel d\'offre - Fournitures'),
            (['consultance', 'consulting', 'étude', 'expertise', 'conseil'], 'Appel d\'offre - Consultance'),
            (['service', 'prestation', 'maintenance', 'support', 'assistance'], 'Appel d\'offre - Services'),
            (['formation', 'training', 'capacitation'], 'Appel d\'offre - Formation'),
        ]
        
        for keywords, category in classifications:
            if any(kw in text_lower for kw in keywords):
                return category
        
        return 'Appel d\'offre'
    
    def _extract_company(self, text: str) -> str:
        """Extraction du nom d'entreprise"""
        # LinkedIn sépare souvent avec · ou •
        parts = re.split(r'[·•|—]', text)
        if len(parts) >= 2:
            candidate = parts[1].strip()
            # Nettoyer et valider
            candidate = re.sub(r'\s+', ' ', candidate)
            if 3 < len(candidate) < 100 and candidate.lower() not in ['ci', 'fr', 'en', 'linkedin']:
                return candidate
        return ''
    
    def _get_realistic_user_agent(self) -> str:
        """User-Agents réalistes et variés"""
        return random.choice([
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15',
        ])
    
    def _get_fallback_notice(self) -> List[Dict]:
        """Notice de consultation manuelle en cas d'échec"""
        logger.info("🔄 Fallback LinkedIn - consultation manuelle")
        return [{
            'title': '🔍 Appels d\'offre Côte d\'Ivoire - LinkedIn',
            'url': self.search_url,
            'source_url': self.search_url,
            'description': 'LinkedIn restreint l\'accès automatisé à ses données de recherche. '
                          'Pour consulter les derniers appels d\'offre en Côte d\'Ivoire, '
                          'veuillez visiter directement ce lien LinkedIn et vous connecter. '
                          'Astuce: Utilisez les filtres "Posts" et "Récent" pour de meilleurs résultats.',
            'category': 'Appel d\'offre / Marché',
            'location': 'Côte d\'Ivoire',
            'employment_type': 'Appel d\'offre',
            'date_publication': datetime.utcnow(),
            'company_name': 'Divers (via LinkedIn)',
            'tags': ['linkedin', 'manuel', 'recherche', 'fallback'],
            'platform': 'LinkedIn',
            'scraped_at': datetime.utcnow().isoformat(),
            'requires_manual_check': True,
            'scraping_method': 'fallback_notification',
            'warning': 'LinkedIn bloque le scraping - consultation manuelle recommandée',
            'manual_tips': [
                'Connectez-vous à LinkedIn pour voir tous les résultats',
                'Utilisez le filtre "Posts" pour voir les publications',
                'Triez par "Récent" pour les dernières opportunités',
                'Activez les alertes pour recevoir des notifications'
            ]
        }]