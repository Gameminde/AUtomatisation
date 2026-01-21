# ⚠️ PROBLÈME : Clé API Gemini Invalide

## 🔴 ERREUR DÉTECTÉE

```
API Key not found. Please pass a valid API key.
Status: INVALID_ARGUMENT
Reason: API_KEY_INVALID
```

## 🔍 DIAGNOSTIC

La clé API Gemini fournie : `AIzaSyA5c3lWXShlK4v_c0_Oe0BnWJsRG773yac`

**Problème possible** :
1. ❌ La clé n'a pas été activée correctement
2. ❌ L'API "Generative Language API" n'est pas activée dans le projet
3. ❌ La clé a été révoquée ou désactivée
4. ❌ Le projet Google Cloud n'a pas les bonnes permissions

---

## ✅ SOLUTION : Obtenir une Nouvelle Clé (5 minutes)

### Option 1 : Via Google AI Studio (RECOMMANDÉ)

1. **Aller sur** : https://aistudio.google.com/

2. **Cliquer** : "Get API Key" dans le menu gauche

3. **Choisir** :
   - "Create API key in new project" (si premier projet)
   - OU sélectionner un projet existant

4. **Copier** la nouvelle clé (format : `AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`)

5. **IMPORTANT** : Tester immédiatement dans AI Studio
   - Essayer un prompt simple dans le playground
   - Vérifier que ça fonctionne avant de copier la clé

### Option 2 : Via Google Cloud Console

1. **Aller sur** : https://console.cloud.google.com/

2. **APIs & Services** → **Credentials**

3. **Vérifier que "Generative Language API" est activée** :
   - APIs & Services → Library
   - Chercher "Generative Language API"
   - Cliquer "Enable" si pas activée

4. **Créer une nouvelle clé** :
   - Credentials → Create Credentials → API Key
   - Copier la clé

---

## 🧪 COMMENT TESTER LA NOUVELLE CLÉ

### Méthode 1 : Dans le Terminal

Une fois la nouvelle clé obtenue :

```powershell
# 1. Modifier manuellement .env
notepad .env

# 2. Remplacer la ligne:
GEMINI_API_KEY=VOTRE_NOUVELLE_CLE_ICI

# 3. Tester
python test_gemini_api.py
```

**Résultat attendu** :
```
Status Code: 200
OK - API Gemini fonctionne !

Contenu genere:
[Un texte généré par Gemini sur l'IA]
```

### Méthode 2 : Test Direct sur AI Studio

Avant de copier la clé, testez-la sur https://aistudio.google.com/ :

1. **Playground** → **Freeform**
2. **Prompt** : "Write a short post about AI"
3. **Run**
4. Si ça fonctionne → La clé est valide

---

## 🔄 ALTERNATIVE : Utiliser Claude API

Si vous avez des difficultés avec Gemini, vous pouvez utiliser Claude API (que vous avez déjà) :

### Modifier ai_generator.py

Remplacer la fonction `call_gemini` par `call_claude` :

```python
def call_claude(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)
    
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text
```

Puis dans `.env` :
```env
CLAUDE_API_KEY=votre_cle_claude
```

---

## 📋 CHECKLIST DE DÉPANNAGE

- [ ] Vérifier que vous êtes sur https://aistudio.google.com/ (pas console.cloud.google.com)
- [ ] Tester la clé dans AI Studio Playground avant de copier
- [ ] Vérifier que "Generative Language API" est activée
- [ ] Créer une nouvelle clé dans un nouveau projet si nécessaire
- [ ] Copier-coller la clé SANS espaces avant/après
- [ ] Tester avec `python test_gemini_api.py`

---

## 🆘 SI ÇA NE FONCTIONNE TOUJOURS PAS

### Vérifier les Restrictions de Clé

1. **Google Cloud Console** → **APIs & Services** → **Credentials**
2. **Cliquer** sur votre clé API
3. **API Restrictions** :
   - Sélectionner "Restrict key"
   - Cocher "Generative Language API"
4. **Save**

### Vérifier le Quota

1. **Google Cloud Console** → **APIs & Services** → **Dashboard**
2. Chercher "Generative Language API"
3. Vérifier les quotas (free tier = 60 req/min)

---

## 💡 CONSEILS

### Pour éviter ce problème à l'avenir

1. **Toujours tester** la clé dans AI Studio avant utilisation
2. **Noter** le projet associé à la clé
3. **Sauvegarder** la clé dans un gestionnaire de mots de passe
4. **Monitorer** les quotas régulièrement

### Limites Gratuites Gemini

```
Requêtes par minute  : 60
Requêtes par jour    : 1,500
Tokens par minute    : 4,000,000
Tokens par jour      : Illimité
```

---

## 🚀 PROCHAINES ÉTAPES

Une fois la clé valide obtenue :

1. ✅ **Tester** : `python test_gemini_api.py` → Status 200
2. ✅ **Générer** : `python main.py generate --limit 3`
3. ✅ **Vérifier** : Supabase → `processed_content` (6 nouvelles lignes)
4. ✅ **Planifier** : `python main.py schedule`
5. ✅ **Continuer** vers Facebook

---

**👉 Action immédiate : Obtenir une nouvelle clé sur https://aistudio.google.com/**

Une fois obtenue, faites-moi signe et je la configurerai immédiatement ! 😊
