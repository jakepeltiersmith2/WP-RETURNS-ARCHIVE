import streamlit as st
import streamlit.components.v1 as components
import json, os, re
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
      .post-card { background: #fff; padding:1rem; margin-bottom:1.0rem;
                   border-radius:8px; box-shadow:0 2px 6px rgba(0,0,0,0.1); }
      .post-card img { max-width:70% !important; height:auto !important;
                       border-radius:4px; margin-bottom:.5rem; }
      .comment-image img { max-width:300px !important; height:auto !important;
                           border-radius:4px; margin-right:.5rem; }
      h1 { font-size:2.5rem !important; }
      h3 { font-size:1.5rem !important; }
      p  { font-size:1.1rem !important; line-height:1.5 !important; }
      .streamlit-expanderHeader { font-size:1.2rem !important; font-weight:500 !important; }
      .stTextInput input { font-size:1rem !important; }
      .streamlit-expanderContent > div { margin-bottom:0.75rem; }
      .block-container { padding-top:1rem; }
    </style>
""", unsafe_allow_html=True)

# ——— CONFIG ———
PAGE_SIZE       = 250
LOCAL_JSON      = os.path.join(os.path.dirname(__file__), "returns_posts.json")
GITHUB_RAW_MEDIA = "https://raw.githubusercontent.com/jakepeltiersmith2/WP-RETURNS-ARCHIVE/main/media"

# ——— UTILITIES ———
def load_posts():
    # Always load fresh from local JSON
    with open(LOCAL_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_date(s: str):
    try:
        return parser.parse(s).date()
    except:
        return None

def format_datetime(s: str) -> str:
    try:
        dt = parser.parse(s)
        return dt.strftime("%d %B %Y at %H:%M")
    except:
        return s

def show_image(path, thumb=False):
    width = 300 if thumb else None
    use_container = not thumb
    if path.startswith("http"):
        st.image(path, width=width, use_container_width=use_container)
        return
    if os.path.exists(path):
        st.image(path, width=width, use_container_width=use_container)
        return
    parts = path.replace("\\","/").split("/media/")
    if len(parts) == 2:
        url = f"{GITHUB_RAW_MEDIA}/{parts[1]}"
        st.image(url, width=width, use_container_width=use_container)
    else:
        st.write(f"🔗 {path}")

# ——— LOAD DATA ———
posts = load_posts()
# DEBUG: show total posts loaded
st.sidebar.write(f"⚙️ Loaded {len(posts)} posts from JSON")

# ——— SIDEBAR FILTERS ———
st.sidebar.title("🔍 Filters")
q = st.sidebar.text_input("Keyword")

# date-range picker
all_dates = [d for d in (parse_date(p["date"]) for p in posts) if d]
mn = min(all_dates) if all_dates else date.today()
mx = date.today()
start, end = st.sidebar.date_input("Date range", [mn, mx], min_value=mn, max_value=mx)

# sort order
sort_by = st.sidebar.selectbox("Sort by", ["Newest first", "Oldest first"])

# Load-more / Load-all
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
    if t and t in p.get("text","").lower():
        return True
    return any(t in c.get("text","").lower() for c in p.get("comments", []))

filtered = [p for p in posts if (not q or matches(p))]
filtered = [p for p in filtered if (d:=parse_date(p["date"])) and start <= d <= end]

# DEBUG: show posts after filtering
st.sidebar.write(f"⚙️ {len(filtered)} posts after filters")

# ——— SKIP DUPLICATES ———
grouped_posts = filtered

# ——— SORTING ———
reverse = (sort_by == "Newest first")
grouped_posts.sort(key=lambda p: parse_date(p["date"]) or date.today(), reverse=reverse)

# ——— RENDER ———
st.title("WP RETURNS GROUP – ARCHIVE")
st.markdown(f"> Showing **{min(len(grouped_posts), st.session_state.count)}** of **{len(grouped_posts)}** posts")

for post in grouped_posts[: st.session_state.count]:
    st.markdown('<div class="post-card">', unsafe_allow_html=True)
    col1, col2 = st.columns([3, 1])
    with col1:
        nice_date = format_datetime(post["date"])
        st.markdown(f"### {post['author']}  ·  *{nice_date}*")
    with col2:
        st.write("")

    if post["text"]:
        st.write(post["text"])
    if post["images"]:
        cols = st.columns(len(post["images"]))
        for c, img in zip(cols, post["images"]):
            with c:
                show_image(img, thumb=False)

    if post["comments"]:
        with st.expander(f"💬 {len(post['comments'])} comments"):
            for c in post["comments"]:
                c_date = format_datetime(c["date"])
                st.markdown(f"**{c['author']}**  ·  *{c_date}*")
                lines = c["text"].split("\n")
                tags = [L for L in lines if re.fullmatch(r"(?:[A-Z][a-z]+(?: [A-Z][a-z]+)*)", L)]
                body = [L for L in lines if L not in tags]
                txt = ("**" + " ".join(tags) + "** " if tags else "") + " ".join(body).strip()
                st.write(txt)
                if c.get("images"):
                    thumbs = st.columns(len(c["images"]))
                    for tc, im in zip(thumbs, c["images"]):
                        with tc:
                            show_image(im, thumb=True)
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
