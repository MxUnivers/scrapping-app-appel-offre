# scrapers/__init__.py
"""
CI Offres Aggregator - Module Scrapers
Export de tous les scrapers pour les sites Côte d'Ivoire
"""

# =============================================================================
# CLASSE DE BASE
# =============================================================================
from .base import BaseScraper

# =============================================================================
# SCRAPERS EMPLOI & OFFRES GÉNÉRALES
# =============================================================================
from .emploi_ci import EmploiCiScraper
from .armp_ci import ArmpScraper

# =============================================================================
# SCRAPERS APPELS D'OFFRES - SITES GOUVERNEMENTAUX & INSTITUTIONNELS
# =============================================================================
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

# =============================================================================
# MANAGER - Orchestration de tous les scrapers
# =============================================================================
from .manager import ScraperManager, run_all_scrapers, run_single_scraper

# =============================================================================
# EXPORT PUBLIC - Toutes les classes disponibles à l'import
# =============================================================================
__all__ = [
    # Base
    'BaseScraper',
    
    # Scrapers emploi/offres générales
    'EmploiCiScraper',
    'ArmpScraper',
    
    # Scrapers appels d'offres - Sites CI
    'J360InfoScraper',              # j360.info
    'MarchesPublicsCiScraper',      # marchespublics.ci
    'EducarriereCiScraper',         # services.educarriere.ci
    'PriciCiScraper',               # prici.ci (travaux + fournitures)
    'FerCiScraper',                 # fer.ci
    'ArcopCiScraper',               # arcop.ci
    'EauxEtForetsGouvCiScraper',    # eauxetforets.gouv.ci
    'CosoCiScraper',                # coso.ci
    'BceaoIntScraper',              # bceao.int
    'BatiriciCiScraper',            # batirici.ci
    'OnadCiScraper',                # onad.ci
    'CorisBankCiScraper',           # cotedivoire.coris.bank
    'FacebookCimarchesScraper',     # facebook.com/cimarches (⚠️ limité)
    
    # Manager & fonctions utilitaires
    'ScraperManager',
    'run_all_scrapers',
    'run_single_scraper',
]

# =============================================================================
# FONCTIONS UTILITAIRES RAPIDES
# =============================================================================

def get_scraper_by_name(name: str):
    """
    Récupère une instance de scraper par son nom (case-insensitive)
    
    Args:
        name: Nom du scraper (ex: "J360.info", "ARMP", "PRICI.ci")
    
    Returns:
        Instance du scraper ou None si non trouvé
    """
    scrapers_map = {
        'emploi.ci': EmploiCiScraper,
        'armp': ArmpScraper,
        'j360.info': J360InfoScraper,
        'marchespublics.ci': MarchesPublicsCiScraper,
        'educarriere.ci': EducarriereCiScraper,
        'prici.ci': PriciCiScraper,
        'fer.ci': FerCiScraper,
        'arcop.ci': ArcopCiScraper,
        'eauxetforets.gouv.ci': EauxEtForetsGouvCiScraper,
        'coso.ci': CosoCiScraper,
        'bceao.int': BceaoIntScraper,
        'batirici.ci': BatiriciCiScraper,
        'onad.ci': OnadCiScraper,
        'coris.bank': CorisBankCiScraper,
        'facebook': FacebookCimarchesScraper,
    }
    
    scraper_class = scrapers_map.get(name.lower())
    if scraper_class:
        return scraper_class()
    return None


def list_available_scrapers():
    """
    Liste tous les scrapers disponibles avec leurs informations
    
    Returns:
        Liste de dictionnaires avec infos sur chaque scraper
    """
    return [
        {'name': 'Emploi.ci', 'class': 'EmploiCiScraper', 'type': 'Emploi', 'url': 'https://www.emploi.ci'},
        {'name': 'ARMP', 'class': 'ArmpScraper', 'type': 'Marchés Publics', 'url': 'https://www.armp.ci'},
        {'name': 'J360.info', 'class': 'J360InfoScraper', 'type': 'Appels d\'offres Afrique', 'url': 'https://www.j360.info'},
        {'name': 'MarchesPublics.ci', 'class': 'MarchesPublicsCiScraper', 'type': 'Portail Officiel MP', 'url': 'https://www.marchespublics.ci'},
        {'name': 'Educarriere.ci', 'class': 'EducarriereCiScraper', 'type': 'Éducation/Formation', 'url': 'https://services.educarriere.ci'},
        {'name': 'PRICI.ci', 'class': 'PriciCiScraper', 'type': 'Travaux & Fournitures', 'url': 'https://www.prici.ci'},
        {'name': 'FER.ci', 'class': 'FerCiScraper', 'type': 'Infrastructures Routières', 'url': 'https://www.fer.ci'},
        {'name': 'ARCOP.ci', 'class': 'ArcopCiScraper', 'type': 'Régulation Marchés Publics', 'url': 'https://arcop.ci'},
        {'name': 'Eaux&Forêts.gouv.ci', 'class': 'EauxEtForetsGouvCiScraper', 'type': 'Environnement', 'url': 'https://eauxetforets.gouv.ci'},
        {'name': 'COSO.ci', 'class': 'CosoCiScraper', 'type': 'Finance/Bourse', 'url': 'https://coso.ci'},
        {'name': 'BCEAO.int', 'class': 'BceaoIntScraper', 'type': 'Banque Centrale UEMOA', 'url': 'https://www.bceao.int'},
        {'name': 'Batirici.ci', 'class': 'BatiriciCiScraper', 'type': 'BTP/Construction', 'url': 'https://www.batirici.ci'},
        {'name': 'ONAD.ci', 'class': 'OnadCiScraper', 'type': 'Office National', 'url': 'https://onad.ci'},
        {'name': 'CorisBank.ci', 'class': 'CorisBankCiScraper', 'type': 'Banque Privée', 'url': 'https://cotedivoire.coris.bank'},
        {'name': 'Facebook/CIMarches', 'class': 'FacebookCimarchesScraper', 'type': 'Réseau Social ⚠️', 'url': 'https://www.facebook.com/cimarches'},
    ]


def get_stats_summary():
    """
    Retourne un résumé statistique des scrapers configurés
    
    Returns:
        Dict avec stats globales
    """
    scrapers_info = list_available_scrapers()
    
    return {
        'total_scrapers': len(scrapers_info),
        'by_type': {},
        'sources': [s['name'] for s in scrapers_info],
        'warning': 'Facebook scraper est limité - consultation manuelle recommandée'
    }
    
    # Comptage par type
    for scraper in scrapers_info:
        t = scraper['type']
        get_stats_summary()['by_type'][t] = get_stats_summary()['by_type'].get(t, 0) + 1