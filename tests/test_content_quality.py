"""
Unit tests for content_quality module.

Tests cover:
- Hook validation
- Body validation
- CTA validation
- Hashtag validation
- Full content validation
"""

# pytest is used implicitly via fixtures


class TestValidateHook:
    """Tests for validate_hook function."""

    def test_validate_hook_good_quality(self):
        """Test validation of high-quality hook."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        hook = "🚨 صدمة! ChatGPT يفهم الصور الآن!"
        result = validator.validate_hook(hook)

        assert result["score"] > 0.5
        assert result["has_emoji"] is True

    def test_validate_hook_with_question(self):
        """Test validation of hook with question."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        hook = "هل تصدق ما فعلته Tesla؟"
        result = validator.validate_hook(hook)

        assert result["has_question"] is True
        assert result["score"] > 0.5

    def test_validate_hook_too_long(self):
        """Test validation of too long hook."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        hook = (
            "هذا هو الخبر الذي سيغير كل شيء في عالم التكنولوجيا والذكاء الاصطناعي وسيؤثر على حياتنا اليومية بشكل كبير جداً "
            * 3
        )
        result = validator.validate_hook(hook)

        assert "Hook trop long" in result["issues"]

    def test_validate_hook_empty(self):
        """Test validation of empty hook."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        result = validator.validate_hook("")

        assert result["score"] == 0
        assert "Hook manquant" in result["issues"]

    def test_validate_hook_generic_content(self):
        """Test validation of generic hook."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        hook = "الذكاء الاصطناعي مهم جداً في عصرنا"
        result = validator.validate_hook(hook)

        # Should have lower score due to generic words
        assert result["score"] < 0.7


class TestValidateBody:
    """Tests for validate_body function."""

    def test_validate_body_good_quality(self):
        """Test validation of high-quality body."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        body = """اكتشفت للتو ميزة جديدة غيرت كل شيء!

OpenAI أطلقت تحديثاً يجعل ChatGPT يحلل أي صورة ترسلها له 🤖

جربت أرسل لقطة شاشة لكود معقد - أعطاني شرح كامل في ثواني!

💡 نصيحتي لكم: جربوا إرسال صور لأخطاء برمجية."""

        result = validator.validate_body(body)

        assert result["score"] > 0.5
        assert result["has_personal_tone"] is True

    def test_validate_body_too_short(self):
        """Test validation of too short body."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        body = "محتوى قصير جداً"
        result = validator.validate_body(body)

        assert "Body trop court" in result["issues"]

    def test_validate_body_empty(self):
        """Test validation of empty body."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        result = validator.validate_body("")

        assert result["score"] == 0
        assert "Body manquant" in result["issues"]


class TestValidateCta:
    """Tests for validate_cta function."""

    def test_validate_cta_good_quality(self):
        """Test validation of good CTA."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        cta = "ما رأيكم؟ شاركونا تجربتكم! 💬"
        result = validator.validate_cta(cta)

        assert result["score"] > 0.7

    def test_validate_cta_with_question(self):
        """Test validation of CTA with question."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        cta = "هل جربتم هذه الميزة؟"
        result = validator.validate_cta(cta)

        assert result["score"] > 0.5

    def test_validate_cta_empty(self):
        """Test validation of empty CTA."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        result = validator.validate_cta("")

        assert result["score"] == 0
        assert "CTA manquant" in result["issues"]


class TestValidateHashtags:
    """Tests for validate_hashtags function."""

    def test_validate_hashtags_good_count(self):
        """Test validation of good hashtag count."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        hashtags = ["#ChatGPT", "#AI", "#تقنية", "#OpenAI", "#الذكاء_الاصطناعي"]
        result = validator.validate_hashtags(hashtags)

        assert result["score"] > 0.7
        assert result["count"] == 5

    def test_validate_hashtags_too_few(self):
        """Test validation of too few hashtags."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        hashtags = ["#AI"]
        result = validator.validate_hashtags(hashtags)

        assert "Peu de hashtags" in result["issues"]

    def test_validate_hashtags_too_many(self):
        """Test validation of too many hashtags."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        hashtags = [f"#tag{i}" for i in range(15)]
        result = validator.validate_hashtags(hashtags)

        assert "Trop de hashtags" in result["issues"]

    def test_validate_hashtags_empty(self):
        """Test validation of empty hashtags."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        result = validator.validate_hashtags([])

        assert "Hashtags manquants" in result["issues"]


class TestValidateContent:
    """Tests for validate_content function."""

    def test_validate_content_full(self):
        """Test full content validation."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        content = {
            "hook": "🚨 صدمة! ChatGPT يفهم الصور الآن!",
            "body": """اكتشفت للتو ميزة جديدة غيرت كل شيء!

OpenAI أطلقت تحديثاً يجعل ChatGPT يحلل أي صورة ترسلها له 🤖

جربت أرسل لقطة شاشة لكود معقد - أعطاني شرح كامل في ثواني!""",
            "cta": "ما رأيكم؟ شاركونا تجربتكم! 💬",
            "hashtags": ["#ChatGPT", "#AI", "#تقنية", "#OpenAI", "#الذكاء_الاصطناعي"],
        }

        result = validator.validate_content(content)

        assert "overall_score" in result
        assert "is_valid" in result
        assert "components" in result
        assert "grade" in result

    def test_validate_content_grade_assignment(self):
        """Test grade assignment based on score."""
        from content_quality import ContentQualityValidator

        validator = ContentQualityValidator()

        assert "A+" in validator._score_to_grade(0.95)
        assert "A " in validator._score_to_grade(0.85)
        assert "B " in validator._score_to_grade(0.75)
        assert "C " in validator._score_to_grade(0.65)
        assert "D " in validator._score_to_grade(0.55)
        assert "F " in validator._score_to_grade(0.45)


class TestValidateGeneratedContent:
    """Tests for validate_generated_content function."""

    def test_validate_generated_content_function(self):
        """Test the convenience function."""
        from content_quality import validate_generated_content

        content = {
            "hook": "🔥 خبر عاجل!",
            "body": "هذا خبر مهم عن التكنولوجيا الجديدة التي ستغير العالم وتؤثر على حياتنا اليومية",
            "cta": "ما رأيكم؟",
            "hashtags": ["#tech", "#AI"],
        }

        result = validate_generated_content(content)

        assert "overall_score" in result
        assert "is_valid" in result
