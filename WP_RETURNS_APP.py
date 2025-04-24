import streamlit as st
import streamlit.components.v1 as components
import json, os, re, requests

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
      /* shrink comment thumbnails to 80px */
      .comment-image img {
        max-width: 80px !important;
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
PAGE_SIZE = 100
LOCAL_JSON = os.path.join(os.path.dirname(__file__), "returns_posts.json")
GITHUB_RAW_JSON = "https://raw.githubusercontent.com/jakepeltiersmith2/WP-RETURNS-ARCHIVE/main/returns_posts.json"
GITHUB_RAW_MEDIA = "https://raw.githubusercontent.com/jakepeltiersmith2/WP-RETURNS-ARCHIVE/main/media"

@st.cache_data
def load_posts():
    if os.path.exists(LOCAL_JSON):
        return json.load(open(LOCAL_JSON, "r", encoding="utf-8"))
    r = requests.get(GITHUB_RAW_JSON, timeout=10); r.raise_for_status()
    return r.json()

posts = load_posts()

# ——— SIDEBAR ———
st.sidebar.title("🔍 Filters")
q = st.sidebar.text_input("Search keyword")

# sort control
sort_order = st.sidebar.selectbox("Sort order", ["Newest first", "Oldest first"])

# load-more
if "count" not in st.session_state:
    st.session_state.count = PAGE_SIZE
if st.sidebar.button("Load more"):
    st.session_state.count += PAGE_SIZE

def matches(post, term):
    t = term.lower()
    if t in post.get("text","").lower(): return True
    return any(t in c.get("text","").lower() for c in post.get("comments",[]))

filtered = [p for p in posts if matches(p, q)] if q else posts

# group duplicate author+date together
grouped, order = {}, []
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
        order.append(key)
    grouped[key]["images"].extend(p.get("images",[]))
grouped_posts = [grouped[k] for k in order]

# apply sort
if sort_order == "Oldest first":
    grouped_posts = list(reversed(grouped_posts))

# ——— HEADER ———
st.title("WP RETURNS GROUP – ARCHIVE")
st.markdown(f"> Showing **{min(len(grouped_posts), st.session_state.count)}** of **{len(grouped_posts)}** posts — *{sort_order}*")

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
        for col, img in zip(cols, post["images"]):
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
                    for tc, im in zip(thumbs, c["images"]):
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
      const anchor = document.getElementById('scroll-anchor');
      new IntersectionObserver(e=>{
        if(e[0].isIntersecting){
          document.querySelectorAll("button").forEach(b=>{
            if(b.innerText.trim()==="Load more") b.click();
          });
        }
      },{threshold:1.0}).observe(anchor);
    }
  </script>
""", height=1)

st.markdown("---")
