#!/usr/bin/env python3
"""
Script pour créer l'administrateur par défaut
Exécution: python scripts/create_admin.py
"""

from mongoengine import connect
from models.user import User
import os
import sys
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

def create_default_admin():
    """Crée l'administrateur par défaut s'il n'existe pas"""
    
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
    
    admin_email = os.getenv('DEFAULT_ADMIN_EMAIL', 'admin@cioffres.ci')
    admin_password = os.getenv('DEFAULT_ADMIN_PASSWORD', 'Admin123!')
    
    # Vérifier si l'admin existe déjà
    existing_admin = User.objects(email=admin_email).first()
    
    if existing_admin:
        print(f"⚠️  L'administrateur {admin_email} existe déjà")
        print(f"   ID: {existing_admin.id}")
        print(f"   Actif: {existing_admin.is_active}")
        print(f"   Admin: {existing_admin.is_admin}")
        return existing_admin
    
    # Créer l'admin
    try:
        admin = User(
            email=admin_email,
            first_name='Admin',
            last_name='CI Offres',
            is_admin=True,
            is_active=True
        )
        admin.set_password(admin_password)
        admin.save()
        
        print("\n" + "="*60)
        print("✅ ADMINISTRATEUR CRÉÉ AVEC SUCCÈS!")
        print("="*60)
        print(f"   📧 Email: {admin_email}")
        print(f"   🔑 Mot de passe: {admin_password}")
        print(f"   🆔 ID: {admin.id}")
        print("="*60)
        print("\n⚠️  IMPORTANT:")
        print("   - Changez le mot de passe après la première connexion!")
        print("   - Ne partagez jamais ces informations!")
        print("   - URL de connexion: http://localhost:5000/auth/login")
        print("="*60 + "\n")
        
        return admin
        
    except Exception as e:
        print(f"❌ Erreur création admin: {e}")
        sys.exit(1)

if __name__ == '__main__':
    create_default_admin()