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


def text_value(value):
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    return str(value).strip()


def parse_result(result, original_url):
    """
    تحويل نتيجة Refetcher إلى الشكل الذي يفهمه الموقع.
    """

    platform = (
        result.get("platform")
        or detect_platform(original_url)
    )

    post = result.get("post") or {}
    author = result.get("author") or {}
    profile = result.get("profile") or {}

    page_name = ""

    for value in [
        author.get("name"),
        author.get("displayName"),
        author.get("username"),
        author.get("handle"),
        profile.get("name"),
        profile.get("username"),
        profile.get("handle"),
    ]:
        if value:
            page_name = text_value(value)
            break

    post_text = ""

    for value in [
        post.get("caption"),
        post.get("text"),
        post.get("description"),
        result.get("caption"),
        result.get("text"),
    ]:
        if value:
            post_text = text_value(value)
            break

    post_url = (
        post.get("normalizedUrl")
        or post.get("url")
        or result.get("url")
        or original_url
    )

    return {
        "page_name": page_name or "الحساب غير معروف",
        "post_text": post_text or "لا يوجد نص منشور ظاهر.",
        "post_url": post_url or original_url,
        "platform": platform,
        "error": None
    }


def parse_error_result(original_url, platform, error_data):
    """
    تحويل خطأ Refetcher إلى نتيجة لا تكسر بقية النتائج.
    """

    if isinstance(error_data, dict):

        category = error_data.get(
            "category",
            "scrape_error"
        )

        message = error_data.get(
            "message",
            "تعذر استخراج هذا الرابط."
        )

        error_text = f"{category}: {message}"

    else:

        error_text = text_value(
            error_data
        ) or "تعذر استخراج هذا الرابط."

    return {
        "page_name": "تعذر استخراج الرابط",
        "post_text": "",
        "post_url": original_url,
        "platform": platform,
        "error": error_text
    }


def request_refetcher(payload):
    """
    إرسال طلب إلى Refetcher.
    """

    headers = {
        "X-API-Key": REFETCHER_API_KEY,
        "Content-Type": "application/json"
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
            "ok": False,
            "status": 0,
            "data": None,
            "error": str(error)
        }

    try:

        data = response.json()

    except ValueError:

        return {
            "ok": False,
            "status": response.status_code,
            "data": None,
            "error": "الخدمة أعادت استجابة غير صالحة."
        }

    return {
        "ok": response.ok,
        "status": response.status_code,
        "data": data,
        "error": None
    }


def result_for_url(result, original_url):
    """
    معالجة نتيجة رابط واحد.
    """

    platform = detect_platform(original_url)

    if not isinstance(result, dict):

        return {
            "page_name": "خطأ",
            "post_text": "",
            "post_url": original_url,
            "platform": platform,
            "error": "نتيجة غير مفهومة من خدمة الاستخراج."
        }

    if result.get("success") is False:

        return parse_error_result(
            original_url,
            result.get("platform") or platform,
            result.get("error")
        )

    return parse_result(
        result,
        original_url
    )


def extract_batch(urls):
    """
    الطريقة الأساسية:
    إرسال جميع الروابط دفعة واحدة.
    """

    response = request_refetcher({
        "urls": urls
    })

    return response


def extract_single(url):
    """
    محاولة ثانية للرابط بشكل منفرد.
    """

    return request_refetcher({
        "url": url
    })


def scrape_urls(urls):
    """
    استخراج آمن:

    1. نحاول Batch.
    2. إذا نجح، نقرأ كل نتيجة.
    3. إذا رفضت الخدمة الطلب بالكامل،
       نجرب كل رابط منفردًا.
    """

    final_results = []

    batch = extract_batch(urls)

    # -----------------------------------
    # الحالة الطبيعية: Refetcher أعاد 200
    # -----------------------------------

    if batch["ok"]:

        data = batch["data"] or {}

        results = data.get("results") or []

        results_by_url = {}

        for result in results:

            if not isinstance(result, dict):
                continue

            result_url = result.get("url")

            if result_url:
                results_by_url[
                    result_url.rstrip("/")
                ] = result

        for original_url in urls:

            result = results_by_url.get(
                original_url.rstrip("/")
            )

            if result is not None:

                final_results.append(
                    result_for_url(
                        result,
                        original_url
                    )
                )

            else:

                # النتيجة غير موجودة في الرد
                # نجرب الرابط منفردًا
                single = extract_single(
                    original_url
                )

                if single["ok"]:

                    single_data = (
                        single["data"] or {}
                    )

                    single_results = (
                        single_data.get("results")
                        or []
                    )

                    if single_results:

                        final_results.append(
                            result_for_url(
                                single_results[0],
                                original_url
                            )
                        )

                    else:

                        final_results.append({
                            "page_name": "لا توجد نتيجة",
                            "post_text": "",
                            "post_url": original_url,
                            "platform": detect_platform(
                                original_url
                            ),
                            "error":
                                "لم ترجع الخدمة نتيجة لهذا الرابط."
                        })

                else:

                    error_data = (
                        (single["data"] or {})
                        if single["data"]
                        else {}
                    )

                    final_results.append(
                        parse_error_result(
                            original_url,
                            detect_platform(
                                original_url
                            ),
                            error_data.get(
                                "error",
                                single["error"]
                            )
                        )
                    )

        return final_results


    # -----------------------------------
    # إذا رفض Refetcher الدفعة كلها
    # -----------------------------------

    for url in urls:

        single = extract_single(url)

        if single["ok"]:

            data = single["data"] or {}

            results = data.get("results") or []

            if results:

                final_results.append(
                    result_for_url(
                        results[0],
                        url
                    )
                )

            else:

                final_results.append({
                    "page_name": "لا توجد نتيجة",
                    "post_text": "",
                    "post_url": url,
                    "platform": detect_platform(url),
                    "error":
                        "لم ترجع الخدمة نتيجة لهذا الرابط."
                })

        else:

            data = single["data"] or {}

            final_results.append(
                parse_error_result(
                    url,
                    detect_platform(url),
                    data.get(
                        "error",
                        single["error"]
                    )
                )
            )

    return final_results


@app.route("/")
def home():

    return render_template(
        "index.html"
    )


@app.route(
    "/extract",
    methods=["POST"]
)
def extract():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        urls = data.get(
            "urls",
            []
        )

        if not isinstance(urls, list):

            return jsonify({
                "success": False,
                "error":
                    "صيغة الروابط غير صحيحة."
            }), 400

        clean_urls = []

        for url in urls:

            if not isinstance(
                url,
                str
            ):
                continue

            url = url.strip()

            if url:
                clean_urls.append(url)

        if not clean_urls:

            return jsonify({
                "success": False,
                "error":
                    "أدخل رابطًا واحدًا على الأقل."
            }), 400

        if len(clean_urls) > 50:

            return jsonify({
                "success": False,
                "error":
                    "الحد الأقصى 50 رابطًا."
            }), 400

        if not REFETCHER_API_KEY:

            return jsonify({
                "success": False,
                "error":
                    "REFETCHER_API_KEY غير موجود."
            }), 500

        results = scrape_urls(
            clean_urls
        )

        successful = sum(
            1
            for item in results
            if not item.get("error")
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

        return jsonify({
            "success": False,
            "error":
                "حدث خطأ داخلي: "
                + str(error)
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
