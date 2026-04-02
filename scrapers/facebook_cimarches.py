from .base import BaseScraper
import logging
import time
import random
import re
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

# Try to import Playwright
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("⚠️ Playwright non installé - Facebook scraper en mode limité")


class FacebookCimarchesScraper(BaseScraper):
    """
    Scraper Facebook CIMarches avec Playwright
    
    ⚠️  ATTENTION: Facebook bloque activement le scraping.
    Ce code est fourni à titre éducatif. Usage commercial = risque légal.
    
    Alternative recommandée: API Graph Facebook officielle
    """
    
    def __init__(self):
        super().__init__('Facebook/CIMarches', 'https://www.facebook.com/cimarches')
        self.delay_between_actions = random.uniform(5, 10)
        
    def scrape(self) -> List[Dict]:
        logger.info(f"🔄 Démarrage scraping {self.site_name} avec Playwright...")
        
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
                    ]
                )
                
                # Contexte réaliste
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=self._get_realistic_user_agent(),
                    locale='fr-FR',
                    timezone_id='Africa/Abidjan',
                    # Optionnel: charger des cookies de session si tu en as
                    # storage_state='facebook_cookies.json'
                )
                
                context.set_extra_http_headers({
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'fr-FR,fr;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                })
                
                page = context.new_page()
                
                # Script anti-détection
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr'] });
                """)
                
                # Navigation
                logger.info(f"   🌐 Navigation vers Facebook...")
                try:
                    page.goto(self.base_url, wait_until='domcontentloaded', timeout=45000)
                except PlaywrightTimeout:
                    logger.warning("⚠️ Timeout Facebook - page peut-être bloquée")
                    browser.close()
                    return self._get_fallback_notice()
                
                # Attendre un peu que le JS charge
                time.sleep(random.uniform(3, 6))
                
                # Vérifier si on est redirigé vers login
                if 'login' in page.url.lower() or 'checkpoint' in page.url.lower():
                    logger.warning("⚠️ Redirigé vers login Facebook - accès refusé")
                    browser.close()
                    return self._get_fallback_notice()
                
                # Extraire le contenu
                offres = self._extract_posts(page)
                
                browser.close()
                
        except Exception as e:
            logger.error(f"❌ Erreur Facebook scraping: {e}")
            return self._get_fallback_notice()
        
        logger.info(f"📦 {len(offres)} posts extraits de {self.site_name}")
        
        # Filtrer pour ne garder que les pertinents
        filtered = [o for o in offres if self._is_relevant_post(o)]
        logger.info(f"✅ {len(filtered)} posts pertinents après filtrage")
        
        if filtered:
            self.save_to_db(filtered)
        
        return filtered
    
    def _extract_posts(self, page) -> List[Dict]:
        """Extrait les posts visibles sur la page"""
        offres = []
        
        try:
            # Facebook utilise des sélecteurs complexes - on essaie plusieurs approches
            
            # Approche 1: Par rôle sémantique (plus stable)
            posts = page.locator('[role="article"]').all()
            
            # Approche 2: Par structure commune
            if not posts:
                posts = page.locator('div[data-pagelet*="FeedUnit"]').all()
            
            # Approche 3: Fallback - tous les div avec du texte
            if not posts:
                # Cette approche est moins précise mais peut fonctionner
                content = page.content()
                return self._extract_from_raw_html(content)
            
            for post in posts[:15]:  # Limite pour éviter le sur-scraping
                try:
                    # Extraire le texte principal
                    text = post.text_content().strip()
                    if len(text) < 30:  # Ignorer les posts trop courts
                        continue
                    
                    # Extraire un lien si présent
                    link_elem = post.locator('a[href*="/cimarches/posts/"]').first
                    post_url = link_elem.get_attribute('href') if link_elem else self.base_url
                    if post_url and not post_url.startswith('http'):
                        post_url = 'https://www.facebook.com' + post_url
                    
                    # Extraire la date (approximative)
                    time_elem = post.locator('time').first
                    date_text = time_elem.get_attribute('datetime') if time_elem else None
                    date_pub = self._normalize_date(date_text) if date_text else datetime.utcnow()
                    
                    offre = {
                        'title': text[:150] + ('...' if len(text) > 150 else ''),
                        'url': post_url,
                        'source_url': self.base_url,
                        'description': text[:500],
                        'category': 'Réseau Social',
                        'location': 'Côte d\'Ivoire',
                        'employment_type': 'Appel d\'offre',
                        'date_publication': date_pub,
                        'company_name': 'CI Marchés (Facebook)',
                        'tags': ['facebook', 'social', 'cimarches', 'post'],
                        'platform': 'Facebook',
                        'scraped_at': datetime.utcnow().isoformat(),
                        'raw_text_length': len(text)
                    }
                    offres.append(offre)
                    
                except Exception as e:
                    logger.debug(f"   Erreur parsing post: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Erreur extraction posts: {e}")
        
        return offres
    
    def _extract_from_raw_html(self, html: str) -> List[Dict]:
        """Fallback: extraction depuis le HTML brut (moins fiable)"""
        offres = []
        
        # Chercher des patterns de texte qui ressemblent à des posts
        # Cette méthode est très basique et peut retourner des faux positifs
        lines = html.split('\n')
        current_text = []
        
        for line in lines:
            clean = line.strip()
            if len(clean) > 50 and 'appel' in clean.lower():
                offres.append({
                    'title': clean[:150],
                    'url': self.base_url,
                    'source_url': self.base_url,
                    'description': clean[:500],
                    'category': 'Réseau Social',
                    'location': 'Côte d\'Ivoire',
                    'employment_type': 'Appel d\'offre',
                    'date_publication': datetime.utcnow(),
                    'company_name': 'CI Marchés (Facebook)',
                    'tags': ['facebook', 'extraction-brute'],
                    'platform': 'Facebook',
                    'scraped_at': datetime.utcnow().isoformat(),
                    'extraction_method': 'raw_html_fallback'
                })
                if len(offres) >= 5:  # Limite
                    break
        
        return offres
    
    def _is_relevant_post(self, offre: Dict) -> bool:
        """Filtre pour vérifier si le post concerne un appel d'offre"""
        text = (offre.get('title', '') + ' ' + offre.get('description', '')).lower()
        
        # Mots-clés positifs
        positive = ['appel d\'offre', 'appel d\'offres', 'marché', 'consultance', 
                   'tender', 'soumission', 'prestataire', 'fournisseur', 'contrat']
        
        # Mots-clés négatifs (offres d'emploi classiques)
        negative = ['recrute', 'hiring', 'nous recherchons', 'poste à pourvoir',
                   'candidat', 'cv', 'entretien', 'salaire']
        
        has_positive = any(kw in text for kw in positive)
        has_negative = any(kw in text for kw in negative)
        
        return has_positive and not has_negative
    
    def _get_realistic_user_agent(self) -> str:
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36',
        ]
        return random.choice(user_agents)
    
    def _get_fallback_notice(self) -> List[Dict]:
        """Notice de consultation manuelle"""
        return [{
            'title': '📱 CI Marchés - Page Facebook',
            'url': 'https://www.facebook.com/cimarches/?locale=fr_FR',
            'source_url': self.base_url,
            'description': 'Facebook restreint l\'accès automatisé. Consultez cette page '
                          'manuellement pour voir les derniers appels d\'offres publiés.',
            'category': 'Réseau Social',
            'location': 'Côte d\'Ivoire',
            'employment_type': 'Appel d\'offre',
            'date_publication': datetime.utcnow(),
            'company_name': 'CI Marchés',
            'tags': ['facebook', 'manuel', 'consultation-requise'],
            'platform': 'Facebook',
            'scraped_at': datetime.utcnow().isoformat(),
            'requires_manual_check': True,
            'scraping_method': 'fallback_notification'
        }]