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
.stApp {background:#070808;color:#f5f5f5;}
[data-testid="stHeader"] {background:#070808;}
.block-container {max-width:1600px;padding:.25rem .65rem 5.2rem;}
.hero {min-height:205px;padding:1rem 1.1rem;margin:.2rem 0 .8rem;border-radius:14px;
 border:1px solid #422727;
 background:linear-gradient(90deg,rgba(0,0,0,.96),rgba(0,0,0,.72) 38%,rgba(0,0,0,.08)),
 linear-gradient(120deg,#361414,#a34a32 58%,#161616);
 display:flex;flex-direction:column;justify-content:center;}
.hero h1 {color:#fff;font-size:1.8rem;font-weight:850;margin:0 0 .25rem;}
.hero p {color:#f0dddd;font-size:.9rem;margin:0 0 .7rem;}
.hero .hero-tag {display:inline-block;background:#e50914;color:white;padding:.2rem .55rem;
 border-radius:6px;font-weight:800;font-size:.78rem;width:max-content;}
h1,h2,h3,p,label,[data-testid="stMarkdownContainer"] {color:#f4f4f4;}
h2,h3 {margin:.48rem 0 .35rem!important;}
[data-testid="stImage"] img {width:100%!important;aspect-ratio:2/3;height:auto!important;
 object-fit:cover;border-radius:8px;border:1px solid #292929;}
div[data-testid="stHorizontalBlock"] {gap:9px!important;align-items:flex-start;}
div[data-testid="stTextInput"] input {background:#1b1b1b;color:white;border:1px solid #444;}
div[data-testid="stButton"]>button,div[data-testid="stFormSubmitButton"]>button,
.stLinkButton a {background:#ed101b;color:#fff;border:0;border-radius:8px;
 min-height:1.9rem;padding:.22rem .35rem;font-size:.75rem;font-weight:700;}
div[data-testid="stButton"]>button:hover,.stLinkButton a:hover {background:#b80710;color:white;}
[data-testid="stAlert"] {border-radius:8px;}
[data-testid="stExpander"] {background:#171717;border:1px solid #333;}
footer {visibility:hidden;}
.bottom-nav {position:fixed;z-index:999;bottom:0;left:0;right:0;background:#080808;
 border-top:1px solid #333;display:flex;justify-content:space-around;align-items:center;
 padding:.5rem .2rem .7rem;color:#eee;font-size:.76rem;text-align:center;}
.bottom-nav span {display:block;font-size:1.25rem;margin-bottom:.12rem;}
.bottom-nav .download {background:#ed1014;border-radius:50%;padding:.55rem .8rem;
 transform:translateY(-12px);border:3px solid #333;font-weight:800;}
@media(max-width:700px) {
 .block-container {padding:.2rem .3rem 5.4rem;}
 .hero {min-height:155px;padding:.7rem .75rem;margin-bottom:.5rem;border-radius:10px;}
 .hero h1 {font-size:1.22rem;} .hero p {font-size:.72rem;margin-bottom:.45rem;}
 .hero .hero-tag {font-size:.68rem;}
 div[data-testid="stHorizontalBlock"] {gap:6px!important;}
 [data-testid="stImage"] img {aspect-ratio:2/3;height:auto!important;}
 h2 {font-size:1.03rem!important;} h3 {font-size:.9rem!important;}
 div[data-testid="stMarkdownContainer"] p {font-size:.69rem;line-height:1.22;}
 div[data-testid="stButton"]>button,div[data-testid="stFormSubmitButton"]>button,
 .stLinkButton a {font-size:.62rem;min-height:1.65rem;padding:.12rem .16rem;}
 .bottom-nav {font-size:.65rem;padding:.35rem .1rem .55rem;}
 .bottom-nav span {font-size:1.08rem;}
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
    # Three readable posters per row on a phone; desktop can show more space per card.
    for row_start in range(0, len(items), 3):
        row_items = items[row_start:row_start + 3]
        columns = st.columns(3, gap="small")
        for col, item in zip(columns, row_items):
            with col:
                if item["cover"]:
                    st.image(item["cover"], use_container_width=True)
                st.markdown("**" + item["title"] + "**")
                if item["episodes"]:
                    st.caption(f"ចំនួន {item['episodes']} ភាគ")
                if st.button("⬇ ទាញយក / មើលរឿង", key=f"drama_{item['id']}", use_container_width=True):
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
                "ជ្រើសរើសភាគ (អតិបរមា 5 ភាគ)",
                list(labels.keys()),
                default=[list(labels.keys())[0]],
            )
            quality = st.selectbox("គុណភាពវីដេអូ", [360, 480, 540, 720, 1080], index=4)
            codec = st.selectbox("ទម្រង់វីដេអូ", ["h264", "hevc"], index=0)
            if st.button("▶ ចាក់វីដេអូ / បង្ហាញតំណ", disabled=not selected_labels):
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
                        st.link_button("⬇ បើក / ទាញយកវីដេអូ", video_url, use_container_width=True)
                        if playback.get("source") == "stream" and playback.get("ready") is False:
                            st.caption("វីដេអូកំពុងរៀបចំនៅម៉ាស៊ីនមេ។ សូមរង់ចាំ រួចចុចតំណម្ដងទៀត។")
                        elif playback.get("source") == "origin":
                            st.caption("តំណនេះជាតំណប្រភពដើម និងមានពេលផុតកំណត់។")
    except Exception as exc:
        st.error(str(exc))

st.divider()
st.markdown("""
<div class="bottom-nav">
 <div><span>⌂</span>ទំព័រដើម</div>
 <div><span>⌕</span>ស្វែងរក</div>
 <div class="download"><span>⬇</span>ទាញយក</div>
 <div><span>▤</span>បណ្ណាល័យ</div>
 <div><span>♙</span>គណនី</div>
</div>
""", unsafe_allow_html=True)
st.caption("Hongguo Drama Downloader · Powered by XiaoYingAPI")
