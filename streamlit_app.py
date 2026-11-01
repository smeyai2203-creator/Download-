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
.stApp { background:#101111; color:#f4f4f4; }
[data-testid="stHeader"] { background:#101111; }
.block-container { max-width:1500px; padding:.45rem .8rem 1.1rem; }
.hero { padding:.5rem .8rem; border-radius:5px; margin-bottom:.45rem;
        background:#171818; border-bottom:1px solid #292929; }
.hero h1 { color:#fff; margin:0 0 .08rem; font-size:1.25rem; }
.hero p { color:#c9c9c9; margin:0; font-size:.78rem; }
h1,h2,h3,p,label,[data-testid="stMarkdownContainer"] { color:#f0f0f0; }
h2,h3 { margin:.48rem 0 .28rem !important; }
[data-testid="stImage"] { width:100%; }
[data-testid="stImage"] img {
 width:100% !important; height:auto !important; aspect-ratio:2/3;
 object-fit:cover; border-radius:5px;
}
div[data-testid="stHorizontalBlock"] {
 display:flex !important; flex-wrap:nowrap !important;
 gap:8px !important; align-items:flex-start;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
 flex:1 1 0 !important; width:0 !important; min-width:0 !important;
}
div[data-testid="stTextInput"] input {
 background:#202222; color:#fff; border:1px solid #444;
}
div[data-testid="stButton"] > button,
div[data-testid="stFormSubmitButton"] > button,
.stLinkButton a {
 background:#292929; color:#fff; border:1px solid #555;
 border-radius:5px; min-height:1.8rem; padding:.18rem .3rem;
 font-size:.75rem; white-space:normal;
}
div[data-testid="stButton"] > button:hover {
 border-color:#e5a12b; color:#ffd27a;
}
[data-testid="stAlert"] { border-radius:7px; }
footer { visibility:hidden; }
@media(max-width:700px) {
 .block-container { padding:.25rem .35rem .8rem; }
 .hero { padding:.4rem .55rem; margin-bottom:.35rem; }
 .hero h1 { font-size:1rem; } .hero p { font-size:.68rem; }
 div[data-testid="stHorizontalBlock"] { gap:5px !important; }
 div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
  flex:1 1 0 !important; width:0 !important; min-width:0 !important;
 }
 [data-testid="stImage"] img { aspect-ratio:2/3; height:auto !important; }
 h2 { font-size:1.02rem !important; }
 h3 { font-size:.92rem !important; }
 div[data-testid="stMarkdownContainer"] p {
  font-size:.68rem; line-height:1.2; overflow-wrap:anywhere;
 }
 div[data-testid="stButton"] > button,
 div[data-testid="stFormSubmitButton"] > button {
  font-size:.65rem; min-height:1.65rem; padding:.12rem .18rem;
 }
}
</style>
<div class="hero">
  <h1>🍎 Hongguo Drama</h1>
  <p>រឿងភាគចិន • ស្វែងរករឿង • មើលភាគ និងទាញយកវីដេអូ</p>
</div>
""", unsafe_allow_html=True)

if not APP_ID or not APP_SECRET:
    st.error(
        "មិនទាន់រកឃើញ API credentials។ សូមពិនិត្យ Streamlit Secrets "
        "ថាមាន XIAOYING_APPID និង XIAOYING_APPSECRET ត្រឹមត្រូវ។"
    )
    st.info("កុំដាក់ APPSECRET ក្នុងកូដ ឬ GitHub។ ដាក់តែក្នុង Streamlit Secrets ប៉ុណ្ណោះ។")

with st.form("search_form"):
    query = st.text_input("ស្វែងរករឿង", placeholder="វាយឈ្មោះរឿងនៅទីនេះ...")
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

selected = st.session_state.get("selected_drama")

# When a drama is selected, show its own detail/player screen only.
# This keeps the user from having to scroll past the poster catalogue.
if selected:
    if st.button("← ត្រឡប់ទៅបញ្ជីរឿង", key="back_to_catalog", use_container_width=True):
        st.session_state["selected_drama"] = None
        st.rerun()

    st.title("📺 " + selected["title"])
    if selected.get("cover"):
        st.image(selected["cover"], use_container_width=True)

    try:
        with st.spinner("កំពុងទាញយកព័ត៌មានភាគ..."):
            detail = get_details(selected["id"])

        description = detail.get("intro") or selected.get("desc") or ""
        if description:
            st.write(description)

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
            chosen_label = st.selectbox("ជ្រើសរើសភាគ", list(labels.keys()), key=f"episode_{selected['id']}")
            quality = st.selectbox("គុណភាពវីដេអូ", [360, 480, 540, 720, 1080], index=4, key=f"quality_{selected['id']}")
            codec = st.selectbox("ទម្រង់វីដេអូ", ["h264", "hevc"], index=0, key=f"codec_{selected['id']}")

            if st.button("▶ មើលភាគនេះ", key=f"play_{selected['id']}", use_container_width=True):
                ep_num = labels[chosen_label]
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
                if video_url:
                    st.session_state[f"playback_{selected['id']}_{ep_num}"] = {
                        "url": video_url,
                        "source": playback.get("source"),
                        "ready": playback.get("ready"),
                    }
                else:
                    st.warning("API មិនបានផ្ដល់តំណវីដេអូទេ។")

            ep_num = labels[chosen_label]
            saved_playback = st.session_state.get(f"playback_{selected['id']}_{ep_num}")
            if saved_playback:
                video_url = saved_playback["url"]
                st.subheader(f"🎬 {chosen_label}")
                st.video(video_url)
                st.link_button("⬇ ទាញយក / បើកវីដេអូ", video_url, use_container_width=True)
                if saved_playback.get("source") == "stream" and saved_playback.get("ready") is False:
                    st.info("វីដេអូកំពុងរៀបចំនៅម៉ាស៊ីនមេ។ សូមរង់ចាំ រួចចុចមើលម្ដងទៀត។")
                elif saved_playback.get("source") == "origin":
                    st.caption("តំណវីដេអូប្រភពដើមអាចមានពេលផុតកំណត់។")
    except Exception as exc:
        st.error(str(exc))

else:
    if items:
        st.subheader(f"🎬 រឿងកំពុងពេញនិយម / លទ្ធផលស្វែងរក ({len(items)})")
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
                    if st.button("មើលរឿង", key=f"drama_{item['id']}", use_container_width=True):
                        st.session_state["selected_drama"] = item
                        st.rerun()
    elif APP_ID and APP_SECRET and (do_search or do_home):
        st.info("រកមិនឃើញរឿងទេ។ សូមសាកល្បងឈ្មោះរឿងផ្សេង។")

st.divider()
st.caption("Hongguo Drama Downloader · Powered by XiaoYingAPI")
