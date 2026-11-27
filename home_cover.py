from pathlib import Path

import streamlit as st


def render_masthead(event_page=False):
    right = ('<a class="ft-home-link" href="?" target="_self">← 返回首页</a>'
             if event_page else '<span class="ft-zone">北京时间 <b>UTC+8</b></span>')
    st.html(f"""
        <header class="ft-mast">
          <div class="ft-brand"><span class="ft-logo" aria-hidden="true"><i></i><i></i><i></i></span>
            <strong>有空</strong><span class="ft-brand-name">Free Time Pro</span></div>
          {right}
        </header>""")


def render_credit():
    st.html("""
        <footer class="ft-credit">
          <div><span>作者</span><strong>潘高</strong><span class="ft-school">中国海洋大学</span></div>
          <a href="mailto:1534827320@qq.com" aria-label="联系作者，邮箱 1534827320@qq.com">
            1534827320@qq.com <span aria-hidden="true">↗</span></a>
        </footer>""")


def overlap_preview():
    # Rows are hourly slots; columns are weekdays. Four people overlap on Thursday.
    rows = ((1, 0, 2, 1, 0), (2, 1, 3, 2, 1), (1, 3, 2, 4, 2), (0, 2, 1, 3, 1))
    cells = ["<span></span>", *(f"<span>周{day}</span>" for day in "一二三四五")]
    for hour, counts in enumerate(rows, start=13):
        cells.append(f'<span class="ft-hour">{hour}:00</span>')
        cells.extend(f'<i class="ft-level-{count}">{"4" if count == 4 else ""}</i>' for count in counts)
    return f"""
    <figure class="ft-board" aria-label="示例：四位成员在周四 15:00 至 16:00 都有空">
      <div class="ft-board-top"><strong>团队空闲分布</strong><small>示例 · 4 人</small></div>
      <div class="ft-matrix" aria-hidden="true">{''.join(cells)}</div>
      <div class="ft-scale" aria-hidden="true">0 人
        <span><i class="ft-level-0"></i><i class="ft-level-1"></i><i class="ft-level-2"></i>
        <i class="ft-level-3"></i><i class="ft-level-4"></i></span>4 人
      </div>
      <figcaption><span>全员有空</span><strong>周四 15:00–16:00</strong></figcaption>
    </figure>"""


def render_cover(local_mode):
    st.html(Path(__file__).with_name("cover.css"))
    with st.container(horizontal_alignment="center"):
        with st.container(key="ft_home", width=1120, gap="small"):
            render_masthead()
            with st.container(key="ft_hero", gap="medium"):
                left, right = st.columns([1.1, 1], gap="medium", vertical_alignment="center")
                with left:
                    st.html("""
                        <div class="ft-intro">
                          <h1>找到大家<br><em>都有空的时间</em></h1>
                          <p>邀请成员在网格上涂出空闲时段，<br>一起选出最多人能参加的时间。</p>
                        </div>""")
                    with st.container(key="ft_actions", horizontal=True, gap="small"):
                        create = st.button("创建活动", type="primary", icon=":material/add:", key="ft_create")
                        join = st.button("加入活动", icon=":material/login:", key="ft_join")
                with right:
                    st.html(overlap_preview())
                st.html("""
                    <dl class="ft-specs">
                      <div><dt>网格模式</dt><dd>整点 / 课节</dd></div>
                      <div><dt>课节校区</dt><dd>崂山 / 西海岸</dd></div>
                      <div><dt>每页日期</dt><dd>最多 7 天</dd></div>
                    </dl>""")
            render_credit()
            if local_mode:
                st.caption("本机试用 · 活动记录保存在本机。")
    return create, join
