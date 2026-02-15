"""
Dashboard de Contrôle - Pipeline Intelligent Unifié

Interface simplifiée pour:
1. Trouver les tendances
2. Générer contenu + image cohérents
3. Prévisualiser
4. Publier sur Facebook

Lancer avec: streamlit run dashboard.py
"""

import streamlit as st
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Configuration de la page
st.set_page_config(
    page_title="🚀 Content Factory",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import config
import config

# Paths
BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "generated_images"
IMAGE_CONFIG_PATH = BASE_DIR / "image_config.json"


# ============================================
# HELPER FUNCTIONS
# ============================================

def load_image_config() -> Dict:
    """Load image configuration."""
    defaults = {
        "text_font_size": 76,
        "text_color": [255, 200, 50],
        "text_max_lines": 2,
        "image_overlay_alpha": 0
    }
    try:
        if IMAGE_CONFIG_PATH.exists():
            with open(IMAGE_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return {**defaults, **json.load(f)}
    except:
        pass
    return defaults


def save_image_config(cfg: Dict) -> bool:
    """Save image configuration."""
    try:
        with open(IMAGE_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Erreur: {e}")
        return False


# ============================================
# SESSION STATE
# ============================================

if "img_config" not in st.session_state:
    st.session_state.img_config = load_image_config()

if "result" not in st.session_state:
    st.session_state.result = None

if "topics" not in st.session_state:
    st.session_state.topics = []

if "selected_topic" not in st.session_state:
    st.session_state.selected_topic = None


# ============================================
# SIDEBAR
# ============================================

with st.sidebar:
    st.header("⚙️ Paramètres Image")
    
    st.session_state.img_config["text_font_size"] = st.slider(
        "Taille police", 20, 100, 
        st.session_state.img_config.get("text_font_size", 76)
    )
    
    # Color picker
    current_color = st.session_state.img_config.get("text_color", [255, 200, 50])
    hex_color = "#{:02x}{:02x}{:02x}".format(*current_color)
    new_color = st.color_picker("Couleur texte", hex_color)
    r, g, b = int(new_color[1:3], 16), int(new_color[3:5], 16), int(new_color[5:7], 16)
    st.session_state.img_config["text_color"] = [r, g, b]
    
    st.session_state.img_config["text_max_lines"] = st.slider(
        "Max lignes", 1, 4, 
        st.session_state.img_config.get("text_max_lines", 2)
    )
    
    st.session_state.img_config["image_overlay_alpha"] = st.slider(
        "Overlay", 0, 100, 
        st.session_state.img_config.get("image_overlay_alpha", 0)
    )
    
    st.divider()
    
    if st.button("💾 Sauvegarder Config", use_container_width=True):
        if save_image_config(st.session_state.img_config):
            st.success("✅ Sauvegardé!")


# ============================================
# MAIN CONTENT
# ============================================

st.title("🚀 Content Factory - Pipeline Intelligent")
st.markdown("Création de contenu viral unifié: Tendance → Article → Image → Publication")
st.divider()


# ============================================
# ÉTAPE 1: TROUVER TENDANCES
# ============================================

st.header("1️⃣ Trouver les Tendances")

col1, col2 = st.columns([3, 1])

with col1:
    source_type = st.radio(
        "Source:",
        ["🔍 Rechercher automatiquement", "✏️ Sujet personnalisé"],
        horizontal=True
    )

with col2:
    if source_type == "🔍 Rechercher automatiquement":
        if st.button("🔎 Rechercher", use_container_width=True, type="primary"):
            with st.spinner("Recherche des tendances..."):
                try:
                    from unified_content_creator import find_all_trending_topics
                    st.session_state.topics = find_all_trending_topics(10)
                    if st.session_state.topics:
                        st.session_state.selected_topic = st.session_state.topics[0]
                except Exception as e:
                    st.error(f"Erreur: {e}")

# Afficher les tendances trouvées
if source_type == "🔍 Rechercher automatiquement" and st.session_state.topics:
    st.subheader("📈 Tendances trouvées:")
    
    for i, topic in enumerate(st.session_state.topics[:5]):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"**{i+1}.** {topic.get('title', '')[:70]}... ({topic.get('source', '')})")
        with col2:
            if st.button("Choisir", key=f"topic_{i}"):
                st.session_state.selected_topic = topic
                st.rerun()

elif source_type == "✏️ Sujet personnalisé":
    custom_title = st.text_input("Titre:", value="OpenAI lance GPT-5 avec des capacités révolutionnaires")
    custom_content = st.text_area("Description:", height=80)
    st.session_state.selected_topic = {
        "title": custom_title,
        "content": custom_content,
        "source": "custom"
    }

# Afficher le sujet sélectionné
if st.session_state.selected_topic:
    st.success(f"✅ **Sujet sélectionné:** {st.session_state.selected_topic.get('title', '')[:80]}...")


st.divider()

# ============================================
# ÉTAPE 2: GÉNÉRER CONTENU + IMAGE
# ============================================

st.header("2️⃣ Générer Contenu + Image")

if st.button("✨ Générer le Post Complet", use_container_width=True, type="primary", disabled=not st.session_state.selected_topic):
    if st.session_state.selected_topic:
        with st.spinner("⏳ Génération en cours... (article + image)"):
            try:
                # Save config first
                save_image_config(st.session_state.img_config)
                
                from unified_content_creator import create_preview
                st.session_state.result = create_preview(st.session_state.selected_topic)
            except Exception as e:
                st.error(f"Erreur: {e}")
                import traceback
                st.code(traceback.format_exc())


st.divider()

# ============================================
# ÉTAPE 3: PRÉVISUALISATION
# ============================================

st.header("3️⃣ Prévisualisation")

if st.session_state.result and st.session_state.result.get("success"):
    result = st.session_state.result
    
    col_article, col_image = st.columns([1, 1])
    
    # Article column
    with col_article:
        st.subheader("📝 Article Généré")
        
        content = result.get("content", {})
        article = content.get("article", {})
        
        st.markdown("**🔥 Hook:**")
        st.info(article.get("hook", "N/A"))
        
        st.markdown("**📖 Body:**")
        st.write(article.get("body", "N/A"))
        
        st.markdown("**💬 CTA:**")
        st.success(article.get("cta", "N/A"))
        
        st.markdown("**#️⃣ Hashtags:**")
        hashtags = article.get("hashtags", [])
        st.write(" ".join(hashtags) if hashtags else "Aucun")
    
    # Image column
    with col_image:
        st.subheader("🖼️ Image Générée")
        
        canvas_path = result.get("canvas_path")
        if canvas_path and Path(canvas_path).exists():
            st.image(canvas_path, use_container_width=True)
        else:
            image_path = result.get("image_path")
            if image_path and Path(image_path).exists():
                st.image(image_path, caption="Image source", use_container_width=True)
            else:
                st.warning("Image non disponible")
        
        # Image keywords used
        image_info = content.get("image", {})
        if image_info:
            st.caption(f"Mots-clés: {', '.join(image_info.get('keywords_en', []))}")

elif st.session_state.result and st.session_state.result.get("error"):
    st.error(f"❌ Erreur: {st.session_state.result['error']}")

else:
    st.info("👆 Sélectionnez un sujet et cliquez sur 'Générer' pour voir le résultat")


st.divider()

# ============================================
# ÉTAPE 4: PUBLICATION
# ============================================

st.header("4️⃣ Publier sur Facebook")

can_publish = (
    st.session_state.result 
    and st.session_state.result.get("success") 
    and st.session_state.result.get("canvas_path")
)

col1, col2 = st.columns([1, 1])

with col1:
    if st.button("📤 PUBLIER SUR FACEBOOK", use_container_width=True, type="primary", disabled=not can_publish):
        with st.spinner("Publication en cours..."):
            try:
                from unified_content_creator import publish_to_facebook, save_to_database, record_publication
                
                result = st.session_state.result
                article = result["content"]["article"]
                canvas_path = result["canvas_path"]
                
                # Save to DB first
                content_id = save_to_database(
                    result["topic"], 
                    result["content"],
                    result["image_path"],
                    canvas_path
                )
                
                # Publish
                post_id = publish_to_facebook(article, canvas_path)
                
                if post_id:
                    st.success(f"✅ Publié avec succès! Post ID: {post_id}")
                    if content_id:
                        record_publication(content_id, post_id)
                else:
                    st.error("❌ Échec de la publication")
                    
            except Exception as e:
                st.error(f"Erreur: {e}")

with col2:
    if st.button("🔄 Nouveau Post", use_container_width=True):
        st.session_state.result = None
        st.session_state.topics = []
        st.session_state.selected_topic = None
        st.rerun()


# ============================================
# FOOTER
# ============================================

st.divider()

# Stats
try:
    client = config.get_supabase_client()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        raw = client.table("raw_articles").select("id", count="exact").execute()
        st.metric("📰 Articles", raw.count if hasattr(raw, 'count') else len(raw.data or []))
    
    with col2:
        proc = client.table("processed_content").select("id", count="exact").execute()
        st.metric("✅ Générés", proc.count if hasattr(proc, 'count') else len(proc.data or []))
    
    with col3:
        pub = client.table("published_posts").select("id", count="exact").execute()
        st.metric("📤 Publiés", pub.count if hasattr(pub, 'count') else len(pub.data or []))
        
except Exception as e:
    st.caption(f"Stats non disponibles: {e}")

st.caption(f"Content Factory v3.0 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
