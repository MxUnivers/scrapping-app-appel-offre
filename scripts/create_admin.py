#!/usr/bin/env python3
"""
Script pour créer les administrateurs par défaut
Exécution: python scripts/create_admin.py
"""

import os
import sys
from pathlib import Path

# Ajouter la racine du projet au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mongoengine import connect
from dotenv import load_dotenv
from models.user import User

# Charger les variables d'environnement
load_dotenv()


def get_mongo_connection():
    """Connexion MongoDB compatible Atlas + localhost"""
    uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
    db = os.getenv('MONGODB_DB', 'ci_offres_db')
    user = os.getenv('MONGODB_USER', '')
    passwd = os.getenv('MONGODB_PASS', '')

    settings = {'host': uri, 'db': db}

    # Ajouter user/pass seulement s'ils sont définis
    # (si déjà dans l'URI Atlas, ne pas les répéter)
    if user and passwd and user not in uri:
        settings['username'] = user
        settings['password'] = passwd
        settings['authentication_source'] = 'admin'

    connect(**settings)


def create_default_admins():
    """Crée les administrateurs par défaut s'ils n'existent pas"""

    # Connexion MongoDB
    try:
        get_mongo_connection()
        print("✅ Connecté à MongoDB")
    except Exception as e:
        print(f"❌ Erreur connexion MongoDB: {e}")
        print("💡 Assurez-vous que MongoDB est démarré")
        sys.exit(1)

    # =========================================================
    # Les 3 admins lus depuis le .env
    # =========================================================
    admins_config = [
        {
            'email':      'aymarbly559@gmail.com',
            'first_name': 'Aymar',
            'last_name':    'Bly',
            'role':       'super_admin',
        },
        {
            'email':      'privat.kouadio@infosoluces.ci',
            'first_name': 'Privat',
            'last_name':  'Kouadio',
            'role':       'admin',
        },
        {
            'email':      'tidiane.diabate@infosoluces.ci',
            'first_name': 'Tidiane',
            'last_name':  'Diabaté',
            'role':       'admin',
        },
    ]

    default_password = os.getenv('DEFAULT_ADMIN_PASSWORD', 'Admin123!')

    created_count  = 0
    existing_count = 0
    error_count    = 0

    print(f"\n🔐 Mot de passe commun: {'*' * len(default_password)}")
    print("-" * 60)

    for i, cfg in enumerate(admins_config, 1):
        email      = cfg['email']
        first_name = cfg['first_name']
        last_name  = cfg['last_name']
        role       = cfg['role']

        print(f"\n[{i}/{len(admins_config)}] {first_name} {last_name} <{email}> [{role}]")

        try:
            existing = User.objects(email=email).first()

            if existing:
                print(f"   ⚠️  Existe déjà  (ID: {existing.id})")
                existing_count += 1
                continue

            admin = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_admin=True,
                is_active=True,
                role=role,
                email_verified=True,  # Pas besoin de vérification pour les admins
            )
            admin.set_password(default_password)
            admin.save()

            print(f"   ✅ Créé avec succès! (ID: {admin.id})")
            created_count += 1

        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            error_count += 1

    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉCAPITULATIF")
    print("=" * 60)
    print(f"   ✅ Créés          : {created_count}")
    print(f"   ⚠️  Déjà existants : {existing_count}")
    print(f"   ❌ Erreurs        : {error_count}")
    print("=" * 60)

    if created_count > 0:
        print(f"\n🔑 Mot de passe commun : {default_password}")
        print("🌐 URL de connexion    : http://localhost:5000/auth/login")
        print("\n⚠️  Changez les mots de passe après la première connexion!")

    print("=" * 60 + "\n")

    return {
        'success': error_count == 0,
        'created': created_count,
        'existing': existing_count,
        'errors': error_count
    }


def list_existing_admins():
    """Liste tous les admins existants dans la base"""
    try:
        get_mongo_connection()

        admins = User.objects(is_admin=True).order_by('email')

        if not admins:
            print("ℹ️  Aucun administrateur trouvé")
            return

        print(f"\n👥 Administrateurs ({admins.count()}):")
        print("-" * 75)
        print(f"{'Email':<40} {'Nom':<20} {'Rôle':<12} {'Actif'}")
        print("-" * 75)

        for admin in admins:
            status = "✅" if admin.is_active else "❌"
            print(f"{admin.email:<40} {admin.first_name} {admin.last_name:<15} {admin.role:<12} {status}")

        print("-" * 75 + "\n")

    except Exception as e:
        print(f"❌ Erreur: {e}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Gestion des administrateurs CI Offres')
    parser.add_argument('--list',   action='store_true', help='Lister les admins existants')
    parser.add_argument('--create', action='store_true', help='Créer les admins (défaut)')

    args = parser.parse_args()

    if args.list:
        list_existing_admins()
    else:
        result = create_default_admins()
        sys.exit(0 if result['success'] else 1)