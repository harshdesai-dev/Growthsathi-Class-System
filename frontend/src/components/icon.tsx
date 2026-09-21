type IconName =
  | "search"
  | "students"
  | "teachers"
  | "parents"
  | "batches"
  | "timetable"
  | "attendance"
  | "fees"
  | "materials"
  | "exams"
  | "results"
  | "announcements"
  | "settings"
  | "profile"
  | "institutes"
  | "subscriptions"
  | "domains"
  | "support"
  | "dashboard"
  | "alert"
  | "check"
  | "arrow-right"
  | "more";

const shapes: Record<IconName, React.ReactNode> = {
  search: <><circle cx="11" cy="11" r="5.5" /><path d="m15.25 15.25 4 4" /></>,
  students: <><circle cx="12" cy="8" r="3" /><path d="M5.5 20c.6-3.1 2.7-5 6.5-5s5.9 1.9 6.5 5M4 11.5a2.5 2.5 0 0 1 1.8-2.4M20 11.5a2.5 2.5 0 0 0-1.8-2.4" /></>,
  teachers: <><circle cx="12" cy="7" r="3" /><path d="M6 20c.6-3.4 2.6-5 6-5s5.4 1.6 6 5M7 12h10" /></>,
  parents: <><circle cx="9" cy="8" r="2.6" /><circle cx="16" cy="10" r="2.2" /><path d="M3.5 20c.4-3 2.2-4.8 5.5-4.8 2.2 0 3.8.8 4.7 2.4M13.5 20c.4-2.4 1.8-3.8 4.4-3.8 1 0 1.8.2 2.6.7" /></>,
  batches: <><rect x="4" y="5" width="16" height="14" rx="2" /><path d="M8 9h8M8 13h5" /></>,
  timetable: <><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4M16 3v4M4 10h16M8 14h3" /></>,
  attendance: <><path d="m5 12 4 4 10-10" /><circle cx="12" cy="12" r="9" /></>,
  fees: <><rect x="4" y="6" width="16" height="12" rx="2" /><path d="M7 10h10M8 15h3" /></>,
  materials: <><path d="M5 4h10l4 4v12H5zM15 4v5h5M8 14h8" /></>,
  exams: <><path d="M7 3h10v18H7zM10 8h4M10 12h4M10 16h2" /></>,
  results: <><path d="M5 20V10M10 20V5M15 20v-7M20 20V8" /></>,
  announcements: <><path d="M4 12h3l9-5v10l-9-5H4zM8 16v3" /><path d="M19 9c1 .7 1.5 1.7 1.5 3S20 14.3 19 15" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.3 1a7 7 0 0 0-1.7-1L14.5 3h-5l-.4 3.1a7 7 0 0 0-1.7 1l-2.3-1-2 3.4 2 1.5a7 7 0 0 0 0 2L3 14.5l2 3.4 2.3-1a7 7 0 0 0 1.7 1l.5 3.1h5l.4-3.1a7 7 0 0 0 1.7-1l2.3 1 2-3.4-2-1.5c.1-.3.1-.7.1-1Z" /></>,
  profile: <><circle cx="12" cy="8" r="3" /><path d="M5 21c.7-3.8 3-5.7 7-5.7s6.3 1.9 7 5.7" /></>,
  institutes: <><path d="M4 20h16M6 20V8l6-4 6 4v12M9 11h1M14 11h1M9 15h1M14 15h1" /></>,
  subscriptions: <><path d="M5 6h14v12H5zM5 10h14M8 14h3" /></>,
  domains: <><circle cx="12" cy="12" r="8" /><path d="M4 12h16M12 4c2 2.2 3 4.8 3 8s-1 5.8-3 8c-2-2.2-3-4.8-3-8s1-5.8 3-8Z" /></>,
  support: <><path d="M5 12a7 7 0 0 1 14 0v4h-3v-4a4 4 0 0 0-8 0v4H5zM12 20h3" /></>,
  dashboard: <><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></>,
  alert: <><path d="M12 4 3.8 19h16.4L12 4Z" /><path d="M12 9v4M12 16h.01" /></>,
  check: <><circle cx="12" cy="12" r="9" /><path d="m8 12 2.6 2.6L16.5 9" /></>,
  "arrow-right": <><path d="M5 12h14M14 6l6 6-6 6" /></>,
  more: <><circle cx="5" cy="12" r="1" fill="currentColor" /><circle cx="12" cy="12" r="1" fill="currentColor" /><circle cx="19" cy="12" r="1" fill="currentColor" /></>,
};

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return <svg aria-hidden="true" className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{shapes[name]}</svg>;
}

export type { IconName };
