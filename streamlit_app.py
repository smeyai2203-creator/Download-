import os
import time
import hmac
import hashlib
import secrets
from urllib.parse import urlparse

import requests
import streamlit as st

st.set_page_config(
    page_title="រឿងភាគចិន",
    page_icon="🍎",
    layout="wide",
)

# XiaoYingAPI — all credentials stay on the Streamlit server.
API_BASE = "https://www.xiaoyingapi.com"
API_PREFIX = "/api/dramas/hongguo"

def get_secret(*names):
    for name in names:
        try:
            value = st.secrets.get(name, "")
        except Exception:
            value = ""
        if value:
            return str(value).strip()
        value = os.getenv(name, "")
        if value:
            return str(value).strip()
    return ""

APP_ID = get_secret("XIAOYING_APPID", "APPID")
APP_SECRET = get_secret("XIAOYING_APPSECRET", "APPSECRET")

def build_signature(params, method, path):
    # XiaoYingAPI HMAC-SHA256 signature format from its Setup Wizard.
    pairs = sorted(
        (key, str(value))
        for key, value in params.items()
        if key != "sign" and value not in (None, "")
    )
    query_string = "&".join(f"{key}={value}" for key, value in pairs)
    raw = method.upper() + "\n" + path + "\n" + query_string
    return hmac.new(
        APP_SECRET.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

def xiaoying_get(endpoint, params=None, timeout=45):
    if not APP_ID or not APP_SECRET:
        raise RuntimeError(
            "មិនទាន់រកឃើញ XiaoYingAPI credentials ទេ។ "
            "សូមដាក់ XIAOYING_APPID និង XIAOYING_APPSECRET ក្នុង "
            "Streamlit → Manage app → Settings → Secrets។"
        )

    # The API signing guide requires the exact request path, including trailing slash.
    path = f"{API_PREFIX}/{endpoint.strip('/')}"
    signed = dict(params or {})
    signed.update({
        "app_id": APP_ID,
        "timestamp": str(int(time.time())),
        "nonce": secrets.token_hex(8),
    })
    signed["sign"] = build_signature(signed, "GET", path)

    try:
        response = requests.get(
            API_BASE + path,
            params=signed,
            timeout=timeout,
            headers={"Accept": "application/json", "User-Agent": "HongguoDramaDownloader/1.0"},
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"មិនអាចភ្ជាប់ XiaoYingAPI បាន៖ {exc}") from exc

    if not response.ok:
        raise RuntimeError(f"XiaoYingAPI HTTP {response.status_code}: {response.text[:400]}")

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError("XiaoYingAPI មិនបានត្រឡប់ JSON ត្រឹមត្រូវទេ។") from exc

    if not isinstance(result, dict):
        raise RuntimeError("ទម្រង់ចម្លើយពី XiaoYingAPI មិនត្រឹមត្រូវទេ។")

    if result.get("code") != 10000:
        message = result.get("msg") or "Unknown API error"
        raise RuntimeError(f"XiaoYingAPI ({result.get('code')}): {message}")

    return result.get("data") or {}

def extract_results(data):
    rows = data.get("results", [])
    return rows if isinstance(rows, list) else []

@st.cache_data(ttl=300, show_spinner=False)
def get_rankings():
    return extract_results(xiaoying_get("rank", {"type": "hot-drama", "page": 1}))

@st.cache_data(ttl=300, show_spinner=False)
def search_dramas(keyword):
    return extract_results(xiaoying_get("search", {"keyword": keyword, "page": 1}))

@st.cache_data(ttl=600, show_spinner=False)
def get_details(series_id):
    return xiaoying_get("detail", {"series_id": str(series_id)})

def normalize_drama(row):
    return {
        "id": str(row.get("series_id") or ""),
        "title": row.get("name") or "Untitled",
        "cover": row.get("cover") or "",
        "episodes": row.get("episode_cnt") or row.get("listed_cnt") or "",
        "desc": row.get("intro") or "",
        "tags": row.get("tags") or [],
    }

def clear_cached_lists():
    get_rankings.clear()
    search_dramas.clear()
    get_details.clear()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Battambang:wght@400;500;600;700&display=swap');
.stApp { background:#0b0b0b; color:#fff; }
[data-testid="stHeader"] { background:#0b0b0b; }
.block-container { max-width:1500px; padding:.45rem .65rem 2rem; }
.hero {
  padding:1rem; margin:.3rem 0 .8rem; border-radius:12px;
  background:linear-gradient(100deg,#171717,#3a1717);
  border:1px solid #563030;
}
.hero h1 { color:#fff; font-size:1.5rem; font-weight:700; margin:0 0 .3rem; }
.hero p { color:#fff; font-size:1rem; line-height:1.6; margin:0; }
.hero .hero-tag { display:inline-block; background:#d71920; color:#fff;
  padding:.25rem .6rem; border-radius:6px; font-weight:700; margin-bottom:.35rem; }
html, body, [class*="css"], button, input, textarea, select {
  font-family:'Battambang',sans-serif !important;
}
h1,h2,h3,p,label,
[data-testid="stMarkdownContainer"],
[data-testid="stCaptionContainer"] { color:#fff !important; }
h2 { font-size:1.25rem !important; line-height:1.6 !important; }
h3 { font-size:1.1rem !important; line-height:1.6 !important; }
.poster-title {
  color:#fff; font-size:1rem; font-weight:700;
  line-height:1.6; min-height:3.2em; margin:.35rem 0;
  overflow-wrap:anywhere;
}
[data-testid="stImage"] img {
  width:100%; aspect-ratio:2/3; height:auto; object-fit:cover;
  border-radius:8px; border:1px solid #444;
}
[data-testid="stTextInput"] input,
[data-testid="stMultiSelect"] input,
[data-testid="stSelectbox"] input {
  background:#202020 !important; color:#fff !important;
  border:1px solid #777 !important; min-height:2.7rem;
}
[data-testid="stTextInput"] label,
[data-testid="stMultiSelect"] label,
[data-testid="stSelectbox"] label {
  color:#fff !important; font-size:1rem !important; font-weight:700 !important;
}
[data-testid="stButton"] > button,
[data-testid="stFormSubmitButton"] > button,
.stLinkButton a {
  background:#d71920 !important; color:#fff !important;
  border:1px solid #ff7378 !important; border-radius:8px;
  min-height:2.6rem; padding:.35rem .55rem;
  font-size:.95rem !important; font-weight:700 !important;
  line-height:1.5; white-space:normal;
}
[data-testid="stButton"] > button:hover,
[data-testid="stFormSubmitButton"] > button:hover,
.stLinkButton a:hover { background:#a90f16 !important; color:#fff !important; }
[data-testid="stCaptionContainer"] { color:#e6e6e6 !important; font-size:.9rem !important; }
[data-testid="stAlert"] { border-radius:8px; }
footer { visibility:hidden; }
@media(max-width:700px) {
  .block-container { padding:.3rem .4rem 1.5rem; }
  .hero { padding:.75rem; }
  .hero h1 { font-size:1.2rem; }
  .hero p { font-size:.9rem; }
  h2 { font-size:1.1rem !important; }
  .poster-title { font-size:.88rem; line-height:1.55; min-height:3.1em; }
  [data-testid="stCaptionContainer"] { font-size:.8rem !important; }
  [data-testid="stButton"] > button,
  [data-testid="stFormSubmitButton"] > button,
  .stLinkButton a { font-size:.82rem !important; min-height:2.35rem; }
}
</style>
<div class="hero">
  <div class="hero-tag">HD • រឿងភាគចិន</div>
  <h1>រឿងភាគចិនថ្មីៗ និងពេញនិយម</h1>
  <p>ស្វែងរករឿងដែលអ្នកចូលចិត្ត • មើលភាគ • ទាញយកវីដេអូ</p>
</div>
""", unsafe_allow_html=True)

if not APP_ID or not APP_SECRET:
    st.error(
        "មិនទាន់រកឃើញ API credentials។ សូមពិនិត្យ Streamlit Secrets "
        "ថាមាន XIAOYING_APPID និង XIAOYING_APPSECRET ត្រឹមត្រូវ។"
    )
    st.info("កុំដាក់ APPSECRET ក្នុងកូដ ឬ GitHub។ ដាក់តែក្នុង Streamlit Secrets ប៉ុណ្ណោះ។")

with st.form("search_form"):
    query = st.text_input("🔎 ស្វែងរករឿង", placeholder="បញ្ចូលចំណងជើងរឿង...")
    c1, c2 = st.columns(2)
    do_search = c1.form_submit_button("🔎 ស្វែងរក", use_container_width=True)
    do_home = c2.form_submit_button("🏠 រឿងកំពុងពេញនិយម", use_container_width=True)

if "drama_items" not in st.session_state:
    st.session_state["drama_items"] = []
if "selected_drama" not in st.session_state:
    st.session_state["selected_drama"] = None

if do_search and query.strip():
    try:
        with st.spinner("កំពុងស្វែងរករឿង..."):
            st.session_state["drama_items"] = search_dramas(query.strip())
            st.session_state["selected_drama"] = None
    except Exception as exc:
        st.error("មានបញ្ហា៖ " + str(exc))
elif do_home or (not st.session_state["drama_items"] and APP_ID and APP_SECRET):
    try:
        with st.spinner("កំពុងទាញយករឿងកំពុងពេញនិយម..."):
            st.session_state["drama_items"] = get_rankings()
    except Exception as exc:
        st.error("មានបញ្ហា៖ " + str(exc))

items = [
    normalize_drama(row)
    for row in st.session_state["drama_items"]
    if isinstance(row, dict) and row.get("series_id")
]

if items:
    st.subheader(f"🔥 រឿងពេញនិយម / លទ្ធផលស្វែងរក ({len(items)})")
    # Three readable posters per row on a phone; desktop can show more space per card.
    for row_start in range(0, len(items), 3):
        row_items = items[row_start:row_start + 3]
        columns = st.columns(3, gap="small")
        for col, item in zip(columns, row_items):
            with col:
                if item["cover"]:
                    st.image(item["cover"], use_container_width=True)
                st.markdown("<div class=\"poster-title\">" + item["title"] + "</div>", unsafe_allow_html=True)
                if item["episodes"]:
                    st.caption(f"ចំនួន {item['episodes']} ភាគ")
                if st.button("មើលរឿង", key=f"drama_{item['id']}", use_container_width=True):
                    st.session_state["selected_drama"] = item
                    st.rerun()
elif APP_ID and APP_SECRET and (do_search or do_home):
    st.info("រកមិនឃើញរឿងទេ។ សូមសាកល្បងឈ្មោះរឿងផ្សេង។")

selected = st.session_state.get("selected_drama")
if selected:
    st.divider()
    st.subheader("📺 ចំណងជើងរឿង៖ " + selected["title"])
    if st.button("← ត្រឡប់ទៅបញ្ជីរឿង"):
        st.session_state["selected_drama"] = None
        st.rerun()

    try:
        with st.spinner("កំពុងទាញយកព័ត៌មានភាគ..."):
            detail = get_details(selected["id"])

        st.write(detail.get("intro") or selected.get("desc") or "")
        episode_rows = detail.get("episodes") or []
        playable_rows = [
            ep for ep in episode_rows
            if isinstance(ep, dict) and ep.get("playable") is True
        ]

        if not playable_rows:
            st.warning("រឿងនេះមិនទាន់មានភាគសម្រាប់មើល ឬទាញយកទេ។")
        else:
            labels = {
                f"ភាគ {int(ep.get('ep', i + 1))}": int(ep.get("ep", i + 1))
                for i, ep in enumerate(playable_rows)
            }
            selected_labels = st.multiselect(
                "ជ្រើសរើសភាគ (អតិបរមា 5 ភាគ)",
                list(labels.keys()),
                default=[list(labels.keys())[0]],
            )
            quality = st.selectbox("គុណភាពវីដេអូ", [360, 480, 540, 720, 1080], index=4)
            codec = st.selectbox("ទម្រង់វីដេអូ", ["h264", "hevc"], index=0)
            if st.button("▶ ចាក់វីដេអូ", disabled=not selected_labels):
                if len(selected_labels) > 5:
                    st.warning("សូមជ្រើសរើសមិនលើស 5 ភាគក្នុងមួយលើក។")
                else:
                    for label in selected_labels:
                        ep_num = labels[label]
                        with st.spinner(f"កំពុងរៀបចំភាគ {ep_num}..."):
                            playback = xiaoying_get(
                                "play",
                                {
                                    "series_id": selected["id"],
                                    "ep": ep_num,
                                    "q": quality,
                                    "codec": codec,
                                },
                            )
                        video_url = playback.get("url")
                        if not video_url:
                            st.warning(f"ភាគ {ep_num}: API មិនបានផ្ដល់តំណវីដេអូទេ។")
                            continue
                        st.markdown(f"### ភាគ {ep_num}")
                        st.video(video_url)
                        st.link_button("⬇ ទាញយកវីដេអូ", video_url, use_container_width=True)
                        if playback.get("source") == "stream" and playback.get("ready") is False:
                            st.caption("វីដេអូកំពុងរៀបចំនៅម៉ាស៊ីនមេ។ សូមរង់ចាំ រួចចុចតំណម្ដងទៀត។")
                        elif playback.get("source") == "origin":
                            st.caption("តំណនេះជាតំណប្រភពដើម និងមានពេលផុតកំណត់។")
    except Exception as exc:
        st.error("មានបញ្ហា៖ " + str(exc))

st.divider()

st.caption("កម្មវិធីមើល និងទាញយករឿងភាគចិន")
