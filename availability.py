from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import scrypt
from hmac import compare_digest
import re
import secrets
import unicodedata


START_HOUR = 8
END_HOUR = 22
MAX_DAYS = 90
FIRST_END = date(2026, 12, 10)
CHINA = timezone(timedelta(hours=8))
EVENT_ID = re.compile(r"[0-9a-f]{16}")
TIMETABLE_SOURCE = "https://jwc.ouc.edu.cn/2022/0903/c6752a376517/page.htm"
GRID_MODES = {
    "hourly": "每格 1 小时",
    "laoshan_2022": "海大课节 · 崂山",
    "west_coast_2022": "海大课节 · 西海岸",
}
# The OUC timetable effective autumn 2022. Versioned keys preserve past activities.
CAMPUS_MORNINGS = {
    "laoshan_2022": ("08:00", "09:00", "10:10", "11:10"),
    "west_coast_2022": ("08:30", "09:25", "10:30", "11:25"),
}
AFTERNOON_AND_EVENING = ("13:30", "14:30", "15:30", "16:30", "17:30", "18:30", "19:30", "20:30")


class AvailabilityError(Exception):
    pass


def today():
    return datetime.now(CHINA).date()


def default_range():
    start = today()
    end = start + timedelta(days=13)
    return start, FIRST_END if start <= FIRST_END <= end else end


def time_rows(event):
    mode = event.get("grid_mode", "hourly")
    if mode == "hourly":
        # Existing records use the two-digit hour as the slot key.
        return [{"key": f"{hour:02d}", "start": f"{hour:02d}:00", "end": f"{hour+1:02d}:00", "lesson": ""}
                for hour in range(START_HOUR, END_HOUR)]
    if mode not in CAMPUS_MORNINGS:
        raise AvailabilityError("无法识别此活动的网格模式。")
    rows = []
    for number, start in enumerate(CAMPUS_MORNINGS[mode] + AFTERNOON_AND_EVENING, start=1):
        hour, minute = map(int, start.split(":"))
        end_hour, end_minute = divmod(hour * 60 + minute + 50, 60)
        rows.append({"key": start, "start": start, "end": f"{end_hour:02d}:{end_minute:02d}", "lesson": f"第{number}节"})
    return rows


def create_event(title, dates, grid_mode="hourly"):
    if grid_mode not in GRID_MODES:
        raise AvailabilityError("请选择活动的网格模式。")
    title = title.strip()
    if not title or len(title) > 80:
        raise AvailabilityError("请输入 1–80 个字的活动名称。")
    if len(dates) != 2:
        raise AvailabilityError("请选择起始和结束日期。")
    start, end = dates
    if not 0 <= (end - start).days < MAX_DAYS:
        raise AvailabilityError(f"每个活动可以选择 1–{MAX_DAYS} 天。")
    return {
        "id": secrets.token_hex(8),
        "title": title,
        "grid_mode": grid_mode,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "members": {},
    }


def dates_for(event):
    start = date.fromisoformat(event["start"])
    end = date.fromisoformat(event["end"])
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def normalize_identity(name, code):
    name = " ".join(unicodedata.normalize("NFKC", name).split())
    if not name or len(name) > 32:
        raise AvailabilityError("请输入 1–32 个字的昵称。")
    if not 6 <= len(code) <= 80:
        raise AvailabilityError("编辑码需要 6–80 个字符。")
    return name.casefold(), name


def _code_hash(code, salt):
    return scrypt(code.encode(), salt=salt, n=2**14, r=8, p=1).hex()


def verify_member(member, code):
    expected = _code_hash(code, bytes.fromhex(member["salt"]))
    if not compare_digest(expected, member["code_hash"]):
        raise AvailabilityError("这个昵称已有人使用。请输入原编辑码，或换个昵称。")


def save_response(event, identity, selected):
    key, name, code = identity
    rows = time_rows(event)
    valid = {f"{day.isoformat()}T{row['key']}" for day in dates_for(event) for row in rows}
    if (not isinstance(selected, list) or len(selected) > len(valid)
            or any(not isinstance(slot, str) or slot not in valid for slot in selected)):
        raise AvailabilityError("有时间格不属于这个活动。请重新打开活动再试。")

    member = event["members"].get(key)
    if member:
        verify_member(member, code)
    else:
        salt = secrets.token_bytes(16)
        member = {"name": name, "salt": salt.hex(), "code_hash": _code_hash(code, salt)}
        event["members"][key] = member
    member["slots"] = sorted(set(selected))


def results(event):
    people = defaultdict(list)
    for member in event["members"].values():
        for slot in member["slots"]:
            people[slot].append(member["name"])

    top = sorted(people, key=lambda slot: (-len(people[slot]), slot))[:3]
    return {"people": dict(people), "top": top, "total": len(event["members"])}
