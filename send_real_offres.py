#!/usr/bin/env python3
"""
CI Offres - Envoi des Appels d'Offres RÉELS aux Utilisateurs

Ce script récupère les VRAIES offres scrapées depuis MongoDB
et les envoie par email aux abonnés.

Usage:
    python send_real_offres.py                    # Envoi aux abonnés actifs (mode sécurisé)
    python send_real_offres.py --test             # Mode test: envoie uniquement à l'admin
    python send_real_offres.py --email x@y.ci     # Envoi test à un email spécifique
    python send_real_offres.py --since 7          # Offres des 7 derniers jours seulement
    python send_real_offres.py --dry-run          # Simulation sans envoyer (voir ce qui serait envoyé)
    python send_real_offres.py --help             # Afficher l'aide

⚠️  Par défaut: envoi aux abonnés actifs uniquement
⚠️  Les offres envoyées sont marquées is_sent=True pour éviter les doublons
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# =============================================================================
# 🔧 AJOUTER LE PROJET AU PYTHONPATH
# =============================================================================
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# =============================================================================

# Imports
from mongoengine import connect, Q
from dotenv import load_dotenv
from config import Config
from models.offre import Offre
from models.subscription import EmailSubscription
from models.user import User
from services.email_service import EmailService
from flask import Flask, render_template_string

# Charger les variables d'environnement
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

class EmailConfig:
    """Configuration centralisée pour l'envoi d'emails"""
    
    # Limites pour éviter les spams
    MAX_OFFRES_PER_EMAIL = 15          # Max offres par email
    MIN_OFFRES_TO_SEND = 1             # Min offres pour déclencher un envoi
    
    # Filtres par défaut
    DEFAULT_DAYS_BACK = 7              # Récupérer les offres des X derniers jours
    EXCLUDE_SENT = True                # Exclure les offres déjà envoyées
    
    # Templates email (inline pour simplicité)
    EMAIL_SUBJECT_TEMPLATE = "🇨🇮 CI Offres - {count} nouvel(le)s opportunité(s) - {date}"
    
    EMAIL_HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CI Offres - Appels d'Offres</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f4f4; line-height: 1.6; color: #333; }
            .container { max-width: 650px; margin: 0 auto; background: white; }
            .header { background: linear-gradient(135deg, #007bff 0%, #0056b3 100%); color: white; padding: 25px; text-align: center; }
            .header h1 { font-size: 24px; margin-bottom: 5px; }
            .header .date { opacity: 0.9; font-size: 14px; }
            .header .flag { font-size: 32px; margin-bottom: 10px; }
            .intro { background: #f8f9fa; padding: 20px; text-align: center; border-bottom: 1px solid #eee; }
            .intro strong { color: #007bff; }
            .offre { border-left: 4px solid #007bff; margin: 0; padding: 20px; background: #fff; border-bottom: 1px solid #eee; }
            .offre:last-child { border-bottom: none; }
            .offre-title { color: #007bff; font-size: 18px; font-weight: 600; margin-bottom: 8px; }
            .offre-title a { color: #007bff; text-decoration: none; }
            .offre-title a:hover { text-decoration: underline; }
            .offre-meta { color: #666; font-size: 13px; margin: 5px 0; }
            .offre-meta span { margin-right: 15px; }
            .offre-desc { color: #555; font-size: 14px; margin: 10px 0; line-height: 1.5; }
            .btn { display: inline-block; background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 10px; font-weight: 500; font-size: 14px; }
            .btn:hover { background: #0056b3; }
            .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; margin-right: 5px; }
            .badge-appel { background: #ffc107; color: #333; }
            .badge-emploi { background: #28a745; color: white; }
            .badge-informatique { background: #17a2b8; color: white; }
            .badge-btp { background: #6c757d; color: white; }
            .footer { background: #f8f9fa; text-align: center; padding: 25px; color: #999; font-size: 12px; border-top: 1px solid #eee; }
            .footer a { color: #007bff; text-decoration: none; }
            .source-tag { background: #e9ecef; padding: 2px 8px; border-radius: 3px; font-size: 11px; color: #666; }
            @media (max-width: 600px) {
                .container { margin: 0 10px; }
                .header { padding: 20px 15px; }
                .offre { padding: 15px; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="flag">🇨🇮</div>
                <h1>CI Offres</h1>
                <div class="date">{date}</div>
            </div>
            
            <div class="intro">
                <p>Bonjour,</p>
                <p>Voici <strong>{count} nouvel(le)s opportunité(s)</strong> en Côte d'Ivoire :</p>
            </div>
            
            {offres_html}
            
            <div class="footer">
                <p>🔍 CI Offres Aggregator - Veille automatique des appels d'offres</p>
                <p style="margin-top: 10px;">
                    <a href="{base_url}/api/offres">Voir toutes les offres</a> • 
                    <a href="{base_url}/api/unsubscribe/{email}">Se désabonner</a>
                </p>
                <p style="margin-top: 15px; color: #bbb;">
                    Ce message a été envoyé à {email} car vous êtes abonné à CI Offres.
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    OFFRE_ITEM_TEMPLATE = """
    <div class="offre">
        <div class="offre-title">
            <a href="{url}" target="_blank">{title}</a>
        </div>
        <div class="offre-meta">
            {badges}
            <span>📍 {location}</span>
            <span>🏢 {source}</span>
            <span>📅 {date}</span>
        </div>
        <div class="offre-desc">{description}</div>
        <a href="{url}" class="btn" target="_blank">Voir l'offre complète →</a>
    </div>
    """


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def print_header(title: str, char: str = "="):
    print(f"\n{char * 70}")
    print(f"  {title}")
    print(f"{char * 70}\n")

def print_success(msg: str): print(f"✅ {msg}")
def print_error(msg: str): print(f"❌ {msg}")
def print_info(msg: str): print(f"ℹ️  {msg}")
def print_warning(msg: str): print(f"⚠️  {msg}")


def init_app() -> tuple:
    """Initialise Flask + MongoDB + Email Service"""
    print_info("Initialisation de l'application...")
    
    app = Flask(__name__)
    app.config.from_object(Config)
    
    try:
        connect(**app.config['MONGODB_SETTINGS'])
        print_success("✅ Connecté à MongoDB")
    except Exception as e:
        print_error(f"❌ Erreur MongoDB: {e}")
        return None, None
    
    email_service = EmailService()
    try:
        email_service.init_app(app)
        print_success("✅ Service Email initialisé")
    except Exception as e:
        print_warning(f"⚠️  Service Email: {e}")
    
    return app, email_service


def get_real_offres(
    days_back: int = EmailConfig.DEFAULT_DAYS_BACK,
    exclude_sent: bool = EmailConfig.EXCLUDE_SENT,
    limit: int = EmailConfig.MAX_OFFRES_PER_EMAIL,
    category: Optional[str] = None
) -> List[Offre]:
    """
    Récupère les VRAIES offres depuis MongoDB
    
    Args:
        days_back: Nombre de jours en arrière pour filtrer
        exclude_sent: Exclure les offres déjà envoyées
        limit: Nombre maximum d'offres à retourner
        category: Filtrer par catégorie (optionnel)
    
    Returns:
        Liste d'objets Offre
    """
    print_info(f"Recherche d'offres réelles (derniers {days_back} jours)...")
    
    # Date limite
    since_date = datetime.utcnow() - timedelta(days=days_back)
    
    # Construire la requête
    query = Q(is_active=True) & Q(date_publication__gte=since_date)
    
    if exclude_sent:
        query &= Q(is_sent=False)
    
    if category:
        query &= Q(category=category)
    
    # Exécuter la requête
    offres = Offre.objects(query)\
        .order_by('-date_publication')\
        .limit(limit)
    
    count = offres.count()
    print_info(f"📦 {count} offre(s) réelle(s) trouvée(s)")
    
    return list(offres)


def format_offre_for_email(offre: Offre) -> str:
    """Formate une offre pour l'email HTML"""
    # Badges selon le type
    badge_class = "badge-appel"
    if "informatique" in (offre.category or "").lower():
        badge_class = "badge-informatique"
    elif "btp" in (offre.category or "").lower() or "construction" in (offre.category or "").lower():
        badge_class = "badge-btp"
    elif offre.employment_type == "Appel d'offre":
        badge_class = "badge-appel"
    else:
        badge_class = "badge-emploi"
    
    badge_text = offre.employment_type or "Opportunité"
    
    badges_html = f'<span class="badge {badge_class}">{badge_text}</span>'
    
    # Description tronquée
    desc = (offre.description or "")[:200]
    if len(offre.description or "") > 200:
        desc += "..."
    
    # Date formatée
    date_str = offre.date_publication.strftime('%d/%m/%Y') if offre.date_publication else "Date inconnue"
    
    return EmailConfig.OFFRE_ITEM_TEMPLATE.format(
        title=offre.title or "Sans titre",
        url=offre.url or "#",
        badges=badges_html,
        location=offre.location or "Côte d'Ivoire",
        source=offre.source or "Source inconnue",
        date=date_str,
        description=desc
    )


def generate_email_html(
    offres: List[Offre], 
    recipient_email: str,
    base_url: str = "http://localhost:5000"
) -> str:
    """Génère le HTML complet de l'email"""
    offres_html = "".join(format_offre_for_email(o) for o in offres)
    
    today = datetime.now().strftime('%d/%m/%Y')
    
    return EmailConfig.EMAIL_HTML_TEMPLATE.format(
        date=today,
        count=len(offres),
        offres_html=offres_html,
        base_url=base_url,
        email=recipient_email
    )


def send_offres_to_subscribers(
    app,
    email_service: EmailService,
    offres: List[Offre],
    test_mode: bool = False,
    test_email: Optional[str] = None,
    dry_run: bool = False
) -> Dict:
    """
    Envoie les offres aux abonnés
    
    Returns:
        Dict avec statistiques d'envoi
    """
    stats = {
        'total_offres': len(offres),
        'subscribers_found': 0,
        'emails_sent': 0,
        'emails_failed': 0,
        'offres_marked_sent': 0,
        'errors': []
    }
    
    if not offres:
        print_warning("⚠️  Aucune offre à envoyer")
        return stats
    
    print_header(f"📧 ENVOI DES {len(offres)} OFFRES")
    
    # Déterminer les destinataires
    if test_email:
        # Mode test: un seul email
        recipients = [(test_email, "Test User")]
        print_info(f"🎯 Mode test: envoi à {test_email}")
    elif test_mode:
        # Mode test par défaut: admin seulement
        admin_email = app.config.get('DEFAULT_ADMIN_EMAIL', 'admin@cioffres.ci')
        recipients = [(admin_email, "Admin")]
        print_info(f"🎯 Mode test: envoi à l'admin ({admin_email})")
    else:
        # Production: tous les abonnés actifs
        subscriptions = EmailSubscription.objects(is_active=True)
        recipients = [(sub.email, f"{sub.email}") for sub in subscriptions]
        stats['subscribers_found'] = len(recipients)
        print_info(f"👥 {len(recipients)} abonné(s) actif(s) trouvé(s)")
    
    if dry_run:
        print_header("🔍 MODE SIMULATION (dry-run)")
        print_info(f"📦 Offres à envoyer: {len(offres)}")
        print_info(f"👥 Destinataires: {len(recipients)}")
        print_info("📧 Aucun email ne sera envoyé (mode simulation)")
        
        for i, offre in enumerate(offres[:5], 1):
            print(f"   {i}. {offre.title[:60]}...")
        if len(offres) > 5:
            print(f"   ... et {len(offres) - 5} autre(s)")
        
        return stats
    
    # Générer le contenu email une fois (réutilisé pour tous)
    base_url = app.config.get('FRONTEND_URL', 'http://localhost:5000')
    email_html = generate_email_html(offres, recipients[0][0], base_url)
    subject = EmailConfig.EMAIL_SUBJECT_TEMPLATE.format(
        count=len(offres),
        date=datetime.now().strftime('%d/%m')
    )
    
    # Envoyer à chaque destinataire
    for email, name in recipients:
        try:
            print_info(f"📤 Envoi à {email}...")
            
            # Personnaliser le HTML avec l'email du destinataire (pour le lien unsubscribe)
            personalized_html = email_html.replace(
                f'href="{base_url}/api/unsubscribe/{{email}}"',
                f'href="{base_url}/api/unsubscribe/{email}"'
            )
            
            from flask_mail import Message
            msg = Message(
                subject=subject,
                recipients=[email],
                html=personalized_html
            )
            
            email_service.mail.send(msg)
            stats['emails_sent'] += 1
            print_success(f"   ✅ Envoyé à {email}")
            
        except Exception as e:
            stats['emails_failed'] += 1
            stats['errors'].append(f"{email}: {str(e)}")
            print_error(f"   ❌ Échec pour {email}: {e}")
    
    # Marquer les offres comme envoyées (sauf en mode test)
    if not test_mode and not test_email:
        print_info("🏷️  Marquage des offres comme envoyées...")
        for offre in offres:
            try:
                offre.is_sent = True
                offre.save()
                stats['offres_marked_sent'] += 1
            except Exception as e:
                print_error(f"   ❌ Erreur marquage offre {offre.id}: {e}")
        print_success(f"   ✅ {stats['offres_marked_sent']} offre(s) marquée(s) comme envoyée(s)")
    
    return stats


def print_stats(stats: Dict):
    """Affiche un résumé des statistiques"""
    print_header("📊 RÉCAPITULATIF")
    
    print(f"📦 Offres traitées:     {stats['total_offres']}")
    print(f"👥 Abonnés trouvés:     {stats['subscribers_found']}")
    print(f"📧 Emails envoyés:      {stats['emails_sent']}")
    print(f"❌ Emails échoués:      {stats['emails_failed']}")
    print(f"🏷️  Offres marquées:    {stats['offres_marked_sent']}")
    
    if stats['errors']:
        print(f"\n⚠️  Erreurs rencontrées:")
        for err in stats['errors'][:5]:  # Afficher max 5 erreurs
            print(f"   - {err}")
        if len(stats['errors']) > 5:
            print(f"   ... et {len(stats['errors']) - 5} autre(s)")


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description='📧 CI Offres - Envoi des appels d\'offres RÉELS aux utilisateurs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Envoi aux abonnés actifs (production)
  python send_real_offres.py
  
  # Mode test: envoie uniquement à l'admin
  python send_real_offres.py --test
  
  # Test à un email spécifique
  python send_real_offres.py --email privat.kouadio@infosoluces.ci
  
  # Offres des 3 derniers jours seulement
  python send_real_offres.py --since 3
  
  # Simulation sans envoyer (voir ce qui serait envoyé)
  python send_real_offres.py --dry-run
  
  # Filtrer par catégorie
  python send_real_offres.py --category "Informatique"
        """
    )
    
    parser.add_argument('--test', action='store_true', help='Mode test: envoi à l\'admin seulement')
    parser.add_argument('--email', type=str, help='Email spécifique pour test')
    parser.add_argument('--since', type=int, default=EmailConfig.DEFAULT_DAYS_BACK, 
                       help=f'Offres des N derniers jours (défaut: {EmailConfig.DEFAULT_DAYS_BACK})')
    parser.add_argument('--limit', type=int, default=EmailConfig.MAX_OFFRES_PER_EMAIL,
                       help=f'Max offres par email (défaut: {EmailConfig.MAX_OFFRES_PER_EMAIL})')
    parser.add_argument('--category', type=str, help='Filtrer par catégorie')
    parser.add_argument('--include-sent', action='store_true', help='Inclure les offres déjà envoyées')
    parser.add_argument('--dry-run', action='store_true', help='Simulation sans envoyer')
    parser.add_argument('--list', action='store_true', help='Lister les offres disponibles sans envoyer')
    
    args = parser.parse_args()
    
    print_header("🇨🇮 CI OFFRES - ENVOI APPELS D'OFFRES RÉELS")
    print_info(f"🕐 Date: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print_info(f"🔧 Mode: {'TEST 🎯' if args.test or args.email else 'PRODUCTION 🚀'}")
    if args.dry_run:
        print_warning("⚠️  Mode simulation (dry-run) - aucun email ne sera envoyé")
    
    # Initialisation
    app, email_service = init_app()
    if not app or not email_service:
        print_error("❌ Échec initialisation")
        sys.exit(1)
    
    # Lister les offres disponibles (sans envoyer)
    if args.list:
        print_header("📦 OFFRES DISPONIBLES")
        offres = get_real_offres(
            days_back=args.since,
            exclude_sent=not args.include_sent,
            limit=args.limit,
            category=args.category
        )
        if not offres:
            print_info("Aucune offre trouvée avec ces critères")
        else:
            for i, o in enumerate(offres, 1):
                sent_status = "✉️ " if o.is_sent else "📬 "
                print(f"{i}. {sent_status}{o.title[:60]}... [{o.source}]")
        sys.exit(0)
    
    # Récupérer les vraies offres
    offres = get_real_offres(
        days_back=args.since,
        exclude_sent=not args.include_sent,
        limit=args.limit,
        category=args.category
    )
    
    if not offres:
        print_warning("⚠️  Aucune offre à envoyer avec ces critères")
        print_info("💡 Astuces:")
        print("   - Réduire --since pour inclure plus d'offres")
        print("   - Utiliser --include-sent pour réenvoyer")
        print("   - Vérifier que tes scrapers ont bien récupéré des offres")
        sys.exit(0)
    
    # Afficher un aperçu des offres
    print_info(f"\n📋 Aperçu des {len(offres)} offre(s) à envoyer:")
    for i, o in enumerate(offres[:3], 1):
        print(f"   {i}. {o.title[:55]}... ({o.source})")
    if len(offres) > 3:
        print(f"   ... et {len(offres) - 3} autre(s)")
    
    # Confirmation pour mode production
    if not args.test and not args.email and not args.dry_run:
        print_warning("\n⚠️  MODE PRODUCTION: Cet envoi touchera TOUS les abonnés actifs!")
        confirm = input("   Confirmer l'envoi ? (tape 'OUI' pour continuer): ").strip()
        if confirm != 'OUI':
            print_info("❌ Envoi annulé")
            sys.exit(0)
    
    # Envoyer les emails
    stats = send_offres_to_subscribers(
        app=app,
        email_service=email_service,
        offres=offres,
        test_mode=args.test,
        test_email=args.email,
        dry_run=args.dry_run
    )
    
    # Afficher les statistiques
    print_stats(stats)
    
    # Code de sortie
    success = stats['emails_failed'] == 0 or stats['emails_sent'] > 0
    sys.exit(0 if success else 1)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    main()