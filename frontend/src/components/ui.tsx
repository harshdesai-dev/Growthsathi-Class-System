"use client";
import { useState } from "react";
import { message, type Row } from "@/lib/api";

export type Field = {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
  options?: { value: string | number; label: string }[];
};
export function text(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.map(text).join(", ");
  if (typeof value === "object") {
    const item = value as Record<string, unknown>;
    if (item.batch_name)
      return `${item.class_name ?? ""} ${item.batch_name} / ${item.roll_number ?? ""}`;
    if (item.result) return `${item.percentage ?? "-"}% / ${item.result}`;
    return Object.entries(item)
      .map(([key, v]) => `${key.replaceAll("_", " ")}: ${text(v)}`)
      .join(" | ");
  }
  return String(value);
}
function inputValue(value: unknown, type?: string) {
  if (
    type === "datetime-local" &&
    typeof value === "string" &&
    /(?:Z|[+-]\d\d:\d\d)$/.test(value)
  ) {
    const date = new Date(value);
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
  }
  return String(value ?? "");
}

export function Editor({
  title,
  fields,
  initial = {},
  onSave,
  onClose,
}: {
  title: string;
  fields: Field[];
  initial?: Record<string, unknown>;
  onSave: (values: Record<string, unknown>) => Promise<void>;
  onClose: () => void;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const data: Record<string, unknown> = {};
    for (const field of fields) {
      const value = form.get(field.name);
      data[field.name] =
        field.type === "checkbox"
          ? value === "on"
          : field.type === "number" || field.type === "select-number"
            ? value
              ? Number(value)
              : null
            : value;
    }
    try {
      await onSave(data);
      onClose();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="modal-backdrop">
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="section-heading">
          <h2>{title}</h2>
          <button className="secondary" onClick={onClose} type="button">
            Close
          </button>
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <form onSubmit={submit} className="form-grid">
          {fields.map((field) => (
            <label key={field.name} htmlFor={`field-${field.name}`}>
              {field.label}
              {field.options ? (
                <select
                  id={`field-${field.name}`}
                  name={field.name}
                  required={field.required}
                  defaultValue={inputValue(initial[field.name], field.type)}
                >
                  <option value="">Choose...</option>
                  {field.options.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ) : field.type === "textarea" ? (
                <textarea
                  id={`field-${field.name}`}
                  name={field.name}
                  required={field.required}
                  defaultValue={inputValue(initial[field.name], field.type)}
                  rows={4}
                />
              ) : (
                <input
                  id={`field-${field.name}`}
                  name={field.name}
                  type={field.type ?? "text"}
                  required={field.required}
                  defaultValue={
                    field.type === "checkbox"
                      ? undefined
                      : inputValue(initial[field.name], field.type)
                  }
                  defaultChecked={
                    field.type === "checkbox"
                      ? Boolean(initial[field.name])
                      : undefined
                  }
                  step={field.type === "number" ? "0.01" : undefined}
                />
              )}
            </label>
          ))}
          <button type="submit" className="span-all" disabled={busy}>
            {busy ? "Saving..." : "Save changes"}
          </button>
        </form>
      </section>
    </div>
  );
}
export function DataTable({
  rows,
  columns,
  actions,
}: {
  rows: Row[];
  columns: [string, string][];
  actions?: (row: Row) => React.ReactNode;
}) {
  if (!rows.length)
    return (
      <div className="empty">
        <h3>No records yet</h3>
        <p>New records will appear here when they are available.</p>
      </div>
    );
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {columns.map(([key, label]) => (
              <th key={key}>{label}</th>
            ))}
            {actions && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              {columns.map(([key]) => (
                <td key={key}>
                  {["status", "is_active", "is_cancelled"].includes(key) ? (
                    <span className="badge">{text(row[key])}</span>
                  ) : (
                    text(row[key])
                  )}
                </td>
              ))}
              {actions && (
                <td>
                  <div className="row-actions">{actions(row)}</div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
