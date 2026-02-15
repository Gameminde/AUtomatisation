import os
from dotenv import load_dotenv
from facebook_oauth import get_oauth_url

# Load environment
load_dotenv()

# Generate URL
try:
    url = get_oauth_url()
    print("\n" + "="*60)
    print("📢 LIEN DE CONNEXION FACEBOOK")
    print("="*60)
    print("Copiez et collez ce lien dans votre navigateur si le bouton ne marche pas :")
    print("\n" + url + "\n")
    print("="*60)
except Exception as e:
    print(f"Erreur: {e}")
