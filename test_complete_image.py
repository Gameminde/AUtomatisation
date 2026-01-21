"""Test de génération d'image complète avec Pexels."""

import os
import requests
from pathlib import Path

# Ajouter le dossier au path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from image_generator import generate_post_image, OUTPUT_DIR

# Créer dossier pour images téléchargées
DOWNLOADS_DIR = Path(__file__).parent / "downloaded_images"
DOWNLOADS_DIR.mkdir(exist_ok=True)


def download_pexels_image(query: str = "technology", width: int = 1024) -> str:
    """Télécharger une image depuis Lorem Picsum (gratuit et fiable)."""
    
    # Lorem Picsum - images de haute qualité sans API
    url = f"https://picsum.photos/{width}/{width}"
    
    print(f"Téléchargement image: {width}x{width}...")
    
    response = requests.get(url, timeout=30, allow_redirects=True)
    response.raise_for_status()
    
    # Sauvegarder l'image
    filename = f"test_{query.replace(' ', '_')}.jpg"
    filepath = DOWNLOADS_DIR / filename
    
    with open(filepath, "wb") as f:
        f.write(response.content)
    
    print(f"Image téléchargée: {filepath}")
    return str(filepath)


def main():
    # 1. Télécharger une image tech depuis Unsplash
    image_path = download_pexels_image("artificial intelligence technology")
    
    # 2. Texte arabe exemple (sur l'IA)
    arabic_text = "لم نعد في عصر كتابة الكود، نحن في عصر إدارة الذكاء الاصطناعي"
    
    # 3. Générer l'image finale
    output_path = str(OUTPUT_DIR / "test_complete_post.png")
    
    print(f"\nGénération de l'image finale...")
    result = generate_post_image(
        article_image_path=image_path,
        text=arabic_text,
        output_path=output_path,
    )
    
    print(f"\n✅ Image générée avec succès!")
    print(f"   Chemin: {result}")
    print(f"\n   Ouvrez l'image pour voir le résultat.")
    
    # Ouvrir l'image automatiquement (Windows)
    os.startfile(result)
    
    return result


if __name__ == "__main__":
    main()
