import os
import re
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

REFETCHER_URL = "https://api.refetcher.com/"
REFETCHER_API_KEY = os.environ.get("REFETCHER_API_KEY", "").strip()

SUPPORTED_PLATFORMS = {
    "facebook.com": "Facebook",
    "www.facebook.com": "Facebook",
    "m.facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "www.instagram.com": "Instagram",
    "x.com": "X / Twitter",
    "www.x.com": "X / Twitter",
    "twitter.com": "X / Twitter",
    "www.twitter.com": "X / Twitter",
}


def clean_url(url):
    if not isinstance(url, str):
        return ""

    url = url.strip()

    if not url:
        return ""

    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url

    return url


def detect_platform(url):
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()

        if host in SUPPORTED_PLATFORMS:
            return SUPPORTED_PLATFORMS[host]

        if host.startswith("www."):
            host = host[4:]

        return SUPPORTED_PLATFORMS.get(host)

    except Exception:
        return None


def get_value(data, *keys):
    if not isinstance(data, dict):
        return None

    for key in keys:
        value = data.get(key)

        if value is not None and str(value).strip():
            return value

    return None


def extract_author_name(item):
    author = item.get("author")

    if isinstance(author, dict):
        name = get_value(
            author,
            "name",
            "displayName",
            "fullName",
            "username",
            "handle"
        )

        if name:
            return str(name).strip()

    profile = item.get("profile")

    if isinstance(profile, dict):
        name = get_value(
            profile,
            "name",
            "displayName",
            "fullName",
            "username",
            "handle"
        )

        if name:
            return str(name).strip()

    name = get_value(
        item,
        "authorName",
        "pageName",
        "accountName",
        "username",
        "handle"
    )

    if name:
        return str(name).strip()

    return "الحساب غير معروف"


def extract_post_text(item):
    post = item.get("post")

    if isinstance(post, dict):
        text = get_value(
            post,
            "caption",
            "description",
            "text",
            "content",
            "title"
        )

        if text:
            return str(text).strip()

    text = get_value(
        item,
        "caption",
        "description",
        "text",
        "content",
        "title"
    )

    if text:
        return str(text).strip()

    return ""


def extract_post_url(item, original_url):
    post = item.get("post")

    if isinstance(post, dict):
        url = get_value(
            post,
            "normalizedUrl",
            "url",
            "canonicalUrl",
            "permalink"
        )

        if url:
            return str(url).strip()

    url = get_value(
        item,
        "normalizedUrl",
        "url",
        "canonicalUrl",
        "permalink"
    )

    if url:
        return str(url).strip()

    return original_url


def normalize_results(data, original_urls):
    if isinstance(data, dict):
        if isinstance(data.get("results"), list):
            items = data["results"]
        elif isinstance(data.get("data"), list):
            items = data["data"]
        elif isinstance(data.get("items"), list):
            items = data["items"]
        else:
            items = [data]
    elif isinstance(data, list):
        items = data
    else:
        items = []

    results = []

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue

        original_url = ""

        if index < len(original_urls):
            original_url = original_urls[index]

        platform = detect_platform(original_url)

        if not platform:
            platform = str(
                get_value(item, "platform", "source")
                or "Unknown"
            )

        page_name = extract_author_name(item)
        post_text = extract_post_text(item)
        post_url = extract_post_url(item, original_url)

        error = item.get("error")

        if error:
            error_text = str(error)
        else:
            error_text = ""

        results.append(
            {
                "page_name": page_name,
                "post_text": post_text,
                "post_url": post_url,
                "platform": platform,
                "has_text": bool(post_text),
                "error": error_text
            }
        )

    return results


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/extract", methods=["POST"])
def extract():
    if not REFETCHER_API_KEY:
        return jsonify(
            {
                "success": False,
                "error": "REFETCHER_API_KEY غير موجود في إعدادات Render."
            }
        ), 500

    data = request.get_json(silent=True) or {}

    urls = data.get("urls", [])

    if isinstance(urls, str):
        urls = urls.splitlines()

    if not isinstance(urls, list):
        return jsonify(
            {
                "success": False,
                "error": "صيغة الروابط غير صحيحة."
            }
        ), 400

    cleaned_urls = []

    for url in urls:
        url = clean_url(url)

        if not url:
            continue

        platform = detect_platform(url)

        if platform:
            cleaned_urls.append(url)

    if not cleaned_urls:
        return jsonify(
            {
                "success": False,
                "error": "لم يتم العثور على روابط Facebook أو Instagram أو X صحيحة."
            }
        ), 400

    if len(cleaned_urls) > 50:
        cleaned_urls = cleaned_urls[:50]

    headers = {
        "X-API-Key": REFETCHER_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "urls": cleaned_urls
    }

    try:
        response = requests.post(
            REFETCHER_URL,
            headers=headers,
            json=payload,
            timeout=90
        )

        response.raise_for_status()

        try:
            response_data = response.json()
        except ValueError:
            return jsonify(
                {
                    "success": False,
                    "error": "الخدمة أعادت استجابة غير صالحة."
                }
            ), 502

        results = normalize_results(
            response_data,
            cleaned_urls
        )

        return jsonify(
            {
                "success": True,
                "results": results
            }
        )

    except requests.exceptions.Timeout:
        return jsonify(
            {
                "success": False,
                "error": "انتهت مهلة الاتصال بالخدمة. حاول مرة أخرى."
            }
        ), 504

    except requests.exceptions.HTTPError:
        try:
            error_data = response.json()
            error_message = (
                error_data.get("error")
                or error_data.get("message")
                or "حدث خطأ من خدمة الاستخراج."
            )
        except Exception:
            error_message = (
                "حدث خطأ من خدمة الاستخراج. "
                f"رمز الخطأ: {response.status_code}"
            )

        return jsonify(
            {
                "success": False,
                "error": str(error_message)
            }
        ), 502

    except requests.exceptions.RequestException as exc:
        return jsonify(
            {
                "success": False,
                "error": f"تعذر الاتصال بخدمة الاستخراج: {str(exc)}"
            }
        ), 502

    except Exception as exc:
        return jsonify(
            {
                "success": False,
                "error": f"حدث خطأ غير متوقع: {str(exc)}"
            }
        ), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port
    )
