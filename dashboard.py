"""
Dashboard Streamlit pour monitorer le pipeline d'automatisation.

Lancer avec: streamlit run dashboard.py
"""

import streamlit as st
from datetime import datetime, timedelta
from pathlib import Path
import json

# Configuration de la page
st.set_page_config(
    page_title="Content Factory Dashboard",
    page_icon="🚀",
    layout="wide"
)

# Import config
import config

# Titre
st.title("🚀 Content Factory Dashboard")
st.markdown("---")

# Sidebar - Status
with st.sidebar:
    st.header("⚙️ Configuration")
    st.info(f"**Modèle IA:** {config.OPENROUTER_MODEL}")
    st.info(f"**Clés API:** {len([k for k in config.OPENROUTER_API_KEYS if k])} configurées")
    
    if st.button("🔄 Rafraîchir"):
        st.rerun()


# Fonction pour lire les stats Supabase
@st.cache_data(ttl=60)
def get_supabase_stats():
    """Récupère les statistiques depuis Supabase."""
    try:
        client = config.get_supabase_client()
        
        # Articles bruts
        raw = client.table("raw_articles").select("id", count="exact").execute()
        raw_count = raw.count if hasattr(raw, 'count') else len(raw.data)
        
        # Articles non traités
        pending = client.table("raw_articles").select("id", count="exact").eq("status", "pending").execute()
        pending_count = pending.count if hasattr(pending, 'count') else len(pending.data)
        
        # Contenu généré
        processed = client.table("processed_content").select("id", count="exact").execute()
        processed_count = processed.count if hasattr(processed, 'count') else len(processed.data)
        
        # Posts planifiés
        scheduled = client.table("scheduled_posts").select("id", count="exact").execute()
        scheduled_count = scheduled.count if hasattr(scheduled, 'count') else len(scheduled.data)
        
        return {
            "raw_articles": raw_count,
            "pending": pending_count,
            "processed": processed_count,
            "scheduled": scheduled_count
        }
    except Exception as e:
        st.error(f"Erreur Supabase: {e}")
        return {"raw_articles": 0, "pending": 0, "processed": 0, "scheduled": 0}


# Métriques principales
col1, col2, col3, col4 = st.columns(4)

stats = get_supabase_stats()

with col1:
    st.metric(
        label="📰 Articles Collectés",
        value=stats["raw_articles"],
        delta=None
    )

with col2:
    st.metric(
        label="⏳ En Attente",
        value=stats["pending"],
        delta=None
    )

with col3:
    st.metric(
        label="✅ Contenu Généré",
        value=stats["processed"],
        delta=None
    )

with col4:
    st.metric(
        label="📅 Planifiés",
        value=stats["scheduled"],
        delta=None
    )

st.markdown("---")

# Section Logs
st.header("📊 Statistiques des Logs")

try:
    log_stats = config.log_stats()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("ℹ️ Total INFO", log_stats["total_info"])
    with col2:
        st.metric("⚠️ Total WARNINGS", log_stats["total_warnings"])
    with col3:
        st.metric("❌ Total ERRORS", log_stats["total_errors"])
    
    # Détail par module
    if log_stats["modules"]:
        st.subheader("Par Module")
        for module, counts in log_stats["modules"].items():
            with st.expander(f"📦 {module}"):
                st.write(f"- INFO: {counts['info']}")
                st.write(f"- WARNINGS: {counts['warnings']}")
                st.write(f"- ERRORS: {counts['errors']}")
except Exception as e:
    st.warning(f"Impossible de lire les logs: {e}")

st.markdown("---")

# Section Images Générées
st.header("🖼️ Images Générées Récentes")

images_dir = Path("generated_images")
if images_dir.exists():
    images = sorted(images_dir.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)[:6]
    
    if images:
        cols = st.columns(3)
        for i, img in enumerate(images):
            with cols[i % 3]:
                st.image(str(img), caption=img.name, use_container_width=True)
    else:
        st.info("Aucune image générée")
else:
    st.warning("Dossier generated_images non trouvé")

st.markdown("---")

# Actions rapides
st.header("⚡ Actions Rapides")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📥 Collecter Articles", use_container_width=True):
        st.info("Exécutez: `python main.py scrape`")
        
with col2:
    if st.button("🤖 Générer Contenu", use_container_width=True):
        st.info("Exécutez: `python main.py generate --limit 10`")

with col3:
    if st.button("📅 Planifier Posts", use_container_width=True):
        st.info("Exécutez: `python main.py schedule`")

# Derniers logs
st.markdown("---")
st.header("📜 Derniers Logs")

pipeline_log = config.LOG_DIR / "pipeline.log"
if pipeline_log.exists():
    try:
        with open(pipeline_log, "r", encoding="utf-8") as f:
            lines = f.readlines()[-20:]  # 20 dernières lignes
        st.code("".join(lines), language="log")
    except Exception as e:
        st.error(f"Erreur lecture logs: {e}")
else:
    st.info("Aucun log de pipeline disponible")

# Footer
st.markdown("---")
st.caption(f"Content Factory v2.0 | Dernière mise à jour: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
