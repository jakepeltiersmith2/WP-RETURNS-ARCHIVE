import streamlit as st
import streamlit.components.v1 as components
import json, os, re

# ——— PAGE CONFIG ———
st.set_page_config(
    page_title="WP RETURNS PAGE ARCHIVE",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ——— GLOBAL STYLES ———
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
      html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }

      /* Card wrapper */
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

      /* Text sizing */
      h1 { font-size: 3rem !important; }
      h3 { font-size: 1.75rem !important; }
      p  { font-size: 1.25rem !important; line-height: 1.6 !important; }
      .streamlit-expanderHeader { font-size: 1.4rem !important; font-weight: 500 !important; }
      .stTextInput input { font-size: 1.1rem !important; }
      .streamlit-expanderContent > div { margin-bottom: 1rem; }
      .block-container { padding-top: 1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ——— CONFIG ———
DATA_PATH = r"\\sbi-srv-10\GeneralShares\Company\Systems\RETURNS ARCHIVE\returns_posts.json"
PAGE_SIZE = 100

# ——— DATA LOADING ———
@st.cache_data(show_spinner=False)
def load_posts(path):
    if not os.path.exists(path):
        st.error(f"Data file not found: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

posts = load_posts(DATA_PATH)

# ——— SIDEBAR ———
st.sidebar.title("🔍 Filters")
q = st.sidebar.text_input("Search keyword")

if "count" not in st.session_state:
    st.session_state.count = PAGE_SIZE

# a hidden “Load more” button we’ll click via JS
load_more = st.sidebar.button("Load more", key="__load_more__")
if load_more:
    st.session_state.count += PAGE_SIZE

# ——— FILTERING ———
def matches(post, term):
    t = term.lower()
    if t in post["text"].lower():
        return True
    return any(t in c["text"].lower() for c in post["comments"])

filtered = [p for p in posts if matches(p, q)] if q else posts

# ——— GROUP DUPLICATES ———
grouped = {}
order = []
for p in filtered:
    key = (p["author"], p["date"])
    if key not in grouped:
        grouped[key] = {
            "author":   p["author"],
            "date":     p["date"],
            "text":     p["text"],
            "images":   [],
            "comments": p["comments"],
        }
        order.append(key)
    grouped[key]["images"].extend(p["images"])
grouped_posts = [grouped[k] for k in order]

# ——— HEADER ———
st.title("WP RETURNS GROUP – ARCHIVE")
st.markdown(
    f"> Showing **{min(len(grouped_posts), st.session_state.count)}** of **{len(grouped_posts)}** posts"
)

# ——— MAIN DISPLAY ———
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
        img_cols = st.columns(len(post["images"]))
        for c, img in zip(img_cols, post["images"]):
            c.image(img, use_container_width=True)

    if post["comments"]:
        with st.expander(f"💬 {len(post['comments'])} comments"):
            for c in post["comments"]:
                # author & date on one line
                st.markdown(f"**{c['author']}**  ·  *{c['date']}*")
                # merge tags + body
                lines = c["text"].split("\n")
                tags, body = [], []
                for L in lines:
                    if re.fullmatch(r"(?:[A-Z][a-z]+(?: [A-Z][a-z]+)*)", L):
                        tags.append(L)
                    else:
                        body.append(L)
                tag_str = " ".join(tags)
                body_str = " ".join(body).strip()
                if tag_str:
                    st.markdown(f"**{tag_str}** {body_str}")
                else:
                    st.write(body_str)

                if c["images"]:
                    thumbs = st.columns(len(c["images"]))
                    for tc, im in zip(thumbs, c["images"]):
                        tc.markdown('<div class="comment-image">', unsafe_allow_html=True)
                        tc.image(im, use_container_width=True)
                        tc.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ——— INFINITE SCROLL ANCHOR ———
components.html(
    """
    <div id="scroll-anchor" style="height:1px; margin-top:-1px;"></div>
    <script>
      if (!window._infScroll_) {
        window._infScroll_ = true;
        const anchor = document.getElementById('scroll-anchor');
        const obs = new IntersectionObserver(entries => {
          if (entries[0].isIntersecting) {
            const btns = window.parent.document.querySelectorAll("button");
            for (const b of btns) {
              if (b.innerText.trim() === "Load more") {
                b.click();
              }
            }
          }
        }, { threshold: 1.0 });
        obs.observe(anchor);
      }
    </script>
    """,
    height=1,
)

st.markdown("---")
