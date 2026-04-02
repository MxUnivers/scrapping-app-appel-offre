import logging
from datetime import datetime

from scrapers.linkedine_ci import LinkedInCiScraper

logger = logging.getLogger(__name__)

# Import TOUS les scrapers
from .emploi_ci import EmploiCiScraper
from .armp_ci import ArmpScraper
from .j360_info import J360InfoScraper
from .marchespublics_ci import MarchesPublicsCiScraper
from .educarriere_ci import EducarriereCiScraper
from .prici_ci import PriciCiScraper
from .fer_ci import FerCiScraper
from .arcop_ci import ArcopCiScraper
from .eauxetforets_gouv_ci import EauxEtForetsGouvCiScraper
from .coso_ci import CosoCiScraper
from .bceao_int import BceaoIntScraper
from .batirici_ci import BatiriciCiScraper
from .onad_ci import OnadCiScraper
from .coris_bank_ci import CorisBankCiScraper
from .facebook_cimarches import FacebookCimarchesScraper


class ScraperManager:
    """Gère l'exécution de TOUS les scrapers CI"""

    def __init__(self):
        self.scrapers = [
            # Scrapers de base
            EmploiCiScraper(),
            ArmpScraper(),
            
            # Sites d'appels d'offres Côte d'Ivoire
            J360InfoScraper(),
            MarchesPublicsCiScraper(),
            EducarriereCiScraper(),
            PriciCiScraper(),  # Gère 2 URLs: travaux + fournitures
            FerCiScraper(),
            ArcopCiScraper(),
            EauxEtForetsGouvCiScraper(),
            CosoCiScraper(),
            BceaoIntScraper(),
            BatiriciCiScraper(),
            OnadCiScraper(),
            CorisBankCiScraper(),
            FacebookCimarchesScraper(),  # ⚠️ Limité
            LinkedInCiScraper(),  # ← NOUVEAU
        ]
        
        logger.info(f"✅ ScraperManager initialisé avec {len(self.scrapers)} sources")
    
    def run_all(self):
        """Exécute TOUS les scrapers avec gestion d'erreurs individuelle"""
        logger.info("🚀 Démarrage du scraping massif - Toutes sources CI...")
        start_time = datetime.utcnow()
        
        results = {}
        total_offres = 0
        successful = 0
        failed = 0
        
        for i, scraper in enumerate(self.scrapers, 1):
            try:
                logger.info(f"▶️  [{i}/{len(self.scrapers)}] Lancement: {scraper.site_name}...")
                
                offres = scraper.scrape()
                count = len(offres) if offres else 0
                
                results[scraper.site_name] = {
                    'status': 'success',
                    'count': count,
                    'timestamp': datetime.utcnow().isoformat()
                }
                total_offres += count
                successful += 1
                
                logger.info(f"✅ [{i}/{len(self.scrapers)}] {scraper.site_name}: {count} offres")
                
            except Exception as e:
                failed += 1
                logger.error(f"❌ [{i}/{len(self.scrapers)}] Erreur {scraper.site_name}: {e}")
                results[scraper.site_name] = {
                    'status': 'error',
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Pause entre les scrapers pour respecter les serveurs
            import time
            time.sleep(3)
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        summary = {
            'status': 'completed',
            'total_offres': total_offres,
            'successful_scrapers': successful,
            'failed_scrapers': failed,
            'total_scrapers': len(self.scrapers),
            'elapsed_seconds': round(elapsed, 2),
            'results': results
        }
        
        logger.info(f"📊 RÉSUMÉ: {total_offres} offres | {successful}/{len(self.scrapers)} OK | {elapsed:.1f}s")
        
        return summary


def run_all_scrapers():
    """Fonction utilitaire pour lancer tous les scrapers"""
    manager = ScraperManager()
    return manager.run_all()


def run_single_scraper(scraper_name):
    """Exécute un seul scraper par nom (pour tests/debug)"""
    manager = ScraperManager()
    
    for scraper in manager.scrapers:
        if scraper.site_name.lower() == scraper_name.lower():
            logger.info(f"🎯 Exécution unique: {scraper.site_name}")
            return scraper.scrape()
    
    logger.error(f"❌ Scraper '{scraper_name}' non trouvé")
    return []