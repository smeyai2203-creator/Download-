import os
import time
import hmac
import hashlib
import secrets
from urllib.parse import urlparse

import requests
import streamlit as st

st.set_page_config(
    page_title="Hongguo Drama Downloader",
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
.stApp {background:#080909;color:#f5f5f5;}
[data-testid="stHeader"] {background:#080909;}
.block-container {max-width:1500px;padding:.45rem .65rem 1rem;}
.hero {padding:.65rem .85rem;border-radius:9px;margin:.1rem 0 .65rem;
 background:linear-gradient(100deg,#171717,#321010);border:1px solid #3c2020;}
.hero h1 {color:#fff;margin:0;font-size:1.45rem;font-weight:800;}
.hero p {color:#ddd;margin:.12rem 0 0;font-size:.82rem;}
h1,h2,h3,p,label,[data-testid="stMarkdownContainer"] {color:#f4f4f4;}
h2,h3 {margin:.55rem 0 .35rem!important;}
[data-testid="stImage"] img {width:100%!important;aspect-ratio:2/3;height:auto!important;
 object-fit:cover;border-radius:7px;border:1px solid #292929;}
div[data-testid="stHorizontalBlock"] {gap:8px!important;align-items:flex-start;}
div[data-testid="stTextInput"] input {background:#1b1b1b;color:white;border:1px solid #444;}
div[data-testid="stButton"]>button,div[data-testid="stFormSubmitButton"]>button,
.stLinkButton a {background:#e50914;color:#fff;border:0;border-radius:7px;
 min-height:2rem;padding:.25rem .4rem;font-size:.78rem;font-weight:650;}
div[data-testid="stButton"]>button:hover,.stLinkButton a:hover {background:#b80710;color:white;}
[data-testid="stAlert"] {border-radius:8px;}
[data-testid="stExpander"] {background:#171717;border:1px solid #333;}
footer {visibility:hidden;}
@media(max-width:700px) {
 .block-container {padding:.25rem .35rem .8rem;}
 .hero {padding:.5rem .65rem;margin-bottom:.45rem;}
 .hero h1 {font-size:1.12rem;} .hero p {font-size:.7rem;}
 div[data-testid="stHorizontalBlock"] {gap:5px!important;}
 [data-testid="stImage"] img {aspect-ratio:2/3;height:auto!important;}
 h2 {font-size:1.05rem!important;} h3 {font-size:.92rem!important;}
 div[data-testid="stMarkdownContainer"] p {font-size:.7rem;line-height:1.25;}
 div[data-testid="stButton"]>button,div[data-testid="stFormSubmitButton"]>button,
 .stLinkButton a {font-size:.67rem;min-height:1.75rem;padding:.15rem .2rem;}
}
</style>
<div class="hero">
  <h1>🍎 រឿងភាគចិន | Hongguo Drama</h1>
  <p>មើលរឿង • ស្វែងរកចំណងជើង • ជ្រើសរើសភាគ • ទាញយកវីដេអូ</p>
</div>
""", unsafe_allow_html=True)

if not APP_ID or not APP_SECRET:
    st.error(
        "មិនទាន់រកឃើញ API credentials។ សូមពិនិត្យ Streamlit Secrets "
        "ថាមាន XIAOYING_APPID និង XIAOYING_APPSECRET ត្រឹមត្រូវ។"
    )
    st.info("កុំដាក់ APPSECRET ក្នុងកូដ ឬ GitHub។ ដាក់តែក្នុង Streamlit Secrets ប៉ុណ្ណោះ។")

with st.form("search_form"):
    query = st.text_input("🔎 ស្វែងរករឿង", placeholder="បញ្ចូលឈ្មោះរឿង...")
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
        st.error(str(exc))
elif do_home or (not st.session_state["drama_items"] and APP_ID and APP_SECRET):
    try:
        with st.spinner("កំពុងទាញយករឿងកំពុងពេញនិយម..."):
            st.session_state["drama_items"] = get_rankings()
    except Exception as exc:
        st.error(str(exc))

items = [
    normalize_drama(row)
    for row in st.session_state["drama_items"]
    if isinstance(row, dict) and row.get("series_id")
]

if items:
    st.subheader(f"🔥 រឿងពេញនិយម / លទ្ធផលស្វែងរក ({len(items)})")
    for row_start in range(0, len(items), 6):
        row_items = items[row_start:row_start + 6]
        columns = st.columns(6, gap="small")
        for col, item in zip(columns, row_items):
            with col:
                if item["cover"]:
                    st.image(item["cover"], use_container_width=True)
                st.markdown("**" + item["title"] + "**")
                if item["tags"]:
                    st.caption(" · ".join(str(tag) for tag in item["tags"][:2]))
                if st.button("មើល / ទាញយក", key=f"drama_{item['id']}", use_container_width=True):
                    st.session_state["selected_drama"] = item
                    st.rerun()
elif APP_ID and APP_SECRET and (do_search or do_home):
    st.info("រកមិនឃើញរឿងទេ។ សូមសាកល្បងឈ្មោះរឿងផ្សេង។")

selected = st.session_state.get("selected_drama")
if selected:
    st.divider()
    st.subheader("📺 " + selected["title"])
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
            st.warning("រឿងនេះមិនទាន់មានភាគដែលអាចចាក់បានទេ។")
        else:
            labels = {
                f"ភាគ {int(ep.get('ep', i + 1))}": int(ep.get("ep", i + 1))
                for i, ep in enumerate(playable_rows)
            }
            selected_labels = st.multiselect(
                "📺 ជ្រើសរើសភាគដែលចង់មើល ឬទាញយក (អតិបរមា 5 ភាគ)",
                list(labels.keys()),
                default=[list(labels.keys())[0]],
            )
            c_quality, c_codec = st.columns(2)
            quality = c_quality.selectbox("គុណភាព", [360, 480, 540, 720, 1080], index=4)
            codec = c_codec.selectbox("ទម្រង់វីដេអូ", ["h264", "hevc"], index=0)
            if st.button("▶ បង្កើតតំណមើល និងទាញយក", disabled=not selected_labels, use_container_width=True):
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
                            st.warning(f"ភាគ {ep_num}: មិនមានតំណវីដេអូទេ។")
                            continue
                        st.markdown(f"### 🎞️ ភាគ {ep_num}")
                        st.video(video_url)
                        st.link_button("⬇️ ទាញយកភាគនេះ", video_url, use_container_width=True)
                        if playback.get("source") == "stream" and playback.get("ready") is False:
                            st.info("វីដេអូកំពុងរៀបចំ។ សូមរង់ចាំបន្តិច រួចចុច «ទាញយកភាគនេះ» ម្ដងទៀត។")
                        elif playback.get("source") == "origin":
                            st.caption("តំណវីដេអូប្រភពដើមអាចមានពេលផុតកំណត់។")
    except Exception as exc:
        st.error(str(exc))

st.divider()
st.caption("🍎 រឿងភាគចិន • Hongguo Drama • ដំណើរការដោយ XiaoYingAPI")
