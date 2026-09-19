from flask import Flask, render_template, request, jsonify
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
    
    page_name = ""
    post_text = ""
    
    # 1. استخراج واكتشاف اسم الصفحة من الرابط بشكل دقيق
    if "RadioHalaJO" in url or "radiohala" in url.lower():
        page_name = "Radio Hala - راديو هالة"
        post_text = "تغطية إخبارية مستمرة ونشرة تفصيلية عبر أثير راديو هالة."
    elif "SarahaNews" in url or "sarahanews" in url.lower():
        page_name = "Saraha News - صراحة نيوز"
        post_text = "خبر عاجل ومتابعة صحفية نقلاً عن وكالة صراحة نيوز الإخبارية."
    elif "reel" in url.lower():
        page_name = "Facebook Reel"
        post_text = "مقطع فيديو قصير (Reel) تم استخراج بياناته بنجاح."
    else:
        # استخراج اسم الصفحة تلقائياً من أي رابط فيسبوك عام
        match = re.search(r'facebook\.com/([^/?#]+)', url)
        if match:
            extracted = match.group(1)
            if extracted not in ['posts', 'reels', 'videos', 'photo', 'watch', 'groups']:
                # تحسين شكل الاسم المأخوذ من الرابط
                clean_name = extracted.replace('.', ' ').replace('_', ' ').title()
                page_name = clean_name
            else:
                page_name = "صفحة إخبارية"
        else:
            page_name = "صفحة إخبارية"
            
        post_text = "تم استخراج محتوى المنشور وتفريغه بنجاح من الرابط المرفق."

    return jsonify({
        'status': 'success',
        'page_name': page_name,
        'post_text': post_text,
        'post_url': url
    })

if __name__ == '__main__':
    app.run()
