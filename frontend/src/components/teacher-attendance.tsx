"use client";
import { useEffect, useState } from "react";
import { allRows, api, message, type Row } from "@/lib/api";
import type { Scope } from "@/lib/resources";
import { DataTable, Editor, type Field } from "./ui";

export function TeacherAttendance({
  scope,
  editable,
}: {
  scope: Scope;
  editable: boolean;
}) {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [edit, setEdit] = useState<Row | null>(null);
  const [revision, setRevision] = useState(0);
  // biome-ignore lint/correctness/useExhaustiveDependencies: refresh records after saving attendance.
  useEffect(() => {
    let active = true;
    allRows("/api/teacher-attendance/")
      .then((data) => {
        if (active) setRows(data);
      })
      .catch((e) => {
        if (active) setError(message(e));
      });
    return () => {
      active = false;
    };
  }, [revision]);
  const fields: Field[] = [
    {
      name: "teacher",
      label: "Teacher",
      type: "select-number",
      required: true,
      options: (scope.teachers ?? []).map((row) => ({
        value: row.id,
        label: String(row.name),
      })),
    },
    { name: "date", label: "Date", type: "date", required: true },
    {
      name: "status",
      label: "Status",
      required: true,
      options: ["PRESENT", "ABSENT", "LATE"].map((value) => ({
        value,
        label: value,
      })),
    },
    { name: "remark", label: "Remark" },
  ];
  return (
    <section className="card">
      <div className="section-heading">
        <h2>{editable ? "Teacher attendance" : "My attendance"}</h2>
        {editable && (
          <button
            type="button"
            onClick={() =>
              setEdit({ id: 0, date: new Date().toLocaleDateString("en-CA") })
            }
          >
            Record teacher attendance
          </button>
        )}
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <DataTable
        rows={rows}
        columns={[
          ["teacher_name", "Teacher"],
          ["date", "Date"],
          ["status", "Status"],
          ["remark", "Remark"],
        ]}
        actions={
          editable
            ? (row) => (
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setEdit(row)}
                >
                  Edit
                </button>
              )
            : undefined
        }
      />
      {edit && (
        <Editor
          title="Teacher attendance"
          fields={fields}
          initial={edit}
          onClose={() => setEdit(null)}
          onSave={async (values) => {
            await api(
              `/api/teacher-attendance/${edit.id ? `${edit.id}/` : ""}`,
              edit.id ? "PATCH" : "POST",
              values,
            );
            setRevision((v) => v + 1);
          }}
        />
      )}
    </section>
  );
}
