#!/usr/bin/env python3
"""
Package Content Factory for Gumroad distribution.

This script creates a clean zip file ready for upload to Gumroad.

Run: python package_for_gumroad.py
"""

import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.resolve()
DIST_DIR = BASE_DIR / 'dist'
PACKAGE_NAME = f"ContentFactory_v2.0_{datetime.now().strftime('%Y%m%d')}"


def create_package():
    """Create the Gumroad package."""
    print("📦 Creating Gumroad Package...")
    print("=" * 50)
    
    # Create dist directory
    DIST_DIR.mkdir(exist_ok=True)
    package_dir = DIST_DIR / PACKAGE_NAME
    
    # Clean previous package
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir()
    
    # Files to include
    include_files = [
        # Main files
        'launcher.py',
        'dashboard_app.py',
        'config.py',
        'database.py',
        'gemini_client.py',
        'facebook_oauth.py',
        'ai_generator.py',
        'image_generator.py',
        'image_pipeline.py',
        'smart_image_search.py',
        'unified_content_creator.py',
        'publisher.py',
        'scheduler.py',
        'scraper.py',
        'auto_runner.py',
        'rate_limiter.py',
        'ban_detector.py',
        'publication_tracker.py',
        'randomization.py',
        'retry_utils.py',
        
        # Config files
        'requirements.txt',
        'env.example',
        'README_GUMROAD.md',
        'start.bat',
        'start.sh',
        'image_config.json',
    ]
    
    include_dirs = [
        'templates',
        'static',
    ]
    
    # Copy files
    print("\n📄 Copying files...")
    for file in include_files:
        src = BASE_DIR / file
        if src.exists():
            shutil.copy2(src, package_dir / file)
            print(f"  ✅ {file}")
        else:
            print(f"  ⚠️ Missing: {file}")
    
    # Copy directories
    print("\n📁 Copying directories...")
    for dir_name in include_dirs:
        src = BASE_DIR / dir_name
        if src.exists():
            shutil.copytree(src, package_dir / dir_name)
            print(f"  ✅ {dir_name}/")
        else:
            print(f"  ⚠️ Missing: {dir_name}/")
    
    # Create empty directories
    (package_dir / 'generated_images').mkdir(exist_ok=True)
    (package_dir / 'downloaded_images').mkdir(exist_ok=True)
    (package_dir / 'logs').mkdir(exist_ok=True)
    
    # Create videos folder with placeholders
    videos_dir = package_dir / 'videos'
    videos_dir.mkdir(exist_ok=True)
    
    (videos_dir / '01-setup.txt').write_text(
        "📹 فيديو الإعداد\n\n"
        "شاهد الفيديو هنا:\n"
        "https://www.loom.com/share/YOUR_SETUP_VIDEO_ID\n\n"
        "في هذا الفيديو:\n"
        "- تشغيل التطبيق\n"
        "- إعداد مفتاح Gemini\n"
        "- إنشاء أول منشور"
    )
    
    (videos_dir / '02-facebook.txt').write_text(
        "📹 ربط Facebook\n\n"
        "شاهد الفيديو هنا:\n"
        "https://www.loom.com/share/YOUR_FACEBOOK_VIDEO_ID\n\n"
        "في هذا الفيديو:\n"
        "- إنشاء Facebook App\n"
        "- ربط الصفحة\n"
        "- إعداد OAuth"
    )
    
    (videos_dir / '03-gemini.txt').write_text(
        "📹 مفتاح Gemini المجاني\n\n"
        "شاهد الفيديو هنا:\n"
        "https://www.loom.com/share/YOUR_GEMINI_VIDEO_ID\n\n"
        "الحصول على المفتاح:\n"
        "1. اذهب إلى makersuite.google.com\n"
        "2. سجل دخول بحساب Google\n"
        "3. انقر Create API Key"
    )
    
    # Create bonuses folder
    bonuses_dir = package_dir / 'bonuses'
    bonuses_dir.mkdir(exist_ok=True)
    
    (bonuses_dir / 'templates_guide.md').write_text(
        "# 🎁 5 قوالب منشورات فيروسية\n\n"
        "## 1. قالب الخبر العاجل\n"
        "```\n"
        "🚨 خبر عاجل!\n"
        "[الخبر الرئيسي]\n\n"
        "التفاصيل الكاملة:\n"
        "[3 نقاط]\n\n"
        "ما رأيكم؟ 💬\n"
        "```\n\n"
        "## 2. قالب السؤال المثير\n"
        "```\n"
        "🤔 هل تعلم أن...\n"
        "[حقيقة مفاجئة]\n\n"
        "والأغرب:\n"
        "[تفصيل]\n\n"
        "من كان يعرف هذا؟ 🙋‍♂️\n"
        "```\n\n"
        "## 3. قالب المقارنة\n"
        "```\n"
        "📊 [منتج A] vs [منتج B]\n\n"
        "الفائز؟\n"
        "[الإجابة]\n\n"
        "السبب:\n"
        "[3 نقاط]\n\n"
        "أنتم مع مين؟ 👇\n"
        "```\n\n"
        "## 4. قالب النصيحة\n"
        "```\n"
        "💡 نصيحة اليوم:\n"
        "[النصيحة]\n\n"
        "لماذا؟\n"
        "[الشرح]\n\n"
        "جربوها وقولولي! 🚀\n"
        "```\n\n"
        "## 5. قالب الإحصائية\n"
        "```\n"
        "📈 90% من الناس لا يعرفون هذا!\n\n"
        "[المعلومة]\n\n"
        "الدليل:\n"
        "[مصدر]\n\n"
        "مفاجأة؟ أم كنتم تعرفون؟ 🤷‍♂️\n"
        "```\n"
    )
    
    # Rename README for package
    readme_src = package_dir / 'README_GUMROAD.md'
    readme_dst = package_dir / 'README.md'
    if readme_src.exists():
        readme_src.rename(readme_dst)
    
    # Rename env.example
    env_src = package_dir / 'env.example'
    env_dst = package_dir / '.env.example'
    if env_src.exists():
        shutil.copy2(env_src, env_dst)
    
    # Create zip file
    print("\n📦 Creating zip file...")
    zip_path = DIST_DIR / f"{PACKAGE_NAME}.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(package_dir):
            # Skip __pycache__
            dirs[:] = [d for d in dirs if d != '__pycache__']
            
            for file in files:
                if file.endswith('.pyc'):
                    continue
                file_path = Path(root) / file
                arcname = file_path.relative_to(package_dir)
                zipf.write(file_path, f"{PACKAGE_NAME}/{arcname}")
    
    # Get file size
    size_mb = zip_path.stat().st_size / 1024 / 1024
    
    print("\n" + "=" * 50)
    print("✅ Package created successfully!")
    print(f"📁 Location: {zip_path}")
    print(f"📊 Size: {size_mb:.1f} MB")
    print("=" * 50)
    
    print("\n📝 Next steps:")
    print("1. Record Loom videos for videos/ folder")
    print("2. Upload to Gumroad")
    print("3. Set price: $97 USD (lifetime access)")
    print("4. Write sales copy")
    print("5. Share on social media!")
    
    return zip_path


if __name__ == "__main__":
    create_package()
