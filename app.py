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


def clean_facebook_url(url):
    url = url.strip()

    # إزالة المسافات والرموز غير الضرورية
    url = url.replace(" ", "")

    # قبول facebook.com و www.facebook.com
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url

    return url


def get_error_message(status_code, data):
    if status_code == 401:
        return "مفتاح Refetcher غير صحيح أو غير موجود."

    if status_code == 402:
        return "رصيد Refetcher غير كافٍ."

    if status_code == 404:
        return "المنشور خاص أو محذوف أو غير متاح للعامة."

    if status_code == 429:
        return "تم تجاوز الحد المسموح مؤقتًا. حاول مرة أخرى."

    if status_code == 400:
        return "الرابط غير صالح أو الطلب غير صحيح."

    if isinstance(data, dict):
        error = data.get("error")

        if isinstance(error, dict):
            return (
                error.get("message")
                or error.get("code")
                or "حدث خطأ أثناء استخراج البيانات."
            )

        if isinstance(error, str):
            return error

    return f"حدث خطأ من خدمة الاستخراج ({status_code})."


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

        # كل رابط في سطر
        urls = [
            clean_facebook_url(x)
            for x in raw_urls.splitlines()
            if x.strip()
        ]

        # إزالة التكرار مع الحفاظ على الترتيب
        urls = list(dict.fromkeys(urls))

        if not urls:
            return jsonify({
                "status": "error",
                "message": "ضع رابط Facebook واحدًا على الأقل."
            }), 400

        # Refetcher يسمح بحد أقصى 50 رابطًا في الطلب
        if len(urls) > 50:
            return jsonify({
                "status": "error",
                "message": "يمكنك إدخال 50 رابطًا كحد أقصى في المرة الواحدة."
            }), 400

        # التأكد أن الروابط Facebook
        valid_urls = []

        for url in urls:
            lower = url.lower()

            if (
                "facebook.com/" in lower
                or "fb.com/" in lower
                or "fb.watch/" in lower
            ):
                valid_urls.append(url)

        if not valid_urls:
            return jsonify({
                "status": "error",
                "message": "لم يتم العثور على روابط Facebook صحيحة."
            }), 400

        if not REFETCHER_API_KEY:
            return jsonify({
                "status": "error",
                "message": "لم يتم وضع REFETCHER_API_KEY في إعدادات Render."
            }), 500

        # طلب واحد لكل الروابط
        payload = {
            "urls": valid_urls
        }

        headers = {
            "X-API-Key": REFETCHER_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json"
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

        # خطأ على مستوى الطلب
        if response.status_code != 200:
            return jsonify({
                "status": "error",
                "message": get_error_message(
                    response.status_code,
                    api_data
                )
            }), response.status_code

        api_results = api_data.get("results", [])

        results = []

        for item in api_results:

            original_url = item.get("url", "")

            if item.get("success") is not True:
                results.append({
                    "success": False,
                    "page_name": "غير متوفر",
                    "post_text": "",
                    "post_url": original_url,
                    "error": (
                        item.get("error", {}).get("message")
                        if isinstance(item.get("error"), dict)
                        else str(item.get("error", "تعذر استخراج المنشور"))
                    )
                })
                continue

            post = item.get("post") or {}
            author = item.get("author") or {}

            # اسم الصفحة / الحساب
            page_name = (
                author.get("name")
                or author.get("handle")
                or "اسم الصفحة غير متوفر"
            )

            # نص المنشور
            post_text = (
                post.get("caption")
                or ""
            ).strip()

            # الرابط الأصلي أو الرابط المطبع من Refetcher
            normalized_url = (
                post.get("normalizedUrl")
                or original_url
            )

            results.append({
                "success": True,
                "page_name": page_name,
                "post_text": post_text,
                "post_url": normalized_url,

                # معلومات إضافية مفيدة
                "published_at": post.get("publishedAt"),
                "type": post.get("type"),

                "metrics": item.get("metrics") or {}
            })

        return jsonify({
            "status": "success",
            "results": results,
            "total": len(results)
        })

    except requests.exceptions.Timeout:
        return jsonify({
            "status": "error",
            "message": "انتهت مهلة الاتصال بخدمة Facebook. حاول مرة أخرى."
        }), 504

    except requests.exceptions.RequestException as e:
        return jsonify({
            "status": "error",
            "message": "تعذر الاتصال بخدمة Refetcher."
        }), 502

    except Exception as e:
        print("SERVER ERROR:", repr(e))

        return jsonify({
            "status": "error",
            "message": "حدث خطأ غير متوقع في الخادم."
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
