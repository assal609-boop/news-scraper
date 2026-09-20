import os
import requests

from flask import Flask, render_template, request, jsonify


app = Flask(__name__)


REFETCHER_API_KEY = os.environ.get("REFETCHER_API_KEY", "").strip()
REFETCHER_URL = "https://api.refetcher.com/"


def detect_platform(url):
    url = str(url).lower()

    if "facebook.com" in url or "fb.com" in url:
        return "facebook"

    if "instagram.com" in url:
        return "instagram"

    if "x.com" in url or "twitter.com" in url:
        return "x"

    return "unknown"


def get_error_message(data, fallback):
    if isinstance(data, dict):
        error = data.get("error")

        if isinstance(error, dict):
            return error.get("message", fallback)

        if error:
            return str(error)

        if data.get("message"):
            return str(data["message"])

    return fallback


def parse_refetcher_result(result, original_url):

    platform = (
        result.get("platform")
        or detect_platform(original_url)
    )

    post = result.get("post") or {}
    author = result.get("author") or {}

    page_name = (
        author.get("name")
        or author.get("handle")
        or author.get("username")
        or "الحساب غير معروف"
    )

    post_text = (
        post.get("caption")
        or post.get("text")
        or post.get("description")
        or result.get("caption")
        or result.get("text")
        or "لا يوجد نص منشور ظاهر."
    )

    post_url = (
        post.get("normalizedUrl")
        or post.get("url")
        or result.get("url")
        or original_url
    )

    return {
        "page_name": str(page_name),
        "post_text": str(post_text),
        "post_url": str(post_url),
        "platform": platform,
        "error": None
    }


def scrape_one(url):

    platform = detect_platform(url)

    if platform == "unknown":

        return {
            "page_name": "رابط غير مدعوم",
            "post_text": "",
            "post_url": url,
            "platform": "unknown",
            "error":
                "الرابط يجب أن يكون Facebook أو Instagram أو X."
        }

    if not REFETCHER_API_KEY:

        return {
            "page_name": "خطأ في إعداد الموقع",
            "post_text": "",
            "post_url": url,
            "platform": platform,
            "error":
                "REFETCHER_API_KEY غير موجود في Render."
        }

    headers = {
        "X-API-Key": REFETCHER_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "urls": [url]
    }

    try:

        response = requests.post(
            REFETCHER_URL,
            headers=headers,
            json=payload,
            timeout=90
        )

    except requests.RequestException as error:

        return {
            "page_name": "تعذر الاتصال",
            "post_text": "",
            "post_url": url,
            "platform": platform,
            "error":
                "تعذر الاتصال بخدمة الاستخراج."
        }

    # لا نفترض أن الرد JSON
    content_type = response.headers.get(
        "Content-Type",
        ""
    ).lower()

    if "application/json" not in content_type:

        return {
            "page_name": "خطأ من خدمة الاستخراج",
            "post_text": "",
            "post_url": url,
            "platform": platform,
            "error":
                "الخدمة أعادت صفحة غير JSON. "
                "رمز الاستجابة: "
                + str(response.status_code)
        }

    try:

        data = response.json()

    except ValueError:

        return {
            "page_name": "خطأ من خدمة الاستخراج",
            "post_text": "",
            "post_url": url,
            "platform": platform,
            "error":
                "الخدمة أعادت استجابة غير صالحة."
        }

    if not response.ok:

        return {
            "page_name": "تعذر استخراج الرابط",
            "post_text": "",
            "post_url": url,
            "platform": platform,
            "error":
                get_error_message(
                    data,
                    "فشل استخراج الرابط."
                )
        }

    results = data.get("results") or []

    if not results:

        return {
            "page_name": "لا توجد نتيجة",
            "post_text": "",
            "post_url": url,
            "platform": platform,
            "error":
                "لم تُرجع الخدمة بيانات لهذا الرابط."
        }

    result = results[0]

    if not isinstance(result, dict):

        return {
            "page_name": "خطأ في البيانات",
            "post_text": "",
            "post_url": url,
            "platform": platform,
            "error":
                "صيغة النتيجة غير صحيحة."
        }

    if result.get("success") is False:

        return {
            "page_name": "تعذر استخراج المنشور",
            "post_text": "",
            "post_url": url,
            "platform": platform,
            "error":
                get_error_message(
                    result,
                    "تعذر استخراج المنشور."
                )
        }

    return parse_refetcher_result(
        result,
        url
    )


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/extract", methods=["POST"])
def extract():

    try:

        data = request.get_json(
            silent=True
        )

        if not isinstance(data, dict):

            return jsonify({
                "success": False,
                "error":
                    "بيانات الطلب غير صحيحة."
            }), 400

        urls = data.get("urls")

        if not isinstance(urls, list):

            return jsonify({
                "success": False,
                "error":
                    "لم يتم إرسال قائمة الروابط."
            }), 400

        urls = [
            str(url).strip()
            for url in urls
            if str(url).strip()
        ]

        if not urls:

            return jsonify({
                "success": False,
                "error":
                    "أدخل رابطًا واحدًا على الأقل."
            }), 400

        if len(urls) > 50:

            return jsonify({
                "success": False,
                "error":
                    "الحد الأقصى 50 رابطًا."
            }), 400

        # كل رابط بشكل منفصل
        # حتى لا يؤثر رابط على رابط آخر

        results = []

        for url in urls:

            result = scrape_one(url)

            results.append(result)

        successful = sum(
            1
            for result in results
            if not result.get("error")
        )

        failed = len(results) - successful

        return jsonify({
            "success": True,
            "total": len(results),
            "successful": successful,
            "failed": failed,
            "results": results
        })

    except Exception as error:

        # مهم جدًا:
        # حتى لو حدث خطأ داخلي،
        # نرجع JSON وليس صفحة HTML

        return jsonify({
            "success": False,
            "error":
                "خطأ داخلي في السيرفر: "
                + str(error)
        }), 500


@app.errorhandler(404)
def not_found(error):

    return jsonify({
        "success": False,
        "error": "المسار غير موجود."
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):

    return jsonify({
        "success": False,
        "error": "طريقة الطلب غير مسموحة."
    }), 405


@app.errorhandler(500)
def internal_error(error):

    return jsonify({
        "success": False,
        "error": "حدث خطأ داخلي في السيرفر."
    }), 500


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
