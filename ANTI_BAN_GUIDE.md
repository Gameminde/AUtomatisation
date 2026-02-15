# 🛡️ Guide Anti-Ban & Sécurité Facebook
> **Comment automatiser sans perdre votre compte.**

---

## 🚨 Règle d'Or : "Don't act like a bot."
Facebook ne bannit pas l'automatisation (l'API Graph est faite pour ça). Facebook bannit le **comportement abusif** (Spam, fréquence inhumaine, contenu de mauvaise qualité).

**Content Factory v2.0 est conçu pour imiter un humain.**

---

## ⚙️ 1. L'Algorithme "Human-Like" (Inclus)

Votre installation contient déjà des sécurités actives dans `scheduler.py` et `publisher.py` :

### ✅ Le "Jitter" Temporel
Si vous demandez de poster à 14h00, le bot ne postera jamais à 14h00:00 pile.
Il postera à 14h03:12, ou 13h58:45.
*   **Pourquoi ?** Les humains ne sont pas précis à la milliseconde.

### ✅ Intervalles Aléatoires
Le planificateur n'utilise pas un rythme fixe (toutes les 2h).
Il tire au sort un délai entre **2h et 4h** entre chaque post.
*   **Résultat** : Votre page a un rythme naturel, parfois calme, parfois actif.

### ✅ Rate Limiting (Pause API)
Entre chaque requête à Facebook, le script fait une pause de 2 à 5 secondes (`REQUEST_SLEEP_SECONDS` dans `.env`).
*   **Pourquoi ?** Pour ne jamais dépasser les quotas de l'API Graph (200 appels/heure).

---

## 🛠️ 2. Configuration Recommandée (Best Practices)

Voici les réglages conseillés selon l'âge de votre page.

### Pour une Page Neuve (< 1 mois)
*   **Fréquence** : 1 à 2 posts par jour MAX.
*   **Contenu** : 100% informatif, 0% liens sortants.
*   **Commande** : `python main.py auto --limit 1` (une fois le matin, une fois le soir).

### Pour une Page Établie (> 6 mois)
*   **Fréquence** : 3 à 5 posts par jour.
*   **Contenu** : Mix News / Engagement.
*   **Commande** : Cron job toutes les 4 heures.

---

## 🚫 3. Les "Interdits" (Ce qui vous fera bannir)

1.  **Dépassement de Vitesse** : Ne tentez pas de poster 50 fois par heure. Facebook bloquera votre Token pour 24h.
2.  **Contenu Dupliqué** : Le bot a un filtre anti-doublon. Ne le désactivez pas. Poster la même news 10 fois est le moyen le plus sûr de mourir.
3.  **Copyright Images** : Utilisez les clés API Pexels/Unsplash. N'utilisez pas Google Images au hasard.

---

## 🆘 4. Que faire en cas de blocage ?

Si vous recevez une erreur `(#32) Page Request Limit Reached` dans les logs :

1.  **ARRÊTEZ TOUT**. Débranchez le bot pendant 24h strictes.
2.  Allez dans `.env` et augmentez la pause :
    ```ini
    REQUEST_SLEEP_SECONDS=15
    ```
3.  Réduisez la fréquence de publication par 2.

*L'automatisation est un marathon, pas un sprint.*
