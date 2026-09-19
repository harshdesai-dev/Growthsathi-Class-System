"use client";
import { useEffect, useState } from "react";
import { api, message, type Row } from "@/lib/api";
import type { Scope } from "@/lib/resources";
import { DataTable, Editor, text } from "./ui";

export function AttendanceEntry({
  scope,
  onDone,
  onClose,
}: {
  scope: Scope;
  onDone: () => void;
  onClose: () => void;
}) {
  const [batch, setBatch] = useState("");
  const [subject, setSubject] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [date, setDate] = useState(() =>
    new Date().toLocaleDateString("en-CA"),
  );
  const [roster, setRoster] = useState<Row[]>([]);
  const [loadingRoster, setLoadingRoster] = useState(false);
  useEffect(() => {
    let active = true;
    setRoster([]);
    setError("");
    if (!batch || !subject || !date) return;
    setLoadingRoster(true);
    api<Row[]>(
      `/api/attendance/roster/?batch=${batch}&subject=${subject}&date=${date}`,
    )
      .then((rows) => {
        if (active) setRoster(rows);
      })
      .catch((e) => {
        if (active) setError(message(e));
      })
      .finally(() => {
        if (active) setLoadingRoster(false);
      });
    return () => {
      active = false;
    };
  }, [batch, subject, date]);
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await api("/api/attendance/record/", "POST", {
        batch: Number(batch),
        subject: Number(subject),
        date: form.get("date"),
        records: roster.map((student) => ({
          student: student.id,
          status: form.get(`status-${student.id}`),
          remark: form.get(`remark-${student.id}`),
        })),
      });
      onDone();
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
        className="modal wide"
        role="dialog"
        aria-modal="true"
        aria-label="Take attendance"
      >
        <div className="section-heading">
          <h2>Take attendance</h2>
          <button type="button" className="secondary" onClick={onClose}>
            Close
          </button>
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <form onSubmit={save}>
          <div className="form-grid">
            <label>
              Batch
              <select
                value={batch}
                onChange={(e) => setBatch(e.target.value)}
                required
              >
                <option value="">Choose...</option>
                {scope.batches.map((row) => (
                  <option key={row.id} value={row.id}>
                    {text(row.name)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Subject
              <select
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                required
              >
                <option value="">Choose...</option>
                {scope.subjects.map((row) => (
                  <option key={row.id} value={row.id}>
                    {text(row.name)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Date
              <input
                name="date"
                type="date"
                value={date}
                onChange={(event) => setDate(event.target.value)}
                required
              />
            </label>
          </div>
          {roster.map((student) => (
            <div
              className="attendance-row"
              key={`${batch}-${subject}-${date}-${student.id}`}
            >
              <strong>{text(student.full_name)}</strong>
              <label>
                <span className="sr-only">
                  Status for {text(student.full_name)}
                </span>
                <select
                  name={`status-${student.id}`}
                  defaultValue={String(student.status)}
                >
                  <option>PRESENT</option>
                  <option>ABSENT</option>
                  <option>LATE</option>
                </select>
              </label>
              <input
                name={`remark-${student.id}`}
                defaultValue={String(student.remark ?? "")}
                aria-label={`Remark for ${text(student.full_name)}`}
                placeholder="Optional remark"
                maxLength={300}
              />
            </div>
          ))}
          {loadingRoster && (
            <p role="status">Loading saved attendance and roster...</p>
          )}
          {!loadingRoster && !roster.length && (
            <p className="muted">
              Choose an assigned batch with enrolled students.
            </p>
          )}
          <button
            type="submit"
            disabled={busy || loadingRoster || !roster.length}
          >
            {busy ? "Saving..." : "Save attendance"}
          </button>
        </form>
      </section>
    </div>
  );
}

export function MarksEntry({
  exam,
  onDone,
  onClose,
}: {
  exam: Row;
  onDone: () => void;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    setBusy(true);
    api<Row[]>(`/api/exams/${exam.id}/marks/`)
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
  }, [exam.id]);
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await api(`/api/exams/${exam.id}/marks/`, "POST", {
        scores: rows?.map((row) => ({
          score: row.id,
          is_absent: form.get(`absent-${row.id}`) === "on",
          marks:
            form.get(`absent-${row.id}`) === "on" ||
            form.get(`marks-${row.id}`) === ""
              ? null
              : form.get(`marks-${row.id}`),
          remark: form.get(`remark-${row.id}`),
        })),
      });
      onDone();
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
        className="modal wide"
        role="dialog"
        aria-modal="true"
        aria-label="Enter marks"
      >
        <div className="section-heading">
          <h2>{text(exam.name)} / Marks</h2>
          <button type="button" className="secondary" onClick={onClose}>
            Close
          </button>
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <p className="muted">
          Maximum: {text(exam.total_marks)}. Results become visible after Admin
          publication.
        </p>
        <form onSubmit={save}>
          {rows?.map((row) => (
            <div className="attendance-row" key={row.id}>
              <strong>{text(row.student_name)}</strong>
              <label>
                Marks
                <input
                  type="number"
                  name={`marks-${row.id}`}
                  min={0}
                  max={Number(exam.total_marks)}
                  step="0.01"
                  defaultValue={row.marks == null ? "" : String(row.marks)}
                />
              </label>
              <label className="inline">
                <input
                  type="checkbox"
                  name={`absent-${row.id}`}
                  defaultChecked={Boolean(row.is_absent)}
                />
                Absent
              </label>
              <input
                name={`remark-${row.id}`}
                aria-label={`Remark for ${text(row.student_name)}`}
                placeholder="Optional remark"
                defaultValue={String(row.remark ?? "")}
              />
            </div>
          ))}
          <button type="submit" disabled={busy || Boolean(exam.published_at)}>
            {busy ? "Loading..." : "Save marks"}
          </button>
        </form>
      </section>
    </div>
  );
}

export function FeeDetail({
  account,
  isAdmin,
  onDone,
  onClose,
}: {
  account: Row;
  isAdmin: boolean;
  onDone: () => void;
  onClose: () => void;
}) {
  const [payment, setPayment] = useState(false);
  const [editPlan, setEditPlan] = useState(false);
  const [reverse, setReverse] = useState<Row | null>(null);
  const [key] = useState(() => crypto.randomUUID());
  return (
    <div className="modal-backdrop">
      <section
        className="modal wide"
        role="dialog"
        aria-modal="true"
        aria-label="Fee details"
      >
        <div className="section-heading">
          <h2>{text(account.student_name)} / Fees</h2>
          <button type="button" className="secondary" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="stats">
          <div className="stat">
            Total<strong>INR {text(account.total_fee)}</strong>
          </div>
          <div className="stat">
            Paid<strong>INR {text(account.paid)}</strong>
          </div>
          <div className="stat">
            Pending<strong>INR {text(account.balance)}</strong>
          </div>
        </div>
        <h3>Installments</h3>
        <DataTable
          rows={account.installments as Row[]}
          columns={[
            ["due_date", "Due date"],
            ["amount", "Amount"],
            ["paid", "Paid"],
            ["status", "Status"],
          ]}
        />
        <h3>Payment history</h3>
        <DataTable
          rows={account.payments as Row[]}
          columns={[
            ["paid_on", "Date"],
            ["amount", "Amount"],
            ["method", "Method"],
            ["receipt_number", "Receipt"],
            ["reversed_at", "Reversed"],
          ]}
          actions={(row) => (
            <>
              <a
                className="button secondary"
                href={`/api/fees/${account.id}/receipt/${row.id}/`}
                target="_blank"
                rel="noreferrer"
              >
                Receipt
              </a>
              {isAdmin && !row.reversed_at && (
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setReverse(row)}
                >
                  Reverse
                </button>
              )}
            </>
          )}
        />
        {isAdmin && (
          <button type="button" onClick={() => setPayment(true)}>
            Record payment
          </button>
        )}
        {isAdmin && !(account.payments as Row[]).length && (
          <button
            type="button"
            className="secondary"
            onClick={() => setEditPlan(true)}
          >
            Edit unused plan
          </button>
        )}
        {editPlan && (
          <FeePlan
            account={account}
            scope={{ students: [], batches: [], subjects: [] }}
            onDone={onDone}
            onClose={onClose}
          />
        )}
        {payment && (
          <Editor
            title="Record payment"
            onClose={() => setPayment(false)}
            fields={[
              {
                name: "amount",
                label: "Amount (INR)",
                type: "number",
                required: true,
              },
              {
                name: "method",
                label: "Method",
                required: true,
                options: ["CASH", "UPI", "BANK"].map((value) => ({
                  value,
                  label: value,
                })),
              },
              {
                name: "paid_on",
                label: "Payment date",
                type: "date",
                required: true,
              },
              { name: "reference", label: "Reference / note" },
            ]}
            initial={{ paid_on: new Date().toLocaleDateString("en-CA") }}
            onSave={async (values) => {
              await api(`/api/fees/${account.id}/payment/`, "POST", {
                ...values,
                idempotency_key: key,
              });
              onDone();
              onClose();
            }}
          />
        )}
        {reverse && (
          <Editor
            title="Reverse payment (history will be retained)"
            fields={[
              {
                name: "reason",
                label: "Reason for reversal",
                required: true,
                type: "textarea",
              },
            ]}
            onClose={() => setReverse(null)}
            onSave={async (values) => {
              await api(`/api/fees/${account.id}/reverse/`, "POST", {
                ...values,
                payment: reverse.id,
              });
              onDone();
              onClose();
            }}
          />
        )}
      </section>
    </div>
  );
}

export function FeePlan({
  account,
  scope,
  onDone,
  onClose,
}: {
  account?: Row;
  scope: Scope;
  onDone: () => void;
  onClose: () => void;
}) {
  const originals = (account?.installments ?? []) as Row[];
  const [installments, setInstallments] = useState(() =>
    originals.length
      ? originals.map((row) => String(row.id))
      : [crypto.randomUUID()],
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      await api(
        `/api/fees/${account ? `${account.id}/` : ""}`,
        account ? "PATCH" : "POST",
        {
          registration: Number(form.get("registration")),
          title: form.get("title"),
          total_fee: form.get("total_fee"),
          installments: installments.map((id) => ({
            due_date: form.get(`due-${id}`),
            amount: form.get(`amount-${id}`),
          })),
        },
      );
      onDone();
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
        aria-label="Create fee plan"
      >
        <div className="section-heading">
          <h2>{account ? "Edit unused fee plan" : "Create fee plan"}</h2>
          <button type="button" className="secondary" onClick={onClose}>
            Close
          </button>
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <form onSubmit={save}>
          <label>
            Student registration
            <select
              name="registration"
              required
              defaultValue={String(account?.registration ?? "")}
              disabled={Boolean(account)}
            >
              {account && (
                <option value={String(account.registration)}>
                  {text(account.student_name)}
                </option>
              )}
              <option value="">Choose...</option>
              {scope.registrations?.map((row) => (
                <option key={row.id} value={row.id}>
                  {text(row.name)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Plan name
            <input
              name="title"
              required
              defaultValue={String(account?.title ?? "")}
            />
          </label>
          <label>
            Total fee (INR)
            <input
              name="total_fee"
              defaultValue={String(account?.total_fee ?? "")}
              type="number"
              min="0.01"
              step="0.01"
              required
            />
          </label>
          <h3>Installments</h3>
          {installments.map((id, index) => (
            <div className="form-grid" key={id}>
              <label>
                Due date {index + 1}
                <input
                  name={`due-${id}`}
                  type="date"
                  required
                  defaultValue={String(
                    originals.find((row) => String(row.id) === id)?.due_date ??
                      "",
                  )}
                />
              </label>
              <label>
                Amount
                <input
                  name={`amount-${id}`}
                  defaultValue={String(
                    originals.find((row) => String(row.id) === id)?.amount ??
                      "",
                  )}
                  type="number"
                  min="0.01"
                  step="0.01"
                  required
                />
              </label>
            </div>
          ))}
          <button
            className="secondary"
            type="button"
            onClick={() =>
              setInstallments([...installments, crypto.randomUUID()])
            }
          >
            Add installment
          </button>
          <button type="submit" disabled={busy}>
            {busy ? "Saving..." : "Create plan"}
          </button>
        </form>
      </section>
    </div>
  );
}
