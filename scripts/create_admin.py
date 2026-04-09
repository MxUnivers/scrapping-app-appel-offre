#!/usr/bin/env python3
"""
Script pour créer les administrateurs par défaut
Exécution: python scripts/create_admin.py
"""

from mongoengine import connect
import os
import sys
from dotenv import load_dotenv
from models.user import User

# Charger les variables d'environnement
load_dotenv()

def create_default_admins():
    """Crée les administrateurs par défaut s'ils n'existent pas"""
    
    # Connexion MongoDB
    try:
        connect(
            host=os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
            db=os.getenv('MONGODB_DB', 'ci_offres_db'),
            username=os.getenv('MONGODB_USER', ''),
            password=os.getenv('MONGODB_PASS', ''),
            authentication_source='admin'
        )
        print("✅ Connecté à MongoDB")
    except Exception as e:
        print(f"❌ Erreur connexion MongoDB: {e}")
        print("💡 Assurez-vous que MongoDB est démarré")
        sys.exit(1)
    
    # Configuration des admins depuis .env ou valeurs par défaut
    admins_config = [
        {
            'email': os.getenv('DEFAULT_ADMIN_EMAIL', 'admin@cioffres.ci'),
            'first_name': os.getenv('DEFAULT_ADMIN_FIRST_NAME', 'Aymar'),
            'last_name': os.getenv('DEFAULT_ADMIN_LAST_NAME', 'Bly'),
            'is_super_admin': True,
        },
        {
            'email': os.getenv('ADMIN_2_EMAIL', 'privat.kouadio@infosoluces.ci'),
            'first_name': os.getenv('ADMIN_2_FIRST_NAME', 'Privat'),
            'last_name': os.getenv('ADMIN_2_LAST_NAME', 'Kouadio'),
            'is_super_admin': False,
        },
        {
            'email': os.getenv('ADMIN_3_EMAIL', 'tidiane.diabate@infosoluces.ci'),  # Correction orthographe
            'first_name': os.getenv('ADMIN_3_FIRST_NAME', 'Tidiane'),
            'last_name': os.getenv('ADMIN_3_LAST_NAME', 'Diabaté'),
            'is_super_admin': False,
        },
    ]
    
    # Mot de passe commun (à changer après première connexion !)
    default_password = os.getenv('DEFAULT_ADMIN_PASSWORD', 'Admin123!')
    
    created_count = 0
    existing_count = 0
    error_count = 0
    
    print(f"\n🔐 Création des administrateurs avec mot de passe: {'*' * len(default_password)}")
    print("-" * 60)
    
    for i, config in enumerate(admins_config, 1):
        email = config['email']
        first_name = config['first_name']
        last_name = config['last_name']
        is_super = config['is_super_admin']
        
        print(f"\n[{i}/{len(admins_config)}] Traitement: {first_name} {last_name} <{email}>")
        
        try:
            # Vérifier si l'utilisateur existe déjà
            existing_user = User.objects(email=email).first()
            
            if existing_user:
                print(f"   ⚠️  Utilisateur existe déjà")
                print(f"      ID: {existing_user.id}")
                print(f"      Admin: {existing_user.is_admin}")
                print(f"      Actif: {existing_user.is_active}")
                existing_count += 1
                continue
            
            # Créer le nouvel admin
            admin = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_admin=True,  # Tous sont admins
                is_active=True
            )
            admin.set_password(default_password)
            admin.save()
            
            print(f"   ✅ Admin créé avec succès!")
            print(f"      ID: {admin.id}")
            created_count += 1
            
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            error_count += 1
            continue
    
    # Résumé final
    print("\n" + "=" * 60)
    print("📊 RÉCAPITULATIF CRÉATION ADMINS")
    print("=" * 60)
    print(f"   ✅ Créés: {created_count}")
    print(f"   ⚠️  Déjà existants: {existing_count}")
    print(f"   ❌ Erreurs: {error_count}")
    print(f"   📦 Total traités: {len(admins_config)}")
    print("=" * 60)
    
    if created_count > 0:
        print("\n🔑 MOT DE PASSE COMMUN (à changer après première connexion):")
        print(f"   {default_password}")
        print("\n🌐 URL de connexion:")
        print("   http://localhost:5000/auth/login")
        print("\n⚠️  SÉCURITÉ:")
        print("   - Changez les mots de passe après la première connexion")
        print("   - Ne partagez jamais ces informations")
        print("   - Utilisez un mot de passe unique par utilisateur en production")
    
    print("=" * 60 + "\n")
    
    # Retourner un statut pour usage programmatique
    return {
        'success': error_count == 0,
        'created': created_count,
        'existing': existing_count,
        'errors': error_count
    }


def list_existing_admins():
    """Liste tous les admins existants dans la base"""
    try:
        connect(
            host=os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
            db=os.getenv('MONGODB_DB', 'ci_offres_db'),
            username=os.getenv('MONGODB_USER', ''),
            password=os.getenv('MONGODB_PASS', ''),
            authentication_source='admin'
        )
        
        admins = User.objects(is_admin=True).order_by('email')
        
        if not admins:
            print("ℹ️  Aucun administrateur trouvé dans la base")
            return
        
        print(f"\n👥 Administrateurs existants ({admins.count()}):")
        print("-" * 70)
        print(f"{'Email':<45} {'Nom':<25} {'Actif':<6}")
        print("-" * 70)
        
        for admin in admins:
            status = "✅" if admin.is_active else "❌"
            print(f"{admin.email:<45} {admin.first_name} {admin.last_name:<20} {status}")
        
        print("-" * 70 + "\n")
        
    except Exception as e:
        print(f"❌ Erreur liste admins: {e}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Gestion des administrateurs CI Offres')
    parser.add_argument('--list', action='store_true', help='Lister les admins existants')
    parser.add_argument('--create', action='store_true', help='Créer les admins par défaut (défaut)')
    
    args = parser.parse_args()
    
    if args.list:
        list_existing_admins()
    else:
        result = create_default_admins()
        # Code de sortie pour usage CI/CD
        sys.exit(0 if result['success'] else 1)