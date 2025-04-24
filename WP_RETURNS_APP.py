import streamlit as st
import streamlit.components.v1 as components
import json, os, re, requests
from datetime import datetime, date
from dateutil import parser

# ——— PAGE CONFIG ———
st.set_page_config(
    page_title="WP RETURNS PAGE ARCHIVE",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ——— GLOBAL STYLES ———
st.markdown("""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
      html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }

      .post-card {
        background: #fff;
        padding: 1rem;
        margin-bottom: 1.5rem;
        border-radius: 8px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
      }
      .post-card img {
        max-width: 70% !important;
        height: auto !important;
        border-radius: 4px;
        margin-bottom: .75rem;
      }
      .comment-image img {
        max-width: 120px !important;
        height: auto !important;
        border-radius: 4px;
        margin-right: .5rem;
      }
      h1 { font-size: 3rem !important; }
      h3 { font-size: 1.75rem !important; }
      p  { font-size: 1.25rem !important; line-height: 1.6 !important; }
      .streamlit-expanderHeader { font-size: 1.4rem !important; font-weight: 500 !important; }
      .stTextInput input { font-size: 1.1rem !important; }
      .streamlit-expanderContent > div { margin-bottom: 1rem; }
      .block-container { padding-top: 1rem; }
    </style>
""", unsafe_allow_html=True)

# ——— CONFIG ———
PAGE_SIZE        = 50
LOCAL_JSON       = os.path.join(os.path.dirname(__file__), "returns_posts.json")
GITHUB_RAW_JSON  = "https://raw.githubusercontent.com/jakepeltiersmith2/WP-RETURNS-ARCHIVE/main/returns_posts.json"
GITHUB_RAW_MEDIA = "https://raw.githubusercontent.com/jakepeltiersmith2/WP-RETURNS-ARCHIVE/main/media"

# ——— UTILITIES ———
@st.cache_data
def load_posts():
    if os.path.exists(LOCAL_JSON):
        return json.load(open(LOCAL_JSON, "r", encoding="utf-8"))
    r = requests.get(GITHUB_RAW_JSON, timeout=10)
    r.raise_for_status()
    return r.json()

def parse_date(s):
    """Attempt to parse a date string like '31 January 2022'. Falls back to today."""
    try:
        return parser.parse(s, dayfirst=True).date()
    except:
        return None

def show_image(path):
    if path.startswith("http"):
        st.image(path, use_container_width=True)
        return
    if os.path.exists(path):
        st.image(path, use_container_width=True)
        return
    parts = path.replace("\\","/").split("/media/")
    if len(parts)==2:
        rel = parts[1]
        url = f"{GITHUB_RAW_MEDIA}/{rel}"
        st.image(url, use_container_width=True)
    else:
        st.write(f"🔗 {path}")

# ——— LOAD DATA ———
posts = load_posts()

# ——— SIDEBAR CONTROLS ———
st.sidebar.title("🔍 Filters")

q = st.sidebar.text_input("Keyword")
# date-range picker
all_dates = [parse_date(p["date"]) for p in posts]
min_d = min([d for d in all_dates if d])+ (date.today() - date.today())  if any(all_dates) else date.today()
max_d = max([d for d in all_dates if d])+ (date.today() - date.today())  if any(all_dates) else date.today()
start, end = st.sidebar.date_input("Date range", [min_d, max_d])

# sort order
order = st.sidebar.radio("Sort by", ["Newest first", "Oldest first"])

# how many posts?
if "count" not in st.session_state:
    st.session_state.count = PAGE_SIZE

# two buttons side by side
b1, b2 = st.sidebar.columns(2)
if b1.button("Load more"):
    st.session_state.count += PAGE_SIZE
if b2.button("Load all"):
    st.session_state.count = len(posts)

# ——— FILTER & SORT POSTS ———
def matches(p):
    t = q.lower()
    if t and t in p.get("text","").lower(): return True
    return any(t in c.get("text","").lower() for c in p.get("comments",[]))

filtered = [p for p in posts if (not q or matches(p))]
# date filter
def in_range(p):
    d = parse_date(p["date"])
    return d and start <= d <= end
filtered = [p for p in filtered if in_range(p)]

# sort
filtered.sort(
    key=lambda p: parse_date(p["date"]) or date.min,
    reverse = (order=="Newest first")
)

# group duplicates (author, date)
grouped = {}
order_keys = []
for p in filtered:
    k = (p["author"], p["date"])
    if k not in grouped:
        grouped[k] = {
            "author": k[0],
            "date":   k[1],
            "text":   p.get("text",""),
            "images": [],
            "comments": p.get("comments",[]),
        }
        order_keys.append(k)
    grouped[k]["images"].extend(p.get("images",[]))
grouped_posts = [ grouped[k] for k in order_keys ]

# ——— RENDER ———
st.title("WP RETURNS GROUP – ARCHIVE")
st.markdown(f"> Showing **{min(len(grouped_posts), st.session_state.count)}** of **{len(grouped_posts)}** posts")

for post in grouped_posts[: st.session_state.count]:
    st.markdown('<div class="post-card">', unsafe_allow_html=True)

    # header
    c1, c2 = st.columns([3,1])
    with c1:
        st.markdown(f"### {post['author']}  ·  *{post['date']}*")
    with c2:
        st.write("")

    # body
    if post["text"]:
        st.write(post["text"])

    # images
    if post["images"]:
        cols = st.columns(len(post["images"]))
        for col,img in zip(cols, post["images"]):
            with col:
                show_image(img)

    # comments
    if post["comments"]:
        with st.expander(f"💬 {len(post['comments'])} comments"):
            for c in post["comments"]:
                st.markdown(f"**{c['author']}**  ·  *{c['date']}*")
                # inline tags + body
                lines = c["text"].split("\n")
                tags = [L for L in lines if re.fullmatch(r"(?:[A-Z][a-z]+(?: [A-Z][a-z]+)*)", L)]
                body = [L for L in lines if L not in tags]
                txt = ("**" + " ".join(tags) + "** " if tags else "") + " ".join(body).strip()
                st.write(txt)
                if c.get("images"):
                    thumbs = st.columns(len(c["images"]))
                    for tc, im in zip(thumbs, c["images"]):
                        with tc:
                            st.markdown('<div class="comment-image">', unsafe_allow_html=True)
                            show_image(im)
                            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ——— INFINITE SCROLL “Load more” ———
components.html("""
  <div id="scroll-anchor" style="height:1px;margin-top:-1px;"></div>
  <script>
    if (!window._infScroll_) {
      window._infScroll_ = true;
      new IntersectionObserver(e => {
        if (e[0].isIntersecting) {
          Array.from(window.parent.document.querySelectorAll("button"))
               .filter(b => b.innerText.trim()==="Load more")
               .forEach(b=>b.click());
        }
      },{threshold:1.0}).observe(
        document.getElementById('scroll-anchor')
      );
    }
  </script>
""", height=1)

st.markdown("---")
