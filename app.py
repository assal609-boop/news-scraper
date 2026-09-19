from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract():
    data = request.get_json() or {}
    raw_urls = data.get('urls', '')
    
    # تقسيم الروابط المدخلة (كل رابط في سطر)
    url_list = [u.strip() for u in raw_urls.split('\n') if u.strip()]
    
    if not url_list:
        return jsonify({'status': 'error', 'message': 'الرجاء إدخال رابط واحد على الأقل.'})
    
    results = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8'
    }

    for url in url_list:
        page_name = ""
        post_text = ""
        
        # تحويل رابط فيسبوك إلى النسخة الخفيفة mbasic لقراءة النص الفعلي مباشرة بدون حظر
        target_url = url
        if "facebook.com" in url or "fb.watch" in url:
            target_url = url.replace("www.facebook.com", "mbasic.facebook.com").replace("web.facebook.com", "mbasic.facebook.com")

        try:
            res = requests.get(target_url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 1. محاولة جلب الميتا داتا الرسمية للمنشور
            og_title = soup.find('meta', property='og:title')
            og_desc = soup.find('meta', property='og:description')
            
            if og_title and og_title.get('content'):
                title_val = og_title['content']
                page_name = re.split(r'[|\-–]', title_val)[0].strip()
                
            if og_desc and og_desc.get('content'):
                post_text = og_desc['content']

            # 2. في حال لم تجلب الميتا داتا النص، نقوم بقراءة الفقرات والنصوص الفعلية من الصفحة مباشرة
            if not post_text or post_text.lower() in ['facebook', 'log in']:
                # البحث عن النصوص داخل وسم الملاحظات والمنشورات p أو article
                paragraphs = soup.find_all(['p', 'article', 'div'])
                candidate_texts = []
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if len(text) > 30 and "Facebook" not in text and "تسجيل الدخول" not in text:
                        candidate_texts.append(text)
                
                if candidate_texts:
                    post_text = candidate_texts[0]

        except Exception as e:
            pass

        # 3. إذا لم يجد اسم الصفحة من الصفحة، يستخرجه من الرابط تلقائياً
        if not page_name or page_name.lower() in ['facebook', 'home', 'log in']:
            match = re.search(r'facebook\.com/([^/?#]+)', url)
            if match:
                extracted = match.group(1)
                if extracted not in ['posts', 'reels', 'videos', 'photo', 'watch', 'groups', 'story']:
                    page_name = extracted.replace('.', ' ').replace('_', ' ').title()
                else:
                    page_name = "صفحة إخبارية"
            else:
                page_name = "صفحة إخبارية"

        # إذا كان المنشور يحتاج تسجيل دخول خاص جداً يظهر تنبيه برمجي ديناميكي
        if not post_text or post_text.lower() in ['facebook', 'log in']:
            post_text = "تعذر قراءة النص المباشر للمنشور بسبب قيود الخصوصية على هذا الرابط المحدد."

        results.append({
            'page_name': page_name,
            'post_text': post_text,
            'post_url': url
        })

    return jsonify({
        'status': 'success',
        'results': results
    })

if __name__ == '__main__':
    app.run()
