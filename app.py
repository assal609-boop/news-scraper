from flask import Flask, render_template, request, jsonify
import requests
import os
import re

app = Flask(__name__)

REFETCHER_API_KEY = os.environ.get("REFETCHER_API_KEY", "").strip()
REFETCHER_URL = "https://api.refetcher.com/"


@app.route("/")
def home():
    return render_template("index.html")


def clean_url(url):
    url = url.strip().replace(" ", "")
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    return url


def detect_platform(url):
    lower = url.lower()
    if "instagram.com" in lower:
        return "Instagram"
    if "x.com" in lower or "twitter.com" in lower:
        return "X / Twitter"
    if "facebook.com" in lower or "fb.watch" in lower:
        return "Facebook"
    return "صفحة إلكترونية"


@app.route("/extract", methods=["POST"])
def extract():
    try:
        data = request.get_json(silent=True) or {}
        raw_urls = data.get("urls", "")

        if not isinstance(raw_urls, str):
            return jsonify({
                "status": "error",
                "message": "صيغة الروابط غير صحيحة."
            }), 400

        urls = [
            clean_url(x)
            for x in raw_urls.splitlines()
            if x.strip()
        ]

        urls = list(dict.fromkeys(urls))

        if not urls:
            return jsonify({
                "status": "error",
                "message": "ضع رابطًا واحدًا على الأقل."
            }), 400

        if len(urls) > 50:
            return jsonify({
                "status": "error",
                "message": "الحد الأقصى 50 رابطًا في المرة الواحدة."
            }), 400

        valid_urls = [u for u in urls if any(p in u.lower() for p in ["facebook.com", "fb.watch", "instagram.com", "x.com", "twitter.com"])]

        if not valid_urls:
            return jsonify({
                "status": "error",
                "message": "الرجاء إدخال روابط صالحة لمصادر مدعومة."
            }), 400

        if not REFETCHER_API_KEY:
            return jsonify({
                "status": "error",
                "message": "مفتاح REFETCHER_API_KEY غير موجود في إعدادات المنصة."
            }), 500

        headers = {
            "X-API-Key": REFETCHER_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = requests.post(
            REFETCHER_URL,
            json={"urls": valid_urls},
            headers=headers,
            timeout=120
        )

        try:
            api_data = response.json()
        except Exception:
            api_data = {}

        if response.status_code != 200:
            return jsonify({
                "status": "error",
                "message": "حدث خطأ من خدمة الاستخراج الخارجية. حاول لاحقاً."
            }), response.status_code

        api_results = api_data.get("results", [])
        results = []

        api_dict = {item.get("url"): item for item in api_results}

        for original_url in valid_urls:
            platform = detect_platform(original_url)
            item = api_dict.get(original_url, {})
            
            post = item.get("post") or {}
            author = item.get("author") or {}

            # استخراج اسم الحساب الصريح بدقة
            page_name = (
                author.get("name")
                or author.get("handle")
                or author.get("username")
                or f"صفحة {platform}"
            )

            # استخراج النص الصريح للمنشور بدقة
            post_text = (
                post.get("caption")
                or post.get("text")
                or post.get("content")
                or ""
            ).strip()

            if not post_text:
                post_text = "النص الصريح غير متوفر أو أن المنشور محمي"

            results.append({
                "success": True,
                "platform": platform,
                "page_name": page_name,
                "post_text": post_text,
                "post_url": original_url
            })

        return jsonify({
            "status": "success",
            "results": results,
            "total": len(results)
        })

    except requests.exceptions.Timeout:
        return jsonify({
            "status": "error",
            "message": "انتهت مهلة الاتصال. حاول مرة أخرى."
        }), 504
    except Exception as e:
        print("SERVER ERROR:", repr(e))
        return jsonify({
            "status": "error",
            "message": "حدث خطأ غير متوقع في الخادم."
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
