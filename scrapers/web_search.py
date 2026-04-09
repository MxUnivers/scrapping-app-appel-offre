from .base import BaseScraper
import logging
import os
import re
import time
import random
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urlparse, urljoin

# Document parsing imports
try:
    import PyPDF2
    from docx import Document as WordDocument
    import openpyxl
    import pandas as pd
    DOCUMENT_PARSING_AVAILABLE = True
except ImportError:
    DOCUMENT_PARSING_AVAILABLE = False
    logging.warning("⚠️  Libraries de parsing de documents non installées")

# Search API imports
try:
    from duckduckgo_search import DDGS
    SEARCH_API_AVAILABLE = True
except ImportError:
    SEARCH_API_AVAILABLE = False
    logging.warning("⚠️  duckduckgo-search non installé - web search désactivé")

logger = logging.getLogger(__name__)


class WebSearchScraper(BaseScraper):
    """
    Scraper de recherche web pour trouver des appels d'offre
    
    Fonctionnalités :
    - Recherche Google/DuckDuckGo avec mots-clés configurables
    - Parcours jusqu'à N résultats de recherche
    - Extraction de contenu et détection d'appels d'offre
    - Téléchargement et parsing de documents (PDF, Word, Excel, CSV)
    - Stockage dans MongoDB avec métadonnées enrichies
    """
    
    def __init__(self):
        super().__init__('WebSearch CI', 'https://duckduckgo.com')
        
        # Mots-clés de recherche pour la Côte d'Ivoire
        self.keywords = [
            "appel d'offre Côte d'Ivoire",
            "marché public Abidjan",
            "consultation entreprise CI",
            "avis d'appel d'offres Côte d'Ivoire",
            "tender Ivory Coast",
            "Reseau Informatique appel d'offre",
            "Consultation batiment Côte d'Ivoire",
            "Cyber sécurité marché public",
            "Microsoft appel d'offre CI",
            "Developpement d'application marché public",
            "Système Information appel d'offre",
            "Vente de matériel informatique Côte d'Ivoire",
            "Informatique consultation entreprise",
            "Acquisition équipement CI",
        ]
        
        # Configuration
        self.max_results_per_keyword = 20  # Résultats de recherche par mot-clé
        self.max_pages_to_visit = 100      # Pages à visiter au total
        self.download_documents = True     # Télécharger les fichiers trouvés
        self.download_folder = Path("downloads/web_search")
        self.download_folder.mkdir(parents=True, exist_ok=True)
        
        # Délais pour éviter les blocages
        self.delay_between_requests = random.uniform(3, 7)
        self.delay_between_keywords = random.uniform(5, 10)
        
        # Filtres de contenu
        self.relevant_keywords = [
            'appel d\'offre', 'appel d\'offres', 'marché public', 'consultation',
            'avis d\'appel', 'tender', 'bid', 'rfp', 'soumission',
            'prestataire', 'fournisseur', 'contrat public', 'DAO', 'DCE'
        ]
        
        self.exclude_keywords = [
            'emploi', 'recrutement', 'stage', 'cdd', 'cdi', 'hiring',
            'offre d\'emploi', 'job', 'career', 'postulez'
        ]
        
        # Extensions de documents à télécharger
        self.document_extensions = [
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv',
            '.ppt', '.pptx', '.txt', '.rtf', '.odt', '.ods'
        ]
    
    def scrape(self) -> List[Dict]:
        """Scrape le web pour trouver des appels d'offre"""
        logger.info(f"🔄 Démarrage WebSearch scraper avec {len(self.keywords)} mots-clés...")
        
        if not SEARCH_API_AVAILABLE:
            logger.error("❌ duckduckgo-search non disponible")
            return []
        
        all_offres = []
        visited_urls = set()
        pages_visited = 0
        
        for i, keyword in enumerate(self.keywords, 1):
            if pages_visited >= self.max_pages_to_visit:
                logger.info(f"✅ Limite de pages atteinte ({self.max_pages_to_visit})")
                break
                
            logger.info(f"[{i}/{len(self.keywords)}] Recherche: '{keyword}'")
            
            try:
                # Effectuer la recherche
                search_results = self._search_web(keyword, max_results=self.max_results_per_keyword)
                
                for result in search_results:
                    if pages_visited >= self.max_pages_to_visit:
                        break
                    
                    url = result.get('href') or result.get('link') or result.get('url')
                    if not url or url in visited_urls:
                        continue
                    
                    # Filtrer les URLs non pertinentes
                    if not self._is_valid_url(url):
                        continue
                    
                    visited_urls.add(url)
                    pages_visited += 1
                    
                    logger.info(f"   📄 [{pages_visited}/{self.max_pages_to_visit}] Visit: {url[:80]}...")
                    
                    # Analyser la page
                    page_data = self._analyze_page(url)
                    if page_data and self._is_relevant_content(page_data):
                        
                        # Extraire les informations
                        offre = self._extract_offre_data(url, page_data, keyword)
                        if offre:
                            all_offres.append(offre)
                            
                            # Télécharger les documents associés
                            if self.download_documents:
                                docs = self._download_documents(url, page_data)
                                if docs:
                                    offre['attached_documents'] = docs
                                    logger.info(f"   📎 {len(docs)} document(s) téléchargé(s)")
                    
                    # Delay entre les pages
                    time.sleep(self.delay_between_requests)
                
                # Delay entre les mots-clés
                time.sleep(self.delay_between_keywords)
                
            except Exception as e:
                logger.error(f"❌ Erreur recherche '{keyword}': {e}")
                continue
        
        logger.info(f"📦 WebSearch terminé: {len(all_offres)} offres trouvées ({pages_visited} pages visitées)")
        
        if all_offres:
            self.save_to_db(all_offres)
        
        return all_offres
    
    def _search_web(self, keyword: str, max_results: int = 20) -> List[Dict]:
        """Effectue une recherche web via DuckDuckGo"""
        results = []
        
        try:
            with DDGS() as ddgs:
                # DuckDuckGo search
                ddg_results = ddgs.text(
                    keyword,
                    region='fr-fr',
                    safesearch='moderate',
                    timelimit='y',  # Résultats de l'année dernière
                    max_results=max_results
                )
                
                for r in ddg_results:
                    results.append({
                        'title': r.get('title', ''),
                        'href': r.get('href', ''),
                        'body': r.get('body', ''),
                        'source': r.get('source', '')
                    })
                    
        except Exception as e:
            logger.warning(f"⚠️  Erreur recherche DuckDuckGo: {e}")
            # Fallback: retourne des résultats vides
            return []
        
        logger.debug(f"   🔍 {len(results)} résultats pour '{keyword}'")
        return results
    
    def _is_valid_url(self, url: str) -> bool:
        """Filtre les URLs non pertinentes"""
        # Exclure les domaines non pertinents
        excluded_domains = [
            'linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com',
            'youtube.com', 'tiktok.com', 'pinterest.com'
        ]
        
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Exclure les réseaux sociaux
        if any(excl in domain for excl in excluded_domains):
            return False
        
        # Exclure les URLs avec certains patterns
        excluded_patterns = ['/job', '/career', '/emploi', '/recrutement', '/hiring']
        if any(pat in url.lower() for pat in excluded_patterns):
            return False
        
        # Accepter uniquement http/https
        if parsed.scheme not in ['http', 'https']:
            return False
        
        return True
    
    def _analyze_page(self, url: str) -> Optional[Dict]:
        """Télécharge et analyse le contenu d'une page"""
        try:
            headers = {
                'User-Agent': self._get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'fr-FR,fr;q=0.9',
            }
            
            response = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
            response.raise_for_status()
            
            # Vérifier le type de contenu
            content_type = response.headers.get('Content-Type', '').lower()
            
            # Si c'est un document direct (PDF, etc.)
            if any(ext in content_type for ext in ['pdf', 'msword', 'excel', 'csv']):
                return {
                    'is_document': True,
                    'content_type': content_type,
                    'content': response.content,
                    'text': '',
                    'links': [],
                    'title': url.split('/')[-1]
                }
            
            # Parser le HTML
            soup = self._parse_html(response.text)
            if not soup:
                return None
            
            # Extraire le texte principal
            text_content = self._extract_main_text(soup)
            
            # Extraire les liens vers des documents
            document_links = self._find_document_links(soup, url)
            
            # Extraire les métadonnées
            title = soup.find('title')
            title_text = title.text.strip() if title else ''
            
            return {
                'is_document': False,
                'content_type': content_type,
                'text': text_content,
                'links': document_links,
                'title': title_text,
                'meta_description': self._get_meta_tag(soup, 'description'),
                'html': response.text[:50000]  # Limiter la taille
            }
            
        except requests.exceptions.RequestException as e:
            logger.debug(f"   Erreur chargement page: {e}")
            return None
        except Exception as e:
            logger.debug(f"   Erreur analyse page: {e}")
            return None
    
    def _extract_main_text(self, soup) -> str:
        """Extrait le texte principal d'une page HTML"""
        # Supprimer les éléments non pertinents
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        
        # Chercher le contenu principal
        main_content = (
            soup.find('main') or 
            soup.find('article') or 
            soup.find('div', class_='content') or
            soup.find('div', id='content') or
            soup.body
        )
        
        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
            # Nettoyer le texte
            text = re.sub(r'\n{3,}', '\n\n', text)
            return text[:10000]  # Limiter à 10k caractères
        
        return soup.get_text(strip=True)[:5000]
    
    def _find_document_links(self, soup, base_url: str) -> List[Dict]:
        """Trouve les liens vers des documents téléchargeables"""
        documents = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True).lower()
            
            # Vérifier si c'est un lien vers un document
            if any(href.lower().endswith(ext) for ext in self.document_extensions):
                full_url = urljoin(base_url, href)
                documents.append({
                    'url': full_url,
                    'text': text or href.split('/')[-1],
                    'extension': Path(href).suffix.lower()
                })
            # Ou si le texte du lien indique un document
            elif any(kw in text for kw in ['pdf', 'télécharger', 'download', 'doc', 'excel']):
                full_url = urljoin(base_url, href)
                # Essayer de détecter l'extension
                ext = self._detect_extension_from_url(full_url)
                if ext:
                    documents.append({
                        'url': full_url,
                        'text': text,
                        'extension': ext
                    })
        
        return documents[:10]  # Limiter à 10 documents par page
    
    def _detect_extension_from_url(self, url: str) -> Optional[str]:
        """Détecte l'extension de fichier depuis une URL"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        for ext in self.document_extensions:
            if path.endswith(ext):
                return ext
        return None
    
    def _is_relevant_content(self, page_data: Dict) -> bool:
        """Détermine si le contenu concerne un appel d'offre"""
        text = (page_data.get('title', '') + ' ' + 
                page_data.get('text', '') + ' ' + 
                page_data.get('meta_description', '')).lower()
        
        # Doit contenir au moins un mot-clé pertinent
        has_relevant = any(kw in text for kw in self.relevant_keywords)
        if not has_relevant:
            return False
        
        # Ne doit pas contenir de mots-clés d'exclusion
        has_excluded = any(kw in text for kw in self.exclude_keywords)
        if has_excluded:
            return False
        
        return True
    
    def _extract_offre_data(self, url: str, page_data: Dict, keyword: str) -> Optional[Dict]:
        """Extrait les données structurées d'un appel d'offre"""
        text = page_data.get('text', '')
        title = page_data.get('title', '')
        
        # Titre
        offre_title = title or self._extract_title_from_text(text) or keyword
        
        # Description
        description = self._extract_snippet(text, max_length=500)
        
        # Date de publication (approximative)
        date_pub = self._extract_date_from_content(text)
        
        # Localisation
        location = self._extract_location(text)
        
        # Type d'offre
        employment_type = self._classify_offer_type(text)
        
        # Entreprise/organisme
        company = self._extract_organization(text)
        
        return {
            'title': offre_title[:200],
            'url': url,
            'source_url': url,
            'description': description,
            'category': 'Web Search',
            'subcategory': keyword,
            'location': location or 'Côte d\'Ivoire',
            'employment_type': employment_type,
            'date_publication': date_pub,
            'company_name': company,
            'tags': ['web-search', keyword, 'auto-detect'],
            'source_type': 'web_search',
            'search_keyword': keyword,
            'content_preview': text[:1000],
            'scraped_at': datetime.utcnow().isoformat()
        }
    
    def _extract_title_from_text(self, text: str) -> Optional[str]:
        """Extrait un titre potentiel depuis le texte"""
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 20]
        for line in lines[:10]:  # Chercher dans les premières lignes
            if any(kw in line.lower() for kw in self.relevant_keywords):
                return line[:150]
        return None
    
    def _extract_snippet(self, text: str, max_length: int = 500) -> str:
        """Extrait un snippet pertinent du texte"""
        # Chercher les phrases contenant des mots-clés
        sentences = re.split(r'[.!?]+', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 30 and any(kw in sentence.lower() for kw in self.relevant_keywords):
                return sentence[:max_length] + ('...' if len(sentence) > max_length else '')
        
        # Fallback: premières lignes
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 10]
        return ' '.join(lines[:3])[:max_length]
    
    def _extract_date_from_content(self, text: str) -> datetime:
        """Extrait une date depuis le contenu"""
        # Patterns de date courants
        patterns = [
            r'(\d{1,2}/\d{1,2}/\d{4})',
            r'(\d{4}-\d{1,2}-\d{1,2})',
            r'(\d{1,2}\s+[a-zA-Z]+\s+\d{4})',
            r'(publié\s+le\s+[\d\s/a-zA-Z]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return self._normalize_date(match.group(1))
                except:
                    continue
        
        return datetime.utcnow()
    
    def _extract_location(self, text: str) -> Optional[str]:
        """Extrait la localisation depuis le texte"""
        locations = {
            'abidjan': 'Abidjan', 'bouaké': 'Bouaké', 'yamoussoukro': 'Yamoussoukro',
            'san-pédro': 'San-Pédro', 'korhogo': 'Korhogo', 'daloa': 'Daloa',
            'côte d\'ivoire': 'Côte d\'Ivoire', 'cote d\'ivoire': 'Côte d\'Ivoire',
            'ivory coast': 'Côte d\'Ivoire'
        }
        
        text_lower = text.lower()
        for key, value in locations.items():
            if key in text_lower:
                return value
        return None
    
    def _classify_offer_type(self, text: str) -> str:
        """Classifie le type d'appel d'offre"""
        text_lower = text.lower()
        
        classifications = [
            (['informatique', 'réseau', 'cyber', 'microsoft', 'application', 'système'], 'Appel d\'offre - Informatique'),
            (['batiment', 'construction', 'travaux', 'infrastructure'], 'Appel d\'offre - BTP'),
            (['matériel', 'équipement', 'fourniture', 'acquisition'], 'Appel d\'offre - Fournitures'),
            (['consultation', 'étude', 'expertise', 'conseil'], 'Appel d\'offre - Consultance'),
            (['vente', 'commercial', 'distribution'], 'Appel d\'offre - Commercial'),
        ]
        
        for keywords, category in classifications:
            if any(kw in text_lower for kw in keywords):
                return category
        
        return 'Appel d\'offre'
    
    def _extract_organization(self, text: str) -> Optional[str]:
        """Tente d'extraire le nom de l'organisme"""
        # Patterns courants pour les organismes en CI
        patterns = [
            r'(?:ministère|direction|agence|office|société)\s+[^.\n]{10,50}',
            r'[A-Z]{2,}(?:\s+[A-Z][a-z]+){2,}',  # Acronymes
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                org = match.group(0).strip()
                if 10 < len(org) < 100:  # Validation basique
                    return org
        return None
    
    def _download_documents(self, page_url: str, page_data: Dict) -> List[Dict]:
        """Télécharge et parse les documents trouvés"""
        if not DOCUMENT_PARSING_AVAILABLE:
            logger.debug("   ⚠️  Parsing de documents désactivé")
            return []
        
        downloaded = []
        document_links = page_data.get('links', [])
        
        for doc in document_links:
            try:
                url = doc['url']
                ext = doc['extension']
                
                logger.debug(f"   📥 Téléchargement: {url[:60]}...")
                
                # Télécharger le fichier
                response = requests.get(url, timeout=30, stream=True)
                response.raise_for_status()
                
                # Nommer le fichier
                filename = self._sanitize_filename(doc['text'] or Path(url).name)
                filepath = self.download_folder / f"{datetime.utcnow().strftime('%Y%m%d')}_{filename}"
                
                # Sauvegarder le fichier
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Parser le contenu si possible
                content_text = self._parse_document(filepath, ext)
                
                downloaded.append({
                    'filename': filename,
                    'filepath': str(filepath),
                    'url': url,
                    'extension': ext,
                    'size_bytes': os.path.getsize(filepath),
                    'parsed_content_preview': content_text[:500] if content_text else None,
                    'downloaded_at': datetime.utcnow().isoformat()
                })
                
                logger.debug(f"   ✅ Document téléchargé: {filename}")
                
            except Exception as e:
                logger.debug(f"   ❌ Erreur téléchargement {doc['url']}: {e}")
                continue
        
        return downloaded
    
    def _sanitize_filename(self, filename: str) -> str:
        """Nettoie un nom de fichier pour le stockage"""
        # Supprimer les caractères invalides
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Limiter la longueur
        return filename[:100] or 'document'
    
    def _parse_document(self, filepath: Path, ext: str) -> Optional[str]:
        """Extrait le texte d'un document"""
        try:
            if ext == '.pdf' and 'PyPDF2' in globals():
                with open(filepath, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ''
                    for page in reader.pages[:5]:  # Limiter aux 5 premières pages
                        text += page.extract_text() or ''
                    return text
            
            elif ext in ['.doc', '.docx'] and 'WordDocument' in globals():
                doc = WordDocument(str(filepath))
                return '\n'.join([p.text for p in doc.paragraphs])
            
            elif ext in ['.xls', '.xlsx'] and 'openpyxl' in globals():
                wb = openpyxl.load_workbook(filepath, data_only=True)
                texts = []
                for sheet in wb.worksheets[:2]:  # 2 premières feuilles
                    for row in sheet.iter_rows(values_only=True):
                        texts.append(' | '.join(str(c) for c in row if c is not None))
                return '\n'.join(texts[:50])  # Limiter
            
            elif ext == '.csv' and 'pandas' in globals():
                df = pd.read_csv(filepath, nrows=20)
                return df.to_string()
            
        except Exception as e:
            logger.debug(f"   Erreur parsing {filepath}: {e}")
        
        return None
    
    def _get_meta_tag(self, soup, name: str) -> str:
        """Extrait une balise meta"""
        meta = soup.find('meta', attrs={'name': name}) or soup.find('meta', attrs={'property': name})
        return meta.get('content', '').strip() if meta else ''
    
    def _get_random_user_agent(self) -> str:
        """Retourne un User-Agent réaliste"""
        return random.choice([
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        ])