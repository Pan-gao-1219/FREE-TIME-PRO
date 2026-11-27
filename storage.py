import base64
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import time

import requests

from availability import AvailabilityError, EVENT_ID


def _path(event_id):
    if not EVENT_ID.fullmatch(event_id):
        raise AvailabilityError("活动码格式不对。")
    return f"events/{event_id}.json"


class LocalStore:
    def __init__(self, filename):
        self.filename = Path(filename)

    def _connect(self):
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.filename, timeout=8)
        db.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        return db

    def get(self, event_id):
        _path(event_id)
        with closing(self._connect()) as db:
            row = db.execute("SELECT data FROM events WHERE id = ?", (event_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def create(self, event):
        _path(event["id"])
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO events VALUES (?, ?)", (event["id"], json.dumps(event, ensure_ascii=False)))

    def update(self, event_id, change):
        _path(event_id)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM events WHERE id = ?", (event_id,)).fetchone()
            if row is None:
                raise AvailabilityError("找不到这个活动。")
            event = json.loads(row[0])
            change(event)
            db.execute("UPDATE events SET data = ? WHERE id = ?", (json.dumps(event, ensure_ascii=False), event_id))
        return event


class GitHubStore:
    def __init__(self, repo, branch, token):
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo, re.ASCII) or not branch or not token:
            raise AvailabilityError("请在 Streamlit Secrets 中检查 GitHub 仓库、分支和令牌。")
        self.base = f"https://api.github.com/repos/{repo}"
        self.branch = branch
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Cache-Control": "no-cache",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        response = self._request("GET", "")
        self._check(response)
        if not response.json().get("private"):
            raise AvailabilityError("请配置私有 GitHub 数据仓库，参与者的记录会保存在其中。")

    def _request(self, method, path, **kwargs):
        try:
            return requests.request(method, self.base + path, headers=self.headers, timeout=(4, 9), **kwargs)
        except requests.RequestException:
            raise AvailabilityError("暂时连不上 GitHub。请稍后重试。") from None

    @staticmethod
    def _check(response):
        if response.ok:
            return
        status = response.status_code
        if status == 429 or response.headers.get("X-RateLimit-Remaining") == "0":
            raise AvailabilityError("GitHub 暂时限制了请求频率。请稍后重试。")
        if status in (401, 403, 404):
            raise AvailabilityError("GitHub 数据仓库不可访问。请检查令牌权限和数据分支。")
        raise AvailabilityError(f"GitHub 存储暂时未完成请求（{status}）。请稍后重试。")

    def _read(self, event_id):
        response = self._request("GET", f"/contents/{_path(event_id)}", params={"ref": self.branch})
        if response.status_code == 404:
            return None, None
        self._check(response)
        file = response.json()
        try:
            data = json.loads(base64.b64decode(file["content"]))
            if data["id"] != event_id:
                raise ValueError("Event ID mismatch")
            return data, file["sha"]
        except (KeyError, TypeError, ValueError):
            raise AvailabilityError("活动数据无法读取。请联系管理员检查数据仓库。") from None

    def _write(self, event, sha=None):
        content = json.dumps(event, ensure_ascii=False, indent=2).encode()
        body = {
            "branch": self.branch,
            "message": "Save availability event",
            "content": base64.b64encode(content).decode("ascii"),
        }
        if sha:
            body["sha"] = sha
        return self._request("PUT", f"/contents/{_path(event['id'])}", json=body)

    def get(self, event_id):
        return self._read(event_id)[0]

    def create(self, event):
        for attempt in range(4):
            response = self._write(event)
            if response.status_code != 409:
                self._check(response)
                return
            time.sleep(0.15 * (attempt + 1))
        raise AvailabilityError("多人正在创建或保存活动。请再试一次。")

    def update(self, event_id, change):
        for attempt in range(4):
            event, sha = self._read(event_id)
            if event is None:
                raise AvailabilityError("找不到这个活动。")
            change(event)
            response = self._write(event, sha)
            stale = response.status_code == 409 or (
                response.status_code == 422 and "sha" in response.text.lower()
            )
            if not stale:
                self._check(response)
                return event
            time.sleep(0.15 * (attempt + 1))
        raise AvailabilityError("多人正在保存活动。请再点一次保存，你涂的格子还在这里。")
