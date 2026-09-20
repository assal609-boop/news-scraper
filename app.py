import os
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
REFETCHER_API_KEY = os.environ.get("REFETCHER_API_KEY", "").strip()
REFETCHER_URL = "https://api.refetcher.com/"

def clean_url(url):
if not url:
return ""

```
return url.strip().strip("\"'<> \t\r\n")
```

def detect_platform(url):
try:
host = urlparse(url).netloc.lower()
host = host.replace("[www](http://www).", "").replace("m.", "")

```
    if host == "facebook.com" or host.endswith(".facebook.com"):
        return "Facebook"

    if host == "instagram.com" or host.endswith(".instagram.com"):
        return "Instagram"

    if (
        host == "x.com"
        or host.endswith(".x.com")
        or host == "twitter.com"
        or host.endswith(".twitter.com")
    ):
        return "X / Twitter"

except Exception:
    pass

return None
```

def normalize_platform(value, fallback=None):
if not value:
return fallback

```
value = str(value).strip().lower()

if value in ("facebook", "fb"):
    return "Facebook"

if value in ("instagram", "ig"):
    return "Instagram"

if value in ("x", "twitter", "x/twitter"):
    return "X / Twitter"

return fallback or str(value)
```

def first_text(*values):
for value in values:
if isinstance(value, str):
value = value.strip()

```
        if value:
            return value

return ""
```

def extract_post_data(item, original_url):
post = item.get("post") or {}
author = item.get("author") or {}
profile = item.get("profile") or {}

```
page_name = first_text(
    author.get("name"),
    author.get("handle"),
    profile.get("name"),
    profile.get("handle"),
    item.get("authorName"),
    item.get("pageName"),
    item.get("username"),
    item.get("name"),
)

post_text = first_text(
    post.get("caption"),
    post.get("description"),
    item.get("caption"),
    item.get("description"),
    item.get("text"),
)

post_url = first_text(
    post.get("normalizedUrl"),
    post.get("url"),
    item.get("normalizedUrl"),
    item.get("url"),
    original_url,
)

return {
    "page_name": page_name or "الحساب غير معروف",
    "post_text": post_text,
    "post_url": post_url or original_url,
    "has_text": bool(post_text),
}
```

def get_item_error(item):
error = item.get("error")

```
if isinstance(error, dict):
    message = first_text(
        error.get("message"),
        error.get("detail"),
        error.get("description"),
    )

    category = first_text(
        error.get("category"),
        error.get("code"),
    )

    if category and message:
        return f"{category}: {message}"

    if message:
        return message

    if category:
        return category

if isinstance(error, str) and error.strip():
    return error.strip()

return "تعذر استخراج بيانات عامة من هذا الرابط."
```

@app.route("/")
def home():
return render_template("index.html")

@app.route("/extract", methods=["POST"])
def extract():
if not REFETCHER_API_KEY:
return jsonify({
"success": False,
"error": "لم يتم إعداد مفتاح Refetcher على الخادم."
}), 500

```
data = request.get_json(silent=True) or {}

urls = data.get("urls", [])

if isinstance(urls, str):
    urls = urls.splitlines()

if not isinstance(urls, list):
    return jsonify({
        "success": False,
        "error": "صيغة الروابط غير صحيحة."
    }), 400

cleaned_urls = []

for url in urls:
    url = clean_url(url)

    if url and url not in cleaned_urls:
        cleaned_urls.append(url)

if not cleaned_urls:
    return jsonify({
        "success": False,
        "error": "أدخل رابطًا واحدًا على الأقل."
    }), 400

if len(cleaned_urls) > 50:
    return jsonify({
        "success": False,
        "error": "الحد الأقصى هو 50 رابطًا في الطلب الواحد."
    }), 400

valid_urls = []
invalid_urls = []

for url in cleaned_urls:
    platform = detect_platform(url)

    if platform:
        valid_urls.append((url, platform))
    else:
        invalid_urls.append(url)

results = []

for url in invalid_urls:
    results.append({
        "success": False,
        "platform": "غير معروف",
        "page_name": "—",
        "post_text": "",
        "post_url": url,
        "error": "الرابط ليس من Facebook أو Instagram أو X / Twitter."
    })

if not valid_urls:
    return jsonify({
        "success": True,
        "results": results
    })

request_urls = [url for url, platform in valid_urls]

headers = {
    "X-API-Key": REFETCHER_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

try:
    response = requests.post(
        REFETCHER_URL,
        headers=headers,
        json={"urls": request_urls},
        timeout=60,
    )

except requests.RequestException as exc:
    return jsonify({
        "success": False,
        "error": f"تعذر الاتصال بخدمة الاستخراج: {str(exc)}"
    }), 502

try:
    api_data = response.json()

except ValueError:
    return jsonify({
        "success": False,
        "error": "خدمة الاستخراج أعادت استجابة غير مفهومة."
    }), 502

if response.status_code >= 400:
    error_message = first_text(
        api_data.get("message"),
        api_data.get("error"),
        api_data.get("detail"),
    )

    return jsonify({
        "success": False,
        "error": error_message or
                 f"حدث خطأ من خدمة الاستخراج ({response.status_code})."
    }), 502

api_results = api_data.get("results", [])

if not isinstance(api_results, list):
    api_results = []

result_by_url = {}

for item in api_results:
    if not isinstance(item, dict):
        continue

    original = first_text(
        item.get("url"),
        item.get("inputUrl"),
        item.get("originalUrl"),
    )

    if original:
        result_by_url[clean_url(original)] = item

for original_url, detected_platform in valid_urls:

    item = result_by_url.get(original_url)

    if item is None:
        for candidate in api_results:

            if not isinstance(candidate, dict):
                continue

            candidate_post = candidate.get("post") or {}

            candidate_url = first_text(
                candidate.get("url"),
                candidate.get("inputUrl"),
                candidate.get("originalUrl"),
                candidate.get("normalizedUrl"),
                candidate_post.get("normalizedUrl"),
            )

            if candidate_url and (
                clean_url(candidate_url) == original_url
                or candidate_url.rstrip("/") ==
                   original_url.rstrip("/")
            ):
                item = candidate
                break

    if item is None:
        results.append({
            "success": False,
            "platform": detected_platform,
            "page_name": "الحساب غير معروف",
            "post_text": "",
            "post_url": original_url,
            "error": "لم يتم العثور على بيانات عامة لهذا الرابط."
        })
        continue

    platform = normalize_platform(
        item.get("platform"),
        detected_platform
    )

    if item.get("error"):
        results.append({
            "success": False,
            "platform": platform,
            "page_name": "الحساب غير معروف",
            "post_text": "",
            "post_url": original_url,
            "error": get_item_error(item)
        })
        continue

    extracted = extract_post_data(
        item,
        original_url
    )

    results.append({
        "success": True,
        "platform": platform,
        "page_name": extracted["page_name"],
        "post_text": extracted["post_text"],
        "post_url": extracted["post_url"],
        "has_text": extracted["has_text"],
        "error": (
            None
            if extracted["has_text"]
            else "تم الوصول إلى الرابط، لكن نص المنشور غير متاح للعامة."
        ),
    })

return jsonify({
    "success": True,
    "results": results
})
```

if **name** == "**main**":
port = int(os.environ.get("PORT", 5000))

```
app.run(
    host="0.0.0.0",
    port=port,
    debug=False
)
```
