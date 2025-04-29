import os
import json
import logging
import requests
from collections import OrderedDict

# ——— CONFIG ———
GROUP_ID      = "4632360133479201"
ACCESS_TOKEN  = "DQWRXTkNOc3VoTW5Ka1h0cXV6MFlONW05X2syLVpOVlh0eDV6cE5FRllxMTQ3elNYdncta3NqOFJINVp6Yy1zUWFOa3lhY1NQR2dqOUF3V2IxQkM2ZAjBDZAU9fNXppUFNKSWpBY1FLaWZADbHpVZA2FJcnpxaHRBUHhWYnVsdmczWktoWHB6dTR5M0lhVGlEYTVkZADk2T2R2a3I1YlA3dkZAvcWotWC1CRHR1WlZAIa3d3eWQ4N1plR045TkJNSWN3T01QRkFTUjJfWmJjbHFHN3JXNzJR"
WORKPLACE_URL = "https://sbinteriorscouk434.workplace.com"
OUTPUT_DIR    = r"C:\RETURNS ARCHIVE"
MEDIA_ROOT    = os.path.join(OUTPUT_DIR, "media")
OUTPUT_JSON   = os.path.join(OUTPUT_DIR, "returns_posts_api.json")

# Fields to fetch for each post and comment
POST_FIELDS = [
    "id",
    "from{name}",
    "created_time",
    "message",
    "attachments{media,subattachments}",
    "comments.limit(100){from{name},created_time,message}"
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(MEDIA_ROOT, exist_ok=True)


def get_feed_posts():
    if not ACCESS_TOKEN:
        raise RuntimeError("ACCESS_TOKEN is missing!")

    # Use the Workplace Graph host rather than graph.facebook.com
    base_url = f"https://graph.workplace.com/v14.0/{GROUP_ID}/feed"
    params   = {
        "access_token": ACCESS_TOKEN,
        "fields":       ",".join(POST_FIELDS),
        "limit":        100,
    }

    posts = OrderedDict()
    url   = base_url

    while url:
        logging.info(f"Requesting {url}")
        r = requests.get(url, params=params)
        try:
            r.raise_for_status()
        except requests.HTTPError:
            logging.error(f"HTTP {r.status_code}: {r.text[:200]}")
            raise
        data = r.json()

        for p in data.get("data", []):
            posts[p["id"]] = p

        paging = data.get("paging", {})
        url    = paging.get("next")
        params = None  # after first request, the `next` URL already contains everything

    return list(posts.values())


def download_images(post):
    pid = post["id"]
    post_dir = os.path.join(MEDIA_ROOT, pid)
    os.makedirs(post_dir, exist_ok=True)
    local_images = []
    idx = 1

    for att in post.get("attachments", {}).get("data", []):
        subs = att.get("subattachments", {}).get("data", [att])
        for sub in subs:
            img = sub.get("media", {}).get("image", {}).get("src")
            if not img:
                continue
            ext = os.path.splitext(img.split("?")[0])[1] or ".jpg"
            fname = f"{pid}_{idx}{ext}"
            path = os.path.join(post_dir, fname)
            try:
                resp = requests.get(img, stream=True, timeout=10)
                resp.raise_for_status()
                with open(path, "wb") as f:
                    for chunk in resp.iter_content(1024):
                        f.write(chunk)
                local_images.append(path)
                idx += 1
            except Exception as e:
                logging.warning(f"Failed to download {img}: {e}")

    return local_images


def normalize_post(api_post):
    post_url = f"{WORKPLACE_URL}/groups/{GROUP_ID}/permalink/{api_post['id']}"
    author   = api_post.get("from", {}).get("name", "")
    date     = api_post.get("created_time", "")
    text     = api_post.get("message", "")
    images   = download_images(api_post)
    comments = []

    for c in api_post.get("comments", {}).get("data", []):
        comments.append({
            "author": c.get("from", {}).get("name", ""),
            "date":   c.get("created_time", ""),
            "text":   c.get("message", ""),
            "images": []
        })

    return {
        "post_url": post_url,
        "author":   author,
        "date":     date,
        "text":     text,
        "images":   images,
        "comments": comments
    }


def main():
    ensure_dirs()
    raw_posts = get_feed_posts()
    logging.info(f"Fetched {len(raw_posts)} posts from API")

    normalized = [normalize_post(p) for p in raw_posts]
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2)

    logging.info(f"Wrote {len(normalized)} posts to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
