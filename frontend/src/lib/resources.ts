import type { Field } from "@/components/ui";
import type { Role, Row } from "./api";
export type Scope = {
  students: Row[];
  batches: Row[];
  subjects: Row[];
  teachers?: Row[];
  registrations?: Row[];
};
export const endpoints: Record<string, string> = {
  institutes: "super-admin/institutes",
  support: "super-admin/institutes",
  subscriptions: "super-admin/subscriptions",
  domains: "super-admin/domains",
};
export const columns: Record<string, [string, string][]> = {
  students: [
    ["full_name", "Student"],
    ["current_enrollment", "Class / Batch / Roll"],
    ["phone", "Phone"],
    ["status", "Status"],
  ],
  teachers: [
    ["full_name", "Teacher"],
    ["qualification", "Qualification"],
    ["phone", "Phone"],
    ["status", "Status"],
  ],
  parents: [
    ["full_name", "Parent"],
    ["phone", "Phone"],
    ["email", "Email"],
  ],
  batches: [
    ["name", "Batch"],
    ["class_name", "Class"],
    ["year_name", "Academic year"],
    ["room", "Room"],
    ["is_active", "Active"],
  ],
  timetable: [
    ["date", "Date"],
    ["starts_at", "Start"],
    ["ends_at", "End"],
    ["batch_name", "Batch"],
    ["subject_name", "Subject"],
    ["teacher_name", "Teacher"],
    ["room", "Room"],
    ["is_cancelled", "Cancelled"],
  ],
  attendance: [
    ["student_name", "Student"],
    ["date", "Date"],
    ["subject_name", "Subject"],
    ["status", "Status"],
    ["remark", "Remark"],
  ],
  fees: [
    ["student_name", "Student"],
    ["title", "Fee plan"],
    ["total_fee", "Total fee"],
    ["paid", "Paid"],
    ["balance", "Pending"],
    ["next_due_date", "Next due date"],
    ["payment_status", "Status"],
  ],
  materials: [
    ["title", "Title"],
    ["subject_name", "Subject"],
    ["topic", "Topic"],
    ["uploader_name", "Shared by"],
    ["downloads", "Downloads"],
  ],
  exams: [
    ["name", "Exam"],
    ["batch_name", "Batch"],
    ["subject_name", "Subject"],
    ["date", "Date"],
    ["total_marks", "Total marks"],
    ["passing_marks", "Pass marks"],
    ["published_at", "Published"],
  ],
  results: [
    ["student_name", "Student"],
    ["exam_name", "Exam"],
    ["subject_name", "Subject"],
    ["marks", "Marks"],
    ["total_marks", "Out of"],
    ["calculation", "Result"],
  ],
  announcements: [
    ["title", "Title"],
    ["audience", "Audience"],
    ["sender_name", "Sender"],
    ["published_at", "Published"],
    ["expires_at", "Expires"],
  ],
  institutes: [
    ["name", "Institute"],
    ["slug", "Code"],
    ["contact_name", "Contact"],
    ["is_active", "Active"],
  ],
  support: [
    ["name", "Institute"],
    ["support_status", "Support status"],
    ["support_note", "Note"],
  ],
  domains: [
    ["hostname", "Hostname"],
    ["institute_name", "Institute"],
    ["is_verified", "Verified"],
    ["is_active", "Active"],
  ],
  subscriptions: [
    ["institute_name", "Institute"],
    ["plan_name", "Plan"],
    ["ends_on", "Renewal"],
    ["status", "Status"],
    ["student_limit", "Student limit"],
    ["storage_limit_mb", "Storage MB"],
  ],
};
export function fieldsFor(
  module: string,
  scope: Scope,
  catalogs: Record<string, Row[]>,
  role: Role,
): Field[] {
  const field = (
    name: string,
    label: string,
    type = "text",
    required = true,
  ): Field => ({ name, label, type, required });
  const select = (
    name: string,
    label: string,
    rows: Row[],
    required = true,
  ): Field => ({
    name,
    label,
    type: "select-number",
    required,
    options: rows.map((row) => ({
      value: row.id,
      label: String(
        row.name ?? row.full_name ?? row.title ?? row.hostname ?? row.id,
      ),
    })),
  });
  const batch = select("batch", "Batch", scope.batches);
  const subject = select("subject", "Subject", scope.subjects);
  if (["students", "teachers", "parents"].includes(module))
    return [
      field("full_name", "Full name"),
      field("username", "Username"),
      field("email", "Recovery email", "email", false),
      field("phone", "Phone", "tel", false),
      field(
        "temporary_password",
        "Temporary password (minimum 12 characters)",
        "password",
        false,
      ),
    ];
  switch (module) {
    case "batches":
      return [
        field("name", "Batch name"),
        select("academic_year", "Academic year", catalogs.years ?? []),
        select("academic_class", "Class", catalogs.classes ?? []),
        field("room", "Room", "text", false),
        field("is_active", "Active", "checkbox", false),
      ];
    case "timetable":
      return [
        batch,
        subject,
        select("teacher", "Teacher", scope.teachers ?? []),
        field("date", "Date", "date"),
        field("starts_at", "Start time", "time"),
        field("ends_at", "End time", "time"),
        field("room", "Room", "text", false),
        field("is_cancelled", "Cancelled", "checkbox", false),
      ];
    case "exams":
      return [
        field("name", "Exam name"),
        batch,
        subject,
        field("date", "Date", "date"),
        field("starts_at", "Start time", "time"),
        field("total_marks", "Total marks", "number"),
        field("passing_marks", "Passing marks", "number"),
        field("instructions", "Instructions", "textarea", false),
        field("is_cancelled", "Cancelled", "checkbox", false),
      ];
    case "materials":
      return [
        field("title", "Title"),
        subject,
        { ...batch, required: role === "TEACHER" },
        ...(role === "ADMIN"
          ? [
              select(
                "academic_class",
                "Or target entire class",
                catalogs.classes ?? [],
                false,
              ),
            ]
          : []),
        field("topic", "Chapter / topic", "text", false),
        field("description", "Description", "textarea", false),
        field(
          "external_url",
          "External / YouTube link (leave empty when using a file)",
          "url",
          false,
        ),
        field("is_important", "Important", "checkbox", false),
        field("is_active", "Visible", "checkbox", false),
      ];
    case "announcements":
      return [
        field("title", "Title"),
        field("message", "Message", "textarea"),
        {
          name: "audience",
          label: "Audience",
          required: true,
          options: (role === "TEACHER"
            ? ["BATCH"]
            : ["ALL", "STUDENTS", "PARENTS", "TEACHERS", "BATCH", "CLASS"]
          ).map((value) => ({ value, label: value })),
        },
        { ...batch, required: false },
        ...(role === "ADMIN"
          ? [
              select(
                "academic_class",
                "Class (class audience only)",
                catalogs.classes ?? [],
                false,
              ),
            ]
          : []),
        field("published_at", "Publish at", "datetime-local"),
        field("expires_at", "Expires at", "datetime-local", false),
        field("is_important", "Important", "checkbox", false),
        field("is_active", "Active", "checkbox", false),
      ];
    case "institutes":
      return [
        field("name", "Institute name"),
        field("slug", "Institute code"),
        field("contact_name", "Contact name"),
        field("phone", "Phone", "tel", false),
        field("email", "Email", "email", false),
        field("address", "Address", "textarea", false),
        field("primary_color", "Brand color", "color"),
        field("is_active", "Active", "checkbox", false),
      ];
    case "domains":
      return [
        select("institute", "Institute", catalogs.institutes ?? []),
        field("hostname", "Hostname (no scheme or path)"),
        field("is_verified", "Ownership and DNS verified", "checkbox", false),
        field("is_active", "Active", "checkbox", false),
      ];
    case "subscriptions":
      return [
        select("institute", "Institute", catalogs.institutes ?? []),
        select("plan", "Plan", catalogs.plans ?? []),
        field("starts_on", "Start date", "date"),
        field("ends_on", "Renewal date", "date"),
        {
          name: "status",
          label: "Status",
          options: ["ACTIVE", "EXPIRED", "CANCELLED"].map((value) => ({
            value,
            label: value,
          })),
          required: true,
        },
        field("student_limit", "Student limit", "number"),
        field("storage_limit_mb", "Storage limit MB", "number"),
        field("payment_note", "Payment note", "text", false),
      ];
    default:
      return [];
  }
}
