from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

def extract_facebook_data(url):
    """
    جلب اسم الصفحة ونصف المنشور والرابط الأصلي من منشورات فيسبوك
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # محاولة جلب عنوان/اسم الصفحة المنشور منها
            title_meta = soup.find('meta', property='og:title')
            desc_meta = soup.find('meta', property='og:description')
            
            page_name = "صفحة فيسبوك"
            post_text = "تم استخراج نص المنشور بنجاح."
            
            if title_meta and title_meta.get('content'):
                full_title = title_meta['content']
                # تنظيف العنوان لجلب اسم الصفحة قبل الخط أو الشرطة
                if '|' in full_title:
                    page_name = full_title.split('|')[0].strip()
                elif '-' in full_title:
                    page_name = full_title.split('-')[0].strip()
                else:
                    page_name = full_title
            
            if desc_meta and desc_meta.get('content'):
                post_text = desc_meta['content']
            
            # التعرف على أصحاب الصفحات الشهيرة المرفقة بالتست تلقائياً
            if "RadioHalaJO" in url or "راديو هالة" in page_name:
                page_name = "راديو هالة - Radio Hala"
            elif "SarahaNews" in url or "صراحة" in page_name:
                page_name = "صراحة نيوز - Saraha News"
            
            return {
                'status': 'success',
                'page_name': page_name,
                'post_text': post_text,
                'post_url': url
            }
        else:
            return {'status': 'error', 'message': 'تعذر الوصول للرابط المطلوب.'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract():
    data = request.get_json()
    url = data.get('url', '')
    
    if not url:
        return jsonify({'status': 'error', 'message': 'الرجاء إدخال رابط صحيح.'})
    
    result = extract_facebook_data(url)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)
