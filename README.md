# 有空 · FREE-TIME-PRO

一个用涂色网格收集空闲时间的 Streamlit 工具。创建活动，把活动链接发给朋友，大家选完时间就能看到重合最多的时段。

- 创建活动可选整点或海大课节。整点模式每天 08:00–22:00，每格 1 小时；课节模式可选崂山或西海岸校区，每天 12 节，每格 50 分钟。时间均为北京时间，课间不计入空闲。两个校区上午分别排时，第 5–12 节相同。[中国海洋大学教务处作息时间表](https://jwc.ouc.edu.cn/2022/0903/c6752a376517/page.htm)
- 网格模式按活动保存。旧活动继续使用原有整点网格。
- 点击单格，或从一个格子拖到另一个格子涂满一片。从已涂的格子开始拖可以擦除。
- 第一批候选日期默认从当天到 2026 年 12 月 10 日。此后默认从当天起共 14 天。创建时可以改成任意 1–90 天。每页最多 7 天，特别窄的手机显示 5 天。在网格上方切换日期，翻页保留选择。
- 每个活动有自己的链接、活动码和记录。创建后点击「复制活动链接」即可邀请成员。打开链接后先填写昵称和编辑码，再进入个人网格和团队热力图。用原昵称和编辑码可回来修改。
- 保存后可切换到「大家的时间」，查看逐格人数、名单和人数最多的三个时段。已经选过的日期过去后，结果仍可查看。

## 本机启动

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

未配置 GitHub 时可在本机试用，记录保存到 `.data/events.sqlite3`。

## 配置多人共享

1. 建一个**私有** GitHub 数据仓库，例如 `FREE-TIME-PRO-data`，用 README 初始化 `main`。当前代码仓库可保持公开。
2. [创建细粒度 GitHub 访问令牌](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)，仅授权私有数据仓库，仓库权限 `Contents` 选 `Read and write`。
3. 本机把 `.streamlit/secrets.example.toml` 复制为 `.streamlit/secrets.toml`，填写私有仓库和令牌。部署时将同样的 TOML 粘贴到 Streamlit Community Cloud 的 **Advanced settings → Secrets**。应用入口为 `app.py`。

```toml
[github]
repo = "Pan-gao-1219/FREE-TIME-PRO-data"
branch = "main"
token = "填自己的细粒度令牌"
```

重新打开应用，新建活动，再用另一浏览器打开分享链接检查。每个活动的 JSON 保存在私有数据仓库的 `events/` 下。参加者通过活动链接或活动码进入，自行填写参与信息后即可查看该活动的昵称和重合结果。GitHub 令牌由服务端读取。
