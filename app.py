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

    return "غير معروف"


def error_message(status_code, data):
    if status_code == 401:
        return "مفتاح Refetcher غير صحيح."

    if status_code == 402:
        return "رصيد Refetcher غير كافٍ."

    if status_code == 429:
        return "تم تجاوز الحد مؤقتًا. حاول مرة أخرى."

    if status_code == 502:
        return "الرابط غير صالح"

    if isinstance(data, dict):
        error = data.get("error")

        if isinstance(error, dict):
            return error.get(
                "message",
                "الرابط غير صالح"
            )

        if isinstance(error, str):
            return error

    return "الرابط غير صالح"


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

        # إزالة الروابط المكررة
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

        valid_urls = []

        for url in urls:

            lower = url.lower()

            if (
                "facebook.com/" in lower
                or "fb.watch/" in lower
                or "instagram.com/" in lower
                or "x.com/" in lower
                or "twitter.com/" in lower
            ):
                valid_urls.append(url)

        if not valid_urls:
            return jsonify({
                "status": "error",
                "message": "الرابط غير صالح"
            }), 400

        if not REFETCHER_API_KEY:

            return jsonify({
                "status": "error",
                "message": "مفتاح REFETCHER_API_KEY غير موجود في Render."
            }), 500

        headers = {
            "X-API-Key": REFETCHER_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        payload = {
            "urls": valid_urls
        }

        response = requests.post(
            REFETCHER_URL,
            json=payload,
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
                "message": error_message(
                    response.status_code,
                    api_data
                )
            }), response.status_code

        api_results = api_data.get("results", [])

        results = []

        for item in api_results:

            original_url = item.get("url", "")

            platform = (
                item.get("platform")
                or detect_platform(original_url)
            )

            # المنشور فشل
            if item.get("success") is not True:

                error = item.get("error")

                # أي فشل في استخراج الرابط
                message = "الرابط غير صالح"

                results.append({
                    "success": False,
                    "platform": platform,
                    "page_name": "غير متوفر",
                    "post_text": "",
                    "post_url": original_url,
                    "error": message
                })

                continue

            post = item.get("post") or {}
            author = item.get("author") or {}

            # اسم الحساب
            page_name = (
                author.get("name")
                or author.get("handle")
                or "الحساب غير معروف"
            )

            # نص المنشور
            post_text = (
                post.get("caption")
                or ""
            ).strip()

            # الرابط الذي سنربطه باسم الحساب
            post_url = (
                post.get("normalizedUrl")
                or original_url
            )

            results.append({

                "success": True,

                "platform": platform,

                "page_name": page_name,

                "post_text": post_text,

                "post_url": post_url

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

    except requests.exceptions.RequestException:

        return jsonify({
            "status": "error",
            "message": "تعذر الاتصال بخدمة الاستخراج."
        }), 502

    except Exception as e:

        print("SERVER ERROR:", repr(e))

        return jsonify({
            "status": "error",
            "message": "حدث خطأ غير متوقع في الخادم."
        }), 500


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
