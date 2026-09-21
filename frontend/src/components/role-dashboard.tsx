"use client";

import Link from "next/link";
import type { Role, Row } from "@/lib/api";
import { inr, number } from "@/lib/format";
import { Icon, type IconName } from "./icon";
import { text } from "./ui";

type Section = {
  title: string;
  module: string;
  columns: [string, string][];
  rows: Row[];
};
type Metric = { label: string; value: string; detail: string; tone?: string };

function metric(
  stats: Record<string, unknown>,
  key: string,
  detail: string,
): Metric {
  return { label: key, value: number(stats[key]), detail };
}

function metrics(role: Role, stats: Record<string, unknown>): Metric[] {
  if (role === "SUPER_ADMIN")
    return [
      metric(stats, "Institutes", "Client institutes"),
      metric(stats, "Active institutes", "Currently active"),
      {
        ...metric(stats, "Inactive institutes", "Needs review"),
        tone: "warning",
      },
      {
        ...metric(stats, "Renewals in 30 days", "Upcoming renewals"),
        tone: "info",
      },
    ];
  if (role === "TEACHER")
    return [
      metric(stats, "Batches", "Assigned batches"),
      metric(stats, "Students", "Students in your scope"),
      metric(stats, "Classes today", "Scheduled today"),
      {
        ...metric(stats, "Exams awaiting marks", "Academic follow-up"),
        tone: "warning",
      },
    ];
  const attendance = {
    label: "Attendance",
    value:
      stats["Attendance (%)"] == null
        ? "—"
        : `${number(stats["Attendance (%)"])}%`,
    detail: role === "PARENT" ? "Across selected child" : "Attendance to date",
  };
  return [
    metric(
      stats,
      "Linked records",
      role === "PARENT" ? "Linked children" : "Your learner record",
    ),
    attendance,
    {
      label: "Fees pending",
      value: inr(stats["Fees pending"]),
      detail: "Outstanding amount",
      tone: "warning",
    },
    metric(stats, "Upcoming exams", "Next academic events"),
  ];
}

function sectionIcon(module: string): IconName {
  const icons: Record<string, IconName> = {
    timetable: "timetable",
    exams: "exams",
    results: "results",
    materials: "materials",
    announcements: "announcements",
    fees: "fees",
    subscriptions: "subscriptions",
    support: "support",
  };
  return icons[module] ?? "dashboard";
}

function SectionCard({ section }: { section: Section }) {
  return (
    <section className="card dashboard-section-card">
      <div className="section-heading">
        <div>
          <span className="section-kicker"><Icon name={sectionIcon(section.module)} size={14} />{section.module}</span>
          <h2>{section.title}</h2>
        </div>
        <Link href={`/portal/${section.module}`}>View all</Link>
      </div>
      {section.rows.length ? (
        <div className="dashboard-list">
          {section.rows.slice(0, 4).map((row) => (
            <Link href={`/portal/${section.module}`} key={row.id}>
              <span className="dashboard-list-marker" aria-hidden="true">
              <Icon name={sectionIcon(section.module)} size={15} />
              </span>
              <span>
                <strong>
                  {text(row[section.columns[0]?.[0]] ?? row.name)}
                </strong>
                <small>
                  {section.columns
                    .slice(1, 3)
                    .map(([key]) => text(row[key]))
                    .filter((value) => value !== "-")
                    .join(" · ") || "Details available in the module"}
                </small>
              </span>
            </Link>
          ))}
        </div>
      ) : (
        <div className="compact-empty">
          <strong>No items to show</strong>
          <span>New information will appear here when it is available.</span>
        </div>
      )}
    </section>
  );
}

export function RoleDashboard({
  role,
  stats,
  sections,
}: {
  role: Role;
  stats: Record<string, unknown>;
  sections: Section[];
}) {
  const copy: Record<Role, string> = {
    ADMIN: "Your institute operational overview.",
    TEACHER: "Your teaching day at a glance.",
    STUDENT: "Your learning priorities, all in one place.",
    PARENT: "A clear view of your child’s progress and upcoming work.",
    SUPER_ADMIN: "A focused view of your GrowthSathi platform operations.",
  };
  const preferred =
    role === "TEACHER"
      ? [
          "Today's classes",
          "Upcoming exams",
          "Recent materials",
          "Recent announcements",
        ]
      : role === "STUDENT"
        ? [
            "Today's classes",
            "Upcoming exams",
            "Latest published results",
            "Recent materials",
            "Recent announcements",
          ]
        : role === "PARENT"
          ? [
              "Upcoming exams",
              "Latest published results",
              "Upcoming and overdue installments",
              "Recent announcements",
            ]
          : ["Upcoming renewals", "Recent operator activity"];
  const ordered = preferred
    .map((title) => sections.find((section) => section.title === title))
    .filter((section): section is Section => Boolean(section));
  return (
    <div className="role-dashboard">
      <p className="dashboard-intro">{copy[role]}</p>
      <section className="primary-kpis" aria-label="Dashboard overview">
        {metrics(role, stats).map((item) => (
          <article
            className={`primary-kpi ${item.tone ?? ""}`}
            key={item.label}
          >
            <span className="kpi-icon" aria-hidden="true">
              <Icon name={metricIcon(item.label)} />
            </span>
            <span className="kpi-label">{item.label}</span>
            <strong>{item.value}</strong>
            <small>{item.detail}</small>
          </article>
        ))}
      </section>
      <div className="role-dashboard-grid">
        {ordered.map((section) => (
          <SectionCard key={section.title} section={section} />
        ))}
      </div>
    </div>
  );
}

function metricIcon(label: string): IconName {
  const names: Record<string, IconName> = { Institutes: "institutes", "Active institutes": "institutes", "Inactive institutes": "institutes", "Renewals in 30 days": "subscriptions", Batches: "batches", Students: "students", "Classes today": "timetable", "Exams awaiting marks": "exams", "Linked records": "students", Attendance: "attendance", "Fees pending": "fees", "Upcoming exams": "exams" };
  return names[label] ?? "dashboard";
}
