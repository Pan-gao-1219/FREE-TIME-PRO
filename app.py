from datetime import timedelta
from pathlib import Path
import sqlite3
from urllib.parse import parse_qs, urlsplit

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from availability import (
    AvailabilityError, EVENT_ID, GRID_MODES, MAX_DAYS, TIMETABLE_SOURCE, create_event,
    dates_for, default_range, normalize_identity, results, save_response, time_rows, today, verify_member,
)
from storage import GitHubStore, LocalStore
from home_cover import render_cover, render_credit, render_masthead
from event_ui import event_banner, event_overview


ROOT = Path(__file__).resolve().parent
GRID_FILES = ROOT / "grid"
WEEKDAYS = "一二三四五六日"

st.set_page_config(
    page_title="有空 · Free Time Pro", page_icon=":material/calendar_month:",
    layout="wide",
)
GRID = st.components.v2.component(
    "free_time_grid",
    html=(GRID_FILES / "index.html").read_text(encoding="utf-8"),
    css=(GRID_FILES / "grid.css").read_text(encoding="utf-8"),
    js=(GRID_FILES / "grid.js").read_text(encoding="utf-8"),
)


@st.cache_resource(show_spinner=False)
def github_store(repo, branch, token):
    return GitHubStore(repo, branch, token)


def get_store():
    try:
        settings = st.secrets.get("github")
    except (FileNotFoundError, StreamlitSecretNotFoundError):
        settings = None
    if settings is None:
        return LocalStore(ROOT / ".data" / "events.sqlite3")
    return github_store(settings.get("repo", ""), settings.get("branch", "main"), settings.get("token", ""))


def go_to(event_id=None):
    if event_id:
        st.query_params["event"] = event_id
    elif "event" in st.query_params:
        del st.query_params["event"]
    st.rerun()


def parse_event_code(value):
    value = value.strip()
    if not EVENT_ID.fullmatch(value):
        try:
            value = parse_qs(urlsplit(value).query).get("event", [""])[0]
        except ValueError:
            value = ""
    if not EVENT_ID.fullmatch(value):
        raise AvailabilityError("请粘贴分享链接或 16 位活动码。")
    return value


@st.dialog("创建活动")
def create_dialog(store):
    start, end = default_range()
    with st.form("new_event", border=False):
        title = st.text_input("活动名称", placeholder="例如：小组讨论", max_chars=80)
        date_range = st.date_input(
            "候选日期", (start, end), min_value=start, max_value=start + timedelta(days=365), format="YYYY/MM/DD"
        )
        mode = st.radio("网格模式", list(GRID_MODES), format_func=GRID_MODES.get, horizontal=True)
        st.caption(f"课节模式每格 50 分钟，所有参与者共用所选校区的[上课时间表]({TIMETABLE_SOURCE})。")
        st.caption(f"默认从今天开始，最多选 {MAX_DAYS} 天。每页最多 7 天，窄屏自动调整为 5 天。")
        if st.form_submit_button("创建并打开", type="primary"):
            try:
                event = create_event(title, date_range, mode)
                store.create(event)
                go_to(event["id"])
            except AvailabilityError as exc:
                st.error(str(exc))
    render_credit()


@st.dialog("加入活动")
def join_dialog():
    with st.form("join_event", border=False):
        code = st.text_input("活动链接或活动码", placeholder="粘贴朋友发给你的链接", max_chars=2048)
        if st.form_submit_button("打开活动"):
            try:
                go_to(parse_event_code(code))
            except AvailabilityError as exc:
                st.error(str(exc))
    render_credit()


def show_event(store, event, read_problem=""):
    event_id = event["id"]
    identity_key = f"identity_{event_id}"
    ack_key = f"ack_{event_id}"
    identity = st.session_state.get(identity_key)
    dates = dates_for(event)
    rows = time_rows(event)
    event_banner(event, dates, rows)
    if dates[-1] < today():
        st.info("候选日期已过去，仍可查看和补填记录。")

    if not identity:
        entry, overview = st.columns([1.8, 1], gap="medium")
        with entry, st.container(key="ft_entry", border=True):
            st.subheader("填写参与信息")
            with st.form(f"identity_form_{event_id}", border=False):
                name_col, code_col = st.columns(2)
                name = name_col.text_input("昵称", max_chars=32, placeholder="大家认得出的名字")
                code = code_col.text_input("编辑码", type="password", max_chars=80, placeholder="至少 6 个字符")
                st.caption("第一次可以自行设定编辑码。以后用相同的昵称和编辑码回来修改。")
                if st.form_submit_button("进入涂格", type="primary"):
                    try:
                        key, display_name = normalize_identity(name, code)
                        member = event["members"].get(key)
                        if member:
                            verify_member(member, code)
                            display_name = member["name"]
                        st.session_state[identity_key] = (key, display_name, code)
                        st.rerun()
                    except AvailabilityError as exc:
                        st.error(str(exc))
        with overview:
            event_overview(event, dates)
        return

    with st.container(key="ft_identity", horizontal=True, vertical_alignment="center"):
        st.text(f"参与者 · {identity[1]}")
        if st.button("切换参与者", type="tertiary"):
            st.session_state.pop(identity_key)
            st.session_state.pop(ack_key, None)
            st.rerun()

    member = event["members"].get(identity[0])
    ack = st.session_state.get(ack_key)
    grid = GRID(
        data={
            "event_id": event_id,
            "dates": [{"iso": day.isoformat(), "label": f"{day.month}/{day.day}",
                       "weekday": f"周{WEEKDAYS[day.weekday()]}"} for day in dates],
            "rows": rows,
            "has_response": member is not None,
            "selected": member["slots"] if member else [],
            "summary": results(event),
            "ack": ack,
        },
        key=f"grid_{event_id}_{identity[0]}",
        on_action_change=lambda: None,
    )
    action = grid.get("action")
    if isinstance(action, dict) and isinstance(action.get("id"), str) and (
        not ack or ack["id"] != action["id"]
    ):
        response = {"id": action["id"], "message": ""}
        if action.get("type") == "save":
            try:
                saved_event = store.update(event_id, lambda latest: save_response(latest, identity, action.get("slots")))
                st.session_state["last_event"] = saved_event
            except AvailabilityError as exc:
                response["message"] = str(exc)
            except sqlite3.Error:
                response["message"] = "本机存储暂时不可用。请再试一次，你涂的格子还在这里。"
        elif action.get("type") == "refresh":
            response["message"] = read_problem
        st.session_state[ack_key] = response
        st.rerun()


try:
    store = get_store()
    event_id = st.query_params.get("event")
    if not event_id:
        create, join = render_cover(local_mode=isinstance(store, LocalStore))
        if create:
            create_dialog(store)
        elif join:
            join_dialog()
    else:
        problem = ""
        try:
            event = store.get(event_id)
            if event:
                st.session_state["last_event"] = event
        except AvailabilityError as exc:
            event = st.session_state.get("last_event")
            if not event or event["id"] != event_id:
                raise
            problem = str(exc)
        st.html(ROOT / "cover.css")
        with st.container(horizontal_alignment="center"):
            with st.container(key="ft_event", width=1120):
                render_masthead(event_page=True)
                if event:
                    show_event(store, event, problem)
                else:
                    st.error("找不到这个活动。请检查链接或活动码。")
                render_credit()
                if isinstance(store, LocalStore):
                    st.caption("本机试用 · 活动记录保存在本机。")
except AvailabilityError as exc:
    st.error(str(exc))
    if st.query_params.get("event") and st.button("返回首页"):
        go_to()
except sqlite3.Error:
    st.error("本机存储不可用。请检查项目目录的写入权限。")
