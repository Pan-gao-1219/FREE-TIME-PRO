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


class AvailabilityError(Exception):
    pass


def today():
    return datetime.now(CHINA).date()


def default_range():
    start = today()
    end = start + timedelta(days=13)
    return start, FIRST_END if start <= FIRST_END <= end else end


def create_event(title, dates):
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
    valid = {f"{day.isoformat()}T{hour:02d}" for day in dates_for(event)
             for hour in range(START_HOUR, END_HOUR)}
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
