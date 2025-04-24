import streamlit as st
import streamlit.components.v1 as components
import json, os, re, requests
from datetime import date
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
      .post-card { background: #fff; padding:1rem; margin-bottom:1.5rem;
                   border-radius:8px; box-shadow:0 2px 6px rgba(0,0,0,0.1); }
      .post-card img { max-width:70% !important; height:auto !important;
                       border-radius:4px; margin-bottom:.75rem; }
      .comment-image img { max-width:120px !important; height:auto !important;
                           border-radius:4px; margin-right:.5rem; }
      h1 { font-size:3rem !important; }
      h3 { font-size:1.75rem !important; }
      p  { font-size:1.25rem !important; line-height:1.6 !important; }
      .streamlit-expanderHeader { font-size:1.4rem !important; font-weight:500 !important; }
      .stTextInput input { font-size:1.1rem !important; }
      .streamlit-expanderContent > div { margin-bottom:1rem; }
      .block-container { padding-top:1rem; }
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
    try:
        return parser.parse(s, dayfirst=True).date()
    except:
        return None

def show_image(path):
    if path.startswith("http"):
        st.image(path, use_container_width=True); return
    if os.path.exists(path):
        st.image(path, use_container_width=True); return
    parts = path.replace("\\","/").split("/media/")
    if len(parts)==2:
        url = f"{GITHUB_RAW_MEDIA}/{parts[1]}"
        st.image(url, use_container_width=True)
    else:
        st.write(f"🔗 {path}")

# ——— LOAD DATA ———
posts = load_posts()

# ——— SIDEBAR FILTERS ———
st.sidebar.title("🔍 Filters")
q = st.sidebar.text_input("Keyword")

# build list of parseable dates
all_dates = [d for d in (parse_date(p["date"]) for p in posts) if d]
if all_dates:
    mn = min(all_dates)
else:
    mn = date.today()
default_end = date.today()

start, end = st.sidebar.date_input(
    "Date range",
    value=[mn, default_end],
    min_value=mn,
    max_value=default_end,
)

# “Load more” & “Load all”
if "count" not in st.session_state:
    st.session_state.count = PAGE_SIZE
c1, c2 = st.sidebar.columns(2)
if c1.button("Load more"):
    st.session_state.count += PAGE_SIZE
if c2.button("Load all"):
    st.session_state.count = len(posts)

# ——— FILTER & RANGE ———
def matches(p):
    t = q.lower()
    if t and t in p.get("text","").lower(): return True
    return any(t in c.get("text","").lower() for c in p.get("comments",[]))

filtered = [p for p in posts if (not q or matches(p))]
def in_range(p):
    d = parse_date(p["date"])
    return d and (start <= d <= end)
filtered = [p for p in filtered if in_range(p)]

# ——— GROUP DUPLICATES ———
grouped = {}
order_keys = []
for p in filtered:
    key = (p["author"], p["date"])
    if key not in grouped:
        grouped[key] = {
            "author":   key[0],
            "date":     key[1],
            "text":     p.get("text",""),
            "images":   [],
            "comments": p.get("comments",[]),
        }
        order_keys.append(key)
    grouped[key]["images"].extend(p.get("images",[]))
grouped_posts = [ grouped[k] for k in order_keys ]

# ——— RENDER ———
st.title("WP RETURNS GROUP – ARCHIVE")
st.markdown(f"> Showing **{min(len(grouped_posts), st.session_state.count)}** of **{len(grouped_posts)}** posts")

for post in grouped_posts[: st.session_state.count]:
    st.markdown('<div class="post-card">', unsafe_allow_html=True)
    col1, col2 = st.columns([3,1])
    with col1:
        st.markdown(f"### {post['author']}  ·  *{post['date']}*")
    with col2:
        st.write("")

    if post["text"]:
        st.write(post["text"])
    if post["images"]:
        cols = st.columns(len(post["images"]))
        for c, img in zip(cols, post["images"]):
            with c:
                show_image(img)

    if post["comments"]:
        with st.expander(f"💬 {len(post['comments'])} comments"):
            for c in post["comments"]:
                st.markdown(f"**{c['author']}**  ·  *{c['date']}*")
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

# ——— INFINITE SCROLL ———
components.html("""
  <div id="scroll-anchor" style="height:1px;margin-top:-1px;"></div>
  <script>
    if (!window._infScroll_) {
      window._infScroll_ = true;
      new IntersectionObserver(e => {
        if (e[0].isIntersecting) {
          Array.from(window.parent.document.querySelectorAll("button"))
               .filter(b=>b.innerText.trim()==="Load more")
               .forEach(b=>b.click());
        }
      },{threshold:1.0}).observe(
        document.getElementById('scroll-anchor')
      );
    }
  </script>
""", height=1)

st.markdown("---")
