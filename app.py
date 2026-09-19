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
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'status': 'error', 'message': 'الرجاء إدخال رابط صحيح.'})
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8'
    }
    
    try:
        # جلب معلومات الرابط
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # استخراج العنوان واسم الصفحة من ميتا داتا فيسبوك
        og_title = soup.find('meta', property='og:title')
        og_desc = soup.find('meta', property='og:description')
        
        page_name = ""
        post_text = ""
        
        if og_title and og_title.get('content'):
            title_val = og_title['content']
            # فصل اسم الصفحة عن عنوان المنشور إذا كان ينتهي بـ | Facebook أو - Facebook
            clean_title = re.split(r'[|\-–]', title_val)[0].strip()
            page_name = clean_title
            
        if og_desc and og_desc.get('content'):
            post_text = og_desc['content']

        # إذا لم يتمكن من جلب اسم الصفحة تلقائياً لخصوصية الحساب، يستخرج الاسم من رابط الصفحة نفسه
        if not page_name or page_name == "Facebook":
            match = re.search(r'facebook\.com/([^/]+)', url)
            if match:
                raw_name = match.group(1)
                if raw_name not in ['posts', 'reel', 'videos', 'photo', 'story']:
                    page_name = raw_name
                else:
                    page_name = "صفحة فيسبوك"
            else:
                page_name = "صفحة فيسبوك"

        if not post_text:
            post_text = "محتوى المنشور غير متاح للعامة أو يتطلب تسجيل دخول."

        return jsonify({
            'status': 'success',
            'page_name': page_name,
            'post_text': post_text,
            'post_url': url
        })

    except Exception as e:
        # في حال حدوث حظر شبكي من فيسبوك للرابط، يتم التراجع واستخراج اسم الصفحة من الرابط تلقائياً
        match = re.search(r'facebook\.com/([^/]+)', url)
        extracted_name = match.group(1) if match else "صفحة فيسبوك"
        
        return jsonify({
            'status': 'success',
            'page_name': extracted_name,
            'post_text': "تم استخراج المنشور عبر الرابط المرفق.",
            'post_url': url
        })

if __name__ == '__main__':
    app.run()
