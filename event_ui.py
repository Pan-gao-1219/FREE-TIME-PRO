from html import escape

import streamlit as st

from availability import GRID_MODES


COPY_LINK = st.components.v2.component(
    "event_invite_link",
    html="""
      <button id="copy" type="button">复制活动链接 <span aria-hidden="true">↗</span></button>
      <span id="notice" role="status"></span>
      <input id="manual" aria-label="手动复制活动链接" readonly hidden>
    """,
    css="""
      button, input {font:600 14px/1.4 Inter,"Microsoft YaHei",sans-serif; box-sizing:border-box;}
      button {cursor:pointer; border:1px solid #c2f0dc; border-radius:9px; background:#c2f0dc;
        color:#123c33; padding:10px 15px; min-height:42px;}
      button:hover {background:#ddffec;} button:focus-visible {outline:3px solid white; outline-offset:-4px;}
      button span {padding-left:6px;} #notice {display:block; color:#e3f4ed; font:13px/1.6 sans-serif;}
      #notice:not(:empty) {margin-top:5px;} input {width:100%; margin-top:5px; padding:5px;}
    """,
    js="""
      export default function({parentElement, data}) {
        const button = parentElement.querySelector("#copy");
        const notice = parentElement.querySelector("#notice");
        const manual = parentElement.querySelector("#manual");
        button.onclick = async () => {
          const url = new URL(window.location.href);
          url.searchParams.set("event", data.id);
          try {
            await navigator.clipboard.writeText(url.href);
            manual.hidden = true;
            notice.textContent = "已复制，可以发给成员了";
          } catch {
            manual.value = url.href;
            manual.hidden = false;
            manual.focus();
            manual.select();
            notice.textContent = "请手动复制下方链接";
          }
        };
      }
    """,
)


def event_banner(event, dates, rows):
    with st.container(key="ft_event_banner"):
        info, invite = st.columns([3, 1], gap="small", vertical_alignment="center")
        with info:
            st.html(f"""
                <div class="ft-event-info">
                  <small>活动工作台 · {GRID_MODES[event.get("grid_mode", "hourly")]}</small><h1>{escape(event["title"])}</h1>
                  <p><span>{dates[0]:%Y/%m/%d} — {dates[-1]:%Y/%m/%d}</span>
                  <span>北京时间 · {rows[0]["start"]}–{rows[-1]["end"]}</span></p>
                </div>""")
        with invite:
            COPY_LINK(data={"id": event["id"]}, key=f"invite_{event['id']}")


def event_overview(event, dates):
    st.html(f"""
        <section class="ft-overview">
          <h3>活动概况</h3>
          <dl><div><dt>已提交</dt><dd>{len(event['members'])} 人</dd></div>
          <div><dt>候选日期</dt><dd>{len(dates)} 天</dd></div>
          <div><dt>每格时长</dt><dd>{"1 小时" if event.get("grid_mode", "hourly") == "hourly" else "1 节 · 50 分钟"}</dd></div></dl>
          <p>成员提交后，可在「大家的时间」查看重合时段和有空的人。</p>
        </section>""")
