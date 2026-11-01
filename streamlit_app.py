import os
import time
import re
from urllib.parse import quote

import requests
import streamlit as st

st.set_page_config(
    page_title="Hongguo Drama Downloader",
    page_icon="🍎",
    layout="wide"
)

BASE = "https://api.apify.com/v2"

ACTORS = {
    "search": "spider_studio~hongguo-search",
    "detail": "spider_studio~hongguo-series-detail",
    "feed": "spider_studio~hongguo-recommend-feed",
    "download": "spider_studio~hongguo-video-download-kvs",
}

def get_token():
    try:
        return st.secrets.get("APIFY_TOKEN", os.getenv("APIFY_TOKEN", ""))
    except Exception:
        return os.getenv("APIFY_TOKEN", "")

TOKEN = get_token()

def api(path, payload=None, timeout=90):
    if not TOKEN:
        raise RuntimeError("សូមកំណត់ APIFY_TOKEN ក្នុង Streamlit Secrets")

    r = requests.request(
        "POST" if payload is not None else "GET",
        BASE + path,
        headers={"Authorization": f"Bearer {TOKEN}"},
        json=payload,
        timeout=timeout
    )

    if not r.ok:
        raise RuntimeError(f"Apify {r.status_code}: {r.text[:300]}")

    return r.json()

def run_actor(actor, data):
    return api(
        f"/acts/{actor}/run-sync-get-dataset-items?timeout=300",
        data,
        timeout=320
    )

def pick(obj, *keys):
    for key in keys:
        value = obj.get(key) if isinstance(obj, dict) else None
        if value not in (None, ""):
            return value

def image_url(value):
    if isinstance(value, str) and value.startswith("http"):
        return value.replace("http://", "https://")
    if isinstance(value, list):
        return image_url(value[0]) if value else None
    if isinstance(value, dict):
        return image_url(
            value.get("url_list")
            or value.get("url")
            or value.get("uri")
        )

def find_cover(obj):
    if not isinstance(obj, dict):
        return None

    for key, value in obj.items():
        if re.search(r"cover|thumb|poster|image|img", key, re.I):
            result = image_url(value)
            if result:
                return result

    for value in obj.values():
        if isinstance(value, dict):
            result = find_cover(value)
            if result:
                return result

    return None

def normalize(item):
    data = item.get("data") or item
    video = (data.get("video_data") or [data])[0]

    return {
        "id": str(
            pick(video, "series_id", "seriesId", "book_id", "id")
            or pick(data, "series_id", "seriesId")
            or ""
        ),
        "title": pick(
            video, "series_name", "title", "name", "book_name"
        ) or "Untitled",
        "cover": find_cover(video) or find_cover(data),
        "episodes": pick(
            video, "episode_cnt", "episodeCount", "series_count"
        ),
        "desc": pick(
            video, "series_intro", "intro", "synopsis", "desc"
        ) or ""
    }

def cards(items):
    result = []
    seen = set()

    for item in items or []:
        if not isinstance(item, dict):
            continue

        if item.get("success") is False:
            continue

        card = normalize(item)

        if card["id"] and card["id"] not in seen:
            result.append(card)
            seen.add(card["id"])

    return result

@st.cache_data(ttl=86400)
def home_items():
    return run_actor(
        ACTORS["feed"],
        {"maxResults": 100, "includeRaw": True}
    )

@st.cache_data(ttl=3600)
def search_items(query):
    return run_actor(
        ACTORS["search"],
        {"queries": [query], "maxPages": 1}
    )

@st.cache_data(ttl=86400)
def detail_items(series_id):
    return run_actor(
        ACTORS["detail"],
        {"seriesIds": [str(series_id)]}
    )

st.markdown("""
<style>
.block-container {
    padding-top: 1.2rem;
    max-width: 1200px;
}
[data-testid="stImage"] img {
    border-radius: 12px;
    object-fit: cover;
}
</style>
""", unsafe_allow_html=True)

st.title("🍎 Hongguo Drama Downloader")
st.caption("ស្វែងរករឿង · មើលភាគ · ទាញយកវីដេអូ")

if not TOKEN:
    st.warning(
        'សូមបន្ថែម APIFY_TOKEN ក្នុង Streamlit Secrets '
        'ឧទាហរណ៍៖ APIFY_TOKEN = "YOUR_TOKEN"'
    )

with st.form("search"):
    query = st.text_input(
        "ស្វែងរករឿង",
        placeholder="បញ្ចូលឈ្មោះរឿង..."
    )

    c1, c2 = st.columns(2)

    search = c1.form_submit_button(
        "🔎 ស្វែងរក",
        use_container_width=True
    )

    home = c2.form_submit_button(
        "🏠 រឿងថ្មី",
        use_container_width=True
    )

if "items" not in st.session_state:
    st.session_state["items"] = []

if search and query.strip():
    try:
        with st.spinner("កំពុងស្វែងរក..."):
            st.session_state["items"] = search_items(query.strip())
            st.session_state.pop("selected", None)
    except Exception as e:
        st.error(str(e))

elif home or (not st.session_state["items"] and TOKEN):
    try:
        with st.spinner("កំពុងទាញយកបញ្ជីរឿង..."):
            st.session_state["items"] = home_items()
    except Exception as e:
        st.error(str(e))

series = cards(st.session_state["items"])

if series:
    st.subheader(f"រឿងដែលរកឃើញ ({len(series)})")

    columns = st.columns(4)

    for i, item in enumerate(series):
        with columns[i % 4]:

            if item["cover"]:
                st.image(
                    item["cover"],
                    use_container_width=True
                )

            st.markdown("**" + item["title"] + "**")

            st.caption(
                "ភាគ៖ " + str(item["episodes"] or "—")
            )

            if st.button(
                "មើលភាគ",
                key="series_" + item["id"],
                use_container_width=True
            ):
                st.session_state.selected = item
                st.rerun()

if st.session_state.get("selected"):

    selected = st.session_state.selected

    st.divider()
    st.subheader("📺 " + selected["title"])

    if st.button("← ត្រឡប់"):
        st.session_state.pop("selected", None)
        st.rerun()

    try:
        with st.spinner("កំពុងទាញយកព័ត៌មានភាគ..."):

            details = detail_items(selected["id"])

        row = next(
            (x for x in details if x.get("success") is not False),
            {}
        )

        if row.get("success") is False:
            st.error(row.get("error", "មិនអាចទាញយកព័ត៌មានបាន"))
        else:
            series_data = row.get("series") or {}
            episodes = row.get("episodes") or []

            st.write(
                series_data.get("synopsis")
                or selected["desc"]
            )

            if not episodes and series_data.get("firstVideoId"):
                episodes = [{
                    "videoId": series_data["firstVideoId"],
                    "episodeIndex": 1
                }]

            choices = {
                f"ភាគ {ep.get('episodeIndex', i+1)}":
                str(ep.get("videoId"))
                for i, ep in enumerate(episodes)
                if ep.get("videoId")
            }

            if choices:

                selected_eps = st.multiselect(
                    "ជ្រើសរើសភាគ",
                    list(choices.keys())
                )

                if st.button(
                    "⬇ រៀបចំទាញយក",
                    disabled=not selected_eps
                ):

                    if len(selected_eps) > 5:
                        st.warning("សូមជ្រើសរើសមិនលើស 5 ភាគ")
                    else:
                        ids = [
                            choices[x] for x in selected_eps
                        ]

                        with st.spinner("កំពុងដំណើរការ..."):

                            result = api(
                                f"/acts/{ACTORS['download']}/runs",
                                {"videoIds": ids}
                            )

                        run_id = result["data"]["id"]

                        status_box = st.empty()
                        progress = st.progress(0)

                        final = None

                        for tick in range(100):

                            time.sleep(3)

                            state = api(
                                f"/actor-runs/{quote(run_id)}"
                            )

                            data = state.get("data", {})
                            status = data.get("status", "RUNNING")

                            status_box.write(
                                "ស្ថានភាព៖ " + status
                            )

                            progress.progress(
                                min((tick + 1) / 100, 0.99)
                            )

                            if status in [
                                "SUCCEEDED",
                                "FAILED",
                                "ABORTED",
                                "TIMED-OUT"
                            ]:

                                dataset = data.get(
                                    "defaultDatasetId"
                                )

                                final = (
                                    api(
                                        f"/datasets/{dataset}/items?clean=true"
                                    )
                                    if dataset else []
                                )

                                break

                        if final is None:
                            st.warning(
                                "ការងារនៅដំណើរការ សូមពិនិត្យម្ដងទៀត"
                            )

                        else:
                            progress.progress(1)

                            for item in final:

                                video = (
                                    item.get("videoUrl")
                                    or item.get("video_url")
                                )

                                if video:
                                    st.video(video)

                                    st.link_button(
                                        "⬇ ទាញយកវីដេអូ",
                                        video
                                    )
                                else:
                                    st.warning(
                                        item.get("error")
                                        or "មិនមានវីដេអូ"
                                    )

    except Exception as e:
        st.error(str(e))

st.divider()

st.caption(
    "Hongguo Drama Downloader · Apify API"
)
