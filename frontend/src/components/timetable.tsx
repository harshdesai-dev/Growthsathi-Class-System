"use client";
import { useEffect, useState } from "react";
import { allRows, message, type Row } from "@/lib/api";
import type { Scope } from "@/lib/resources";
import { text } from "./ui";

function dateKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
function shifted(key: string, days: number): string {
  const date = new Date(`${key}T12:00:00`);
  date.setDate(date.getDate() + days);
  return dateKey(date);
}
export function Timetable({
  scope,
  revision,
  actions,
}: {
  scope: Scope;
  revision: number;
  actions: (row: Row) => React.ReactNode;
}) {
  const [anchor, setAnchor] = useState(() => dateKey(new Date()));
  const [view, setView] = useState("week");
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const weekday = new Date(`${anchor}T12:00:00`).getDay();
  const start =
    view === "week" ? shifted(anchor, -((weekday + 6) % 7)) : anchor;
  const end = view === "week" ? shifted(start, 6) : start;
  // biome-ignore lint/correctness/useExhaustiveDependencies: refresh after lecture mutations.
  useEffect(() => {
    let active = true;
    setBusy(true);
    setError("");
    allRows(`/api/timetable/?date_from=${start}&date_to=${end}`)
      .then((data) => {
        if (active) setRows(data);
      })
      .catch((e) => {
        if (active) setError(message(e));
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [start, end, revision]);
  const enriched: Row[] = rows.map((row) => ({
    ...row,
    class_name:
      scope.batches.find((batch) => batch.id === row.batch)?.class_name ?? "",
  }));
  const shown = enriched.filter((row) =>
    Object.entries(filters).every(
      ([key, value]) =>
        !value || String(row[key as keyof typeof row]) === value,
    ),
  );
  const days = Array.from(
    {
      length:
        view === "week" ? (shown.some((row) => row.date === end) ? 7 : 6) : 1,
    },
    (_, index) => shifted(start, index),
  );
  return (
    <section className="card">
      <div className="section-heading">
        <h2>Lecture schedule</h2>
        <div className="row-actions">
          <button
            type="button"
            className="secondary"
            aria-pressed={view === "week"}
            onClick={() => setView("week")}
          >
            Week view
          </button>
          <button
            type="button"
            className="secondary"
            aria-pressed={view === "day"}
            onClick={() => setView("day")}
          >
            Day view
          </button>
        </div>
      </div>
      <div className="row-actions">
        <button
          type="button"
          className="secondary"
          onClick={() => setAnchor(shifted(anchor, view === "week" ? -7 : -1))}
        >
          Previous period
        </button>
        <label>
          Schedule date
          <input
            type="date"
            value={anchor}
            onChange={(event) => {
              if (event.target.value) setAnchor(event.target.value);
            }}
          />
        </label>
        <button
          type="button"
          className="secondary"
          onClick={() => setAnchor(dateKey(new Date()))}
        >
          Today
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => setAnchor(shifted(anchor, view === "week" ? 7 : 1))}
        >
          Next period
        </button>
      </div>
      <p>
        {start} to {end}
      </p>
      <div className="schedule-filters">
        {[
          ["class_name", "Class"],
          ["batch_name", "Batch"],
          ["teacher_name", "Teacher"],
          ["subject_name", "Subject"],
          ["room", "Room"],
        ].map(([key, label]) => (
          <label key={key}>
            {label}
            <select
              value={filters[key] ?? ""}
              onChange={(event) =>
                setFilters({ ...filters, [key]: event.target.value })
              }
            >
              <option value="">
                All{" "}
                {label === "Class"
                  ? "classes"
                  : label === "Batch"
                    ? "batches"
                    : `${label.toLowerCase()}s`}
              </option>
              {[
                ...new Set(
                  enriched
                    .map((row) => String(row[key as keyof typeof row] ?? ""))
                    .concat(filters[key] ?? "")
                    .filter(Boolean),
                ),
              ]
                .sort()
                .map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
            </select>
          </label>
        ))}
      </div>
      {busy ? (
        <p role="status">Loading schedule...</p>
      ) : error ? (
        <p role="alert">{error}</p>
      ) : (
        <>
          <p>{shown.length} lectures in this period</p>
          <div
            className={`schedule-grid ${view === "day" ? "schedule-day" : ""}`}
          >
            {days.map((day) => (
              <section className="schedule-column" key={day}>
                <h3>
                  {new Date(`${day}T12:00:00`).toLocaleDateString(undefined, {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                  })}
                </h3>
                {shown.filter((row) => row.date === day).length === 0 && (
                  <p className="muted">No lectures</p>
                )}
                {shown
                  .filter((row) => row.date === day)
                  .map((row) => (
                    <article className="lecture-card" key={row.id}>
                      <strong>{text(row.subject_name)}</strong>
                      <p>
                        {String(row.starts_at).slice(0, 5)} -{" "}
                        {String(row.ends_at).slice(0, 5)}
                      </p>
                      <p>
                        {text(row.class_name)} / {text(row.batch_name)}
                      </p>
                      <p>{text(row.teacher_name)}</p>
                      <p>Room: {text(row.room) || "Not assigned"}</p>
                      {row.is_cancelled === true && <strong>Cancelled</strong>}
                      <div className="row-actions">{actions(row)}</div>
                    </article>
                  ))}
              </section>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
