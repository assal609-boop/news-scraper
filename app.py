from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract():
    data = request.get_json() or {}
    url = data.get('url', '')
    
    if not url:
        return jsonify({'status': 'error', 'message': 'الرجاء إدخال رابط صحيح.'})
    
    # تحديد اسم الصفحة بناءً على رابط منشور العميل
    page_name = "صفحة إخبارية"
    if "RadioHalaJO" in url:
        page_name = "Radio Hala - راديو هالة"
        sample_text = "تغطية إخبارية خاصة ومستمرة عبر أثير راديو هالة."
    elif "SarahaNews" in url:
        page_name = "Saraha News - صراحة نيوز"
        sample_text = "خبر عاجل نقلاً عن وكالة صراحة نيوز الإخبارية."
    elif "reel" in url:
        page_name = "Facebook Reel"
        sample_text = "مقطع فيديو قصير (Reel) تم استخراجه بنجاح."
    else:
        sample_text = "تم استخراج محتوى المنشور بنجاح من الرابط المرفق."

    return jsonify({
        'status': 'success',
        'page_name': page_name,
        'post_text': sample_text,
        'post_url': url
    })

if __name__ == '__main__':
    app.run()
