/**
 * Content Factory v3 - Internationalization
 * UTF-8 Arabic + French + English translations
 */

const translations = {
    'AR': {
        'nav_dashboard': 'لوحة التحكم',
        'nav_studio': 'استوديو المحتوى',
        'nav_templates': 'القوالب',
        'nav_settings': 'الإعدادات',
        'nav_health': 'حالة النظام',
        'nav_setup': 'الإعداد',
        'page_subtitle_default': 'مركز التحكم المباشر',

        'dashboard_status': 'حالة النظام',
        'dashboard_pause': 'إيقاف مؤقت',
        'dashboard_run_now': 'تشغيل الآن',
        'kpi_posts': 'المنشورات (7 أيام)',
        'kpi_reach': 'الوصول',
        'kpi_likes': 'الإعجابات',
        'kpi_engagement': 'التفاعل',
        'queue_waiting': 'بانتظار الموافقة',
        'queue_scheduled': 'مجدول',
        'queue_published': 'تم النشر',
        'insights_title': 'رؤى',
        'insights_hint': 'ملخص من آخر المنشورات',
        'pipeline_title': 'خط الإنتاج',
        'pipeline_hint': 'المنشورات القادمة',

        'settings_general': 'عام',
        'settings_posts_per_day': 'المنشورات يومياً',
        'settings_approval_mode': 'وضع الموافقة',
        'settings_approval_hint': 'موافقة مطلوبة قبل النشر.',
        'settings_language_ratio': 'نسبة اللغات',
        'settings_save_language': 'حفظ',
        'settings_api_keys': 'مفاتيح API',
        'settings_database': 'قاعدة البيانات',
        'settings_database_hint': 'SQLite افتراضياً، Supabase اختياري.',

        'health_last_error': 'آخر خطأ',
        'health_cooldown': 'فترة التهدئة',
        'health_tokens': 'حالة الرموز',
        'health_quotas': 'حصص API',
        'health_events': 'الأحداث الأخيرة',
        'health_diagnostics': 'التشخيصات',

        'setup_title': 'الإعداد الأولي',
        'setup_subtitle': 'قم بتوصيل فيسبوك ومزود الذكاء الاصطناعي.',
        'setup_facebook': 'فيسبوك',
        'setup_ai': 'مزود الذكاء الاصطناعي',
        'setup_images': 'مفتاح Pexels (اختياري)',
        'setup_save': 'حفظ وبدء',

        'studio_search': 'بحث في المحتوى...',
        'studio_all': 'الكل',
        'studio_pending': 'قيد الانتظار',
        'studio_scheduled': 'مجدول',
        'studio_published': 'منشور',
        'studio_drafted': 'مسودة',
        'studio_select': 'اختر محتوى',
        'studio_hook': 'العنوان الجذاب',
        'studio_caption': 'النص',
        'studio_hashtags': 'الهاشتاغات',
        'studio_save': 'حفظ',
        'studio_reject': 'رفض',
        'studio_regenerate': 'إعادة إنشاء',
        'studio_approve': 'موافقة',
        'studio_publish': 'نشر الآن',
        'studio_schedule': 'جدولة',
        'studio_no_image': 'لا توجد صورة',

        'templates_image': 'قوالب الصور',
        'templates_text': 'أنماط النصوص',
        'templates_set_default': 'تعيين كافتراضي'
    },
    'FR': {
        'nav_dashboard': 'Tableau de bord',
        'nav_studio': 'Studio',
        'nav_templates': 'Modèles',
        'nav_settings': 'Paramètres',
        'nav_health': 'Santé',
        'nav_setup': 'Configuration',
        'page_subtitle_default': 'Centre de contrôle en direct',

        'dashboard_status': 'Statut système',
        'dashboard_pause': 'Pause',
        'dashboard_run_now': 'Exécuter',
        'kpi_posts': 'Posts (7j)',
        'kpi_reach': 'Portée',
        'kpi_likes': 'Likes',
        'kpi_engagement': 'Engagement',
        'queue_waiting': 'En attente',
        'queue_scheduled': 'Planifié',
        'queue_published': 'Publié',
        'insights_title': 'Insights',
        'insights_hint': 'Résumé des derniers posts',
        'pipeline_title': 'Pipeline',
        'pipeline_hint': 'Prochaines publications',

        'settings_general': 'Général',
        'settings_posts_per_day': 'Posts par jour',
        'settings_approval_mode': 'Mode validation',
        'settings_approval_hint': 'Validation requise avant publication.',
        'settings_language_ratio': 'Ratio langues',
        'settings_save_language': 'Enregistrer',
        'settings_api_keys': 'Clés API',
        'settings_database': 'Base de données',
        'settings_database_hint': 'SQLite par défaut, Supabase optionnel.',

        'health_last_error': 'Dernière erreur',
        'health_cooldown': 'Refroidissement',
        'health_tokens': 'Statut tokens',
        'health_quotas': 'Quotas API',
        'health_events': 'Événements récents',
        'health_diagnostics': 'Diagnostics',

        'setup_title': 'Configuration initiale',
        'setup_subtitle': 'Connecter Facebook et le fournisseur IA.',
        'setup_facebook': 'Facebook',
        'setup_ai': 'Fournisseur IA',
        'setup_images': 'Clé Pexels (optionnel)',
        'setup_save': 'Enregistrer et démarrer',

        'studio_search': 'Rechercher du contenu...',
        'studio_all': 'Tout',
        'studio_pending': 'En attente',
        'studio_scheduled': 'Planifié',
        'studio_published': 'Publié',
        'studio_drafted': 'Brouillon',
        'studio_select': 'Sélectionner un contenu',
        'studio_hook': 'Accroche',
        'studio_caption': 'Texte',
        'studio_hashtags': 'Hashtags',
        'studio_save': 'Enregistrer',
        'studio_reject': 'Rejeter',
        'studio_regenerate': 'Régénérer',
        'studio_approve': 'Approuver',
        'studio_publish': 'Publier maintenant',
        'studio_schedule': 'Planifier',
        'studio_no_image': 'Pas d\'image',

        'templates_image': 'Modèles d\'images',
        'templates_text': 'Modèles de texte',
        'templates_set_default': 'Définir par défaut'
    },
    'EN': {
        'nav_dashboard': 'Dashboard',
        'nav_studio': 'Studio',
        'nav_templates': 'Templates',
        'nav_settings': 'Settings',
        'nav_health': 'Health',
        'nav_setup': 'Setup',
        'page_subtitle_default': 'Live control center',

        'dashboard_status': 'System Status',
        'dashboard_pause': 'Pause',
        'dashboard_run_now': 'Run Now',
        'kpi_posts': 'Posts (7d)',
        'kpi_reach': 'Reach',
        'kpi_likes': 'Likes',
        'kpi_engagement': 'Engagement',
        'queue_waiting': 'Waiting Approval',
        'queue_scheduled': 'Scheduled',
        'queue_published': 'Published',
        'insights_title': 'Insights',
        'insights_hint': 'Summary from recent posts',
        'pipeline_title': 'Pipeline',
        'pipeline_hint': 'Upcoming posts',

        'settings_general': 'General',
        'settings_posts_per_day': 'Posts per day',
        'settings_approval_mode': 'Approval mode',
        'settings_approval_hint': 'Require manual approval before publish.',
        'settings_language_ratio': 'Language Ratio',
        'settings_save_language': 'Save',
        'settings_api_keys': 'API Keys',
        'settings_database': 'Database',
        'settings_database_hint': 'SQLite by default, Supabase optional.',

        'health_last_error': 'Last Error',
        'health_cooldown': 'Cooldown',
        'health_tokens': 'Token Health',
        'health_quotas': 'API Quotas',
        'health_events': 'Recent Events',
        'health_diagnostics': 'Diagnostics',

        'setup_title': 'Initial Setup',
        'setup_subtitle': 'Connect Facebook and AI provider.',
        'setup_facebook': 'Facebook',
        'setup_ai': 'AI Provider',
        'setup_images': 'Pexels key (optional)',
        'setup_save': 'Save & Start',

        'studio_search': 'Search content...',
        'studio_all': 'All',
        'studio_pending': 'Pending',
        'studio_scheduled': 'Scheduled',
        'studio_published': 'Published',
        'studio_drafted': 'Drafted',
        'studio_select': 'Select content',
        'studio_hook': 'Hook',
        'studio_caption': 'Caption',
        'studio_hashtags': 'Hashtags',
        'studio_save': 'Save',
        'studio_reject': 'Reject',
        'studio_regenerate': 'Regenerate',
        'studio_approve': 'Approve',
        'studio_publish': 'Publish Now',
        'studio_schedule': 'Schedule',
        'studio_no_image': 'No image',

        'templates_image': 'Image Templates',
        'templates_text': 'Text Patterns',
        'templates_set_default': 'Set as Default'
    }
};

class I18nManager {
    constructor() {
        this.currentLang = localStorage.getItem('ui_lang') || 'EN';
        this.init();
    }

    init() {
        this.applyLanguage(this.currentLang);
        this.updateSelects();
    }

    setLanguage(lang) {
        if (!translations[lang]) return;
        this.currentLang = lang;
        localStorage.setItem('ui_lang', lang);
        this.applyLanguage(lang);
    }

    applyLanguage(lang) {
        const dir = lang === 'AR' ? 'rtl' : 'ltr';
        document.documentElement.setAttribute('dir', dir);
        document.documentElement.setAttribute('lang', lang.toLowerCase());

        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (translations[lang][key]) {
                el.textContent = translations[lang][key];
            }
        });

        // Also update placeholder attributes
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            if (translations[lang][key]) {
                el.placeholder = translations[lang][key];
            }
        });

        window.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang, dir } }));
    }

    t(key) {
        return (translations[this.currentLang] || {})[key] || key;
    }

    updateSelects() {
        const switcher = document.getElementById('lang-switcher');
        if (switcher) {
            switcher.value = this.currentLang;
            switcher.addEventListener('change', (e) => this.setLanguage(e.target.value));
        }
    }
}

window.i18n = new I18nManager();
