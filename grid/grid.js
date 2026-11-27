const planners = new WeakMap();

export default function renderComponent({ parentElement, data, setTriggerValue }) {
  const planner = parentElement.querySelector("#planner");
  if (!planner) return;
  if (!planners.has(planner)) planners.set(planner, createPlanner(planner));
  planners.get(planner)(data, setTriggerValue);
}

function createPlanner(planner) {
  const byId = (id) => planner.querySelector(`#${id}`);
  const grid = byId("grid");
  const weekPicker = byId("week");
  let pageSize = 7;

  let data;
  let mode;
  let page = 0;
  let selected = new Set();
  let saved = new Set();
  let pending;
  let drag;
  let cells = [];
  let detailSlot;
  let sendAction;

  function message(text, error = false) {
    const status = byId("message");
    status.textContent = text;
    status.hidden = !text;
    status.dataset.error = String(error);
  }

  function storeAction(type) {
    if (pending) return;
    const random = crypto.getRandomValues(new Uint32Array(2));
    pending = { id: `${random[0]}-${random[1]}`, type };
    if (type === "save") pending.slots = [...selected];
    message(type === "save" ? "正在保存…" : "正在刷新…");
    updateActions();
    sendAction("action", pending);
  }

  function dirty() {
    return selected.size !== saved.size || [...selected].some((slot) => !saved.has(slot));
  }

  function visibleDays() {
    return data.dates.slice(page * pageSize, (page + 1) * pageSize);
  }

  function rebuildDatePicker() {
    const choices = [];
    for (let i = 0; i < data.dates.length; i += pageSize) {
      const first = data.dates[i].label;
      const last = data.dates[Math.min(i + pageSize, data.dates.length) - 1].label;
      choices.push(new Option(first === last ? first : `${first} – ${last}`, i / pageSize));
    }
    weekPicker.replaceChildren(...choices);
  }

  function daysPerPage(width) {
    return width > 0 && width < 328 ? 5 : 7;
  }

  new ResizeObserver(([entry]) => {
    if (!data || !entry.contentRect.width) return;
    const size = daysPerPage(entry.contentRect.width);
    if (size === pageSize) return;
    if (drag) stopPaint();
    const firstVisible = page * pageSize;
    pageSize = size;
    page = Math.floor(firstVisible / size);
    rebuildDatePicker();
    render();
  }).observe(planner);

  function slotLabel(slot) {
    const date = data.dates.find((day) => day.iso === slot.slice(0, 10));
    const row = data.rows.find((item) => item.key === slot.slice(11));
    return [date.label, date.weekday, row.lesson, `${row.start}–${row.end}`].filter(Boolean).join(" ");
  }

  function node(tag, className, label) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (label) element.textContent = label;
    return element;
  }

  function updateActions() {
    const isSaved = data.has_response && !dirty();
    byId("save").disabled = Boolean(pending) || isSaved;
    byId("save").textContent = isSaved ? "已保存" : "保存我的时间";
    byId("clear").disabled = Boolean(pending) || !cells.some((cell) => selected.has(cell.dataset.slot));
    byId("refresh").disabled = Boolean(pending);
  }

  function updateCellColors() {
    for (const cell of cells) {
      const active = selected.has(cell.dataset.slot);
      cell.setAttribute("aria-pressed", String(active));
      cell.textContent = active ? "✓" : "";
    }
    updateActions();
  }

  function showDetail(slot) {
    detailSlot = slot;
    const names = data.summary.people[slot] || [];
    const detail = byId("detail");
    detail.hidden = false;
    detail.textContent = `${slotLabel(slot)} · ${names.length ? `${names.length} 人有空：${names.join("、")}` : "还没有人标记有空"}`;
    for (const cell of cells) cell.setAttribute("aria-current", String(cell.dataset.slot === slot));
  }

  function renderGroup() {
    const { top, total, people } = data.summary;
    byId("people-count").textContent = `${total} 人已提交`;
    byId("empty-results").hidden = top.length > 0;
    const suggestions = top.map((slot) => {
      const button = node("button");
      button.append(node("span", "", slotLabel(slot)), node("b", "", `${people[slot].length} 人`));
      button.type = "button";
      button.addEventListener("click", () => {
        const index = data.dates.findIndex((day) => day.iso === slot.slice(0, 10));
        detailSlot = slot;
        page = Math.floor(index / pageSize);
        render();
        cells.find((cell) => cell.dataset.slot === slot)?.focus({ preventScroll: true });
      });
      return button;
    });
    byId("recommendations").replaceChildren(...suggestions);
  }

  function render() {
    const editing = mode === "mine";
    const days = visibleDays();
    planner.dataset.mode = mode;
    byId("view-heading").textContent = editing ? "标记空闲时段" : "团队空闲热力图";
    byId("scale").hidden = editing;
    byId("mine").setAttribute("aria-pressed", String(editing));
    byId("group").setAttribute("aria-pressed", String(!editing));
    byId("group-summary").hidden = editing;
    byId("editor-actions").hidden = !editing;
    byId("detail").hidden = true;
    byId("previous").disabled = page === 0;
    byId("next").disabled = (page + 1) * pageSize >= data.dates.length;
    weekPicker.value = String(page);
    weekPicker.parentElement.hidden = weekPicker.options.length === 1;
    byId("guide").textContent = editing
      ? "点选或拖涂空闲时段，翻页后可一起保存。"
      : "数字是有空的人数，颜色越深表示人越多。点格子看都有谁。";

    grid.classList.toggle("editor", editing);
    grid.style.setProperty("--days", days.length);
    grid.style.setProperty("--page-size", pageSize);
    const contents = document.createDocumentFragment();
    contents.append(node("span", "hour", "时段"));
    for (const day of days) {
      const heading = node("div", "day", day.label);
      heading.append(node("small", "", day.weekday));
      contents.append(heading);
    }

    cells = [];
    grid.classList.toggle("campus", Boolean(data.rows[0].lesson));
    data.rows.forEach((period, row) => {
      const axis = node("span", "hour", period.lesson || period.start);
      if (period.lesson) axis.append(node("small", "", `${period.start}–${period.end}`));
      contents.append(axis);
      days.forEach((day, column) => {
        const slot = `${day.iso}T${period.key}`;
        const cell = node("button", "cell");
        cell.type = "button";
        cell.dataset.slot = slot;
        cell.dataset.row = row;
        cell.dataset.column = column;
        const label = slotLabel(slot);
        if (editing) {
          cell.setAttribute("aria-label", label);
          cell.title = label;
        } else {
          const count = data.summary.people[slot]?.length || 0;
          const share = count / Math.max(1, data.summary.total);
          cell.textContent = count || "";
          if (count) {
            cell.style.background = `hsl(162 49% ${92 - 67 * share}%)`;
            cell.style.color = share > .59 ? "white" : "#172a25";
          }
          cell.title = `${label} · ${count} 人有空`;
          cell.setAttribute("aria-label", cell.title);
        }
        contents.append(cell);
        cells.push(cell);
      });
    });
    if (!data.rows[0].lesson) contents.append(node("span", "hour", data.rows.at(-1).end));
    grid.replaceChildren(contents);
    if (editing) updateCellColors();
    else {
      renderGroup();
      if (cells.some((cell) => cell.dataset.slot === detailSlot)) showDetail(detailSlot);
      updateActions();
    }
  }

  function navigate(pageNumber) {
    page = pageNumber;
    detailSlot = undefined;
    render();
  }

  function paintTo(cell) {
    if (drag.end === cell) return;
    drag.end = cell;
    const row = Number(cell.dataset.row);
    const column = Number(cell.dataset.column);
    selected = new Set(drag.before);
    for (const candidate of cells) {
      const r = Number(candidate.dataset.row);
      const c = Number(candidate.dataset.column);
      if (r >= Math.min(row, drag.row) && r <= Math.max(row, drag.row)
          && c >= Math.min(column, drag.column) && c <= Math.max(column, drag.column)) {
        if (drag.paint) selected.add(candidate.dataset.slot);
        else selected.delete(candidate.dataset.slot);
      }
    }
    updateCellColors();
  }

  grid.addEventListener("pointerdown", (event) => {
    const cell = event.target.closest(".cell");
    if (mode !== "mine" || !cell || pending || drag || event.button !== 0) return;
    event.preventDefault();
    drag = {
      id: event.pointerId,
      row: Number(cell.dataset.row),
      column: Number(cell.dataset.column),
      before: selected,
      paint: !selected.has(cell.dataset.slot),
      events: new AbortController(),
    };
    const options = { capture: true, signal: drag.events.signal };
    window.addEventListener("pointermove", movePaint, options);
    window.addEventListener("pointerup", finishPaint, options);
    window.addEventListener("pointercancel", cancelPaint, options);
    window.addEventListener("blur", cancelPaint, options);
    message("");
    paintTo(cell);
  });

  function paintAtPoint(event) {
    const cell = grid.getRootNode().elementFromPoint(event.clientX, event.clientY)?.closest(".cell");
    if (cell) paintTo(cell);
  }

  function stopPaint() {
    drag.events.abort();
    drag = undefined;
  }

  function movePaint(event) {
    if (drag?.id !== event.pointerId) return;
    if (event.pointerType === "mouse" && event.buttons === 0) stopPaint();
    else paintAtPoint(event);
  }

  function finishPaint(event) {
    if (drag?.id !== event.pointerId) return;
    paintAtPoint(event);
    stopPaint();
  }

  function cancelPaint(event) {
    if (!drag || (event.type !== "blur" && drag.id !== event.pointerId)) return;
    selected = drag.before;
    stopPaint();
    updateCellColors();
  }

  grid.addEventListener("click", (event) => {
    const cell = event.target.closest(".cell");
    if (!cell) return;
    if (mode === "group") showDetail(cell.dataset.slot);
    else if (!pending && event.detail === 0) {
      if (selected.has(cell.dataset.slot)) selected.delete(cell.dataset.slot);
      else selected.add(cell.dataset.slot);
      message("");
      updateCellColors();
    }
  });

  byId("mine").addEventListener("click", () => { mode = "mine"; render(); });
  byId("group").addEventListener("click", () => { mode = "group"; render(); });
  byId("previous").addEventListener("click", () => navigate(page - 1));
  byId("next").addEventListener("click", () => navigate(page + 1));
  weekPicker.addEventListener("change", () => navigate(Number(weekPicker.value)));
  byId("save").addEventListener("click", () => storeAction("save"));
  byId("refresh").addEventListener("click", () => storeAction("refresh"));
  byId("clear").addEventListener("click", () => {
    for (const cell of cells) selected.delete(cell.dataset.slot);
    message("");
    updateCellColors();
  });

  return function update(next, setTriggerValue) {
    sendAction = setTriggerValue;
    const opening = !data || next.event_id !== data.event_id;
    if (opening) {
      mode = "mine";
      page = 0;
      selected = new Set(next.selected);
      saved = new Set(next.selected);
    } else if (!pending && !dirty()) {
      selected = new Set(next.selected);
      saved = new Set(next.selected);
    }
    if (pending && next.ack?.id === pending.id) {
      if (next.ack.message) message(next.ack.message, true);
      else if (pending.type === "save") {
        selected = new Set(next.selected);
        saved = new Set(next.selected);
        message("空闲时间已保存。");
      } else message("结果已刷新。");
      pending = undefined;
    }
    data = next;
    planner.hidden = false;
    if (opening) {
      pageSize = daysPerPage(planner.clientWidth);
      rebuildDatePicker();
    }
    render();
  };
}
