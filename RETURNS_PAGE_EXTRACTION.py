import os
import re
import json
import pickle
import logging
import requests
import time
from collections import OrderedDict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    WebDriverException,
)
from webdriver_manager.chrome import ChromeDriverManager

# ========== CONFIGURATION ==========
WORKPLACE_URL = "https://sbinteriorscouk434.workplace.com"
MEDIA_URL     = f"{WORKPLACE_URL}/groups/4632360133479201/media"

OUTPUT_DIR    = r"C:\RETURNS ARCHIVE"
MEDIA_ROOT    = os.path.join(OUTPUT_DIR, "media")
COOKIES_FILE  = os.path.join(OUTPUT_DIR, "cookies.pkl")
OUTPUT_JSON   = os.path.join(OUTPUT_DIR, "returns_posts.json")

EMAIL       = "jake@sbinteriors.co.uk"
PASSWORD    = "Megmilo2021!"
MAX_SCROLLS = 350
# ===================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def init_driver():
    opts = webdriver.ChromeOptions()
    opts.add_argument("--incognito")
    opts.add_argument("--start-maximized")
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts
    )


def ensure_output_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(MEDIA_ROOT, exist_ok=True)
    logging.info(f"Ensured output dirs at {OUTPUT_DIR} and {MEDIA_ROOT}")


def load_existing_posts():
    """Load existing JSON into an OrderedDict(post_url -> post_dict)."""
    if not os.path.exists(OUTPUT_JSON):
        return OrderedDict()
    try:
        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        od = OrderedDict((p["post_url"], p) for p in data)
        logging.info(f"Loaded {len(od)} existing posts from JSON")
        return od
    except Exception as e:
        logging.warning(f"Could not parse existing JSON ({e}), starting fresh")
        return OrderedDict()


def save_posts_map(posts_map: OrderedDict):
    """Persist our OrderedDict back to JSON, preserving insertion order."""
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(list(posts_map.values()), f, indent=2)
    logging.info(f"Wrote {len(posts_map)} total posts to JSON")


def save_cookies(driver):
    with open(COOKIES_FILE, "wb") as f:
        pickle.dump(driver.get_cookies(), f)
    logging.info("Saved cookies")


def load_cookies_and_verify(driver):
    if not os.path.exists(COOKIES_FILE):
        logging.info("No cookies, will login manually")
        return False
    driver.get(WORKPLACE_URL)
    with open(COOKIES_FILE, "rb") as f:
        for c in pickle.load(f):
            driver.add_cookie(c)
    driver.refresh()
    driver.get(MEDIA_URL)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "img.x1rg5ohu"))
        )
        logging.info("Loaded via cookies")
        return True
    except TimeoutException:
        logging.info("Cookie login failed")
        return False


def login_workplace(driver):
    driver.get(f"{WORKPLACE_URL}/work/landing/input/")
    # accept cookie banner if present
    try:
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Accept')]"))
        )
        btn.click()
    except:
        pass

    email = WebDriverWait(driver,10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type=email],#email"))
    )
    email.clear(); email.send_keys(EMAIL)
    try:
        driver.find_element(By.XPATH, "//button[.='Next' or .='Continue']").click()
    except:
        email.send_keys("\n")

    pw = None
    for by,sel in [(By.CSS_SELECTOR,"input[type=password]"),(By.ID,"pass")]:
        try:
            e = WebDriverWait(driver,5).until(
                EC.presence_of_element_located((by,sel))
            )
            if e.is_displayed():
                pw = e
                break
        except:
            pass
    if not pw:
        logging.error("Password field not found")
        return False
    pw.clear(); pw.send_keys(PASSWORD)
    try:
        driver.find_element(By.XPATH, "//button[.='Log In' or .='Continue']").click()
    except:
        pw.send_keys("\n")

    save_cookies(driver)
    return True


def scroll_media_page(driver):
    driver.get(MEDIA_URL)
    selector = "img.x1rg5ohu.x5yr21d.xl1xv1r"
    prev, stagnant = 0, 0
    for i in range(1, MAX_SCROLLS+1):
        thumbs = driver.find_elements(By.CSS_SELECTOR, selector)
        cnt = len(thumbs)
        logging.info(f"Scroll {i}/{MAX_SCROLLS} — {cnt} thumbnails")
        if cnt == prev:
            stagnant += 1
        else:
            stagnant = 0
        if stagnant >= 3:
            logging.info("No new thumbnails; stopping")
            break
        prev = cnt
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)


def get_post_id(url):
    m = re.search(r"fbid=(\d+)", url)
    return m.group(1) if m else "unknown"


def ensure_post_media_dir(pid):
    path = os.path.join(MEDIA_ROOT, pid)
    os.makedirs(path, exist_ok=True)
    return path


def download_image_to(path, url, retries=3):
    for attempt in range(retries):
        try:
            if not os.path.exists(path):
                r = requests.get(url, stream=True, timeout=10)
                r.raise_for_status()
                with open(path, "wb") as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
            return
        except Exception as e:
            logging.warning(f"Download {url} failed (try {attempt+1}): {e}")
            time.sleep(1)
    logging.error(f"Giving up on {url}")


def expand_all_replies(driver, comment_xpath):
    while True:
        toggles = driver.find_elements(
            By.XPATH,
            "//span[contains(text(),' replied')] | //span[contains(text(),'replies')]"
        )
        if not toggles:
            return
        clicked_any = False
        for tog in toggles:
            before = len(driver.find_elements(By.XPATH, comment_xpath))
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", tog)
                tog.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", tog)
            except:
                continue
            try:
                WebDriverWait(driver, 2).until(
                    lambda d: len(d.find_elements(By.XPATH, comment_xpath)) > before
                )
                clicked_any = True
            except TimeoutException:
                pass
            time.sleep(0.2)
        if not clicked_any:
            return


def scrape_from_media_images(driver):
    posts_map = load_existing_posts()
    comment_xpath = (
        "//div[starts-with(@aria-label,'Comment by') or starts-with(@aria-label,'Reply by')]"
    )

    thumbs = driver.find_elements(By.CSS_SELECTOR, "img.x1rg5ohu.x5yr21d.xl1xv1r")
    total = len(thumbs)
    logging.info(f"Found {total} thumbnails, {len(posts_map)} already in JSON")

    for idx, img in enumerate(thumbs, start=1):
        post_url = img.find_element(By.XPATH, "./ancestor::a[1]").get_attribute("href")
        exists   = post_url in posts_map

        if not exists:
            logging.info(f"[{idx}/{total}] Scraping NEW {post_url}")
        else:
            logging.debug(f"[{idx}/{total}] Re-checking {post_url}")

        for attempt in range(1,4):
            try:
                # —— open post —— #
                driver.execute_script("window.open(arguments[0], '_blank')", post_url)
                driver.switch_to.window(driver.window_handles[-1])
                WebDriverWait(driver,10).until(lambda d: d.current_url != MEDIA_URL)

                # —— author & date & text logic unchanged —— #
                author = driver.find_element(
                    By.XPATH, "/html/body/div[1]//span/div/h2//a"
                ).text
                date_elem = driver.find_element(
                    By.XPATH, "/html/body/div[1]//div/div[2]/span/div/span[1]/span/span/a"
                )
                date = date_elem.get_attribute("aria-label") or date_elem.text
                try:
                    driver.find_element(By.XPATH, "//div[text()='See more']").click()
                    time.sleep(0.3)
                except NoSuchElementException:
                    pass
                try:
                    cont = driver.find_element(By.XPATH,
                        "/html/body/div[1]/div/div[1]/div/div/div[2]/div[3]/div/div/"
                        "div[1]/div/div[2]/div[2]/div/div/div[2]/div[1]/div/div[2]/"
                        "div/div/div/div[1]/div[1]/div[1]/div[2]/span"
                    )
                    raw = cont.get_attribute("textContent") or ""
                    text = "\n".join(l.strip() for l in raw.splitlines() if l.strip())
                except NoSuchElementException:
                    text = ""

                # —— download post images —— #
                pid = get_post_id(post_url)
                post_dir = ensure_post_media_dir(pid)
                local_images = []
                for i, el in enumerate(driver.find_elements(
                    By.CSS_SELECTOR, "img[data-visualcompletion='media-vc-image']"
                ), start=1):
                    url = el.get_attribute("src")
                    ext = os.path.splitext(url.split("?",1)[0])[1] or ".jpg"
                    fn = f"{pid}_{i}{ext}"
                    pth = os.path.join(post_dir, fn)
                    download_image_to(pth, url)
                    local_images.append(pth)

                # —— expand replies —— #
                expand_all_replies(driver, comment_xpath)
                prev = len(driver.find_elements(By.XPATH, comment_xpath))
                stable = 0
                while stable < 3:
                    time.sleep(0.5)
                    curr = len(driver.find_elements(By.XPATH, comment_xpath))
                    if curr == prev:
                        stable += 1
                    else:
                        prev, stable = curr, 0

                # —— scrape comments, with new author/text logic —— #
                cmts = []
                comment_dir = os.path.join(post_dir, "comments")
                os.makedirs(comment_dir, exist_ok=True)

                for cdiv in driver.find_elements(By.XPATH, comment_xpath):
                    # collect all non-empty lines of comment
                    lines = [
                        span.text.strip()
                        for span in cdiv.find_elements(By.CSS_SELECTOR, "span[dir='auto']")
                        if span.text.strip()
                    ]
                    # first line is author, rest is text
                    c_author = lines[0] if lines else ""
                    c_text = "\n".join(lines[1:]) if len(lines) > 1 else ""

                    # grab date
                    try:
                        c_date = cdiv.find_element(
                            By.CSS_SELECTOR, "a[href*='comment_id']"
                        ).text
                    except:
                        c_date = ""

                    # download any images in comment
                    imgs = []
                    for i, im in enumerate(cdiv.find_elements(By.TAG_NAME, "img"), start=1):
                        src = im.get_attribute("src") or ""
                        if "data:image" in src or "profile" in src:
                            continue
                        ext = os.path.splitext(src.split("?",1)[0])[1] or ".jpg"
                        fn = f"{pid}_c{i}{ext}"
                        pth = os.path.join(comment_dir, fn)
                        download_image_to(pth, src)
                        imgs.append(pth)

                    cmts.append({
                        "author": c_author,
                        "date":   c_date,
                        "text":   c_text,
                        "images": imgs
                    })

                new_entry = {
                    "author":   author,
                    "date":     date,
                    "text":     text,
                    "images":   local_images,
                    "post_url": post_url,
                    "comments": cmts
                }

                # —— insert or update in posts_map —— #
                if not exists:
                    updated = OrderedDict()
                    updated[post_url] = new_entry
                    updated.update(posts_map)
                    posts_map.clear()
                    posts_map.update(updated)
                    logging.info(f"Prepended new post: {post_url}")
                    save_posts_map(posts_map)
                else:
                    if new_entry != posts_map[post_url]:
                        logging.info(f"Updating changed post: {post_url}")
                        posts_map[post_url] = new_entry
                        save_posts_map(posts_map)
                    else:
                        logging.debug(f"No change for {post_url}")

                # clean up and close
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                break

            except WebDriverException as e:
                logging.error(f"[{idx}/{total}] Error on {post_url} (try {attempt}): {e}")
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                time.sleep(2)
                if attempt == 3:
                    logging.error(f"Giving up on {post_url} after 3 attempts")

    logging.info(f"Finished scraping. Total posts now: {len(posts_map)}")
    return posts_map


def main():
    ensure_output_dirs()
    driver = init_driver()

    if not load_cookies_and_verify(driver):
        if not login_workplace(driver):
            driver.quit()
            return

    scroll_media_page(driver)
    scrape_from_media_images(driver)
    driver.quit()
    logging.info("All done!")


if __name__ == "__main__":
    main()
