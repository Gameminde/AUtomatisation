# 🤖 Content Factory Automation - Guide de Démarrage

Bienvenue ! Vous venez d'acquérir votre nouvel assistant marketing autonome.
Ce guide vous permet d'installer et de lancer votre robot en moins de 10 minutes.

---

## 📋 1. Préconditions (Avant de commencer)

Assurez-vous d'avoir :
1.  **Un ordinateur** (Windows, Mac ou Linux) connecté à internet.
2.  **Python installé** (Version 3.9 ou plus).
    *   *Vérifier* : Ouvrez un terminal et tapez `python --version`.
3.  **Vos Clés API** (Ne vous inquiétez pas, c'est simple) :
    *   **Gemini API Key** : [Obtenir ici (Google AI Studio)](https://aistudio.google.com/app/apikey) - *Gratuit*.
    *   **Facebook Page Access Token** : Guide inclus dans le dossier `DOCS/FACEBOOK_SETUP.pdf`.

---

## 🚀 2. Installation Rapide (Windows)

1.  **Décompressez l'archive** `content-factory-v2.zip` sur votre Bureau.
2.  Ouvrez le dossier.
3.  Double-cliquez sur le fichier **`install.bat`**.
    *   *Cela va installer toutes les dépendances automatiquement.*
4.  Une fois terminé, une fenêtre noire se ferme. C'est prêt !

*(Sur Mac/Linux : ouvrez un terminal et lancez `sh install.sh`)*

---

## ⚙️ 3. Configuration

1.  Trouvez le fichier **`.env.example`** dans le dossier.
2.  Renommez-le en **`.env`** (juste `.env`).
3.  Ouvrez ce fichier avec le Bloc-notes.
4.  Remplissez vos clés secrètes :

```ini
# Vos clés secrètes
GEMINI_API_KEY=collez_votre_clé_ici
FACEBOOK_ACCESS_TOKEN=collez_votre_token_facebook_ici
FACEBOOK_PAGE_ID=123456789 (L'ID de votre page)

# Laissez le reste par défaut pour commencer !
DB_MODE=sqlite
```

Enregistrez et fermez.

---

## ▶️ 4. Lancement

Double-cliquez sur **`start_dashboard.bat`**.
Une fenêtre s'ouvre. Attendez quelques secondes...

👉 Ouvrez votre navigateur et allez sur : **`http://localhost:5000`**

**Félicitations !** Vous êtes sur le tableau de bord de votre Content Factory.

---

## 🎮 5. Votre Première Action

Sur le Dashboard :
1.  Allez dans l'onglet **"Contrôle"**.
2.  Cliquez sur **"Générer 1 Post (Test)"**.
3.  Regardez les logs défiler...
4.  Une fois fini, allez dans l'onglet **"Planning"**. Votre post est là !
5.  Il sera publié automatiquement à l'heure prévue.

---

## 🆘 Besoin d'aide ?

*   **Wiki Technique complet** : Voir le fichier `WIKI.md` inclus.
*   **Guide Anti-Ban** : Voir `ANTI_BAN_GUIDE.md` pour les réglages de sécurité.
*   **Support** : Contactez-nous à `support@contentfactory.io` (inclure votre n° de commande).

---
*© 2026 Content Factory Automation. Tous droits réservés.*
