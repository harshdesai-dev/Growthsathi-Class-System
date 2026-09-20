"use client";
import Image from "next/image";
import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { AdminDashboard } from "@/components/admin-dashboard";
import { EntityDetail } from "@/components/entity-detail";
import { ModuleFilters } from "@/components/module-filters";
import { TeacherAttendance } from "@/components/teacher-attendance";
import { Timetable } from "@/components/timetable";
import { DataTable, Editor, type Field, text } from "@/components/ui";
import {
  AttendanceEntry,
  FeeDetail,
  FeePlan,
  MarksEntry,
} from "@/components/workflows";
import {
  allRows,
  api,
  type Branding,
  context,
  message,
  type Page,
  type Row,
  type User,
} from "@/lib/api";
import {
  canOpen,
  navigation,
  navigationGroups,
  navSymbols,
} from "@/lib/navigation";
import { columns, endpoints, fieldsFor, type Scope } from "@/lib/resources";

const emptyScope: Scope = { students: [], batches: [], subjects: [] };
type Edit = {
  title: string;
  fields: Field[];
  initial?: Record<string, unknown>;
  save: (values: Record<string, unknown>) => Promise<void>;
};

export default function Portal({
  params,
}: {
  params: Promise<{ module: string }>;
}) {
  const { module } = use(params);
  const [user, setUser] = useState<User | null>(null);
  const [brand, setBrand] = useState<Branding | null>(null);
  const [scope, setScope] = useState<Scope>(emptyScope);
  const [catalogs, setCatalogs] = useState<Record<string, Row[]>>({});
  const [rows, setRows] = useState<Row[]>([]);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [filterState, setFilterState] = useState<
    Record<string, Record<string, string>>
  >({});
  const filterQuery = new URLSearchParams(filterState[module] ?? {}).toString();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [stats, setStats] = useState<Record<string, unknown>>({});
  const [dashboardSections, setDashboardSections] = useState<
    {
      title: string;
      module: string;
      columns: [string, string][];
      rows: Row[];
    }[]
  >([]);
  const [summarySections, setSummarySections] = useState<
    { title: string; columns: [string, string][]; rows: Row[] }[]
  >([]);
  const [settings, setSettings] = useState<
    Record<string, Record<string, unknown>>
  >({});
  const [edit, setEdit] = useState<Edit | null>(null);
  const [detail, setDetail] = useState<Row | null>(null);
  const [marks, setMarks] = useState<Row | null>(null);
  const [attendance, setAttendance] = useState(false);
  const [feePlan, setFeePlan] = useState(false);
  const [sidebar, setSidebar] = useState(false);
  const [notifications, setNotifications] = useState<Row[] | null>(null);
  const [child, setChild] = useState("");
  const [uploaded, setUploaded] = useState<number | null>(null);
  const admin = user?.role === "ADMIN";
  const teacher = user?.role === "TEACHER";
  const platform = user?.role === "SUPER_ADMIN";
  const reload = useCallback(() => {
    setRevision((value) => value + 1);
    setNotice("Changes saved.");
  }, []);
  const options = (items: Row[], label = "name") =>
    items.map((row) => ({
      value: row.id,
      label: String(row[label] ?? row.full_name ?? row.id),
    }));
  const select = (
    name: string,
    label: string,
    items: Row[],
    key = "name",
  ): Field => ({
    name,
    label,
    type: "select-number",
    required: true,
    options: options(items, key),
  });

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const branding = await context();
        const me = await api<User>("/api/auth/me/");
        if (me.must_change_password) {
          window.location.assign("/account/password");
          return;
        }
        if (active) {
          setBrand(branding);
          setUser(me);
        }
      } catch {
        if (active) window.location.assign("/login");
      }
    })();
    return () => {
      active = false;
    };
  }, []);
  // biome-ignore lint/correctness/useExhaustiveDependencies: revision reloads server data after a mutation.
  useEffect(() => {
    if (!user) return;
    let active = true;
    (async () => {
      try {
        if (user.role !== "SUPER_ADMIN") {
          const data = await api<Scope>("/api/scope/");
          if (active) setScope(data);
        }
        if (user.role === "ADMIN") {
          const [years, classes] = await Promise.all([
            allRows("/api/academic-years/"),
            allRows("/api/academic-classes/"),
          ]);
          if (active) setCatalogs({ years, classes });
        }
        if (user.role === "SUPER_ADMIN") {
          const [institutes, plans] = await Promise.all([
            allRows("/api/super-admin/institutes/"),
            allRows("/api/super-admin/plans/"),
          ]);
          if (active) setCatalogs({ institutes, plans });
        }
      } catch (e) {
        if (active) setError(message(e));
      }
    })();
    return () => {
      active = false;
    };
  }, [user, revision]);
  // biome-ignore lint/correctness/useExhaustiveDependencies: revision reloads server data after a mutation.
  useEffect(() => {
    if (!user) return;
    let active = true;
    setLoading(true);
    setError("");
    setRows([]);
    setStats({});
    setSummarySections([]);
    setDetail(null);
    (async () => {
      try {
        if (!canOpen(user.role, module))
          throw new Error("This page is not available for your role.");
        if (module === "dashboard") {
          const data = await api<Record<string, unknown>>(
            `/api/dashboard/${child ? `?student=${child}` : ""}`,
          );
          if (active) {
            const { sections, ...metrics } = data;
            setStats(metrics);
            setDashboardSections((sections ?? []) as typeof dashboardSections);
          }
        } else if (module === "settings") {
          const data =
            await api<Record<string, Record<string, unknown>>>(
              "/api/settings/",
            );
          if (active) setSettings(data);
        } else if (module === "profile") {
          const data = await api<Row>("/api/profile/");
          if (active) setDetail(data);
        } else if (module !== "create-institute" && module !== "timetable") {
          const endpoint = endpoints[module] ?? module;
          const filters = new URLSearchParams({
            page: String(page),
            search: query,
          });
          for (const [key, value] of new URLSearchParams(filterQuery))
            if (value) filters.set(key, value);
          if (child) filters.set("student", child);
          const data = await api<Page<Row>>(`/api/${endpoint}/?${filters}`);
          if (active) {
            setRows(data.results);
            setCount(data.count);
          }
          if (["attendance", "fees", "results"].includes(module)) {
            const summary = await api<Record<string, unknown>>(
              `/api/${module}/summary/?${filters}`,
            );
            if (active) {
              const { sections, counts, ...metrics } = summary;
              setStats({
                ...((counts ?? {}) as Record<string, unknown>),
                ...metrics,
              });
              setSummarySections((sections ?? []) as typeof summarySections);
            }
          }
        }
      } catch (e) {
        if (active) setError(message(e));
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [user, module, page, query, revision, child, filterQuery]);

  async function mutate(path: string, data: unknown, method = "POST") {
    await api(path, method, data);
    reload();
  }
  function openEdit(target: string, row?: Row) {
    if (!user) return;
    const creating = !row;
    const fields = fieldsFor(target, scope, catalogs, user.role);
    setEdit({
      title: `${creating ? "Add" : "Edit"} ${target.replaceAll("-", " ")}`,
      fields,
      initial: row ?? {
        is_active: true,
        primary_color: "#2563eb",
        published_at: new Date(
          Date.now() - new Date().getTimezoneOffset() * 60000,
        )
          .toISOString()
          .slice(0, 16),
      },
      save: async (values) => {
        const data = { ...values };
        for (const key of ["expires_at", "batch", "academic_class"])
          if (data[key] === "") data[key] = null;
        for (const key of ["published_at", "expires_at"])
          if (data[key]) data[key] = new Date(String(data[key])).toISOString();
        if (target === "materials" && uploaded) data.file_asset = uploaded;
        if (["students", "teachers", "parents"].includes(target) && creating) {
          data.role = {
            students: "STUDENT",
            teachers: "TEACHER",
            parents: "PARENT",
          }[target];
          if (!data.temporary_password) delete data.temporary_password;
          await mutate("/api/users/", data);
        } else
          await mutate(
            `/api/${endpoints[target] ?? target}/${row ? `${row.id}/` : ""}`,
            data,
            row ? "PATCH" : "POST",
          );
        setUploaded(null);
      },
    });
  }
  function createInstitute() {
    const fields = [
      ...fieldsFor("institutes", scope, catalogs, "SUPER_ADMIN"),
      { name: "admin_name", label: "Initial Admin name", required: true },
      {
        name: "admin_username",
        label: "Initial Admin username",
        required: true,
      },
      {
        name: "admin_email",
        label: "Initial Admin recovery email",
        type: "email",
        required: true,
      },
    ];
    setEdit({
      title: "Create institute",
      fields,
      initial: { is_active: true, primary_color: "#2563eb" },
      save: async (values) => {
        const { admin_name, admin_username, admin_email, ...institute } =
          values;
        await mutate("/api/super-admin/institutes/", {
          ...institute,
          initial_admin: {
            full_name: admin_name,
            username: admin_username,
            email: admin_email,
            role: "ADMIN",
          },
        });
      },
    });
  }
  async function accountStatus(row: Row) {
    if (!window.confirm(`Change login access for ${text(row.full_name)}?`))
      return;
    try {
      await mutate(`/api/users/${row.user}/status/`, {
        status: row.status === "DISABLED" ? "ACTIVE" : "DISABLED",
      });
    } catch (e) {
      setError(message(e));
    }
  }
  function rowActions(row: Row) {
    return (
      <>
        <button
          type="button"
          className="secondary"
          onClick={() => setDetail(row)}
        >
          View
        </button>
        {admin && ["students", "teachers", "parents"].includes(module) && (
          <>
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setEdit({
                  title: "Edit account details",
                  fields: [
                    { name: "full_name", label: "Full name", required: true },
                    { name: "email", label: "Email", type: "email" },
                    { name: "phone", label: "Phone", type: "tel" },
                  ],
                  initial: row,
                  save: (values) =>
                    mutate(`/api/users/${row.user}/`, values, "PATCH"),
                })
              }
            >
              Edit account
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => accountStatus(row)}
            >
              {row.status === "DISABLED" ? "Enable login" : "Disable login"}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                api(`/api/users/${row.user}/recovery/`, "POST", {})
                  .then(() => setNotice("Recovery instructions sent."))
                  .catch((e) => setError(message(e)));
              }}
            >
              Send access link
            </button>
          </>
        )}
        {admin && ["students", "teachers", "parents"].includes(module) && (
          <button
            type="button"
            className="secondary"
            onClick={() =>
              setEdit({
                title: "Edit profile",
                initial: row,
                fields: [
                  { name: "address", label: "Address", type: "textarea" },
                  ...(module === "teachers"
                    ? [
                        { name: "qualification", label: "Qualification" },
                        {
                          name: "experience_years",
                          label: "Experience (years)",
                          type: "number",
                        },
                        {
                          name: "joining_date",
                          label: "Joining date",
                          type: "date",
                        },
                      ]
                    : module === "students"
                      ? [
                          {
                            name: "date_of_birth",
                            label: "Date of birth",
                            type: "date",
                          },
                          {
                            name: "joining_date",
                            label: "Joining date",
                            type: "date",
                          },
                        ]
                      : [
                          {
                            name: "emergency_phone",
                            label: "Emergency phone",
                            type: "tel",
                          },
                        ]),
                ],
                save: (values) =>
                  mutate(
                    `/api/${module}/${row.id}/`,
                    Object.fromEntries(
                      Object.entries(values).map(([key, value]) => [
                        key,
                        value === "" &&
                        ["date_of_birth", "joining_date"].includes(key)
                          ? null
                          : value,
                      ]),
                    ),
                    "PATCH",
                  ),
              })
            }
          >
            Edit profile
          </button>
        )}
        {admin && module === "students" && (
          <button
            type="button"
            className="secondary"
            onClick={() =>
              setEdit({
                title: "Enroll / transfer student",
                fields: [
                  select("batch", "New batch", scope.batches),
                  {
                    name: "roll_number",
                    label: "Roll number for academic year",
                    required: true,
                  },
                ],
                save: (values) =>
                  mutate(`/api/students/${row.id}/transfer/`, values),
              })
            }
          >
            Change batch
          </button>
        )}
        {admin && module === "teachers" && (
          <button
            type="button"
            className="secondary"
            onClick={() =>
              setEdit({
                title: "Assign batch and subject",
                fields: [
                  select("batch", "Batch", scope.batches),
                  select("subject", "Subject", scope.subjects),
                ],
                save: (values) =>
                  mutate("/api/teacher-assignments/", {
                    ...values,
                    teacher: row.id,
                    is_active: true,
                  }),
              })
            }
          >
            Assign
          </button>
        )}
        {admin && module === "parents" && (
          <button
            type="button"
            className="secondary"
            onClick={() =>
              setEdit({
                title: "Link child",
                fields: [
                  select("student", "Student", scope.students, "full_name"),
                  {
                    name: "relationship",
                    label: "Relationship",
                    required: true,
                  },
                ],
                save: (values) =>
                  mutate("/api/parent-links/", {
                    ...values,
                    parent: row.id,
                    is_active: true,
                  }),
              })
            }
          >
            Link child
          </button>
        )}
        {(admin || platform) &&
          ![
            "students",
            "teachers",
            "parents",
            "fees",
            "attendance",
            "results",
            "support",
          ].includes(module) && (
            <button
              type="button"
              className="secondary"
              onClick={() => openEdit(module, row)}
            >
              Edit
            </button>
          )}
        {teacher && ["materials", "announcements"].includes(module) && (
          <button
            type="button"
            className="secondary"
            onClick={() => openEdit(module, row)}
          >
            Edit own
          </button>
        )}
        {(admin || teacher) && module === "exams" && (
          <button
            type="button"
            className="secondary"
            onClick={() => setMarks(row)}
          >
            Enter marks
          </button>
        )}
        {admin && module === "exams" && (
          <button
            type="button"
            className="secondary"
            onClick={() =>
              setEdit({
                title: `${row.published_at ? "Unpublish" : "Publish"} results: ${text(row.name)}`,
                fields: [
                  {
                    name: "confirmed",
                    label: row.published_at
                      ? "I confirm these results should be hidden from students and parents."
                      : "I confirm these results are ready for students and parents.",
                    type: "checkbox",
                    required: true,
                  },
                ],
                save: async (values) => {
                  if (!values.confirmed)
                    throw new Error("Please confirm the publication change.");
                  await mutate(`/api/exams/${row.id}/publication/`, {
                    published: !row.published_at,
                  });
                },
              })
            }
          >
            {row.published_at ? "Unpublish" : "Publish results"}
          </button>
        )}
        {admin && module === "fees" && (
          <button
            type="button"
            className="secondary"
            onClick={() =>
              mutate(`/api/fees/${row.id}/remind/`, {}).catch((e) =>
                setError(message(e)),
              )
            }
          >
            Send reminder
          </button>
        )}
        {module === "results" && (
          <a
            className="button secondary"
            href={`/api/results/${row.id}/report_card/`}
            target="_blank"
            rel="noreferrer"
          >
            Report card
          </a>
        )}
        {module === "materials" &&
          (row.file_asset ? (
            <a
              className="button secondary"
              href={`/api/materials/${row.id}/download/`}
              target="_blank"
              rel="noreferrer"
            >
              Download
            </a>
          ) : (
            <a
              className="button secondary"
              href={String(row.external_url)}
              target="_blank"
              rel="noreferrer"
            >
              Open link
            </a>
          ))}
        {module === "announcements" && Boolean(row.attachment) && (
          <a
            className="button secondary"
            href={`/api/announcements/${row.id}/attachment/`}
            target="_blank"
            rel="noreferrer"
          >
            Attachment
          </a>
        )}
        {platform && module === "support" && (
          <>
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setEdit({
                  title: "Support note",
                  fields: [
                    {
                      name: "support_note",
                      label: "Internal support note",
                      type: "textarea",
                    },
                    {
                      name: "support_status",
                      label: "Support status",
                      options: [
                        { value: "NONE", label: "None" },
                        { value: "OPEN", label: "Open" },
                        { value: "RESOLVED", label: "Resolved" },
                      ],
                    },
                  ],
                  initial: row,
                  save: (values) =>
                    mutate(
                      `/api/super-admin/institutes/${row.id}/`,
                      values,
                      "PATCH",
                    ),
                })
              }
            >
              Support note
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setEdit({
                  title: "Send Admin recovery link",
                  fields: [
                    select(
                      "admin",
                      "Admin",
                      (row.admin_accounts ?? []) as Row[],
                      "full_name",
                    ),
                  ],
                  save: (values) =>
                    mutate(
                      `/api/super-admin/institutes/${row.id}/admin_recovery/`,
                      values,
                    ),
                })
              }
            >
              Admin recovery
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setEdit({
                  title: "Admin account access",
                  fields: [
                    select(
                      "admin",
                      "Admin",
                      (row.admin_accounts ?? []) as Row[],
                      "full_name",
                    ),
                    {
                      name: "status",
                      label: "Access",
                      options: [
                        { value: "ACTIVE", label: "Enable" },
                        { value: "DISABLED", label: "Disable" },
                      ],
                      required: true,
                    },
                  ],
                  save: (values) =>
                    mutate(
                      `/api/super-admin/institutes/${row.id}/admin_status/`,
                      values,
                    ),
                })
              }
            >
              Admin access
            </button>
          </>
        )}
        {platform && module === "support" && (
          <button
            type="button"
            className="secondary"
            onClick={() => {
              api<Record<string, unknown>>(
                `/api/super-admin/institutes/${row.id}/usage/`,
              )
                .then((data) => setDetail({ id: row.id, ...data }))
                .catch((e) => setError(message(e)));
            }}
          >
            Usage
          </button>
        )}
      </>
    );
  }
  async function upload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const data = new FormData();
    data.append("file", file);
    try {
      const asset = await api<{ id: number }>("/api/files/", "POST", data);
      setUploaded(asset.id);
      setNotice("File uploaded. Add material details to share it.");
    } catch (e) {
      setError(message(e));
    }
  }
  function catalogEditor(kind: string) {
    const fieldSets: Record<string, Field[]> = {
      years: [
        { name: "name", label: "Academic year", required: true },
        { name: "starts_on", label: "Starts", type: "date", required: true },
        { name: "ends_on", label: "Ends", type: "date", required: true },
        { name: "is_current", label: "Current year", type: "checkbox" },
      ],
      classes: [{ name: "name", label: "Class name", required: true }],
      subjects: [
        { name: "name", label: "Subject name", required: true },
        { name: "code", label: "Subject code", required: true },
      ],
      plans: [
        { name: "name", label: "Plan name", required: true },
        {
          name: "student_limit",
          label: "Student limit",
          type: "number",
          required: true,
        },
        {
          name: "storage_limit_mb",
          label: "Storage MB",
          type: "number",
          required: true,
        },
        {
          name: "billing_cycle",
          label: "Billing cycle",
          options: [
            { value: "MONTHLY", label: "Monthly" },
            { value: "YEARLY", label: "Yearly" },
          ],
          required: true,
        },
      ],
    };
    const paths: Record<string, string> = {
      years: "academic-years",
      classes: "academic-classes",
      subjects: "subjects",
      plans: "super-admin/plans",
    };
    setEdit({
      title: `Add ${kind}`,
      fields: fieldSets[kind],
      save: (values) => mutate(`/api/${paths[kind]}/`, values),
    });
  }

  if (!user || !brand)
    return (
      <main className="auth-page">
        <p role="status">Opening your workspace...</p>
      </main>
    );
  const title =
    navigation[user.role].find(([key]) => key === module)?.[1] ??
    "Page unavailable";
  const dashboardDescription: Record<User["role"], string> = {
    ADMIN: `Here’s what’s happening at ${brand.name} today.`,
    TEACHER: "Your classes, students, and teaching priorities in one place.",
    STUDENT: "Keep up with your classes, learning, and upcoming work.",
    PARENT: "A clear view of your child’s learning progress and updates.",
    SUPER_ADMIN: "Monitor institutes and keep the platform running smoothly.",
  };
  const creatable =
    (admin &&
      [
        "students",
        "teachers",
        "parents",
        "batches",
        "timetable",
        "materials",
        "exams",
        "announcements",
      ].includes(module)) ||
    (teacher && ["materials", "announcements"].includes(module)) ||
    (platform && ["institutes", "domains", "subscriptions"].includes(module));
  return (
    <div
      className="app-shell"
      style={
        { "--accent": brand.primary_color ?? "#2563eb" } as React.CSSProperties
      }
    >
      <aside className={`sidebar ${sidebar ? "open" : ""}`}>
        <div className="brand">
          {brand.has_logo ? (
            <Image
              src="/api/branding/logo/"
              width={38}
              height={40}
              alt={`${brand.name} logo`}
              unoptimized
            />
          ) : (
            <span className="brand-mark">{brand.name.slice(0, 1)}</span>
          )}
          <div>
            <strong>{brand.name}</strong>
            <small>{platform ? "PLATFORM CONTROL" : "CLASS MANAGEMENT"}</small>
          </div>
        </div>
        <nav aria-label="Main navigation">
          {(
            navigationGroups[user.role] ?? [
              ["Workspace", navigation[user.role].map(([key]) => key)],
            ]
          ).map(([group, modules]) => (
            <div className="nav-group" key={group}>
              <span className="nav-group-label">{group}</span>
              {modules.map((key) => {
                const label =
                  navigation[user.role].find(([item]) => item === key)?.[1] ??
                  key;
                return (
                  <Link
                    onClick={() => {
                      setSidebar(false);
                      setPage(1);
                      setQuery("");
                      setSearch("");
                      setNotice("");
                    }}
                    className={key === module ? "active" : ""}
                    key={key}
                    href={`/portal/${key}`}
                  >
                    <span className="nav-icon" aria-hidden="true">
                      {navSymbols[key] ?? "•"}
                    </span>
                    {label}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span>Powered by GrowthSathi</span>
          <small>One connected learning community</small>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <button
            type="button"
            className="secondary menu-toggle"
            onClick={() => setSidebar(!sidebar)}
            aria-label="Toggle navigation"
          >
            Menu
          </button>
          <span className="muted">
            {brand.name} / {title}
          </span>
          <div className="topbar-actions">
            {!platform && (
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  if (notifications) setNotifications(null);
                  else
                    api<Page<Row>>("/api/notifications/")
                      .then((data) => setNotifications(data.results))
                      .catch((e) => setError(message(e)));
                }}
              >
                Alerts
              </button>
            )}
            <span className="user-name">{user.full_name}</span>
            <span className="avatar" aria-hidden="true">
              {user.full_name.slice(0, 1)}
            </span>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                api("/api/auth/logout/", "POST", {})
                  .then(() => window.location.assign("/login"))
                  .catch((e) => setError(message(e)));
              }}
            >
              Sign out
            </button>
          </div>
        </header>
        <main className="content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                {user.role.replaceAll("_", " ")} WORKSPACE
              </span>
              <h1>{title}</h1>
              <p className="muted">
                {module === "dashboard"
                  ? dashboardDescription[user.role]
                  : "View and manage the information that matters."}
              </p>
            </div>
            <div className="row-actions">
              {creatable && (
                <button
                  type="button"
                  onClick={() =>
                    module === "institutes"
                      ? createInstitute()
                      : openEdit(module)
                  }
                >
                  + Add{" "}
                  {module === "materials"
                    ? "material"
                    : module === "batches"
                      ? "batch"
                      : module === "timetable"
                        ? "lecture"
                        : module.replace(/s$/, "")}
                </button>
              )}
              {module === "attendance" && (admin || teacher) && (
                <button type="button" onClick={() => setAttendance(true)}>
                  Take attendance
                </button>
              )}
              {module === "fees" && admin && (
                <button type="button" onClick={() => setFeePlan(true)}>
                  Create fee plan
                </button>
              )}
            </div>
          </div>
          {user.role === "PARENT" && (
            <label className="child-selector">
              Child
              <select
                value={child}
                onChange={(e) => {
                  setChild(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All linked children</option>
                {scope.students.map((row) => (
                  <option key={row.id} value={row.id}>
                    {text(row.full_name)}
                  </option>
                ))}
              </select>
            </label>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {notice && (
            <p className="success" role="status">
              {notice}
            </p>
          )}
          {notifications && (
            <section className="card">
              <div className="section-heading">
                <h2>Recent alerts</h2>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setNotifications(null)}
                >
                  Close
                </button>
              </div>
              {notifications.length ? (
                notifications.map((row) => (
                  <div className="alert-row" key={row.id}>
                    <Link
                      href={`/portal/${row.kind === "timetable" && user.role === "PARENT" ? "announcements" : row.kind}`}
                    >
                      {text(row.kind)} updated
                    </Link>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => {
                        api(`/api/notifications/${row.id}/read/`, "POST", {})
                          .then(() =>
                            setNotifications(
                              notifications.filter(
                                (item) => item.id !== row.id,
                              ),
                            ),
                          )
                          .catch((e) => setError(message(e)));
                      }}
                    >
                      Mark read
                    </button>
                  </div>
                ))
              ) : (
                <p className="muted">You are all caught up.</p>
              )}
            </section>
          )}
          {loading ? (
            <section className="card skeleton" role="status">
              Loading {title.toLowerCase()}...
            </section>
          ) : (
            <>
              {["dashboard", "attendance", "fees", "results"].includes(
                module,
              ) &&
                canOpen(user.role, module) && (
                  <div
                    className={`stats ${module === "dashboard" && admin ? "admin-stats-hidden" : ""}`}
                  >
                    {Object.entries(stats).map(([key, value]) => (
                      <div className="stat" key={key}>
                        <span>{key.replaceAll("_", " ")}</span>
                        <strong>{text(value)}</strong>
                      </div>
                    ))}
                  </div>
                )}
              {module === "dashboard" && admin ? (
                <AdminDashboard stats={stats} sections={dashboardSections} />
              ) : module === "dashboard" ? (
                <section className="card">
                  <h2>
                    {user.role === "ADMIN"
                      ? "Run your institute with confidence"
                      : "Your workspace"}
                  </h2>
                  <p className="muted">
                    {user.role === "ADMIN"
                      ? "Open a module to review live records and take your next operational action."
                      : "Choose a module to see live records and take your next action."}
                  </p>
                  <div className="quick-links">
                    {navigation[user.role].slice(1, 7).map(([key, label]) => (
                      <Link key={key} href={`/portal/${key}`}>
                        {label}
                        <span>Open &rarr;</span>
                      </Link>
                    ))}
                  </div>
                </section>
              ) : null}
              {module === "dashboard" &&
                !admin &&
                dashboardSections.map((section) => (
                  <section className="card" key={section.title}>
                    <div className="section-heading">
                      <h2>{section.title}</h2>
                      <Link href={`/portal/${section.module}`}>
                        Open module
                      </Link>
                    </div>
                    <DataTable rows={section.rows} columns={section.columns} />
                  </section>
                ))}
              {summarySections.map((section) => (
                <section className="card" key={section.title}>
                  <h2>{section.title}</h2>
                  <DataTable rows={section.rows} columns={section.columns} />
                </section>
              ))}
              {module === "create-institute" && (
                <section className="card">
                  <h2>Welcome a new institute</h2>
                  <p>
                    Set up its identity and initial Admin account. Then
                    configure a verified domain and subscription.
                  </p>
                  <button type="button" onClick={createInstitute}>
                    Create institute
                  </button>
                </section>
              )}
              {module === "settings" && (
                <>
                  <section className="card">
                    <div className="section-heading">
                      <h2>Institute details</h2>
                      <button
                        type="button"
                        onClick={() =>
                          setEdit({
                            title: "Institute branding",
                            fields: fieldsFor(
                              "institutes",
                              scope,
                              catalogs,
                              "ADMIN",
                            ).filter(
                              (f) => !["slug", "is_active"].includes(f.name),
                            ),
                            initial: settings.branding,
                            save: (values) =>
                              mutate(
                                "/api/settings/",
                                { branding: values },
                                "PATCH",
                              ),
                          })
                        }
                      >
                        Edit details
                      </button>
                    </div>
                    <p>{text(settings.branding)}</p>
                    <label>
                      Upload institute logo (PNG/JPEG)
                      <input
                        type="file"
                        accept="image/png,image/jpeg"
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (file) {
                            const form = new FormData();
                            form.append("logo", file);
                            try {
                              await api("/api/settings/", "POST", form);
                              reload();
                            } catch (err) {
                              setError(message(err));
                            }
                          }
                        }}
                      />
                    </label>
                  </section>
                  <section className="card">
                    <div className="section-heading">
                      <h2>Academic defaults</h2>
                      <button
                        type="button"
                        onClick={() =>
                          setEdit({
                            title: "Attendance and exam defaults",
                            fields: [
                              {
                                name: "attendance_threshold",
                                label: "Low attendance threshold (%)",
                                type: "number",
                                required: true,
                              },
                              {
                                name: "default_passing_percentage",
                                label: "Default passing percentage",
                                type: "number",
                                required: true,
                              },
                              {
                                name: "fee_due_day",
                                label: "Default fee due day (1-28)",
                                type: "number",
                                required: true,
                              },
                              {
                                name: "absence_alerts",
                                label: "Absence alerts",
                                type: "checkbox",
                              },
                            ],
                            initial: settings.settings,
                            save: (values) =>
                              mutate(
                                "/api/settings/",
                                { settings: values },
                                "PATCH",
                              ),
                          })
                        }
                      >
                        Edit defaults
                      </button>
                    </div>
                    <p>{text(settings.settings)}</p>
                    <div className="row-actions">
                      {["years", "classes", "subjects"].map((kind) => (
                        <button
                          type="button"
                          key={kind}
                          className="secondary"
                          onClick={() => catalogEditor(kind)}
                        >
                          Add {kind}
                        </button>
                      ))}
                    </div>
                    <h3>Academic years</h3>
                    <p>
                      {catalogs.years
                        ?.map((row) => text(row.name))
                        .join(", ") || "No academic years yet"}
                    </p>
                    <h3>Classes and subjects</h3>
                    <p>
                      {catalogs.classes
                        ?.map((row) => text(row.name))
                        .join(", ")}
                    </p>
                    <p>
                      {scope.subjects.map((row) => text(row.name)).join(", ") ||
                        "No subjects yet"}
                    </p>
                  </section>
                </>
              )}
              {module === "profile" && (
                <section className="card">
                  <h2>{user.full_name}</h2>
                  {detail?.profile != null && (
                    <p className="muted">{text(detail.profile)}</p>
                  )}
                  <p>
                    {user.username} / {user.role}
                  </p>
                  <p>
                    {user.email} / {user.phone}
                  </p>
                  <div className="row-actions">
                    <button
                      type="button"
                      onClick={() =>
                        setEdit({
                          title: "Contact details",
                          fields: [
                            { name: "email", label: "Email", type: "email" },
                            { name: "phone", label: "Phone", type: "tel" },
                          ],
                          initial: user,
                          save: async (values) => {
                            await mutate("/api/profile/", values, "PATCH");
                            setUser({ ...user, ...values } as User);
                          },
                        })
                      }
                    >
                      Edit contact details
                    </button>
                    <Link className="button secondary" href="/account/password">
                      Change password
                    </Link>
                  </div>
                </section>
              )}
              {((admin && module === "attendance") ||
                (teacher && module === "profile")) && (
                <TeacherAttendance scope={scope} editable={Boolean(admin)} />
              )}
              {module === "timetable" && (
                <Timetable
                  scope={scope}
                  revision={revision}
                  actions={rowActions}
                />
              )}
              {columns[module] && module !== "timetable" && (
                <section className="card">
                  <div className="section-heading">
                    <h2>
                      {title}
                      <span className="count">{count}</span>
                    </h2>
                    <form
                      className="search"
                      onSubmit={(e) => {
                        e.preventDefault();
                        setQuery(search);
                        setPage(1);
                      }}
                    >
                      <input
                        aria-label={`Search ${title}`}
                        placeholder="Search records..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                      <button type="submit" className="secondary">
                        Search
                      </button>
                    </form>
                  </div>
                  {module === "materials" && (admin || teacher) && (
                    <label className="upload">
                      Upload a file before adding material details
                      <input
                        type="file"
                        accept=".pdf,.doc,.docx,.ppt,.pptx,.jpg,.jpeg,.png"
                        onChange={upload}
                      />
                      {uploaded && (
                        <span className="success">File ready to attach.</span>
                      )}
                    </label>
                  )}
                  {module === "subscriptions" && platform && (
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => catalogEditor("plans")}
                    >
                      Add plan
                    </button>
                  )}
                  <ModuleFilters
                    module={module}
                    scope={scope}
                    classes={catalogs.classes ?? []}
                    values={filterState[module] ?? {}}
                    onChange={(values) => {
                      setFilterState({ ...filterState, [module]: values });
                      setPage(1);
                    }}
                  />
                  {(admin || (teacher && module !== "fees")) &&
                    ["attendance", "fees", "results"].includes(module) && (
                      <a
                        className="button secondary"
                        href={`/api/${module}/report/?${filterQuery}&search=${encodeURIComponent(query)}${child ? `&student=${child}` : ""}`}
                      >
                        Download filtered report
                      </a>
                    )}
                  <DataTable
                    rows={rows}
                    columns={
                      teacher && module === "students"
                        ? columns.students.slice(0, 2)
                        : columns[module]
                    }
                    actions={rowActions}
                  />
                  <div className="pagination">
                    <span>{count} records</span>
                    <button
                      type="button"
                      className="secondary"
                      disabled={page === 1}
                      onClick={() => setPage(page - 1)}
                    >
                      Previous
                    </button>
                    <span>Page {page}</span>
                    <button
                      type="submit"
                      className="secondary"
                      disabled={page * 30 >= count}
                      onClick={() => setPage(page + 1)}
                    >
                      Next
                    </button>
                  </div>
                </section>
              )}
            </>
          )}
        </main>
      </div>
      {edit && (
        <Editor {...edit} onSave={edit.save} onClose={() => setEdit(null)} />
      )}
      {attendance && (
        <AttendanceEntry
          scope={scope}
          onDone={reload}
          onClose={() => setAttendance(false)}
        />
      )}
      {marks && (
        <MarksEntry
          exam={marks}
          onDone={reload}
          onClose={() => setMarks(null)}
        />
      )}
      {feePlan && (
        <FeePlan
          scope={scope}
          onDone={reload}
          onClose={() => setFeePlan(false)}
        />
      )}
      {detail &&
        ["students", "teachers", "parents", "batches"].includes(module) && (
          <EntityDetail
            module={module}
            row={detail}
            user={user}
            scope={scope}
            onClose={() => setDetail(null)}
            onDone={reload}
          />
        )}
      {detail && module === "fees" && (
        <FeeDetail
          account={detail}
          isAdmin={Boolean(admin)}
          onDone={reload}
          onClose={() => setDetail(null)}
        />
      )}
      {detail &&
        ![
          "fees",
          "profile",
          "students",
          "teachers",
          "parents",
          "batches",
        ].includes(module) && (
          <div className="modal-backdrop">
            <section
              className="modal"
              role="dialog"
              aria-modal="true"
              aria-label="Record details"
            >
              <div className="section-heading">
                <h2>Record details</h2>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setDetail(null)}
                >
                  Close
                </button>
              </div>
              <dl>
                {Object.entries(detail)
                  .filter(
                    ([key]) => !["id", "user", "uploaded_by"].includes(key),
                  )
                  .map(([key, value]) => (
                    <div key={key}>
                      <dt>{key.replaceAll("_", " ")}</dt>
                      <dd>{text(value)}</dd>
                    </div>
                  ))}
              </dl>
            </section>
          </div>
        )}
    </div>
  );
}
