"use client";
import type { Row } from "@/lib/api";
import type { Scope } from "@/lib/resources";

type Filter = {
  key: string;
  label: string;
  options?: [string, string][];
  type?: string;
};
export function ModuleFilters({
  module,
  scope,
  classes,
  values,
  onChange,
}: {
  module: string;
  scope: Scope;
  classes: Row[];
  values: Record<string, string>;
  onChange: (values: Record<string, string>) => void;
}) {
  const choices = (rows: Row[], label = "name"): [string, string][] =>
    rows.map((row) => [
      String(row.id),
      String(row[label] ?? row.full_name ?? row.id),
    ]);
  const fields: Record<string, Filter> = {
    class: { key: "class", label: "Class", options: choices(classes) },
    batch: { key: "batch", label: "Batch", options: choices(scope.batches) },
    subject: {
      key: "subject",
      label: "Subject",
      options: choices(scope.subjects),
    },
    teacher: {
      key: "teacher",
      label: "Teacher",
      options: choices(scope.teachers ?? []),
    },
    account: {
      key: "status",
      label: "Account status",
      options: [
        ["ACTIVE", "Active"],
        ["DISABLED", "Disabled"],
        ["PENDING", "Pending activation"],
      ],
    },
    active: {
      key: "is_active",
      label: "Status",
      options: [
        ["true", "Active"],
        ["false", "Inactive"],
      ],
    },
    attendance: {
      key: "status",
      label: "Attendance status",
      options: [
        ["PRESENT", "Present"],
        ["ABSENT", "Absent"],
        ["LATE", "Late"],
      ],
    },
    cancelled: {
      key: "is_cancelled",
      label: "Schedule status",
      options: [
        ["false", "Scheduled"],
        ["true", "Cancelled"],
      ],
    },
    audience: {
      key: "audience",
      label: "Audience",
      options: ["ALL", "STUDENTS", "PARENTS", "TEACHERS", "BATCH", "CLASS"].map(
        (value) => [value, value],
      ),
    },
    important: {
      key: "is_important",
      label: "Importance",
      options: [
        ["true", "Important"],
        ["false", "Normal"],
      ],
    },
    date_from: { key: "date_from", label: "From date", type: "date" },
    date_to: { key: "date_to", label: "To date", type: "date" },
    topic: { key: "topic", label: "Chapter / topic", type: "text" },
  };
  const mapping: Record<string, string[]> = {
    students: ["class", "batch", "account"],
    teachers: ["batch", "subject", "account"],
    parents: ["class", "batch", "account"],
    batches: ["class", "subject", "teacher", "active"],
    attendance: [
      "class",
      "batch",
      "subject",
      "attendance",
      "date_from",
      "date_to",
    ],
    fees: ["class", "batch"],
    exams: ["class", "batch", "subject", "cancelled", "date_from", "date_to"],
    results: ["class", "batch", "subject", "date_from", "date_to"],
    materials: ["batch", "subject", "topic", "important"],
    announcements: [
      "audience",
      "class",
      "batch",
      "important",
      "date_from",
      "date_to",
    ],
  };
  const selected = (mapping[module] ?? [])
    .map((key) => fields[key])
    .filter((field) => !field.options || field.options.length);
  if (!selected.length) return null;
  return (
    <fieldset className="module-filters">
      <legend>Filter records</legend>
      <div className="schedule-filters">
        {selected.map((field) => (
          <label key={field.key} htmlFor={`filter-${module}-${field.key}`}>
            {field.label}
            {field.options ? (
              <select
                id={`filter-${module}-${field.key}`}
                value={values[field.key] ?? ""}
                onChange={(event) =>
                  onChange({ ...values, [field.key]: event.target.value })
                }
              >
                <option value="">All</option>
                {field.options.map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id={`filter-${module}-${field.key}`}
                type={field.type}
                value={values[field.key] ?? ""}
                onChange={(event) =>
                  onChange({ ...values, [field.key]: event.target.value })
                }
              />
            )}
          </label>
        ))}
        <button
          type="button"
          className="secondary"
          onClick={() => onChange({})}
        >
          Clear filters
        </button>
      </div>
    </fieldset>
  );
}
