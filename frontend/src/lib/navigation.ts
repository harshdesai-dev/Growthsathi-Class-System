import type { Role } from "./api";
export const navigation: Record<Role, [string, string][]> = {
  ADMIN: [
    ["dashboard", "Dashboard"],
    ["students", "Students"],
    ["teachers", "Teachers"],
    ["parents", "Parents"],
    ["batches", "Batches"],
    ["timetable", "Timetable"],
    ["attendance", "Attendance"],
    ["fees", "Fees"],
    ["materials", "Notes & Materials"],
    ["exams", "Exams"],
    ["results", "Results"],
    ["announcements", "Announcements"],
    ["settings", "Settings"],
  ],
  TEACHER: [
    ["dashboard", "Dashboard"],
    ["batches", "My Batches"],
    ["timetable", "Timetable"],
    ["attendance", "Attendance"],
    ["materials", "Notes & Materials"],
    ["exams", "Exams"],
    ["results", "Results"],
    ["announcements", "Announcements"],
    ["profile", "Profile"],
  ],
  STUDENT: [
    ["dashboard", "Dashboard"],
    ["timetable", "Timetable"],
    ["attendance", "Attendance"],
    ["fees", "Fees"],
    ["materials", "Notes & Materials"],
    ["exams", "Exams"],
    ["results", "Results"],
    ["announcements", "Announcements"],
    ["profile", "Profile"],
  ],
  PARENT: [
    ["dashboard", "Dashboard"],
    ["attendance", "Attendance"],
    ["fees", "Fees"],
    ["exams", "Exams"],
    ["results", "Results"],
    ["announcements", "Announcements"],
    ["students", "Child Profile"],
    ["profile", "My Profile"],
  ],
  SUPER_ADMIN: [
    ["dashboard", "Dashboard"],
    ["institutes", "Institutes"],
    ["create-institute", "Create Institute"],
    ["subscriptions", "Subscriptions"],
    ["domains", "Domains / Branding"],
    ["support", "Usage & Support"],
  ],
};
export function canOpen(role: Role, module: string) {
  return navigation[role].some(([key]) => key === module);
}

export const navigationGroups: Partial<Record<Role, [string, string[]][]>> = {
  ADMIN: [
    ["Overview", ["dashboard"]],
    ["Academics", ["students", "teachers", "parents", "batches", "timetable"]],
    ["Operations", ["attendance", "fees"]],
    ["Learning", ["materials", "exams", "results"]],
    ["Communication", ["announcements"]],
    ["System", ["settings"]],
  ],
  TEACHER: [
    ["Overview", ["dashboard"]],
    ["Teaching", ["batches", "timetable", "attendance"]],
    ["Learning", ["materials", "exams", "results"]],
    ["Communication", ["announcements"]],
    ["Account", ["profile"]],
  ],
  STUDENT: [
    ["Overview", ["dashboard"]],
    [
      "My learning",
      ["timetable", "attendance", "materials", "exams", "results"],
    ],
    ["Account", ["fees", "announcements", "profile"]],
  ],
  PARENT: [
    ["Overview", ["dashboard"]],
    ["My child", ["attendance", "fees", "exams", "results", "students"]],
    ["Updates", ["announcements"]],
    ["Account", ["profile"]],
  ],
  SUPER_ADMIN: [
    ["Overview", ["dashboard"]],
    [
      "Institute management",
      ["institutes", "create-institute", "subscriptions"],
    ],
    ["Platform", ["domains", "support"]],
  ],
};

export const navSymbols: Record<string, string> = {
  dashboard: "▦",
  students: "♙",
  teachers: "♙",
  parents: "♙",
  batches: "▤",
  timetable: "◷",
  attendance: "✓",
  fees: "₹",
  materials: "▱",
  exams: "✦",
  results: "↗",
  announcements: "◉",
  settings: "⚙",
  profile: "◌",
  institutes: "⌂",
  "create-institute": "+",
  subscriptions: "◇",
  domains: "⌘",
  support: "?",
};
