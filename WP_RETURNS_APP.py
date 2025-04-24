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
      .sidebar-button-row > div { display: inline-block; margin-right: 0.5rem; }
    </style>
""", unsafe_allow_html=True)

# ——— CONFIG ———
PAGE_SIZE       = 50
LOCAL_JSON      = os.path.join(os.path.dirname(__file__), "returns_posts.json")
GITHUB_RAW_JSON = (
    "https://raw.githubusercontent.com/jakepeltiersmith2/"
    "WP-RETURNS-ARCHIVE/main/returns_posts.json"
)
GITHUB_RAW_MEDIA= (
    "https://raw.githubusercontent.com/jakepeltiersmith2/"
    "WP-RETURNS-ARCHIVE/main/media"
)

@st.cache_data
def load_posts():
    # load local if present, else from GitHub
    if os.path.exists(LOCAL_JSON):
        posts = json.load(open(LOCAL_JSON, "r", encoding="utf-8"))
    else:
        r = requests.get(GITHUB_RAW_JSON, timeout=10)
        r.raise_for_status()
        posts = r.json()

    # parse each post date into a date object
    for p in posts:
        try:
            # handles "31 January 2022" or "31 January at 14:32"
            p["_date_dt"] = parser.parse(p["date"], dayfirst=True).date()
        except Exception:
            p["_date_dt"] = None
    return posts

posts = load_posts()

# ——— SIDEBAR FILTERS ———
st.sidebar.title("🔍 Filters")

# keyword search
q = st.sidebar.text_input("Search keyword")

# date range picker
dates = [p["_date_dt"] for p in posts if p["_date_dt"]]
if dates:
    ds, de = min(dates), max(dates)
else:
    ds = de = date.today()

start_date, end_date = st.sidebar.date_input(
    "Date range",
    value=(ds, de),
    min_value=ds,
    max_value=de
)

# sort order
sort_order = st.sidebar.radio(
    "Sort by",
    ("Newest first", "Oldest first")
)

# pagination controls
if "count" not in st.session_state:
    st.session_state.count = PAGE_SIZE

# place buttons side by side
b1, b2 = st.sidebar.beta_columns(2)
with b1:
    load_more = st.button("Load more")
with b2:
    load_all = st.button("Load all")

if load_more:
    st.session_state.count += PAGE_SIZE
if load_all:
    st.session_state.count = len(posts)

# ——— FILTER & SORT ———
def matches(p):
    # date filter
    dt = p.get("_date_dt")
    if dt is None or not (start_date <= dt <= end_date):
        return False
    # keyword filter
    if q:
        text = p.get("text","").lower()
        if q.lower() in text:
            return True
        for c in p.get("comments",[]):
            if q.lower() in c.get("text","").lower():
                return True
        return False
    return True

filtered = [p for p in posts if matches(p)]

# sort by date_dt
filtered.sort(key=lambda p: p["_date_dt"] or date.min,
              reverse=(sort_order=="Newest first"))

# ——— GROUP DUPLICATES ———
grouped, order = {}, []
for p in filtered:
    key = (p["author"], p["date"])
    if key not in grouped:
        grouped[key] = {
            "author": key[0],
            "date":   key[1],
            "text":   p.get("text",""),
            "images": [],
            "comments": p.get("comments",[])
        }
        order.append(key)
    grouped[key]["images"].extend(p.get("images",[]))

grouped_posts = [ grouped[k] for k in order ]

# ——— HEADER ———
st.title("WP RETURNS GROUP – ARCHIVE")
st.markdown(
    f"> Showing **{min(len(grouped_posts), st.session_state.count)}**"
    f" of **{len(grouped_posts)}** posts"
)

# helper to display image (local or GitHub raw)
def show_image(path):
    if path.startswith("http"):
        st.image(path, use_container_width=True)
        return
    if os.path.exists(path):
        st.image(path, use_container_width=True)
        return
    parts = path.replace("\\","/").split("/media/")
    if len(parts)==2:
        url = f"{GITHUB_RAW_MEDIA}/{parts[1]}"
        st.image(url, use_container_width=True)
    else:
        st.write(f"🔗 {path}")

# ——— MAIN DISPLAY ———
for post in grouped_posts[: st.session_state.count]:
    st.markdown('<div class="post-card">', unsafe_allow_html=True)
    c1, c2 = st.columns([3,1])
    with c1:
        st.markdown(f"### {post['author']}  ·  *{post['date']}*")
    with c2:
        st.write("")

    if post["text"]:
        st.write(post["text"])
    if post["images"]:
        cols = st.columns(len(post["images"]))
        for col,img in zip(cols, post["images"]):
            with col:
                show_image(img)

    if post["comments"]:
        with st.expander(f"💬 {len(post['comments'])} comments"):
            for c in post["comments"]:
                st.markdown(f"**{c['author']}**  ·  *{c['date']}*")
                lines = c["text"].split("\n"); tags, body = [], []
                for L in lines:
                    if re.fullmatch(r"(?:[A-Z][a-z]+(?: [A-Z][a-z]+)*)", L):
                        tags.append(L)
                    else:
                        body.append(L)
                txt = ("**" + " ".join(tags) + "** " if tags else "") + " ".join(body).strip()
                st.write(txt)
                if c.get("images"):
                    thumbs = st.columns(len(c["images"]))
                    for tc,im in zip(thumbs, c["images"]):
                        with tc:
                            st.markdown('<div class="comment-image">', unsafe_allow_html=True)
                            show_image(im)
                            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ——— INFINITE SCROLL ANCHOR ———
components.html("""
  <div id="scroll-anchor" style="height:1px;margin-top:-1px;"></div>
  <script>
    if (!window._infScroll_) {
      window._infScroll_ = true;
      new IntersectionObserver(e=>{
        if(e[0].isIntersecting){
          document.querySelectorAll("button").forEach(b=>{
            if(b.innerText.trim()==="Load more") b.click();
          });
        }
      },{threshold:1.0}).observe(
        document.getElementById('scroll-anchor')
      );
    }
  </script>
""", height=1)

st.markdown("---")
