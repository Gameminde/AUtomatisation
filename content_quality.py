"""
Content Quality Validator - Validation et amélioration du contenu généré
Based on: "Écrire des posts courts et engageants sur la tech et le gaming"
"""

import re
from typing import Dict, List
import config

logger = config.get_logger("content_quality")


# Indicateurs d'une bonne accroche
HOOK_INDICATORS = {
    "question": ["هل", "ما", "كيف", "لماذا", "أين", "متى", "؟"],
    "shock": ["صدمة", "مفاجأة", "عاجل", "خطير", "لن تصدق", "غير معقول"],
    "statistics": ["%", "90%", "80%", "70%", "الملايين", "آلاف"],
    "emojis": ["🚨", "💥", "🔥", "⚠️", "❗", "🤯", "😱"],
    "teaser": ["السر", "الحقيقة", "لا يريدونك", "لم تعرف", "اكتشف"],
}

# CTA patterns
CTA_PATTERNS = [
    "ما رأيكم",
    "شاركونا",
    "ما تجربتكم",
    "هل جربتم",
    "من معي",
    "تاغ",
    "أخبرونا",
    "💬",
]

# Mots à éviter (contenu générique)
GENERIC_WORDS = [
    "مهم جداً",
    "رائع جداً",
    "بشكل كبير",
    "في الوقت الحالي",
    "من المعروف أن",
]


class ContentQualityValidator:
    """Validateur de qualité du contenu généré"""

    def __init__(self):
        self.min_hook_score = 0.6
        self.min_overall_score = 0.7

    def validate_hook(self, hook: str) -> Dict:
        """
        Valide la qualité de l'accroche

        Args:
            hook: Texte de l'accroche

        Returns:
            dict: score, issues, suggestions
        """
        issues = []
        suggestions = []
        score = 0.5  # Score de base

        if not hook:
            return {
                "score": 0,
                "issues": ["Hook manquant"],
                "suggestions": ["Ajouter une accroche percutante"],
            }

        # Vérifier longueur
        word_count = len(hook.split())
        if word_count > 20:
            issues.append("Hook trop long")
            suggestions.append("Réduire à moins de 15 mots")
            score -= 0.1
        elif word_count <= 10:
            score += 0.1  # Bonus pour concision

        # Vérifier présence d'indicateurs d'engagement
        has_question = any(q in hook for q in HOOK_INDICATORS["question"])
        has_shock = any(s in hook for s in HOOK_INDICATORS["shock"])
        has_stat = any(s in hook for s in HOOK_INDICATORS["statistics"])
        has_emoji = any(e in hook for e in HOOK_INDICATORS["emojis"])
        has_teaser = any(t in hook for t in HOOK_INDICATORS["teaser"])

        engagement_count = sum([has_question, has_shock, has_stat, has_emoji, has_teaser])

        if engagement_count == 0:
            issues.append("Hook sans élément d'engagement")
            suggestions.append("Ajouter question, statistique, ou élément choc")
            score -= 0.2
        else:
            score += 0.1 * engagement_count

        # Vérifier si commence par emoji (bonus)
        if hook[0] in "🚨💥🔥⚠️❗🤯😱🎮🤖":
            score += 0.1

        # Vérifier mots génériques (malus)
        generic_count = sum(1 for w in GENERIC_WORDS if w in hook)
        if generic_count > 0:
            issues.append(f"{generic_count} mot(s) générique(s) détecté(s)")
            suggestions.append("Utiliser un langage plus percutant")
            score -= 0.1 * generic_count

        # Cap score
        score = max(0, min(1, score))

        return {
            "score": score,
            "issues": issues,
            "suggestions": suggestions,
            "has_question": has_question,
            "has_emoji": has_emoji,
            "word_count": word_count,
        }

    def validate_cta(self, cta: str) -> Dict:
        """
        Valide le Call-to-Action

        Args:
            cta: Texte du CTA

        Returns:
            dict: score, issues, suggestions
        """
        issues = []
        suggestions = []
        score = 0.5

        if not cta:
            return {
                "score": 0,
                "issues": ["CTA manquant"],
                "suggestions": ["Ajouter une question ou invitation à interagir"],
            }

        # Vérifier présence de patterns CTA
        has_cta_pattern = any(p in cta for p in CTA_PATTERNS)

        if has_cta_pattern:
            score += 0.3
        else:
            issues.append("CTA faible")
            suggestions.append("Utiliser: 'ما رأيكم؟' ou 'شاركونا تجربتكم'")

        # Vérifier question directe
        if "؟" in cta:
            score += 0.2

        # Vérifier emoji
        if "💬" in cta or "🙋" in cta:
            score += 0.1

        score = max(0, min(1, score))

        return {"score": score, "issues": issues, "suggestions": suggestions}

    def validate_body(self, body: str) -> Dict:
        """
        Valide le corps du contenu

        Args:
            body: Texte du body

        Returns:
            dict: score, issues, suggestions
        """
        issues = []
        suggestions = []
        score = 0.5

        if not body:
            return {
                "score": 0,
                "issues": ["Body manquant"],
                "suggestions": ["Ajouter du contenu à valeur ajoutée"],
            }

        word_count = len(body.split())

        # Vérifier longueur
        if word_count < 30:
            issues.append("Body trop court")
            suggestions.append("Développer avec plus de détails")
            score -= 0.1
        elif word_count > 300:
            issues.append("Body trop long")
            suggestions.append("Réduire pour garder l'attention")
            score -= 0.1
        else:
            score += 0.1

        # Vérifier présence de valeur
        value_indicators = ["نصيحة", "اكتشفت", "السر", "طريقة", "كيف"]
        has_value = any(v in body for v in value_indicators)

        if has_value:
            score += 0.2
        else:
            suggestions.append("Ajouter conseil pratique ou insight")

        # Vérifier ton personnel
        personal_indicators = ["اكتشفت", "جربت", "رأيي", "تجربتي", "أنصحكم"]
        has_personal = any(p in body for p in personal_indicators)

        if has_personal:
            score += 0.15

        # Vérifier emojis (engagement visuel)
        emoji_count = len(re.findall(r"[\U0001F300-\U0001F9FF]", body))
        if 1 <= emoji_count <= 4:
            score += 0.1
        elif emoji_count > 6:
            issues.append("Trop d'emojis")
            score -= 0.1

        score = max(0, min(1, score))

        return {
            "score": score,
            "issues": issues,
            "suggestions": suggestions,
            "word_count": word_count,
            "has_personal_tone": has_personal,
        }

    def validate_hashtags(self, hashtags: List[str]) -> Dict:
        """
        Valide les hashtags

        Args:
            hashtags: Liste de hashtags

        Returns:
            dict: score, issues, suggestions
        """
        issues = []
        suggestions = []
        score = 0.5

        if not hashtags:
            return {
                "score": 0.3,
                "issues": ["Hashtags manquants"],
                "suggestions": ["Ajouter 5-7 hashtags pertinents"],
            }

        count = len(hashtags)

        if count < 3:
            issues.append("Peu de hashtags")
            suggestions.append("Ajouter plus de hashtags (5-7 recommandé)")
            score -= 0.1
        elif count > 10:
            issues.append("Trop de hashtags")
            suggestions.append("Réduire à 5-7 hashtags")
            score -= 0.1
        elif 5 <= count <= 7:
            score += 0.2

        # Vérifier mélange arabe/anglais
        arabic_tags = [h for h in hashtags if any("\u0600" <= c <= "\u06ff" for c in h)]
        english_tags = [h for h in hashtags if any("a" <= c.lower() <= "z" for c in h)]

        if arabic_tags and english_tags:
            score += 0.2  # Bon mélange

        score = max(0, min(1, score))

        return {"score": score, "issues": issues, "suggestions": suggestions, "count": count}

    def validate_content(self, content: Dict) -> Dict:
        """
        Validation complète du contenu

        Args:
            content: Dict avec hook, body, cta, hashtags

        Returns:
            dict: overall_score, components, is_valid, improvements
        """
        hook_result = self.validate_hook(content.get("hook", ""))
        body_result = self.validate_body(
            content.get("body", "") or content.get("generated_text", "")
        )
        cta_result = self.validate_cta(content.get("cta", "") or content.get("call_to_action", ""))
        hashtags_result = self.validate_hashtags(content.get("hashtags", []))

        # Calculer score global (pondéré)
        weights = {"hook": 0.35, "body": 0.30, "cta": 0.20, "hashtags": 0.15}  # Hook très important

        overall_score = (
            hook_result["score"] * weights["hook"]
            + body_result["score"] * weights["body"]
            + cta_result["score"] * weights["cta"]
            + hashtags_result["score"] * weights["hashtags"]
        )

        is_valid = overall_score >= self.min_overall_score

        # Collecter toutes les améliorations
        all_issues = (
            hook_result.get("issues", [])
            + body_result.get("issues", [])
            + cta_result.get("issues", [])
            + hashtags_result.get("issues", [])
        )

        all_suggestions = (
            hook_result.get("suggestions", [])
            + body_result.get("suggestions", [])
            + cta_result.get("suggestions", [])
            + hashtags_result.get("suggestions", [])
        )

        result = {
            "overall_score": overall_score,
            "is_valid": is_valid,
            "components": {
                "hook": hook_result,
                "body": body_result,
                "cta": cta_result,
                "hashtags": hashtags_result,
            },
            "issues": all_issues,
            "suggestions": all_suggestions[:5],  # Top 5 suggestions
            "grade": self._score_to_grade(overall_score),
        }

        logger.info(
            f"Content quality: {result['grade']} ({overall_score:.0%}) - "
            f"Issues: {len(all_issues)}"
        )

        return result

    def _score_to_grade(self, score: float) -> str:
        """Convertit score en grade lisible"""
        if score >= 0.9:
            return "A+ 🌟"
        elif score >= 0.8:
            return "A 🔥"
        elif score >= 0.7:
            return "B ✅"
        elif score >= 0.6:
            return "C ⚠️"
        elif score >= 0.5:
            return "D ⚡"
        else:
            return "F ❌"


def validate_generated_content(content: Dict) -> Dict:
    """
    Fonction simple pour valider du contenu généré

    Args:
        content: Dict avec hook, body, cta, hashtags

    Returns:
        dict: Résultat de validation
    """
    validator = ContentQualityValidator()
    return validator.validate_content(content)


if __name__ == "__main__":
    # Test avec du contenu exemple
    print("🧪 Test Content Quality Validator\n")

    # Contenu de bonne qualité
    good_content = {
        "hook": "🚨 صدمة! ChatGPT يفهم الصور الآن!",
        "body": """اكتشفت للتو ميزة جديدة غيرت كل شيء!

OpenAI أطلقت تحديثاً يجعل ChatGPT يحلل أي صورة ترسلها له 🤖

جربت أرسل لقطة شاشة لكود معقد - أعطاني شرح كامل في ثواني!

💡 نصيحتي لكم: جربوا إرسال صور لأخطاء برمجية أو رسوم بيانية.
ستوفرون ساعات من البحث!""",
        "cta": "هل جربتم هذه الميزة؟ شاركونا تجربتكم! 💬",
        "hashtags": ["#ChatGPT", "#الذكاء_الاصطناعي", "#تقنية", "#OpenAI", "#AI"],
    }

    # Contenu de mauvaise qualité
    bad_content = {
        "hook": "الذكاء الاصطناعي مهم جداً في عصرنا",
        "body": "هناك تطورات كثيرة في مجال التكنولوجيا.",
        "cta": "",
        "hashtags": ["#tech"],
    }

    validator = ContentQualityValidator()

    print("=" * 60)
    print("✅ CONTENU DE BONNE QUALITÉ:")
    print("=" * 60)
    result = validator.validate_content(good_content)
    print(f"Grade: {result['grade']}")
    print(f"Score: {result['overall_score']:.0%}")
    print(f"Valid: {result['is_valid']}")

    print("\n" + "=" * 60)
    print("❌ CONTENU DE MAUVAISE QUALITÉ:")
    print("=" * 60)
    result = validator.validate_content(bad_content)
    print(f"Grade: {result['grade']}")
    print(f"Score: {result['overall_score']:.0%}")
    print(f"Valid: {result['is_valid']}")
    print(f"Issues: {result['issues']}")
    print(f"Suggestions: {result['suggestions']}")
