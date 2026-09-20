"use client";
import { useEffect, useState } from "react";
import { allRows, api, message, type Row, type User } from "@/lib/api";
import type { Scope } from "@/lib/resources";
import { DataTable, text } from "./ui";

export function EntityDetail({
  module,
  row,
  user,
  scope,
  onClose,
  onDone,
}: {
  module: string;
  row: Row;
  user: User;
  scope: Scope;
  onClose: () => void;
  onDone: () => void;
}) {
  const [tab, setTab] = useState("Overview");
  const [items, setItems] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [version, setVersion] = useState(0);
  const admin = user.role === "ADMIN";
  const tabs =
    module === "students"
      ? [
          "Overview",
          "Attendance",
          ...(user.role !== "TEACHER" ? ["Fees"] : []),
          "Results",
          ...(admin ? ["Enrollment history", "Documents"] : []),
        ]
      : module === "teachers"
        ? ["Overview", "Assignments", "Attendance"]
        : module === "parents"
          ? ["Overview", "Linked children"]
          : ["Overview", "Students"];
  // biome-ignore lint/correctness/useExhaustiveDependencies: version reloads server records after relationship changes.
  useEffect(() => {
    if (tab === "Overview") return;
    let active = true;
    setLoading(true);
    setError("");
    const paths: Record<string, string> = {
      Attendance:
        module === "teachers"
          ? "/api/teacher-attendance/"
          : `/api/attendance/?student=${row.id}`,
      Fees: `/api/fees/?student=${row.id}`,
      Results: `/api/results/?student=${row.id}`,
      Assignments: "/api/teacher-assignments/",
      "Linked children": "/api/parent-links/",
      "Enrollment history": `/api/students/${row.id}/history/`,
      Documents: `/api/files/?student=${row.id}`,
    };

    async function load() {
      try {
        let data: Row[];
        if (tab === "Students")
          data = scope.students.filter(
            (item) => (item.current_enrollment as Row | null)?.batch === row.id,
          );
        else if (["Documents", "Enrollment history"].includes(tab))
          data = await api<Row[]>(paths[tab]);
        else data = await allRows(paths[tab]);
        if (
          tab === "Assignments" ||
          (tab === "Attendance" && module === "teachers")
        )
          data = data.filter((item) => item.teacher === row.id);
        if (tab === "Linked children")
          data = data.filter((item) => item.parent === row.id);
        if (active) setItems(data);
      } catch (e) {
        if (active) setError(message(e));
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [tab, module, row.id, scope.students, version]);
  async function unlink(item: Row) {
    if (
      !window.confirm(
        "Remove this access relationship? Historical records will be retained.",
      )
    )
      return;
    try {
      await api(
        `/api/${tab === "Assignments" ? "teacher-assignments" : "parent-links"}/${item.id}/`,
        "PATCH",
        { is_active: false },
      );
      setVersion((v) => v + 1);
      onDone();
    } catch (e) {
      setError(message(e));
    }
  }
  const cols: Record<string, [string, string][]> = {
    Attendance:
      module === "teachers"
        ? [
            ["date", "Date"],
            ["status", "Status"],
            ["remark", "Remark"],
          ]
        : [
            ["date", "Date"],
            ["subject_name", "Subject"],
            ["status", "Status"],
          ],
    Fees: [
      ["title", "Plan"],
      ["total_fee", "Total"],
      ["paid", "Paid"],
      ["balance", "Pending"],
    ],
    Results: [
      ["exam_name", "Exam"],
      ["marks", "Marks"],
      ["total_marks", "Total"],
      ["calculation", "Result"],
    ],
    Assignments: [
      ["batch", "Batch"],
      ["subject", "Subject"],
      ["is_active", "Active"],
    ],
    "Linked children": [
      ["student", "Student"],
      ["relationship", "Relationship"],
      ["is_active", "Active"],
    ],
    "Enrollment history": [
      ["batch_name", "Batch"],
      ["roll_number", "Roll"],
      ["started_at", "Started"],
      ["ended_at", "Ended"],
    ],
    Documents: [
      ["name", "Document"],
      ["size", "Bytes"],
    ],
    Students: [
      ["full_name", "Student"],
      ["current_enrollment", "Class / batch / roll"],
    ],
  };
  const displayRows = items.map((item) => ({
    ...item,
    batch:
      scope.batches.find((value) => value.id === item.batch)?.name ??
      item.batch,
    subject:
      scope.subjects.find((value) => value.id === item.subject)?.name ??
      item.subject,
    student:
      scope.students.find((value) => value.id === item.student)?.full_name ??
      item.student,
  }));
  return (
    <div className="modal-backdrop">
      <section
        className="modal wide"
        role="dialog"
        aria-modal="true"
        aria-label="Profile details"
      >
        <div className="section-heading">
          <h2>{text(row.full_name ?? row.name)}</h2>
          <button type="button" className="secondary" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="row-actions">
          {tabs.map((name) => (
            <button
              type="button"
              className={tab === name ? "" : "secondary"}
              key={name}
              onClick={() => setTab(name)}
            >
              {name}
            </button>
          ))}
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {tab === "Overview" ? (
          <dl>
            {Object.entries(row)
              .filter(([key]) => !["id", "user"].includes(key))
              .map(([key, value]) => (
                <div key={key}>
                  <dt>{key.replaceAll("_", " ")}</dt>
                  <dd>{text(value)}</dd>
                </div>
              ))}
          </dl>
        ) : loading ? (
          <p role="status">Loading...</p>
        ) : (
          <>
            <DataTable
              rows={displayRows}
              columns={cols[tab]}
              actions={(item) => (
                <>
                  {["Assignments", "Linked children"].includes(tab) &&
                    Boolean(item.is_active) && (
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => unlink(item)}
                      >
                        Remove access
                      </button>
                    )}
                  {tab === "Documents" && (
                    <a
                      href={`/api/files/${item.id}/`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Download
                    </a>
                  )}
                  {tab === "Results" && (
                    <a
                      href={`/api/results/${item.id}/report_card/`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Report card
                    </a>
                  )}
                </>
              )}
            />
            {tab === "Documents" && (
              <label>
                Add private student document
                <input
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
                  onChange={async (event) => {
                    const file = event.target.files?.[0];
                    if (!file) return;
                    const form = new FormData();
                    form.append("file", file);
                    form.append("student", String(row.id));
                    try {
                      await api("/api/files/", "POST", form);
                      setVersion((v) => v + 1);
                    } catch (e) {
                      setError(message(e));
                    }
                  }}
                />
              </label>
            )}
          </>
        )}
      </section>
    </div>
  );
}
