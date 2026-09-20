"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { allRows, type Row } from "@/lib/api";
import { inr, number } from "@/lib/format";

type DashboardSection = {
  title: string;
  module: string;
  columns: [string, string][];
  rows: Row[];
};

type Day = { label: string; attended: number; total: number };

function numeric(stats: Record<string, unknown>, key: string) {
  const value = Number(stats[key]);
  return Number.isFinite(value) ? value : 0;
}

function shortDate(date: Date) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
  }).format(date);
}

export function AdminDashboard({
  stats,
  sections,
}: {
  stats: Record<string, unknown>;
  sections: DashboardSection[];
}) {
  const [attendance, setAttendance] = useState<Row[] | null>(null);
  const [trendError, setTrendError] = useState(false);

  useEffect(() => {
    const start = new Date();
    start.setDate(start.getDate() - 6);
    const from = start.toLocaleDateString("en-CA");
    let active = true;
    allRows(`/api/attendance/?date_from=${from}`)
      .then((rows) => active && setAttendance(rows))
      .catch(() => active && setTrendError(true));
    return () => {
      active = false;
    };
  }, []);

  const days = useMemo<Day[]>(() => {
    const list = Array.from({ length: 7 }, (_, index) => {
      const date = new Date();
      date.setHours(0, 0, 0, 0);
      date.setDate(date.getDate() - (6 - index));
      return {
        date: date.toLocaleDateString("en-CA"),
        label: shortDate(date),
        attended: 0,
        total: 0,
      };
    });
    for (const row of attendance ?? []) {
      const day = list.find((item) => item.date === row.date);
      if (!day) continue;
      day.total += 1;
      if (row.status === "PRESENT" || row.status === "LATE") day.attended += 1;
    }
    return list.map(({ label, attended, total }) => ({
      label,
      attended,
      total,
    }));
  }, [attendance]);

  const todayTotal =
    numeric(stats, "Present today") +
    numeric(stats, "Absent today") +
    numeric(stats, "Late today");
  const todayAttendance = todayTotal
    ? ((numeric(stats, "Present today") + numeric(stats, "Late today")) * 100) /
      todayTotal
    : null;
  const collected = numeric(stats, "Fees collected");
  const pending = numeric(stats, "Fees pending");
  const overdue = numeric(stats, "Overdue fees");
  const totalFees = collected + pending;
  const collection = totalFees ? Math.round((collected * 100) / totalFees) : 0;
  const lowAttendance =
    sections.find((section) => section.title === "Low attendance")?.rows ?? [];
  const classes =
    sections.find((section) => section.title === "Today's classes")?.rows ?? [];
  const exams =
    sections.find((section) => section.title === "Upcoming exams")?.rows ?? [];
  const trendHasHistory = days.filter((day) => day.total > 0).length > 1;
  const maxTrend = Math.max(
    ...days.map((day) => (day.total ? (day.attended / day.total) * 100 : 0)),
    1,
  );
  const attention = [
    lowAttendance.length
      ? {
          tone: "danger",
          title: "Low attendance",
          detail: `${lowAttendance.length} ${lowAttendance.length === 1 ? "student is" : "students are"} below the attendance threshold.`,
          href: "/portal/attendance",
          action: "Review attendance",
        }
      : null,
    overdue > 0
      ? {
          tone: "warning",
          title: "Overdue fees",
          detail: `${inr(overdue)} is overdue. This amount is included in pending fees.`,
          href: "/portal/fees",
          action: "Review fees",
        }
      : null,
    numeric(stats, "Exams awaiting marks") > 0
      ? {
          tone: "info",
          title: "Marks awaiting entry",
          detail: `${number(stats["Exams awaiting marks"])} exam${numeric(stats, "Exams awaiting marks") === 1 ? "" : "s"} still need marks.`,
          href: "/portal/exams",
          action: "Open exams",
        }
      : null,
  ].filter(Boolean) as {
    tone: string;
    title: string;
    detail: string;
    href: string;
    action: string;
  }[];

  return (
    <div className="admin-dashboard">
      <section className="primary-kpis" aria-label="Institute overview">
        <Metric
          icon="♙"
          label="Students"
          value={number(stats.Students)}
          detail={`${number(stats.Batches)} active batches`}
        />
        <Metric
          icon="✓"
          label="Attendance today"
          value={todayAttendance === null ? "—" : `${number(todayAttendance)}%`}
          detail={
            todayTotal
              ? `${number(stats["Present today"])} present · ${number(stats["Absent today"])} absent`
              : "No attendance recorded today"
          }
        />
        <Metric
          icon="₹"
          label="Fees collected"
          value={inr(collected)}
          detail={
            totalFees ? `${collection}% of expected fees` : "No fee plans yet"
          }
        />
        <Metric
          icon="◷"
          label="Fees pending"
          value={inr(pending)}
          detail={
            overdue > 0 ? `${inr(overdue)} overdue` : "No overdue installments"
          }
          tone={overdue > 0 ? "warning" : undefined}
        />
      </section>

      <section className="operational-strip" aria-label="Operational summary">
        <span>
          <strong>{number(stats.Teachers)}</strong> teachers
        </span>
        <span>
          <strong>{number(stats["Classes today"])}</strong> classes today
        </span>
        <span>
          <strong>{number(stats["Upcoming exams"])}</strong> upcoming exams
        </span>
        <span>
          <strong>
            {number(
              stats["Attendance threshold"] ??
                stats["Attendance threshold (%)"],
            )}
            %
          </strong>{" "}
          attendance threshold
        </span>
      </section>

      <div className="dashboard-grid">
        <section className="card trend-card">
          <div className="section-heading">
            <div>
              <h2>Attendance trend</h2>
              <p className="muted">Last seven days of recorded attendance.</p>
            </div>
            <Link href="/portal/attendance">View attendance</Link>
          </div>
          {attendance === null && !trendError ? (
            <p className="chart-empty">Loading attendance history…</p>
          ) : trendHasHistory ? (
            <div
              className="attendance-chart"
              role="img"
              aria-label="Attendance percentage by day for the last seven days"
            >
              {days.map((day) => {
                const percentage = day.total
                  ? Math.round((day.attended / day.total) * 100)
                  : 0;
                return (
                  <div className="trend-day" key={day.label}>
                    <span className="trend-value">
                      {day.total ? `${percentage}%` : ""}
                    </span>
                    <div className="trend-track">
                      <span
                        style={{ height: `${(percentage / maxTrend) * 100}%` }}
                      />
                    </div>
                    <small>{day.label}</small>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="chart-empty">
              More attendance history is needed to show a trend.
            </p>
          )}
        </section>
        <section className="card collection-card">
          <div className="section-heading">
            <div>
              <h2>Fee collection</h2>
              <p className="muted">Collected versus outstanding fees.</p>
            </div>
            <Link href="/portal/fees">View fees</Link>
          </div>
          {totalFees ? (
            <div className="collection-body">
              <div
                className="donut"
                style={
                  {
                    "--collection": `${collection * 3.6}deg`,
                  } as React.CSSProperties
                }
              >
                <strong>{collection}%</strong>
                <span>collected</span>
              </div>
              <div className="collection-legend">
                <span>
                  <i className="legend-collected" />
                  Collected <strong>{inr(collected)}</strong>
                </span>
                <span>
                  <i className="legend-pending" />
                  Pending <strong>{inr(pending)}</strong>
                </span>
                {overdue > 0 && (
                  <span>
                    <i className="legend-overdue" />
                    Overdue <strong>{inr(overdue)}</strong>
                  </span>
                )}
              </div>
            </div>
          ) : (
            <p className="chart-empty">No fee plans are available yet.</p>
          )}
        </section>
        <section className="card attention-card">
          <div className="section-heading">
            <div>
              <h2>Needs attention</h2>
              <p className="muted">
                Operational items that may need a follow-up.
              </p>
            </div>
          </div>
          {attention.length ? (
            <div className="attention-list">
              {attention.map((item) => (
                <Link
                  className={`attention-item ${item.tone}`}
                  href={item.href}
                  key={item.title}
                >
                  <span aria-hidden="true">!</span>
                  <div>
                    <strong>{item.title}</strong>
                    <small>{item.detail}</small>
                  </div>
                  <em>{item.action} →</em>
                </Link>
              ))}
            </div>
          ) : (
            <div className="on-track">
              <span>✓</span>
              <div>
                <strong>Everything looks on track.</strong>
                <small>
                  There are no current attendance, fee, or marks follow-ups.
                </small>
              </div>
            </div>
          )}
        </section>
      </div>

      <div className="dashboard-grid dashboard-grid-bottom">
        <section className="card activity-card">
          <div className="section-heading">
            <div>
              <h2>{classes.length ? "Today’s classes" : "Upcoming exams"}</h2>
              <p className="muted">
                {classes.length
                  ? "Your scheduled teaching activity for today."
                  : "The next academic milestones."}
              </p>
            </div>
            <Link href={classes.length ? "/portal/timetable" : "/portal/exams"}>
              Open module
            </Link>
          </div>
          <ActivityRows
            rows={classes.length ? classes : exams}
            empty="There are no scheduled classes or upcoming exams."
          />
        </section>
        <section className="card actions-card">
          <h2>Quick actions</h2>
          <p className="muted">Jump straight to common institute tasks.</p>
          <div className="dashboard-actions">
            <Link href="/portal/attendance">
              Take attendance <span>→</span>
            </Link>
            <Link href="/portal/students">
              Add student <span>→</span>
            </Link>
            <Link href="/portal/announcements">
              Create announcement <span>→</span>
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}

function Metric({
  icon,
  label,
  value,
  detail,
  tone,
}: {
  icon: string;
  label: string;
  value: string;
  detail: string;
  tone?: string;
}) {
  return (
    <article className={`primary-kpi ${tone ?? ""}`}>
      <span className="kpi-icon" aria-hidden="true">
        {icon}
      </span>
      <span className="kpi-label">{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function ActivityRows({ rows, empty }: { rows: Row[]; empty: string }) {
  if (!rows.length) return <p className="chart-empty">{empty}</p>;
  return (
    <div className="activity-rows">
      {rows.slice(0, 4).map((row) => (
        <div key={row.id}>
          <strong>
            {String(row.subject_name ?? row.name ?? "Scheduled activity")}
          </strong>
          <span>
            {[row.starts_at, row.batch_name, row.date]
              .filter(Boolean)
              .join(" · ")}
          </span>
        </div>
      ))}
    </div>
  );
}
