import { DragEvent, FormEvent, useEffect, useState } from "react";

type Shift = {
  id: number;
  employee_id: number;
  shift_date: string;
  start_at: string;
  end_at: string;
  role_label: string | null;
  location_name: string | null;
  is_published: boolean;
  published_at: string | null;
  published_by_name: string | null;
};

type Note = {
  id: number;
  employee_id: number | null;
  title: string;
  body: string;
  is_active: boolean;
  show_at_clock_in: boolean;
};

type User = {
  id: number;
  full_name: string;
  email: string | null;
  role: string;
  is_active: boolean;
  employee_number: string | null;
  job_title: string | null;
};

type Integration = {
  id: number;
  organization_id: number;
  provider: string;
  status: string;
  settings: Record<string, unknown> | null;
  last_synced_at: string | null;
};

type ClockLookupResponse = {
  employee_name: string;
  employee_id: number;
  schedule: Shift[];
  notes: Note[];
};

type ClockResponse = ClockLookupResponse & {
  status: string;
};

type LoginResponse = {
  message: string;
  access_token: string;
  token_type: string;
  user: User;
};

type DashboardSummary = {
  organization_id: number;
  active_employees: number;
  currently_clocked_in: number;
  report_recipients: number;
  connected_integrations: number;
  pending_notifications: number;
};

type QuickBooksActionResponse = {
  message: string;
  integration: Integration;
  export_summary?: {
    entries: number;
    hours: number;
    start_date: string;
    end_date: string;
  };
};

type SchedulePublishResponse = {
    message: string;
    week_start: string;
    week_end: string;
    published_shift_count: number;
};

type SchedulePublication = {
  id: number;
  organization_id: number;
  week_start: string;
  week_end: string;
  action: string;
  shift_count: number;
  published_by_name: string;
  comment: string | null;
  created_at: string;
  acknowledged_count: number;
};

type ScheduleAcknowledgment = {
  id: number;
  organization_id: number;
  employee_id: number;
  week_start: string;
  acknowledged_at: string;
};

type AvailabilityRequest = {
  id: number;
  organization_id: number;
  employee_id: number;
  weekday: number | null;
  start_time: string;
  end_time: string;
  start_date: string | null;
  end_date: string | null;
  note: string | null;
  status: string;
  manager_response: string | null;
  created_at: string;
};

type CoverageTarget = {
  id: number;
  organization_id: number;
  weekday: number;
  daypart: "morning" | "lunch" | "close";
  role_label: string | null;
  required_headcount: number;
  created_at: string;
};

type QuickBooksAuthorization = {
  authorization_url: string;
  state: string;
};

type QuickBooksConfigStatus = {
  configured: boolean;
  client_id_present: boolean;
  client_secret_present: boolean;
  redirect_uri: string;
  environment: string;
  scopes: string[];
};

type SetupOverview = {
  organization_id: number;
  organization_name: string;
  timezone: string;
  admin_count: number;
  manager_count: number;
  employee_count: number;
  scheduled_shift_count: number;
  note_count: number;
  report_recipient_count: number;
  time_entry_count: number;
  quickbooks_configured: boolean;
  quickbooks_connected: boolean;
  checklist: Array<{
    key: string;
    label: string;
    complete: boolean;
    detail: string;
  }>;
};

type TimeOffRequest = {
  id: number;
  organization_id: number;
  employee_id: number;
  start_date: string;
  end_date: string;
  reason: string;
  status: string;
  manager_response: string | null;
  created_at: string;
};

type ShiftChangeRequest = {
  id: number;
  organization_id: number;
  shift_id: number;
  requester_employee_id: number;
  request_type: "pickup" | "swap";
  note: string;
  status: string;
  manager_response: string | null;
  replacement_employee_id: number | null;
  replacement_employee_name: string | null;
  created_at: string;
  reviewed_at: string | null;
  shift_date: string;
  shift_start_at: string;
  shift_end_at: string;
  requester_name: string;
};

type NotificationItem = {
  key: string;
  category: string;
  title: string;
  detail: string;
  created_at: string | null;
  target_tab: string | null;
  target_id: number | null;
};

type TimeEntry = {
  id: number;
  organization_id: number;
  employee_id: number;
  clock_in_at: string;
  clock_out_at: string | null;
  clock_in_source: string;
  clock_out_source: string | null;
  notes: string | null;
  approved: boolean;
};

type ReportRecipient = {
  id: number;
  organization_id: number;
  email: string;
  report_type: string;
  is_active: boolean;
  created_at: string;
};

type EmployeeSelfProfile = {
  employee_id: number;
  full_name: string;
  employee_number: string | null;
  job_title: string | null;
  preferred_weekly_hours: number | null;
  preferred_shift_notes: string | null;
};

type AdminTab = "setup" | "employees" | "schedules" | "notes" | "requests" | "timesheets" | "integrations";
type EmployeeTab = "home" | "schedule" | "request_off" | "availability" | "shift_changes" | "profile";
type KeypadField = "employee" | "pin";
type RequestQueueTab = "pending" | "approved";
type RequestBoardTab = "time_off" | "shift_changes";

const API_BASE = "http://127.0.0.1:8000/api";
const SHIFT_TEMPLATES = [
  { key: "morning", label: "Morning", start: "08:00", end: "14:00", role: "Morning Shift" },
  { key: "lunch", label: "Lunch", start: "10:00", end: "16:00", role: "Lunch Rush" },
  { key: "close", label: "Close", start: "16:00", end: "22:00", role: "Closing Shift" },
  { key: "full", label: "Full Day", start: "09:00", end: "17:00", role: "Full Day Coverage" },
] as const;

function formatShiftWindow(shift: Shift) {
  const start = new Date(shift.start_at);
  const end = new Date(shift.end_at);
  return {
    day: start.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }),
    time: `${start.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })} - ${end.toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    })}`,
  };
}

function toIsoDateTime(dateValue: string, timeValue: string) {
  return new Date(`${dateValue}T${timeValue}:00`).toISOString();
}

function splitIsoDateTime(value: string) {
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return {
    date: local.toISOString().slice(0, 10),
    time: local.toISOString().slice(11, 16),
  };
}

function formatDate(dateValue: string) {
  return new Date(dateValue).toLocaleDateString(undefined, { month: "short", day: "numeric", weekday: "short" });
}

function buildScheduleCalendar(shifts: Shift[]) {
  if (shifts.length === 0) {
    return [];
  }
  const byDate = new Map<string, Shift[]>();
  for (const shift of shifts) {
    const items = byDate.get(shift.shift_date) ?? [];
    items.push(shift);
    byDate.set(shift.shift_date, items);
  }
  return Array.from(byDate.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([shiftDate, items]) => ({ shiftDate, items }));
}

function getWeekStartIso(value = new Date()) {
  const result = new Date(value);
  const day = result.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  result.setDate(result.getDate() + diff);
  result.setHours(0, 0, 0, 0);
  return result.toISOString().slice(0, 10);
}

function addDays(dateValue: string, amount: number) {
  const result = new Date(`${dateValue}T00:00:00`);
  result.setDate(result.getDate() + amount);
  return result.toISOString().slice(0, 10);
}

function formatWeekLabel(weekStart: string) {
  const start = new Date(`${weekStart}T00:00:00`);
  const end = new Date(`${addDays(weekStart, 6)}T00:00:00`);
  return `${start.toLocaleDateString(undefined, { month: "short", day: "numeric" })} - ${end.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  })}`;
}

function formatScheduleDayLabel(dateValue: string) {
  return new Date(`${dateValue}T00:00:00`).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

function weekdayLabel(value: number) {
  return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][value] ?? "Day";
}

function coverageDaypartLabel(value: CoverageTarget["daypart"]) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function resolveDaypartFromHour(hour: number) {
  if (hour < 11) {
    return "morning" as const;
  }
  if (hour < 16) {
    return "lunch" as const;
  }
  return "close" as const;
}

function resolveDaypart(shift: Shift) {
  return resolveDaypartFromHour(new Date(shift.start_at).getHours());
}

function resolveDaypartFromTimeLabel(value: string) {
  const [hours] = value.split(":").map(Number);
  return resolveDaypartFromHour(hours ?? 0);
}

function getShiftHours(shift: Shift) {
  const start = new Date(shift.start_at).getTime();
  const end = new Date(shift.end_at).getTime();
  return Math.max(0, end - start) / 36e5;
}

function rangesOverlap(startA: string, endA: string, startB: string, endB: string) {
  return new Date(startA).getTime() < new Date(endB).getTime() && new Date(startB).getTime() < new Date(endA).getTime();
}

export default function App() {
  const [organizationId, setOrganizationId] = useState("1");
  const [employeeNumber, setEmployeeNumber] = useState("1001");
  const [pinCode, setPinCode] = useState("1234");
  const [activeKeypadField, setActiveKeypadField] = useState<KeypadField>("employee");
  const [employeePortal, setEmployeePortal] = useState<ClockLookupResponse | null>(null);
  const [employeeTab, setEmployeeTab] = useState<EmployeeTab>("home");
  const [employeeClockMessage, setEmployeeClockMessage] = useState("Enter employee number and PIN to clock in.");
  const [employeeError, setEmployeeError] = useState("");
  const [isClockLoading, setIsClockLoading] = useState(false);
  const [employeeRequests, setEmployeeRequests] = useState<TimeOffRequest[]>([]);
  const [employeeAvailabilityRequests, setEmployeeAvailabilityRequests] = useState<AvailabilityRequest[]>([]);
  const [employeeShiftChangeRequests, setEmployeeShiftChangeRequests] = useState<ShiftChangeRequest[]>([]);
  const [employeeScheduleAcknowledgments, setEmployeeScheduleAcknowledgments] = useState<ScheduleAcknowledgment[]>([]);
  const [employeeProfile, setEmployeeProfile] = useState<EmployeeSelfProfile | null>(null);
  const [requestOffForm, setRequestOffForm] = useState({
    start_date: new Date().toISOString().slice(0, 10),
    end_date: new Date().toISOString().slice(0, 10),
    reason: "",
  });
  const [requestOffMessage, setRequestOffMessage] = useState("");
  const [availabilityForm, setAvailabilityForm] = useState({
    mode: "recurring" as "recurring" | "date_range",
    weekday: String(new Date().getDay()),
    start_time: "09:00",
    end_time: "17:00",
    start_date: new Date().toISOString().slice(0, 10),
    end_date: new Date().toISOString().slice(0, 10),
    note: "",
  });
  const [employeeProfileForm, setEmployeeProfileForm] = useState({
    preferred_weekly_hours: "",
    preferred_shift_notes: "",
  });

  const [adminEmail, setAdminEmail] = useState("admin@demodiner.com");
  const [adminPassword, setAdminPassword] = useState("admin1234");
  const [adminUser, setAdminUser] = useState<User | null>(null);
  const [token, setToken] = useState("");
  const [adminError, setAdminError] = useState("");
  const [adminMessage, setAdminMessage] = useState("");
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [employees, setEmployees] = useState<User[]>([]);
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [orgTimeOffRequests, setOrgTimeOffRequests] = useState<TimeOffRequest[]>([]);
  const [orgAvailabilityRequests, setOrgAvailabilityRequests] = useState<AvailabilityRequest[]>([]);
  const [orgShiftChangeRequests, setOrgShiftChangeRequests] = useState<ShiftChangeRequest[]>([]);
  const [timeEntries, setTimeEntries] = useState<TimeEntry[]>([]);
  const [reportRecipients, setReportRecipients] = useState<ReportRecipient[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [coverageTargets, setCoverageTargets] = useState<CoverageTarget[]>([]);
  const [schedulePublications, setSchedulePublications] = useState<SchedulePublication[]>([]);
  const [adminTab, setAdminTab] = useState<AdminTab>("setup");
  const [setupMessage, setSetupMessage] = useState("Preparing demo workspace...");
  const [exportSummary, setExportSummary] = useState<QuickBooksActionResponse["export_summary"] | null>(null);
  const [quickBooksAuth, setQuickBooksAuth] = useState<QuickBooksAuthorization | null>(null);
  const [quickBooksConfig, setQuickBooksConfig] = useState<QuickBooksConfigStatus | null>(null);
  const [setupOverview, setSetupOverview] = useState<SetupOverview | null>(null);

  const emptyEmployeeForm = {
    id: null as number | null,
    full_name: "",
    email: "",
    employee_number: "",
    pin_code: "",
    job_title: "",
    is_active: true,
  };
  const [employeeForm, setEmployeeForm] = useState(emptyEmployeeForm);

  const emptyShiftForm = {
    id: null as number | null,
    employee_id: "",
    shift_date: "",
    start_time: "09:00",
    end_time: "17:00",
    location_name: "Main Store",
    role_label: "",
  };
  const [shiftForm, setShiftForm] = useState(emptyShiftForm);
  const [scheduleWeekStart, setScheduleWeekStart] = useState(getWeekStartIso());

  const emptyNoteForm = {
    id: null as number | null,
    employee_id: "all",
    title: "",
    body: "",
    is_active: true,
    show_at_clock_in: true,
  };
  const [noteForm, setNoteForm] = useState(emptyNoteForm);

  const [quickBooksForm, setQuickBooksForm] = useState({
    company_name: "Demo Diner Books",
    realm_id: "realm-1",
    start_date: new Date().toISOString().slice(0, 10),
    end_date: new Date().toISOString().slice(0, 10),
  });
  const [requestReviewForm, setRequestReviewForm] = useState({
    id: null as number | null,
    status: "pending",
    manager_response: "",
  });
  const [requestQueueTab, setRequestQueueTab] = useState<RequestQueueTab>("pending");
  const [reportRecipientForm, setReportRecipientForm] = useState({
    email: "",
    report_type: "daily_labor_summary",
  });
  const [requestBoardTab, setRequestBoardTab] = useState<RequestBoardTab>("time_off");
  const [draggingShiftId, setDraggingShiftId] = useState<number | null>(null);
  const [dragTargetDate, setDragTargetDate] = useState<string | null>(null);
  const [publicationForm, setPublicationForm] = useState({ id: null as number | null, comment: "" });
  const [availabilityReviewForm, setAvailabilityReviewForm] = useState({
    id: null as number | null,
    status: "pending",
    manager_response: "",
  });
  const [coverageTargetForm, setCoverageTargetForm] = useState({
    weekday: String(new Date().getDay()),
    daypart: "lunch" as CoverageTarget["daypart"],
    role_label: "",
    required_headcount: "2",
  });
  const [shiftChangeForm, setShiftChangeForm] = useState({
    shift_id: "",
    request_type: "pickup" as ShiftChangeRequest["request_type"],
    note: "",
  });
  const [pickupBoard, setPickupBoard] = useState<ShiftChangeRequest[]>([]);
  const [shiftChangeReviewForm, setShiftChangeReviewForm] = useState({
    id: null as number | null,
    status: "pending",
    manager_response: "",
    replacement_employee_id: "",
  });
  const [timeEntryReviewForm, setTimeEntryReviewForm] = useState({
    id: null as number | null,
    approved: false,
    notes: "",
    clock_out_at: "",
  });

  useEffect(() => {
    const storedToken = window.localStorage.getItem("labortrackiq_token");
    const storedUser = window.localStorage.getItem("labortrackiq_user");
    const storedOrg = window.localStorage.getItem("labortrackiq_org");

    if (storedToken) {
      setToken(storedToken);
    }
    if (storedUser) {
      setAdminUser(JSON.parse(storedUser) as User);
    }
    if (storedOrg) {
      setOrganizationId(storedOrg);
    }
  }, []);

  useEffect(() => {
    async function bootstrap() {
      try {
        const response = await fetch(`${API_BASE}/bootstrap/demo`, { method: "POST" });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail ?? "Unable to create demo data.");
        }
        setOrganizationId(String(data.organization_id));
        setAdminEmail(data.admin_email);
        setEmployeeNumber(data.employee_number);
        setPinCode(data.employee_pin);
        setSetupMessage("Demo data is ready. Use the default credentials or replace them with real accounts.");
      } catch (error) {
        setSetupMessage(error instanceof Error ? error.message : "Unable to prepare demo workspace.");
      }
    }

    void bootstrap();
  }, []);

  useEffect(() => {
    if (token && organizationId) {
      void loadAdminData(token, organizationId);
    }
  }, [token, organizationId]);

  async function apiFetch(path: string, options: RequestInit = {}, accessToken = token) {
    const headers = new Headers(options.headers ?? {});
    if (!headers.has("Content-Type") && options.body) {
      headers.set("Content-Type", "application/json");
    }
    if (accessToken) {
      headers.set("Authorization", `Bearer ${accessToken}`);
    }
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    const raw = await response.text();
    const data = raw ? JSON.parse(raw) : {};
    if (!response.ok) {
      throw new Error(data.detail ?? "Request failed.");
    }
    return data;
  }

  async function employeeApiFetch(path: string, options: RequestInit = {}) {
    const headers = new Headers(options.headers ?? {});
    if (employeeNumber) {
      headers.set("X-Employee-Number", employeeNumber);
    }
    if (pinCode) {
      headers.set("X-Employee-Pin", pinCode);
    }
    return apiFetch(path, { ...options, headers }, "");
  }

  async function loadAdminData(accessToken: string, orgId: string) {
    try {
      const [summaryData, userData, shiftData, noteData, integrationData, setupOverviewData, requestData, publicationData, availabilityData, coverageData, shiftChangeData, notificationData, timeEntryData, recipientData] = await Promise.all([
        apiFetch(`/organizations/${orgId}/dashboard-summary`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/users`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/shifts`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/notes`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/integrations`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/setup-overview`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/time-off-requests`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/schedule/publications`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/availability-requests`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/coverage-targets`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/shift-change-requests`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/notifications`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/time-entries`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/report-recipients`, {}, accessToken),
      ]);
      const quickBooksConfigData = (await apiFetch(
        `/organizations/${orgId}/integrations/quickbooks/config-status`,
        {},
        accessToken,
      )) as QuickBooksConfigStatus;
      setSummary(summaryData as DashboardSummary);
      setEmployees(userData as User[]);
      setShifts(shiftData as Shift[]);
      setNotes(noteData as Note[]);
      setIntegrations(integrationData as Integration[]);
      setQuickBooksConfig(quickBooksConfigData);
      setSetupOverview(setupOverviewData as SetupOverview);
      setOrgTimeOffRequests(requestData as TimeOffRequest[]);
      setSchedulePublications(publicationData as SchedulePublication[]);
      setOrgAvailabilityRequests(availabilityData as AvailabilityRequest[]);
      setCoverageTargets(coverageData as CoverageTarget[]);
      setOrgShiftChangeRequests(shiftChangeData as ShiftChangeRequest[]);
      setNotifications(notificationData as NotificationItem[]);
      setTimeEntries(timeEntryData as TimeEntry[]);
      setReportRecipients(recipientData as ReportRecipient[]);
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to load admin data.");
    }
  }

  async function refreshAdminData(message?: string) {
    if (!token) {
      return;
    }
    if (message) {
      setAdminMessage(message);
    }
    await loadAdminData(token, organizationId);
  }

  async function loadEmployeeRequests(employeeId: number) {
    try {
      const data = (await employeeApiFetch(`/employees/${employeeId}/time-off-requests`)) as TimeOffRequest[];
      setEmployeeRequests(data);
    } catch (error) {
      setEmployeeError(error instanceof Error ? error.message : "Unable to load requests.");
    }
  }

  async function loadEmployeeAvailabilityRequests(employeeId: number) {
    try {
      const data = (await employeeApiFetch(`/employees/${employeeId}/availability-requests`)) as AvailabilityRequest[];
      setEmployeeAvailabilityRequests(data);
    } catch (error) {
      setEmployeeError(error instanceof Error ? error.message : "Unable to load availability requests.");
    }
  }

  async function loadEmployeeShiftChangeRequests(employeeId: number) {
    try {
      const data = (await employeeApiFetch(`/employees/${employeeId}/shift-change-requests`)) as ShiftChangeRequest[];
      setEmployeeShiftChangeRequests(data);
    } catch (error) {
      setEmployeeError(error instanceof Error ? error.message : "Unable to load shift change requests.");
    }
  }

  async function loadEmployeeProfile(employeeId: number) {
    try {
      const data = (await employeeApiFetch(`/employees/${employeeId}/profile`)) as EmployeeSelfProfile;
      setEmployeeProfile(data);
      setEmployeeProfileForm({
        preferred_weekly_hours: data.preferred_weekly_hours ? String(data.preferred_weekly_hours) : "",
        preferred_shift_notes: data.preferred_shift_notes ?? "",
      });
    } catch (error) {
      setEmployeeError(error instanceof Error ? error.message : "Unable to load employee profile.");
    }
  }

  async function loadPickupBoard(employeeId: number) {
    try {
      const data = (await employeeApiFetch(`/employees/${employeeId}/pickup-board`)) as ShiftChangeRequest[];
      setPickupBoard(data);
    } catch (error) {
      setEmployeeError(error instanceof Error ? error.message : "Unable to load pickup board.");
    }
  }

  async function loadEmployeeScheduleAcknowledgments(employeeId: number) {
    try {
      const data = (await employeeApiFetch(`/employees/${employeeId}/schedule/acknowledgments`)) as ScheduleAcknowledgment[];
      setEmployeeScheduleAcknowledgments(data);
    } catch (error) {
      setEmployeeError(error instanceof Error ? error.message : "Unable to load schedule acknowledgments.");
    }
  }

  function resetEmployeeForm() {
    setEmployeeForm(emptyEmployeeForm);
  }

  function resetShiftForm() {
    setShiftForm(emptyShiftForm);
  }

  function loadShiftIntoForm(shift: Shift) {
    const parts = splitIsoDateTime(shift.start_at);
    const endParts = splitIsoDateTime(shift.end_at);
    setShiftForm({
      id: shift.id,
      employee_id: String(shift.employee_id),
      shift_date: shift.shift_date,
      start_time: parts.time,
      end_time: endParts.time,
      location_name: shift.location_name ?? "",
      role_label: shift.role_label ?? "",
    });
  }

  function applyShiftTemplate(templateKey: (typeof SHIFT_TEMPLATES)[number]["key"]) {
    const template = SHIFT_TEMPLATES.find((item) => item.key === templateKey);
    if (!template) {
      return;
    }
    setShiftForm((current) => ({
      ...current,
      shift_date: current.shift_date || scheduleWeekStart,
      start_time: template.start,
      end_time: template.end,
      role_label: current.role_label || template.role,
    }));
  }

  function prepareShiftForDate(dateValue: string) {
    setShiftForm((current) => ({
      ...current,
      id: null,
      shift_date: dateValue,
      role_label: current.role_label || "Scheduled Shift",
    }));
  }

  function prepareShiftFromAvailability(request: AvailabilityRequest, dateValue: string) {
    setShiftForm({
      id: null,
      employee_id: String(request.employee_id),
      shift_date: dateValue,
      start_time: request.start_time,
      end_time: request.end_time,
      location_name: "Main Store",
      role_label: "Available Coverage",
    });
  }

  async function handleAutofillCoverage(dateValue: string, daypart: CoverageTarget["daypart"], roleLabel?: string | null) {
    const dayEntry = weekSchedule.find((day) => day.dateValue === dateValue);
    if (!dayEntry) {
      return;
    }

    const matchingSuggestions = dayEntry.availabilitySuggestions.filter((request) => {
      const matchesDaypart = resolveDaypartFromTimeLabel(request.start_time) === daypart;
      if (!matchesDaypart) {
        return false;
      }
      if (!roleLabel) {
        return true;
      }
      const employee = employeeOptions.find((item) => item.id === request.employee_id);
      return (employee?.job_title ?? "").trim().toLowerCase() === roleLabel.trim().toLowerCase();
    });

    if (matchingSuggestions.length === 0) {
      setAdminError("No approved availability matches that staffing gap yet.");
      return;
    }

    setAdminError("");
    try {
      for (const request of matchingSuggestions) {
        await apiFetch("/shifts", {
          method: "POST",
          body: JSON.stringify({
            organization_id: Number(organizationId),
            employee_id: request.employee_id,
            shift_date: dateValue,
            start_at: toIsoDateTime(dateValue, request.start_time),
            end_at: toIsoDateTime(dateValue, request.end_time),
            location_name: "Main Store",
            role_label: roleLabel || "Available Coverage",
          }),
        });
      }
      await refreshAdminData(`${matchingSuggestions.length} shift(s) added from approved availability.`);
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to auto-fill staffing coverage.");
    }
  }

  function moveScheduleWeek(direction: number) {
    setScheduleWeekStart((current) => addDays(current, direction * 7));
  }

  function resetNoteForm() {
    setNoteForm(emptyNoteForm);
  }

  function resetRequestReviewForm() {
    setRequestReviewForm({ id: null, status: "pending", manager_response: "" });
  }

  function appendKeypadValue(value: string) {
    if (activeKeypadField === "employee") {
      setEmployeeNumber((current) => `${current}${value}`.slice(0, 8));
    } else {
      setPinCode((current) => `${current}${value}`.slice(0, 8));
    }
  }

  function clearKeypadValue() {
    if (activeKeypadField === "employee") {
      setEmployeeNumber("");
    } else {
      setPinCode("");
    }
  }

  function backspaceKeypadValue() {
    if (activeKeypadField === "employee") {
      setEmployeeNumber((current) => current.slice(0, -1));
    } else {
      setPinCode((current) => current.slice(0, -1));
    }
  }

  async function handleEmployeeClockAction() {
    setIsClockLoading(true);
    setEmployeeError("");
    try {
      const data = (await apiFetch(
        "/clock/in-out",
        {
          method: "POST",
          body: JSON.stringify({
            organization_id: Number(organizationId),
            employee_number: employeeNumber,
            pin_code: pinCode,
            source: "tablet-keypad",
          }),
        },
        "",
      )) as ClockResponse;
      setEmployeePortal(data);
      setEmployeeTab("home");
      setEmployeeClockMessage(`${data.employee_name} ${data.status.replace("_", " ")} successfully.`);
      setRequestOffMessage("");
      await loadEmployeeRequests(data.employee_id);
      await loadEmployeeAvailabilityRequests(data.employee_id);
      await loadEmployeeShiftChangeRequests(data.employee_id);
      await loadEmployeeProfile(data.employee_id);
      await loadPickupBoard(data.employee_id);
      await loadEmployeeScheduleAcknowledgments(data.employee_id);
      if (token) {
        await loadAdminData(token, organizationId);
      }
    } catch (error) {
      setEmployeeError(error instanceof Error ? error.message : "Unable to clock in or out.");
    } finally {
      setIsClockLoading(false);
    }
  }

  function handleEmployeeLogout() {
    setEmployeePortal(null);
    setEmployeeTab("home");
    setEmployeeClockMessage("Employee signed out from the kiosk.");
    setRequestOffMessage("");
    setEmployeeRequests([]);
    setEmployeeAvailabilityRequests([]);
    setEmployeeShiftChangeRequests([]);
    setEmployeeProfile(null);
    setPickupBoard([]);
    setEmployeeScheduleAcknowledgments([]);
    setPinCode("");
    setActiveKeypadField("employee");
  }

  async function handleRequestOffSubmit(event: FormEvent) {
    event.preventDefault();
    if (!employeePortal) {
      return;
    }
    setEmployeeError("");
    try {
      await employeeApiFetch(
        "/time-off-requests",
        {
          method: "POST",
          body: JSON.stringify({
            organization_id: Number(organizationId),
            employee_id: employeePortal.employee_id,
            start_date: requestOffForm.start_date,
            end_date: requestOffForm.end_date,
            reason: requestOffForm.reason,
          }),
        },
      );
      setRequestOffMessage("Request off submitted for manager review.");
      setRequestOffForm({
        start_date: new Date().toISOString().slice(0, 10),
        end_date: new Date().toISOString().slice(0, 10),
        reason: "",
      });
      await loadEmployeeRequests(employeePortal.employee_id);
    } catch (error) {
      setEmployeeError(error instanceof Error ? error.message : "Unable to submit request off.");
    }
  }

  async function handleAcknowledgeSchedule() {
    if (!employeePortal || !employeeLatestPublishedShift) {
      return;
    }
    const latestWeekStart = getWeekStartIso(new Date(`${employeeLatestPublishedShift.shift_date}T00:00:00`));
    setEmployeeError("");
    try {
      await employeeApiFetch(
        "/schedule/acknowledgments",
        {
          method: "POST",
          body: JSON.stringify({
            organization_id: Number(organizationId),
            employee_id: employeePortal.employee_id,
            week_start: latestWeekStart,
          }),
        },
      );
      setRequestOffMessage("Schedule update acknowledged.");
      await loadEmployeeScheduleAcknowledgments(employeePortal.employee_id);
      if (token) {
        await loadAdminData(token, organizationId);
      }
    } catch (error) {
      setEmployeeError(error instanceof Error ? error.message : "Unable to acknowledge the schedule update.");
    }
  }

  async function handleAvailabilitySubmit(event: FormEvent) {
    event.preventDefault();
    if (!employeePortal) {
      return;
    }
    setEmployeeError("");
    try {
      await employeeApiFetch(
        "/availability-requests",
        {
          method: "POST",
          body: JSON.stringify({
            organization_id: Number(organizationId),
            employee_id: employeePortal.employee_id,
            weekday: availabilityForm.mode === "recurring" ? Number(availabilityForm.weekday) : null,
            start_time: availabilityForm.start_time,
            end_time: availabilityForm.end_time,
            start_date: availabilityForm.mode === "date_range" ? availabilityForm.start_date : null,
            end_date: availabilityForm.mode === "date_range" ? availabilityForm.end_date : null,
            note: availabilityForm.note || null,
          }),
        },
      );
      setRequestOffMessage("Availability request submitted for manager review.");
      await loadEmployeeAvailabilityRequests(employeePortal.employee_id);
    } catch (error) {
      setEmployeeError(error instanceof Error ? error.message : "Unable to submit availability request.");
    }
  }

  async function handleEmployeeProfileSubmit(event: FormEvent) {
    event.preventDefault();
    if (!employeePortal) {
      return;
    }
    setEmployeeError("");
    try {
      const data = (await employeeApiFetch(
        `/employees/${employeePortal.employee_id}/profile`,
        {
          method: "PUT",
          body: JSON.stringify({
            preferred_weekly_hours: employeeProfileForm.preferred_weekly_hours
              ? Number(employeeProfileForm.preferred_weekly_hours)
              : null,
            preferred_shift_notes: employeeProfileForm.preferred_shift_notes || null,
          }),
        },
      )) as EmployeeSelfProfile;
      setEmployeeProfile(data);
      setRequestOffMessage("Profile preferences updated.");
    } catch (error) {
      setEmployeeError(error instanceof Error ? error.message : "Unable to update employee preferences.");
    }
  }

  async function handleShiftChangeSubmit(event: FormEvent) {
    event.preventDefault();
    if (!employeePortal || !shiftChangeForm.shift_id) {
      return;
    }
    setEmployeeError("");
    try {
      await employeeApiFetch(
        "/shift-change-requests",
        {
          method: "POST",
          body: JSON.stringify({
            organization_id: Number(organizationId),
            shift_id: Number(shiftChangeForm.shift_id),
            requester_employee_id: employeePortal.employee_id,
            request_type: shiftChangeForm.request_type,
            note: shiftChangeForm.note,
          }),
        },
      );
      setRequestOffMessage("Shift change request sent for manager review.");
      setShiftChangeForm({ shift_id: "", request_type: "pickup", note: "" });
      await loadEmployeeShiftChangeRequests(employeePortal.employee_id);
      await loadPickupBoard(employeePortal.employee_id);
      if (token) {
        await loadAdminData(token, organizationId);
      }
    } catch (error) {
      setEmployeeError(error instanceof Error ? error.message : "Unable to submit shift change request.");
    }
  }

  async function handleClaimPickupRequest(requestId: number) {
    if (!employeePortal) {
      return;
    }
    setEmployeeError("");
    try {
      await employeeApiFetch(
        `/shift-change-requests/${requestId}/claim`,
        {
          method: "POST",
          body: JSON.stringify({ employee_id: employeePortal.employee_id }),
        },
      );
      setRequestOffMessage("Pickup interest sent to the manager for approval.");
      await loadPickupBoard(employeePortal.employee_id);
      await loadEmployeeShiftChangeRequests(employeePortal.employee_id);
      if (token) {
        await loadAdminData(token, organizationId);
      }
    } catch (error) {
      setEmployeeError(error instanceof Error ? error.message : "Unable to claim pickup request.");
    }
  }

  async function handleAdminLogin(event: FormEvent) {
    event.preventDefault();
    setAdminError("");
    try {
      const data = (await apiFetch(
        "/auth/login",
        {
          method: "POST",
          body: JSON.stringify({
            organization_id: Number(organizationId),
            email: adminEmail,
            password: adminPassword,
          }),
        },
        "",
      )) as LoginResponse;
      setToken(data.access_token);
      setAdminUser(data.user);
      setAdminMessage(data.message);
      window.localStorage.setItem("labortrackiq_token", data.access_token);
      window.localStorage.setItem("labortrackiq_user", JSON.stringify(data.user));
      window.localStorage.setItem("labortrackiq_org", organizationId);
      await loadAdminData(data.access_token, organizationId);
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to log in.");
    }
  }

  function handleLogout() {
    setToken("");
    setAdminUser(null);
    setSummary(null);
    setEmployees([]);
    setShifts([]);
    setNotes([]);
    setIntegrations([]);
    setSetupOverview(null);
    setAdminMessage("Signed out.");
    window.localStorage.removeItem("labortrackiq_token");
    window.localStorage.removeItem("labortrackiq_user");
    window.localStorage.removeItem("labortrackiq_org");
  }

  async function handleSubmitEmployee(event: FormEvent) {
    event.preventDefault();
    setAdminError("");
    try {
      if (employeeForm.id) {
        await apiFetch(`/users/${employeeForm.id}`, {
          method: "PUT",
          body: JSON.stringify({
            full_name: employeeForm.full_name,
            email: employeeForm.email || null,
            employee_number: employeeForm.employee_number,
            pin_code: employeeForm.pin_code,
            job_title: employeeForm.job_title || null,
            is_active: employeeForm.is_active,
          }),
        });
        await refreshAdminData("Employee updated.");
      } else {
        await apiFetch("/users", {
          method: "POST",
          body: JSON.stringify({
            organization_id: Number(organizationId),
            full_name: employeeForm.full_name,
            email: employeeForm.email || null,
            role: "employee",
            employee_number: employeeForm.employee_number,
            pin_code: employeeForm.pin_code,
            job_title: employeeForm.job_title || null,
          }),
        });
        await refreshAdminData("Employee created.");
      }
      resetEmployeeForm();
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to save employee.");
    }
  }

  async function handleArchiveEmployee() {
    if (!employeeForm.id) {
      return;
    }
    setAdminError("");
    try {
      const response = await apiFetch(`/users/${employeeForm.id}`, { method: "DELETE" });
      await refreshAdminData(response.message ?? "Employee archived.");
      resetEmployeeForm();
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to archive employee.");
    }
  }

  async function handleSubmitShift(event: FormEvent) {
    event.preventDefault();
    setAdminError("");
    const payload = {
      organization_id: Number(organizationId),
      employee_id: Number(shiftForm.employee_id),
      shift_date: shiftForm.shift_date,
      start_at: toIsoDateTime(shiftForm.shift_date, shiftForm.start_time),
      end_at: toIsoDateTime(shiftForm.shift_date, shiftForm.end_time),
      location_name: shiftForm.location_name || null,
      role_label: shiftForm.role_label || null,
    };
    try {
      if (shiftForm.id) {
        await apiFetch(`/shifts/${shiftForm.id}`, {
          method: "PUT",
          body: JSON.stringify({
            employee_id: payload.employee_id,
            shift_date: payload.shift_date,
            start_at: payload.start_at,
            end_at: payload.end_at,
            location_name: payload.location_name,
            role_label: payload.role_label,
          }),
        });
        await refreshAdminData("Shift updated.");
      } else {
        await apiFetch("/shifts", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        await refreshAdminData("Shift created.");
      }
      resetShiftForm();
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to save shift.");
    }
  }

  async function handleDeleteShift() {
    if (!shiftForm.id) {
      return;
    }
    setAdminError("");
    try {
      const response = await apiFetch(`/shifts/${shiftForm.id}`, { method: "DELETE" });
      await refreshAdminData(response.message ?? "Shift deleted.");
      resetShiftForm();
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to delete shift.");
    }
  }

  async function handleCopyPreviousWeek() {
    const selectedWeekShifts = shifts.filter(
      (shift) => shift.shift_date >= scheduleWeekStart && shift.shift_date <= addDays(scheduleWeekStart, 6),
    );
    if (selectedWeekShifts.length > 0) {
      setAdminError("This week already has shifts. Clear or edit the existing shifts before copying another week.");
      return;
    }

    const previousWeekStart = addDays(scheduleWeekStart, -7);
    const previousWeekShifts = shifts.filter(
      (shift) => shift.shift_date >= previousWeekStart && shift.shift_date <= addDays(previousWeekStart, 6),
    );
    if (previousWeekShifts.length === 0) {
      setAdminError("No shifts were found in the previous week to copy.");
      return;
    }

    setAdminError("");
    for (const shift of previousWeekShifts) {
      const daysFromPreviousWeek =
        Math.round(
          (new Date(`${shift.shift_date}T00:00:00`).getTime() - new Date(`${previousWeekStart}T00:00:00`).getTime()) / 86400000,
        ) || 0;
      await apiFetch("/shifts", {
        method: "POST",
        body: JSON.stringify({
          organization_id: Number(organizationId),
          employee_id: shift.employee_id,
          shift_date: addDays(scheduleWeekStart, daysFromPreviousWeek),
          start_at: toIsoDateTime(addDays(scheduleWeekStart, daysFromPreviousWeek), splitIsoDateTime(shift.start_at).time),
          end_at: toIsoDateTime(addDays(scheduleWeekStart, daysFromPreviousWeek), splitIsoDateTime(shift.end_at).time),
          location_name: shift.location_name,
          role_label: shift.role_label,
        }),
      });
    }

    await refreshAdminData("Previous week copied into the current planner.");
  }

  async function handlePublishScheduleWeek() {
    setAdminError("");
    try {
      const response = (await apiFetch(`/organizations/${organizationId}/schedule/publish`, {
        method: "POST",
        body: JSON.stringify({ week_start: scheduleWeekStart, force_publish: false }),
      })) as SchedulePublishResponse;
      await refreshAdminData(`${response.published_shift_count} shift(s) published for ${formatWeekLabel(scheduleWeekStart)}.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to publish schedule.";
      if (message.startsWith("Publish override required:")) {
        const shouldOverride = window.confirm(`${message}\n\nPublish anyway?`);
        if (!shouldOverride) {
          setAdminError(message);
          return;
        }
        try {
          const response = (await apiFetch(`/organizations/${organizationId}/schedule/publish`, {
            method: "POST",
            body: JSON.stringify({ week_start: scheduleWeekStart, force_publish: true }),
          })) as SchedulePublishResponse;
          await refreshAdminData(
            `${response.published_shift_count} shift(s) published with a staffing override for ${formatWeekLabel(scheduleWeekStart)}.`,
          );
          return;
        } catch (overrideError) {
          setAdminError(overrideError instanceof Error ? overrideError.message : "Unable to override and publish schedule.");
          return;
        }
      }
      setAdminError(message);
    }
  }

  async function handleUnpublishScheduleWeek() {
    setAdminError("");
    try {
      const response = (await apiFetch(`/organizations/${organizationId}/schedule/unpublish`, {
        method: "POST",
        body: JSON.stringify({ week_start: scheduleWeekStart }),
      })) as SchedulePublishResponse;
      await refreshAdminData(`${response.published_shift_count} published shift(s) moved back to draft for ${formatWeekLabel(scheduleWeekStart)}.`);
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to unpublish schedule.");
    }
  }

  async function handleSavePublicationComment(event?: FormEvent) {
    event?.preventDefault();
    if (!publicationForm.id) {
      return;
    }
    setAdminError("");
    try {
      await apiFetch(`/schedule/publications/${publicationForm.id}`, {
        method: "PUT",
        body: JSON.stringify({ comment: publicationForm.comment || null }),
      });
      await refreshAdminData("Schedule snapshot comment saved.");
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to save schedule comment.");
    }
  }

  async function handleRestorePublication(publicationId: number) {
    setAdminError("");
    try {
      const response = (await apiFetch(`/schedule/publications/${publicationId}/restore`, {
        method: "POST",
      })) as { message: string; restored_shift_count: number };
      await refreshAdminData(`${response.restored_shift_count} shift(s) restored from the snapshot as draft shifts.`);
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to restore schedule snapshot.");
    }
  }

  async function handleReviewAvailability(event: FormEvent) {
    event.preventDefault();
    if (!availabilityReviewForm.id) {
      return;
    }
    setAdminError("");
    try {
      await apiFetch(`/availability-requests/${availabilityReviewForm.id}`, {
        method: "PUT",
        body: JSON.stringify({
          status: availabilityReviewForm.status,
          manager_response: availabilityReviewForm.manager_response || null,
        }),
      });
      await refreshAdminData("Availability request updated.");
      setAvailabilityReviewForm({ id: null, status: "pending", manager_response: "" });
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to update availability request.");
    }
  }

  async function handleSaveCoverageTarget(event: FormEvent) {
    event.preventDefault();
    setAdminError("");
    try {
      await apiFetch("/coverage-targets", {
        method: "POST",
        body: JSON.stringify({
          organization_id: Number(organizationId),
          weekday: Number(coverageTargetForm.weekday),
          daypart: coverageTargetForm.daypart,
          role_label: coverageTargetForm.role_label || null,
          required_headcount: Number(coverageTargetForm.required_headcount),
        }),
      });
      await refreshAdminData("Coverage target saved.");
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to save coverage target.");
    }
  }

  async function handleMoveShiftToDate(shiftId: number, targetDate: string) {
    const shift = shifts.find((item) => item.id === shiftId);
    if (!shift || shift.shift_date === targetDate) {
      return;
    }

    setAdminError("");
    try {
      const startParts = splitIsoDateTime(shift.start_at);
      const endParts = splitIsoDateTime(shift.end_at);
      await apiFetch(`/shifts/${shift.id}`, {
        method: "PUT",
        body: JSON.stringify({
          employee_id: shift.employee_id,
          shift_date: targetDate,
          start_at: toIsoDateTime(targetDate, startParts.time),
          end_at: toIsoDateTime(targetDate, endParts.time),
          location_name: shift.location_name,
          role_label: shift.role_label,
        }),
      });
      await refreshAdminData("Shift moved on the weekly planner.");
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to move shift.");
    } finally {
      setDraggingShiftId(null);
      setDragTargetDate(null);
    }
  }

  function handleShiftDragStart(event: DragEvent<HTMLButtonElement>, shiftId: number) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(shiftId));
    setDraggingShiftId(shiftId);
  }

  function handleShiftDragEnd() {
    setDraggingShiftId(null);
    setDragTargetDate(null);
  }

  function handleDayDragOver(event: DragEvent<HTMLDivElement>, targetDate: string) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setDragTargetDate(targetDate);
  }

  async function handleDayDrop(event: DragEvent<HTMLDivElement>, targetDate: string) {
    event.preventDefault();
    const rawShiftId = event.dataTransfer.getData("text/plain");
    const shiftId = Number(rawShiftId);
    if (Number.isFinite(shiftId) && shiftId > 0) {
      await handleMoveShiftToDate(shiftId, targetDate);
    } else {
      setDraggingShiftId(null);
      setDragTargetDate(null);
    }
  }

  async function handleSubmitNote(event: FormEvent) {
    event.preventDefault();
    setAdminError("");
    const payload = {
      organization_id: Number(organizationId),
      employee_id: noteForm.employee_id === "all" ? null : Number(noteForm.employee_id),
      title: noteForm.title,
      body: noteForm.body,
      is_active: noteForm.is_active,
      show_at_clock_in: noteForm.show_at_clock_in,
    };
    try {
      if (noteForm.id) {
        await apiFetch(`/notes/${noteForm.id}`, {
          method: "PUT",
          body: JSON.stringify({
            employee_id: payload.employee_id,
            title: payload.title,
            body: payload.body,
            is_active: payload.is_active,
            show_at_clock_in: payload.show_at_clock_in,
          }),
        });
        await refreshAdminData("Note updated.");
      } else {
        await apiFetch("/notes", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        await refreshAdminData("Manager note created.");
      }
      resetNoteForm();
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to save note.");
    }
  }

  async function handleDeleteNote() {
    if (!noteForm.id) {
      return;
    }
    setAdminError("");
    try {
      const response = await apiFetch(`/notes/${noteForm.id}`, { method: "DELETE" });
      await refreshAdminData(response.message ?? "Note deleted.");
      resetNoteForm();
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to delete note.");
    }
  }

  async function handleConnectQuickBooks() {
    setAdminError("");
    setExportSummary(null);
    try {
      const response = (await apiFetch(`/organizations/${organizationId}/integrations/quickbooks/connect`, {
        method: "POST",
        body: JSON.stringify({
          organization_id: Number(organizationId),
          company_name: quickBooksForm.company_name,
          realm_id: quickBooksForm.realm_id,
        }),
      })) as QuickBooksActionResponse;
      setQuickBooksAuth(null);
      await refreshAdminData(response.message);
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to connect QuickBooks.");
    }
  }

  async function handleGenerateQuickBooksAuthUrl() {
    setAdminError("");
    try {
      const response = (await apiFetch(
        `/organizations/${organizationId}/integrations/quickbooks/authorize-url`,
        {},
      )) as QuickBooksAuthorization;
      setQuickBooksAuth(response);
      setAdminMessage("QuickBooks authorization URL generated.");
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to generate QuickBooks authorization URL.");
    }
  }

  async function handleDisconnectIntegration(integrationId: number) {
    setAdminError("");
    setExportSummary(null);
    try {
      const response = (await apiFetch(`/integrations/${integrationId}/disconnect`, {
        method: "POST",
      })) as QuickBooksActionResponse;
      setQuickBooksAuth(null);
      await refreshAdminData(response.message);
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to disconnect QuickBooks.");
    }
  }

  async function handleExportLabor(integrationId: number) {
    setAdminError("");
    try {
      const response = (await apiFetch(`/integrations/${integrationId}/export-labor`, {
        method: "POST",
        body: JSON.stringify({
          start_date: quickBooksForm.start_date,
          end_date: quickBooksForm.end_date,
        }),
      })) as QuickBooksActionResponse;
      setExportSummary(response.export_summary ?? null);
      await refreshAdminData(response.message);
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to export labor.");
    }
  }

  async function handleRefreshQuickBooks(integrationId: number) {
    setAdminError("");
    try {
      const response = (await apiFetch(`/integrations/${integrationId}/refresh`, {
        method: "POST",
      })) as QuickBooksActionResponse;
      await refreshAdminData(response.message);
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to refresh QuickBooks tokens.");
    }
  }

  async function handleReviewRequest(event: FormEvent) {
    event.preventDefault();
    if (!requestReviewForm.id) {
      return;
    }
    setAdminError("");
    try {
      await apiFetch(`/time-off-requests/${requestReviewForm.id}`, {
        method: "PUT",
        body: JSON.stringify({
          status: requestReviewForm.status,
          manager_response: requestReviewForm.manager_response || null,
        }),
      });
      await refreshAdminData("Time-off request updated.");
      resetRequestReviewForm();
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to update request.");
    }
  }

  async function handleReviewShiftChange(event: FormEvent) {
    event.preventDefault();
    if (!shiftChangeReviewForm.id) {
      return;
    }
    setAdminError("");
    try {
      await apiFetch(`/shift-change-requests/${shiftChangeReviewForm.id}`, {
        method: "PUT",
        body: JSON.stringify({
          status: shiftChangeReviewForm.status,
          manager_response: shiftChangeReviewForm.manager_response || null,
          replacement_employee_id: shiftChangeReviewForm.replacement_employee_id
            ? Number(shiftChangeReviewForm.replacement_employee_id)
            : null,
        }),
      });
      await refreshAdminData("Shift change request updated.");
      setShiftChangeReviewForm({ id: null, status: "pending", manager_response: "", replacement_employee_id: "" });
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to update shift change request.");
    }
  }

  async function handleReviewTimeEntry(event: FormEvent) {
    event.preventDefault();
    if (!timeEntryReviewForm.id) {
      return;
    }
    setAdminError("");
    try {
      await apiFetch(`/time-entries/${timeEntryReviewForm.id}`, {
        method: "PUT",
        body: JSON.stringify({
          approved: timeEntryReviewForm.approved,
          notes: timeEntryReviewForm.notes || null,
          clock_out_at: timeEntryReviewForm.clock_out_at || null,
        }),
      });
      await refreshAdminData("Time entry updated.");
      setTimeEntryReviewForm({ id: null, approved: false, notes: "", clock_out_at: "" });
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to update time entry.");
    }
  }

  async function handleSubmitReportRecipient(event: FormEvent) {
    event.preventDefault();
    setAdminError("");
    try {
      await apiFetch("/report-recipients", {
        method: "POST",
        body: JSON.stringify({
          organization_id: Number(organizationId),
          email: reportRecipientForm.email,
          report_type: reportRecipientForm.report_type,
        }),
      });
      setReportRecipientForm({ email: "", report_type: "daily_labor_summary" });
      await refreshAdminData("Report recipient added.");
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to add report recipient.");
    }
  }

  async function handleArchiveReportRecipient(recipientId: number) {
    setAdminError("");
    try {
      await apiFetch(`/report-recipients/${recipientId}`, {
        method: "DELETE",
      });
      await refreshAdminData("Report recipient archived.");
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to archive report recipient.");
    }
  }

  const employeeHomeShifts = employeePortal?.schedule.slice(0, 3) ?? [];
  const employeeNotes = employeePortal?.notes ?? [];
  const scheduleCalendar = buildScheduleCalendar(employeePortal?.schedule ?? []);
  const employeeLatestPublishedShift = [...(employeePortal?.schedule ?? [])]
    .filter((shift) => shift.published_at)
    .sort((a, b) => (b.published_at ?? "").localeCompare(a.published_at ?? ""))[0];
  const employeeAcknowledgedWeeks = new Set(employeeScheduleAcknowledgments.map((acknowledgment) => acknowledgment.week_start));
  const employeeLatestPublishedWeekStart = employeeLatestPublishedShift
    ? getWeekStartIso(new Date(`${employeeLatestPublishedShift.shift_date}T00:00:00`))
    : null;
  const employeeLatestScheduleAcknowledged = employeeLatestPublishedWeekStart
    ? employeeAcknowledgedWeeks.has(employeeLatestPublishedWeekStart)
    : false;
  const employeeOptions = employees.filter((employee) => employee.role === "employee" && employee.is_active);
  const quickBooksIntegration = integrations.find((integration) => integration.provider === "quickbooks");
  const scheduleWeekDays = Array.from({ length: 7 }, (_, index) => addDays(scheduleWeekStart, index));
  const scheduleWeekEnd = scheduleWeekDays[scheduleWeekDays.length - 1];
  const weeklyShifts = shifts
    .filter((shift) => shift.shift_date >= scheduleWeekStart && shift.shift_date <= scheduleWeekEnd)
    .sort((a, b) => a.start_at.localeCompare(b.start_at));
  const weekSchedule = scheduleWeekDays.map((dateValue) => ({
    dateValue,
    label: formatScheduleDayLabel(dateValue),
    shifts: weeklyShifts.filter((shift) => shift.shift_date === dateValue),
    requests: orgTimeOffRequests.filter(
      (request) =>
        request.status !== "denied" && request.start_date <= dateValue && request.end_date >= dateValue,
    ),
    availabilitySuggestions: orgAvailabilityRequests.filter((request) => {
      const weekday = new Date(`${dateValue}T00:00:00`).getDay();
      const employeeScheduled = weeklyShifts.some((shift) => shift.shift_date === dateValue && shift.employee_id === request.employee_id);
      const employeeOff = orgTimeOffRequests.some(
        (timeOff) =>
          timeOff.status === "approved" &&
          timeOff.employee_id === request.employee_id &&
          timeOff.start_date <= dateValue &&
          timeOff.end_date >= dateValue,
      );
      const matchesDate =
        request.weekday !== null
          ? request.weekday === weekday
          : Boolean(request.start_date && request.end_date && request.start_date <= dateValue && request.end_date >= dateValue);
      return request.status === "approved" && matchesDate && !employeeScheduled && !employeeOff;
    }),
  }));
  const weekCoverageSummaries = weekSchedule.map((day) => {
    const weekday = new Date(`${day.dateValue}T00:00:00`).getDay();
    const dayTargets = coverageTargets.filter((target) => target.weekday === weekday);
    const dayparts = dayTargets.map((target) => {
      const scheduled = day.shifts.filter(
        (shift) =>
          resolveDaypart(shift) === target.daypart &&
          (!target.role_label || (shift.role_label ?? "").trim().toLowerCase() === target.role_label.trim().toLowerCase()),
      ).length;
      const availableSuggestions = day.availabilitySuggestions.filter((request) => {
        if (resolveDaypartFromTimeLabel(request.start_time) !== target.daypart) {
          return false;
        }
        if (!target.role_label) {
          return true;
        }
        const employee = employeeOptions.find((item) => item.id === request.employee_id);
        return (employee?.job_title ?? "").trim().toLowerCase() === target.role_label.trim().toLowerCase();
      }).length;
      return {
        daypart: target.daypart,
        role_label: target.role_label,
        scheduled,
        required: target.required_headcount,
        availableSuggestions,
        shortage: Math.max(0, target.required_headcount - scheduled),
      };
    });

    return {
      dateValue: day.dateValue,
      dayparts,
      shortages: dayparts.filter((entry) => entry.shortage > 0),
    };
  });
  const weeklyCoverageWarnings = weekCoverageSummaries.filter((day) => day.shortages.length > 0);
  const totalCoverageShortage = weeklyCoverageWarnings.reduce(
    (total, day) => total + day.shortages.reduce((dayTotal, entry) => dayTotal + entry.shortage, 0),
    0,
  );
  const scheduledEmployeeCount = new Set(weeklyShifts.map((shift) => shift.employee_id)).size;
  const weeklyHours = weeklyShifts.reduce((total, shift) => total + getShiftHours(shift), 0);
  const publishedWeeklyShifts = weeklyShifts.filter((shift) => shift.is_published);
  const draftWeeklyShifts = weeklyShifts.filter((shift) => !shift.is_published);
  const weeklyLatestPublishedShift = [...publishedWeeklyShifts]
    .filter((shift) => shift.published_at)
    .sort((a, b) => (b.published_at ?? "").localeCompare(a.published_at ?? ""))[0];
  const weeklyPendingRequests = orgTimeOffRequests.filter(
    (request) =>
      request.status === "pending" && request.start_date <= scheduleWeekEnd && request.end_date >= scheduleWeekStart,
  );
  const approvedWeekRequests = orgTimeOffRequests.filter(
    (request) =>
      request.status === "approved" && request.start_date <= scheduleWeekEnd && request.end_date >= scheduleWeekStart,
  );
  const scheduleConflictSummaries = weekSchedule
    .map((day) => {
      const overlaps: string[] = [];
      for (let index = 0; index < day.shifts.length; index += 1) {
        const currentShift = day.shifts[index];
        const currentEmployee = employeeOptions.find((item) => item.id === currentShift.employee_id);
        for (let compareIndex = index + 1; compareIndex < day.shifts.length; compareIndex += 1) {
          const compareShift = day.shifts[compareIndex];
          if (currentShift.employee_id !== compareShift.employee_id) {
            continue;
          }
          if (rangesOverlap(currentShift.start_at, currentShift.end_at, compareShift.start_at, compareShift.end_at)) {
            overlaps.push(`${currentEmployee?.full_name ?? `Employee ${currentShift.employee_id}`} has overlapping shifts.`);
          }
        }
      }

      const approvedConflicts = day.shifts.flatMap((shift) => {
        const employee = employeeOptions.find((item) => item.id === shift.employee_id);
        return approvedWeekRequests
          .filter(
            (request) =>
              request.employee_id === shift.employee_id && request.start_date <= day.dateValue && request.end_date >= day.dateValue,
          )
          .map(() => `${employee?.full_name ?? `Employee ${shift.employee_id}`} is scheduled during approved time off.`);
      });

      const longShiftFlags = day.shifts
        .filter((shift) => getShiftHours(shift) > 10)
        .map((shift) => {
          const employee = employeeOptions.find((item) => item.id === shift.employee_id);
          return `${employee?.full_name ?? `Employee ${shift.employee_id}`} has a shift longer than 10 hours.`;
        });

      return {
        dateValue: day.dateValue,
        issues: [...new Set([...overlaps, ...approvedConflicts, ...longShiftFlags])],
      };
    })
    .filter((day) => day.issues.length > 0);
  const weeklyEmployeeHours = employeeOptions
    .map((employee) => ({
      employee,
      hours: weeklyShifts.filter((shift) => shift.employee_id === employee.id).reduce((total, shift) => total + getShiftHours(shift), 0),
    }))
    .filter((entry) => entry.hours > 0);
  const overtimeWarnings = weeklyEmployeeHours.filter((entry) => entry.hours > 40);
  const formShiftStart = shiftForm.shift_date ? toIsoDateTime(shiftForm.shift_date, shiftForm.start_time) : "";
  const formShiftEnd = shiftForm.shift_date ? toIsoDateTime(shiftForm.shift_date, shiftForm.end_time) : "";
  const shiftFormWarnings = shiftForm.employee_id && shiftForm.shift_date
    ? [
        ...shifts
          .filter(
            (shift) =>
              shift.employee_id === Number(shiftForm.employee_id) &&
              shift.id !== shiftForm.id &&
              shift.shift_date === shiftForm.shift_date &&
              formShiftStart &&
              formShiftEnd &&
              rangesOverlap(shift.start_at, shift.end_at, formShiftStart, formShiftEnd),
          )
          .map(() => "This employee already has another shift that overlaps this time."),
        ...approvedWeekRequests
          .filter(
            (request) =>
              request.employee_id === Number(shiftForm.employee_id) &&
              request.start_date <= shiftForm.shift_date &&
              request.end_date >= shiftForm.shift_date,
          )
          .map(() => "This employee has approved time off on the selected date."),
        ...(shiftForm.shift_date && formShiftStart && formShiftEnd && new Date(formShiftEnd).getTime() <= new Date(formShiftStart).getTime()
          ? ["Shift end time must be after the start time."]
          : []),
        ...(shiftForm.shift_date && formShiftStart && formShiftEnd && (new Date(formShiftEnd).getTime() - new Date(formShiftStart).getTime()) / 36e5 > 10
          ? ["This shift is longer than 10 hours."]
          : []),
      ]
    : [];
  const pendingTimeOffRequests = orgTimeOffRequests.filter((request) => request.status === "pending");
  const approvedTimeOffRequests = orgTimeOffRequests.filter((request) => request.status === "approved");
  const visibleTimeOffRequests = requestQueueTab === "pending" ? pendingTimeOffRequests : approvedTimeOffRequests;
  const pendingShiftChangeRequests = orgShiftChangeRequests.filter((request) => request.status === "pending");
  const approvedShiftChangeRequests = orgShiftChangeRequests.filter((request) => request.status === "approved");
  const visibleShiftChangeRequests = requestQueueTab === "pending" ? pendingShiftChangeRequests : approvedShiftChangeRequests;
  const openTimeEntries = timeEntries.filter((entry) => !entry.clock_out_at);
  const pendingTimeEntries = timeEntries.filter((entry) => !entry.approved && Boolean(entry.clock_out_at));
  const approvedTimeEntries = timeEntries.filter((entry) => entry.approved && Boolean(entry.clock_out_at));
  const pendingAvailabilityRequests = orgAvailabilityRequests.filter((request) => request.status === "pending");
  const recentSchedulePublications = schedulePublications.slice(0, 6);

  function handleNotificationClick(item: NotificationItem) {
    if (item.category === "availability") {
      setAdminTab("schedules");
      if (item.target_id) {
        const request = orgAvailabilityRequests.find((entry) => entry.id === item.target_id);
        if (request) {
          setAvailabilityReviewForm({
            id: request.id,
            status: request.status,
            manager_response: request.manager_response ?? "",
          });
        }
      }
      return;
    }
    if (item.category === "time_off") {
      setAdminTab("requests");
      setRequestBoardTab("time_off");
      setRequestQueueTab("pending");
      if (item.target_id) {
        const request = orgTimeOffRequests.find((entry) => entry.id === item.target_id);
        if (request) {
          setRequestReviewForm({
            id: request.id,
            status: request.status,
            manager_response: request.manager_response ?? "",
          });
        }
      }
      return;
    }
    if (item.category === "shift_change") {
      setAdminTab("requests");
      setRequestBoardTab("shift_changes");
      setRequestQueueTab("pending");
      if (item.target_id) {
        const request = orgShiftChangeRequests.find((entry) => entry.id === item.target_id);
        if (request) {
          setShiftChangeReviewForm({
            id: request.id,
            status: request.status,
            manager_response: request.manager_response ?? "",
            replacement_employee_id: request.replacement_employee_id ? String(request.replacement_employee_id) : "",
          });
        }
      }
      return;
    }
    if (item.category === "time_entry") {
      setAdminTab("timesheets");
      if (item.target_id) {
        const entry = timeEntries.find((record) => record.id === item.target_id);
        if (entry) {
          setTimeEntryReviewForm({
            id: entry.id,
            approved: entry.approved,
            notes: entry.notes ?? "",
            clock_out_at: entry.clock_out_at ? new Date(entry.clock_out_at).toISOString().slice(0, 16) : "",
          });
        }
      }
    }
  }

  return (
    <div className="app-shell">
      <section className="brand-banner panel">
        <div className="brand-lockup">
          <img className="brand-mark" src="/miseiq-mark.svg" alt="MiseIQ brand mark" />
          <div>
            <p className="eyebrow">MiseIQ Brand System</p>
            <h2>MiseIQ Workforce</h2>
          </div>
        </div>
        <p className="brand-copy">
          Styled to match your MiseIQ site with a deep navy foundation, warm parchment surfaces, gold accents, and
          serif-led headings for a more premium hospitality operations feel.
        </p>
      </section>

      <section className="employee-shell">
        {!employeePortal ? (
          <div className="kiosk-layout">
            <div className="kiosk-copy panel">
              <div className="inline-brand">
                <img className="inline-brand-mark" src="/miseiq-mark.svg" alt="MiseIQ brand mark" />
              </div>
              <p className="eyebrow">MiseIQ Workforce</p>
              <h1 className="kiosk-title">Clock In to the Shift Board</h1>
              <p className="hero-text">
                Employees use the keypad to enter their employee number and PIN. After clock-in, they land on their
                home screen with notes, current schedule, full calendar, and request-off tools.
              </p>
              <div className="brand-illustration-card">
                <img className="brand-illustration" src="/miseiq-ops-illustration.svg" alt="MiseIQ operations illustration" />
                <div className="brand-illustration-copy">
                  <strong>Shift intelligence, branded for MiseIQ</strong>
                  <p>Labor visibility, schedules, request management, and clock activity in the same premium operating system feel.</p>
                </div>
              </div>
              <div className="status-strip">{setupMessage}</div>
            </div>

            <div className="kiosk-panel">
              <div className="field-toggle-row">
                <button
                  className={activeKeypadField === "employee" ? "field-pill active-field-pill" : "field-pill"}
                  type="button"
                  onClick={() => setActiveKeypadField("employee")}
                >
                  Employee #{employeeNumber || "Tap to enter"}
                </button>
                <button
                  className={activeKeypadField === "pin" ? "field-pill active-field-pill" : "field-pill"}
                  type="button"
                  onClick={() => setActiveKeypadField("pin")}
                >
                  PIN {pinCode ? "*".repeat(pinCode.length) : "Tap to enter"}
                </button>
              </div>

              <div className="keypad-grid">
                {["1", "2", "3", "4", "5", "6", "7", "8", "9", "C", "0", "<"].map((key) => (
                  <button
                    key={key}
                    className={key === "C" || key === "<" ? "keypad-button keypad-button-secondary" : "keypad-button"}
                    type="button"
                    onClick={() => {
                      if (key === "C") {
                        clearKeypadValue();
                        return;
                      }
                      if (key === "<") {
                        backspaceKeypadValue();
                        return;
                      }
                      appendKeypadValue(key);
                    }}
                  >
                    {key}
                  </button>
                ))}
              </div>

              <button className="primary-button wide-button" type="button" onClick={() => void handleEmployeeClockAction()} disabled={isClockLoading}>
                {isClockLoading ? "Working..." : "Clock In / Out"}
              </button>

              <div className="note-banner">{employeeError || employeeClockMessage}</div>
            </div>
          </div>
        ) : (
            <div className="employee-portal">
              <div className="employee-portal-header">
                <div>
                <p className="eyebrow">MiseIQ Workforce</p>
                <h1 className="kiosk-title">{employeePortal.employee_name}</h1>
                <p className="hero-text">{employeeClockMessage}</p>
              </div>
              <div className="employee-portal-actions">
                <button className="primary-button" type="button" onClick={() => void handleEmployeeClockAction()}>
                  Clock In / Out
                </button>
                <button className="ghost-button" type="button" onClick={handleEmployeeLogout}>
                  Log Out
                </button>
              </div>
            </div>

            <div className="tab-row">
              {(["home", "schedule", "shift_changes", "request_off", "availability", "profile"] as EmployeeTab[]).map((tab) => (
                <button
                  key={tab}
                  className={employeeTab === tab ? "tab active-tab" : "tab"}
                  type="button"
                  onClick={() => setEmployeeTab(tab)}
                >
                  {tab === "request_off"
                    ? "Request Off"
                    : tab === "availability"
                      ? "Availability"
                    : tab === "shift_changes"
                        ? "Shift Changes"
                        : tab === "profile"
                          ? "Profile"
                        : tab[0].toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>

            {employeeError ? <div className="inline-error">{employeeError}</div> : null}
            {requestOffMessage ? <div className="inline-message">{requestOffMessage}</div> : null}
            {employeeLatestPublishedShift ? (
              <div className="schedule-notice-banner">
                <div>
                  Latest published schedule update:{" "}
                  {new Date(employeeLatestPublishedShift.published_at ?? "").toLocaleDateString()} by{" "}
                  {employeeLatestPublishedShift.published_by_name ?? "your manager"}.
                </div>
                {!employeeLatestScheduleAcknowledged ? (
                  <button className="primary-button" type="button" onClick={() => void handleAcknowledgeSchedule()}>
                    Acknowledge Update
                  </button>
                ) : (
                  <span className="publish-pill published-pill">Acknowledged</span>
                )}
              </div>
            ) : null}

            {employeeTab === "home" ? (
              <div className="employee-grid">
                <article className="panel">
                  <div className="panel-heading">
                    <p className="eyebrow">Shift Notes</p>
                    <h3>What You Need Today</h3>
                  </div>
                  <div className="notes">
                    {employeeNotes.length > 0 ? (
                      employeeNotes.map((note) => (
                        <div className="note-card" key={note.id}>
                          <strong>{note.title}</strong>
                          <p>{note.body}</p>
                        </div>
                      ))
                    ) : (
                      <div className="empty-state">No manager notes are posted for this shift yet.</div>
                    )}
                  </div>
                </article>

                <article className="panel">
                  <div className="panel-heading">
                    <p className="eyebrow">Coming Up</p>
                    <h3>Your Next Shifts</h3>
                  </div>
                  <div className="list">
                    {employeeHomeShifts.length > 0 ? (
                      employeeHomeShifts.map((shift) => {
                        const window = formatShiftWindow(shift);
                        return (
                          <div className="list-row" key={shift.id}>
                            <div>
                              <strong>{window.day}</strong>
                              <p>{window.time}</p>
                            </div>
                            <span>{shift.role_label ?? shift.location_name ?? "Scheduled"}</span>
                          </div>
                        );
                      })
                    ) : (
                      <div className="empty-state">No upcoming shifts are posted yet.</div>
                    )}
                  </div>
                </article>
              </div>
            ) : null}

            {employeeTab === "schedule" ? (
              <article className="panel">
                <div className="panel-heading">
                  <p className="eyebrow">Published Schedule</p>
                  <h3>Bi-Weekly / Monthly View</h3>
                </div>
                <div className="schedule-calendar">
                  {scheduleCalendar.length > 0 ? (
                    scheduleCalendar.map((day) => (
                      <div className="calendar-day" key={day.shiftDate}>
                        <strong>{formatDate(day.shiftDate)}</strong>
                        {day.items.map((shift) => {
                          const window = formatShiftWindow(shift);
                          return (
                            <div className="calendar-shift" key={shift.id}>
                              <p>{window.time}</p>
                              <p>{shift.role_label ?? shift.location_name ?? "Scheduled"}</p>
                            </div>
                          );
                        })}
                      </div>
                    ))
                  ) : (
                    <div className="empty-state">No schedule has been posted for you yet.</div>
                  )}
                </div>
                <div className="schedule-sidebar-list employee-ack-feed">
                  <strong>Acknowledgment History</strong>
                  {employeeScheduleAcknowledgments.length > 0 ? (
                    employeeScheduleAcknowledgments.map((acknowledgment) => (
                      <div className="entity-card" key={acknowledgment.id}>
                        <strong>{formatWeekLabel(acknowledgment.week_start)}</strong>
                        <p>Acknowledged on {new Date(acknowledgment.acknowledged_at).toLocaleString()}</p>
                      </div>
                    ))
                  ) : (
                    <div className="empty-state">You have not acknowledged a published schedule yet.</div>
                  )}
                </div>
              </article>
            ) : null}

            {employeeTab === "request_off" ? (
              <div className="employee-grid">
                <form className="stack-form" onSubmit={handleRequestOffSubmit}>
                  <h4>Request Off</h4>
                  <div className="split-row">
                    <input
                      type="date"
                      value={requestOffForm.start_date}
                      onChange={(event) => setRequestOffForm({ ...requestOffForm, start_date: event.target.value })}
                    />
                    <input
                      type="date"
                      value={requestOffForm.end_date}
                      onChange={(event) => setRequestOffForm({ ...requestOffForm, end_date: event.target.value })}
                    />
                  </div>
                  <textarea
                    placeholder="Tell the admin why you need the time off"
                    value={requestOffForm.reason}
                    onChange={(event) => setRequestOffForm({ ...requestOffForm, reason: event.target.value })}
                  />
                  <button className="primary-button" type="submit">
                    Submit Request
                  </button>
                </form>

                <div className="scroll-list">
                  {employeeRequests.length > 0 ? (
                    employeeRequests.map((request) => (
                      <div className="entity-card" key={request.id}>
                        <strong>
                          {formatDate(request.start_date)} to {formatDate(request.end_date)}
                        </strong>
                        <p>{request.reason}</p>
                        <p>Status: {request.status}</p>
                        {request.manager_response ? <p>Manager reply: {request.manager_response}</p> : null}
                      </div>
                    ))
                  ) : (
                    <div className="empty-state">No request-off submissions yet.</div>
                  )}
                </div>
              </div>
            ) : null}

            {employeeTab === "availability" ? (
              <div className="employee-grid">
                <form className="stack-form" onSubmit={handleAvailabilitySubmit}>
                  <h4>Availability</h4>
                  <select
                    value={availabilityForm.mode}
                    onChange={(event) =>
                      setAvailabilityForm({
                        ...availabilityForm,
                        mode: event.target.value as "recurring" | "date_range",
                      })
                    }
                  >
                    <option value="recurring">Recurring Weekly Availability</option>
                    <option value="date_range">Date-Specific Availability</option>
                  </select>
                  {availabilityForm.mode === "recurring" ? (
                    <select value={availabilityForm.weekday} onChange={(event) => setAvailabilityForm({ ...availabilityForm, weekday: event.target.value })}>
                      {Array.from({ length: 7 }, (_, value) => (
                        <option key={value} value={value}>
                          {weekdayLabel(value)}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <div className="split-row">
                      <input
                        type="date"
                        value={availabilityForm.start_date}
                        onChange={(event) => setAvailabilityForm({ ...availabilityForm, start_date: event.target.value })}
                      />
                      <input
                        type="date"
                        value={availabilityForm.end_date}
                        onChange={(event) => setAvailabilityForm({ ...availabilityForm, end_date: event.target.value })}
                      />
                    </div>
                  )}
                  <div className="split-row">
                    <input
                      type="time"
                      value={availabilityForm.start_time}
                      onChange={(event) => setAvailabilityForm({ ...availabilityForm, start_time: event.target.value })}
                    />
                    <input
                      type="time"
                      value={availabilityForm.end_time}
                      onChange={(event) => setAvailabilityForm({ ...availabilityForm, end_time: event.target.value })}
                    />
                  </div>
                  <textarea
                    placeholder="Optional note for your manager"
                    value={availabilityForm.note}
                    onChange={(event) => setAvailabilityForm({ ...availabilityForm, note: event.target.value })}
                  />
                  <button className="primary-button" type="submit">
                    Submit Availability
                  </button>
                </form>

                <div className="scroll-list">
                  {employeeAvailabilityRequests.length > 0 ? (
                    employeeAvailabilityRequests.map((request) => (
                      <div className="entity-card" key={request.id}>
                        <strong>
                          {request.weekday !== null
                            ? `${weekdayLabel(request.weekday)} • ${request.start_time} - ${request.end_time}`
                            : `${formatDate(request.start_date ?? "")} to ${formatDate(request.end_date ?? "")} • ${request.start_time} - ${request.end_time}`}
                        </strong>
                        {request.note ? <p>{request.note}</p> : null}
                        <p>Status: {request.status}</p>
                        {request.manager_response ? <p>Manager reply: {request.manager_response}</p> : null}
                      </div>
                    ))
                  ) : (
                    <div className="empty-state">No recurring availability requests submitted yet.</div>
                  )}
                </div>
              </div>
            ) : null}

            {employeeTab === "shift_changes" ? (
              <div className="employee-grid">
                <form className="stack-form" onSubmit={handleShiftChangeSubmit}>
                  <h4>Shift Pickup or Swap</h4>
                  <select value={shiftChangeForm.shift_id} onChange={(event) => setShiftChangeForm({ ...shiftChangeForm, shift_id: event.target.value })}>
                    <option value="">Select one of your published shifts</option>
                    {(employeePortal?.schedule ?? []).map((shift) => {
                      const window = formatShiftWindow(shift);
                      return (
                        <option key={shift.id} value={shift.id}>
                          {window.day} • {window.time}
                        </option>
                      );
                    })}
                  </select>
                  <select
                    value={shiftChangeForm.request_type}
                    onChange={(event) =>
                      setShiftChangeForm({
                        ...shiftChangeForm,
                        request_type: event.target.value as ShiftChangeRequest["request_type"],
                      })
                    }
                  >
                    <option value="pickup">Need Pickup</option>
                    <option value="swap">Need Swap</option>
                  </select>
                  <textarea
                    placeholder="Tell your manager what changed and who might be able to help."
                    value={shiftChangeForm.note}
                    onChange={(event) => setShiftChangeForm({ ...shiftChangeForm, note: event.target.value })}
                  />
                  <button className="primary-button" type="submit">
                    Submit Shift Change
                  </button>
                </form>

                <div className="scroll-list">
                  {employeeShiftChangeRequests.length > 0 ? (
                    employeeShiftChangeRequests.map((request) => {
                      const shiftWindow = formatShiftWindow({
                        id: request.shift_id,
                        employee_id: request.requester_employee_id,
                        shift_date: request.shift_date,
                        start_at: request.shift_start_at,
                        end_at: request.shift_end_at,
                        role_label: null,
                        location_name: null,
                        is_published: true,
                        published_at: null,
                        published_by_name: null,
                      });
                      return (
                        <div className="entity-card" key={request.id}>
                          <strong>
                            {request.request_type === "pickup" ? "Pickup Request" : "Swap Request"} • {shiftWindow.day}
                          </strong>
                          <p>{shiftWindow.time}</p>
                          <p>{request.note}</p>
                          <p>Status: {request.status}</p>
                          {request.replacement_employee_name ? <p>Reassigned to: {request.replacement_employee_name}</p> : null}
                          {request.manager_response ? <p>Manager reply: {request.manager_response}</p> : null}
                        </div>
                      );
                    })
                  ) : (
                    <div className="empty-state">No shift change requests yet.</div>
                  )}
                </div>
                <div className="scroll-list">
                  <div className="panel-heading">
                    <p className="eyebrow">Pickup Board</p>
                    <h4>Open Shifts You Can Claim</h4>
                  </div>
                  {pickupBoard.length > 0 ? (
                    pickupBoard.map((request) => {
                      const shiftWindow = formatShiftWindow({
                        id: request.shift_id,
                        employee_id: request.requester_employee_id,
                        shift_date: request.shift_date,
                        start_at: request.shift_start_at,
                        end_at: request.shift_end_at,
                        role_label: null,
                        location_name: null,
                        is_published: true,
                        published_at: null,
                        published_by_name: null,
                      });
                      return (
                        <div className="entity-card" key={`pickup-${request.id}`}>
                          <strong>{request.requester_name} needs coverage</strong>
                          <p>{shiftWindow.day}</p>
                          <p>{shiftWindow.time}</p>
                          <p>{request.note}</p>
                          {request.replacement_employee_name ? (
                            <p>Claimed by: {request.replacement_employee_name}</p>
                          ) : (
                            <button className="primary-button" type="button" onClick={() => void handleClaimPickupRequest(request.id)}>
                              I Can Take This
                            </button>
                          )}
                        </div>
                      );
                    })
                  ) : (
                    <div className="empty-state">No open pickup requests right now.</div>
                  )}
                </div>
              </div>
            ) : null}

            {employeeTab === "profile" ? (
              <div className="employee-grid">
                <form className="stack-form" onSubmit={handleEmployeeProfileSubmit}>
                  <h4>Scheduling Preferences</h4>
                  <input value={employeeProfile?.full_name ?? ""} disabled />
                  <input value={employeeProfile?.job_title ?? "No job title set"} disabled />
                  <input
                    min="0"
                    placeholder="Preferred weekly hours"
                    type="number"
                    value={employeeProfileForm.preferred_weekly_hours}
                    onChange={(event) => setEmployeeProfileForm({ ...employeeProfileForm, preferred_weekly_hours: event.target.value })}
                  />
                  <textarea
                    placeholder="Preferred shifts, availability notes, or scheduling preferences"
                    value={employeeProfileForm.preferred_shift_notes}
                    onChange={(event) => setEmployeeProfileForm({ ...employeeProfileForm, preferred_shift_notes: event.target.value })}
                  />
                  <button className="primary-button" type="submit">
                    Save Preferences
                  </button>
                </form>

                <div className="scroll-list">
                  <div className="entity-card">
                    <strong>Profile Snapshot</strong>
                    <p>Employee #: {employeeProfile?.employee_number ?? "Not set"}</p>
                    <p>Job Title: {employeeProfile?.job_title ?? "Not set"}</p>
                    <p>Preferred Weekly Hours: {employeeProfile?.preferred_weekly_hours ?? "Not set"}</p>
                    <p>{employeeProfile?.preferred_shift_notes ?? "No scheduling preferences saved yet."}</p>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </section>

      <section className="dashboard-grid">
        <article className="panel admin-panel admin-panel-expanded">
          <div className="panel-heading">
            <p className="eyebrow">MiseIQ Admin</p>
            <h3>Workforce Operations Console</h3>
          </div>

          {!adminUser ? (
            <div className="admin-login-shell">
              <form className="admin-form" onSubmit={handleAdminLogin}>
                <label>
                  Admin Email
                  <input value={adminEmail} onChange={(event) => setAdminEmail(event.target.value)} />
                </label>
                <label>
                  Password
                  <input type="password" value={adminPassword} onChange={(event) => setAdminPassword(event.target.value)} />
                </label>
                <button className="primary-button" type="submit">
                  Admin Login
                </button>
              </form>
              <aside className="admin-brand-panel">
                <img className="admin-brand-illustration" src="/miseiq-ops-illustration.svg" alt="MiseIQ operations illustration" />
                <p className="eyebrow">MiseIQ Control Layer</p>
                <h4>Owner-grade workforce visibility</h4>
                <p className="muted-copy">
                  Review labor planning, request queues, clock activity, and publishing workflows in a dashboard that matches the rest of your MiseIQ brand.
                </p>
              </aside>
            </div>
          ) : (
            <>
              <div className="admin-toolbar">
                <div className="admin-welcome">
                  Signed in as <strong>{adminUser.full_name}</strong> ({adminUser.role})
                </div>
                <button className="ghost-button" type="button" onClick={handleLogout}>
                  Logout
                </button>
              </div>
              <div className="tab-row">
                {(["setup", "employees", "schedules", "notes", "requests", "timesheets", "integrations"] as AdminTab[]).map((tab) => (
                  <button
                    key={tab}
                    className={adminTab === tab ? "tab active-tab" : "tab"}
                    type="button"
                    onClick={() => setAdminTab(tab)}
                  >
                    {tab[0].toUpperCase() + tab.slice(1)}
                  </button>
                ))}
              </div>
            </>
          )}

          {adminError ? <div className="inline-error">{adminError}</div> : null}
          {adminMessage ? <div className="inline-message">{adminMessage}</div> : null}

          {adminUser && summary ? (
            <>
              <div className="metric-grid">
                <div className="metric">
                  <span>{summary.active_employees}</span>
                  <p>Employees</p>
                </div>
                <div className="metric">
                  <span>{summary.currently_clocked_in}</span>
                  <p>Clocked In Now</p>
                </div>
                <div className="metric">
                  <span>{summary.report_recipients}</span>
                  <p>Report Recipients</p>
                </div>
                <div className="metric">
                  <span>{summary.connected_integrations}</span>
                  <p>Connected Apps</p>
                </div>
                <div className="metric">
                  <span>{summary.pending_notifications}</span>
                  <p>Needs Review</p>
                </div>
              </div>

              {adminTab === "setup" && setupOverview ? (
                <div className="admin-section">
                  <div className="stack-form">
                    <h4>Setup Overview</h4>
                    <div className="summary-card">
                      <strong>{setupOverview.organization_name}</strong>
                      <p>Timezone: {setupOverview.timezone}</p>
                      <p>
                        {setupOverview.quickbooks_configured
                          ? "QuickBooks credentials are loaded."
                          : "QuickBooks credentials still need to be added to .env."}
                      </p>
                    </div>
                    <div className="metric-grid">
                      <div className="metric">
                        <span>{setupOverview.employee_count}</span>
                        <p>Employees</p>
                      </div>
                      <div className="metric">
                        <span>{setupOverview.scheduled_shift_count}</span>
                        <p>Shifts</p>
                      </div>
                      <div className="metric">
                        <span>{setupOverview.note_count}</span>
                        <p>Notes</p>
                      </div>
                      <div className="metric">
                        <span>{setupOverview.time_entry_count}</span>
                        <p>Time Entries</p>
                      </div>
                      <div className="metric">
                        <span>{reportRecipients.filter((recipient) => recipient.is_active).length}</span>
                        <p>Active Recipients</p>
                      </div>
                    </div>

                    {weeklyLatestPublishedShift ? (
                      <div className="publish-history-card">
                        <strong>Last published</strong>
                        <p>
                          {new Date(weeklyLatestPublishedShift.published_at ?? "").toLocaleString()} by{" "}
                          {weeklyLatestPublishedShift.published_by_name ?? "an admin"}
                        </p>
                      </div>
                    ) : null}
                    <div className="schedule-sidebar-list">
                      <strong>Notification Center</strong>
                      {notifications.length > 0 ? (
                        notifications.map((item) => (
                          <button className="entity-card entity-button" key={item.key} type="button" onClick={() => handleNotificationClick(item)}>
                            <strong>{item.title}</strong>
                            <p>{item.detail}</p>
                            {item.created_at ? <p>{new Date(item.created_at).toLocaleString()}</p> : null}
                          </button>
                        ))
                      ) : (
                        <div className="empty-state">Everything is caught up right now.</div>
                      )}
                    </div>
                    <form className="schedule-sidebar-list" onSubmit={handleSubmitReportRecipient}>
                      <strong>Report Recipients</strong>
                      <input
                        placeholder="Email address"
                        value={reportRecipientForm.email}
                        onChange={(event) => setReportRecipientForm({ ...reportRecipientForm, email: event.target.value })}
                      />
                      <select
                        value={reportRecipientForm.report_type}
                        onChange={(event) => setReportRecipientForm({ ...reportRecipientForm, report_type: event.target.value })}
                      >
                        <option value="daily_labor_summary">Daily Labor Summary</option>
                        <option value="missed_punch_report">Missed Punch Report</option>
                        <option value="payroll_export">Payroll Export</option>
                      </select>
                      <button className="primary-button" type="submit">
                        Add Recipient
                      </button>
                      {reportRecipients.length > 0 ? (
                        <div className="target-list">
                          {reportRecipients.map((recipient) => (
                            <div className="target-card" key={recipient.id}>
                              <strong>{recipient.email}</strong>
                              <p>{recipient.report_type}</p>
                              <p>{recipient.is_active ? "Active" : "Archived"}</p>
                              {recipient.is_active ? (
                                <button className="ghost-button mini-action-button" type="button" onClick={() => void handleArchiveReportRecipient(recipient.id)}>
                                  Archive
                                </button>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="empty-state">No report recipients added yet.</div>
                      )}
                    </form>
                  </div>
                  <div className="scroll-list">
                    {setupOverview.checklist.map((item) => (
                      <div className="entity-card" key={item.key}>
                        <strong>{item.complete ? "Complete" : "Needs Attention"}</strong>
                        <p>{item.label}</p>
                        <p>{item.detail}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {adminTab === "employees" ? (
                <div className="admin-section">
                  <form className="stack-form" onSubmit={handleSubmitEmployee}>
                    <h4>{employeeForm.id ? "Edit Employee" : "Add Employee"}</h4>
                    <input placeholder="Full name" value={employeeForm.full_name} onChange={(event) => setEmployeeForm({ ...employeeForm, full_name: event.target.value })} />
                    <input placeholder="Email" value={employeeForm.email} onChange={(event) => setEmployeeForm({ ...employeeForm, email: event.target.value })} />
                    <input placeholder="Employee number" value={employeeForm.employee_number} onChange={(event) => setEmployeeForm({ ...employeeForm, employee_number: event.target.value })} />
                    <input placeholder="PIN" value={employeeForm.pin_code} onChange={(event) => setEmployeeForm({ ...employeeForm, pin_code: event.target.value })} />
                    <input placeholder="Job title" value={employeeForm.job_title} onChange={(event) => setEmployeeForm({ ...employeeForm, job_title: event.target.value })} />
                    <label className="checkbox-row">
                      <input type="checkbox" checked={employeeForm.is_active} onChange={(event) => setEmployeeForm({ ...employeeForm, is_active: event.target.checked })} />
                      Active employee
                    </label>
                    <div className="action-row">
                      <button className="primary-button" type="submit">
                        {employeeForm.id ? "Save Employee" : "Create Employee"}
                      </button>
                      <button className="ghost-button" type="button" onClick={resetEmployeeForm}>
                        Clear
                      </button>
                      {employeeForm.id ? (
                        <button className="danger-button" type="button" onClick={() => void handleArchiveEmployee()}>
                          Archive
                        </button>
                      ) : null}
                    </div>
                  </form>
                  <div className="scroll-list">
                    {employeeOptions.map((employee) => (
                      <button
                        className="entity-card entity-button"
                        key={employee.id}
                        type="button"
                        onClick={() =>
                          setEmployeeForm({
                            id: employee.id,
                            full_name: employee.full_name,
                            email: employee.email ?? "",
                            employee_number: employee.employee_number ?? "",
                            pin_code: "",
                            job_title: employee.job_title ?? "",
                            is_active: employee.is_active,
                          })
                        }
                      >
                        <strong>{employee.full_name}</strong>
                        <p>{employee.job_title ?? "No job title set"}</p>
                        <p>
                          #{employee.employee_number ?? "No number"} {employee.email ? `• ${employee.email}` : ""}
                        </p>
                        <p>{employee.is_active ? "Active" : "Archived"}</p>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              {adminTab === "schedules" ? (
                <div className="admin-section schedule-builder-section">
                  <div className="schedule-planner panel">
                    <div className="section-heading">
                      <div>
                        <p className="eyebrow">Schedule Builder</p>
                        <h3>Weekly Planner</h3>
                      </div>
                      <p className="muted-copy">Build a week in one place, then use templates and copy-forward to speed up the routine.</p>
                    </div>

                    <div className="schedule-toolbar">
                      <div className="schedule-week-controls">
                        <button className="ghost-button" type="button" onClick={() => moveScheduleWeek(-1)}>
                          Previous Week
                        </button>
                        <button className="ghost-button" type="button" onClick={() => setScheduleWeekStart(getWeekStartIso())}>
                          This Week
                        </button>
                        <button className="ghost-button" type="button" onClick={() => moveScheduleWeek(1)}>
                          Next Week
                        </button>
                      </div>
                      <div className="schedule-week-meta">
                        <strong>{formatWeekLabel(scheduleWeekStart)}</strong>
                        <input type="date" value={scheduleWeekStart} onChange={(event) => setScheduleWeekStart(event.target.value)} />
                      </div>
                    </div>

                    <div className="metric-grid">
                      <div className="metric">
                        <span>{weeklyShifts.length}</span>
                        <p>Shifts This Week</p>
                      </div>
                      <div className="metric">
                        <span>{scheduledEmployeeCount}</span>
                        <p>Scheduled Employees</p>
                      </div>
                      <div className="metric">
                        <span>{weeklyHours.toFixed(1)}</span>
                        <p>Hours Planned</p>
                      </div>
                      <div className="metric">
                        <span>{weeklyPendingRequests.length}</span>
                        <p>Pending Requests</p>
                      </div>
                      <div className="metric">
                        <span>{publishedWeeklyShifts.length}</span>
                        <p>Published</p>
                      </div>
                      <div className="metric">
                        <span>{draftWeeklyShifts.length}</span>
                        <p>Draft</p>
                      </div>
                      <div className="metric">
                        <span>{totalCoverageShortage}</span>
                        <p>Open Coverage Spots</p>
                      </div>
                    </div>

                    {scheduleConflictSummaries.length > 0 || overtimeWarnings.length > 0 || weeklyCoverageWarnings.length > 0 ? (
                      <div className="planner-alerts">
                        {scheduleConflictSummaries.map((day) => (
                          <div className="planner-alert-card" key={day.dateValue}>
                            <strong>{formatScheduleDayLabel(day.dateValue)}</strong>
                            {day.issues.map((issue) => (
                              <p key={issue}>{issue}</p>
                            ))}
                          </div>
                        ))}
                        {overtimeWarnings.map((warning) => (
                          <div className="planner-alert-card" key={warning.employee.id}>
                            <strong>{warning.employee.full_name}</strong>
                            <p>{warning.hours.toFixed(1)} scheduled hours this week may trigger overtime.</p>
                          </div>
                        ))}
                        {weeklyCoverageWarnings.map((day) => (
                          <div className="planner-alert-card" key={`coverage-${day.dateValue}`}>
                            <strong>{formatScheduleDayLabel(day.dateValue)}</strong>
                            {day.shortages.map((entry) => (
                              <div className="coverage-warning-row" key={`${day.dateValue}-${entry.daypart}-${entry.role_label ?? "all"}`}>
                                <p>
                                  {coverageDaypartLabel(entry.daypart)}
                                  {entry.role_label ? ` (${entry.role_label})` : ""} needs {entry.shortage} more team member(s) to reach {entry.required}.
                                </p>
                                {entry.availableSuggestions > 0 ? (
                                  <button
                                    className="ghost-button mini-action-button"
                                    type="button"
                                    onClick={() => void handleAutofillCoverage(day.dateValue, entry.daypart, entry.role_label)}
                                  >
                                    Auto-Fill {entry.availableSuggestions}
                                  </button>
                                ) : null}
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    ) : null}

                    <div className="action-row">
                      <button className="primary-button" type="button" onClick={() => void handleCopyPreviousWeek()}>
                        Copy Previous Week
                      </button>
                      <button className="primary-button secondary-publish-button" type="button" onClick={() => void handlePublishScheduleWeek()}>
                        Publish Week
                      </button>
                      <button className="ghost-button" type="button" onClick={() => void handleUnpublishScheduleWeek()}>
                        Unpublish Week
                      </button>
                      <button className="ghost-button" type="button" onClick={() => prepareShiftForDate(scheduleWeekStart)}>
                        Add Shift to Monday
                      </button>
                    </div>

                    <div className="week-grid">
                      {weekSchedule.map((day) => (
                        <div
                          className={`week-day-card${dragTargetDate === day.dateValue ? " day-drop-target" : ""}`}
                          key={day.dateValue}
                          onDragOver={(event) => handleDayDragOver(event, day.dateValue)}
                          onDrop={(event) => void handleDayDrop(event, day.dateValue)}
                        >
                          <div className="week-day-header">
                            <div>
                              <strong>{day.label}</strong>
                              <p>{day.shifts.length} shift(s)</p>
                            </div>
                            <button className="ghost-button" type="button" onClick={() => prepareShiftForDate(day.dateValue)}>
                              Add Shift
                            </button>
                          </div>

                          {day.requests.length > 0 ? (
                            <div className="day-request-list">
                              {day.requests.map((request) => {
                                const employee = employeeOptions.find((item) => item.id === request.employee_id);
                                return (
                                  <div className="mini-request" key={request.id}>
                                    <strong>{employee?.full_name ?? `Employee ${request.employee_id}`}</strong>
                                    <span className={`status-pill status-${request.status}`}>{request.status}</span>
                                  </div>
                                );
                              })}
                            </div>
                          ) : null}

                          {day.availabilitySuggestions.length > 0 ? (
                            <div className="day-request-list">
                              {day.availabilitySuggestions.map((request) => {
                                const employee = employeeOptions.find((item) => item.id === request.employee_id);
                                return (
                                  <div className="mini-request availability-suggestion" key={request.id}>
                                    <div className="mini-request-copy">
                                      <strong>{employee?.full_name ?? `Employee ${request.employee_id}`}</strong>
                                      <span>{request.start_time} - {request.end_time}</span>
                                    </div>
                                    <button
                                      className="ghost-button mini-action-button"
                                      type="button"
                                      onClick={() => prepareShiftFromAvailability(request, day.dateValue)}
                                    >
                                      Use
                                    </button>
                                  </div>
                                );
                              })}
                            </div>
                          ) : null}

                          <div className="day-shift-list">
                            {scheduleConflictSummaries.find((item) => item.dateValue === day.dateValue) ||
                            weekCoverageSummaries.find((item) => item.dateValue === day.dateValue && item.shortages.length > 0) ? (
                              <div className="day-warning-banner">
                                {scheduleConflictSummaries.find((item) => item.dateValue === day.dateValue)
                                  ? "Conflicts detected for this day."
                                  : "Coverage target is short for one or more dayparts."}
                              </div>
                            ) : null}
                            {weekCoverageSummaries
                              .find((item) => item.dateValue === day.dateValue)
                              ?.shortages.map((entry) => (
                                <div className="coverage-gap-card" key={`${day.dateValue}-${entry.daypart}-${entry.role_label ?? "all"}`}>
                                  <strong>
                                    {coverageDaypartLabel(entry.daypart)}
                                    {entry.role_label ? ` • ${entry.role_label}` : ""}
                                  </strong>
                                  <p>
                                    {entry.scheduled}/{entry.required} scheduled
                                  </p>
                                  {entry.availableSuggestions > 0 ? (
                                    <button
                                      className="ghost-button mini-action-button"
                                      type="button"
                                      onClick={() => void handleAutofillCoverage(day.dateValue, entry.daypart, entry.role_label)}
                                    >
                                      Auto-Fill {entry.availableSuggestions}
                                    </button>
                                  ) : (
                                    <p>No approved matches yet.</p>
                                  )}
                                </div>
                              ))}
                            {day.shifts.length > 0 ? (
                              day.shifts.map((shift) => {
                                const window = formatShiftWindow(shift);
                                const employee = employeeOptions.find((item) => item.id === shift.employee_id);
                                return (
                                  <button
                                    className={`entity-card entity-button shift-tile${
                                      draggingShiftId === shift.id ? " dragging-shift" : ""
                                    }`}
                                    key={shift.id}
                                    type="button"
                                    draggable
                                    onDragStart={(event) => handleShiftDragStart(event, shift.id)}
                                    onDragEnd={handleShiftDragEnd}
                                    onClick={() => loadShiftIntoForm(shift)}
                                  >
                                    <div className="shift-tile-header">
                                      <strong>{employee?.full_name ?? `Employee ${shift.employee_id}`}</strong>
                                      <span className={shift.is_published ? "publish-pill published-pill" : "publish-pill draft-pill"}>
                                        {shift.is_published ? "Published" : "Draft"}
                                      </span>
                                    </div>
                                    <p>{window.time}</p>
                                    <p>{shift.role_label ?? shift.location_name ?? "Scheduled shift"}</p>
                                  </button>
                                );
                              })
                            ) : (
                              <div className="empty-state">No shifts scheduled yet.</div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <form className="stack-form schedule-form" onSubmit={handleSubmitShift}>
                    <h4>{shiftForm.id ? "Edit Shift" : "Quick Add Shift"}</h4>
                    <p className="muted-copy">Choose an employee, tap a template, then save. You can also load a shift directly from the week view to edit it.</p>
                    <select value={shiftForm.employee_id} onChange={(event) => setShiftForm({ ...shiftForm, employee_id: event.target.value })}>
                      <option value="">Select employee</option>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {employee.full_name}
                        </option>
                      ))}
                    </select>
                    <input type="date" value={shiftForm.shift_date} onChange={(event) => setShiftForm({ ...shiftForm, shift_date: event.target.value })} />
                    <div className="template-chip-row">
                      {SHIFT_TEMPLATES.map((template) => (
                        <button
                          key={template.key}
                          className="ghost-button"
                          type="button"
                          onClick={() => applyShiftTemplate(template.key)}
                        >
                          {template.label}
                        </button>
                      ))}
                    </div>
                    <div className="split-row">
                      <input type="time" value={shiftForm.start_time} onChange={(event) => setShiftForm({ ...shiftForm, start_time: event.target.value })} />
                      <input type="time" value={shiftForm.end_time} onChange={(event) => setShiftForm({ ...shiftForm, end_time: event.target.value })} />
                    </div>
                    {shiftFormWarnings.length > 0 ? (
                      <div className="form-warning-stack">
                        {shiftFormWarnings.map((warning) => (
                          <div className="form-warning" key={warning}>
                            {warning}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    <input placeholder="Location" value={shiftForm.location_name} onChange={(event) => setShiftForm({ ...shiftForm, location_name: event.target.value })} />
                    <input placeholder="Role label" value={shiftForm.role_label} onChange={(event) => setShiftForm({ ...shiftForm, role_label: event.target.value })} />
                    {shiftForm.id ? (
                      <div className="quick-reassign-panel">
                        <strong>Quick Reassign</strong>
                        <p className="muted-copy">Switch the employee here and save to hand the shift to someone else.</p>
                      </div>
                    ) : null}
                    <div className="action-row">
                      <button className="primary-button" type="submit">
                        {shiftForm.id ? "Save Shift" : "Create Shift"}
                      </button>
                      <button className="ghost-button" type="button" onClick={resetShiftForm}>
                        Clear
                      </button>
                      {shiftForm.id ? (
                        <button className="danger-button" type="button" onClick={() => void handleDeleteShift()}>
                          Delete
                        </button>
                      ) : null}
                    </div>
                    {weeklyPendingRequests.length > 0 ? (
                      <div className="schedule-sidebar-list">
                        <strong>Pending Time-Off Requests This Week</strong>
                        {weeklyPendingRequests.map((request) => {
                          const employee = employeeOptions.find((item) => item.id === request.employee_id);
                          return (
                            <button
                              className="entity-card entity-button"
                              key={request.id}
                              type="button"
                              onClick={() => {
                                setAdminTab("requests");
                                setRequestQueueTab("pending");
                                setRequestReviewForm({
                                  id: request.id,
                                  status: request.status,
                                  manager_response: request.manager_response ?? "",
                                });
                              }}
                            >
                              <strong>{employee?.full_name ?? `Employee ${request.employee_id}`}</strong>
                              <p>
                                {formatDate(request.start_date)} to {formatDate(request.end_date)}
                              </p>
                              <p>{request.reason}</p>
                            </button>
                          );
                        })}
                      </div>
                    ) : null}
                    <form className="schedule-sidebar-list" onSubmit={handleSaveCoverageTarget}>
                      <strong>Staffing Targets</strong>
                      <p className="muted-copy">Set how many people you want by daypart so the planner can flag under-covered days.</p>
                      <div className="split-row">
                        <select
                          value={coverageTargetForm.weekday}
                          onChange={(event) => setCoverageTargetForm({ ...coverageTargetForm, weekday: event.target.value })}
                        >
                          {Array.from({ length: 7 }, (_, index) => (
                            <option key={index} value={index}>
                              {weekdayLabel(index)}
                            </option>
                          ))}
                        </select>
                        <select
                          value={coverageTargetForm.daypart}
                          onChange={(event) =>
                            setCoverageTargetForm({
                              ...coverageTargetForm,
                              daypart: event.target.value as CoverageTarget["daypart"],
                            })
                          }
                        >
                          <option value="morning">Morning</option>
                          <option value="lunch">Lunch</option>
                          <option value="close">Close</option>
                        </select>
                      </div>
                      <input
                        placeholder="Optional role label, like Server or Cashier"
                        value={coverageTargetForm.role_label}
                        onChange={(event) => setCoverageTargetForm({ ...coverageTargetForm, role_label: event.target.value })}
                      />
                      <input
                        min="0"
                        type="number"
                        value={coverageTargetForm.required_headcount}
                        onChange={(event) => setCoverageTargetForm({ ...coverageTargetForm, required_headcount: event.target.value })}
                      />
                      <button className="primary-button" type="submit">
                        Save Staffing Target
                      </button>
                      {coverageTargets.length > 0 ? (
                        <div className="target-list">
                          {coverageTargets.map((target) => (
                            <div className="target-card" key={target.id}>
                              <strong>
                                {weekdayLabel(target.weekday)} • {coverageDaypartLabel(target.daypart)}
                              </strong>
                              {target.role_label ? <p>{target.role_label}</p> : null}
                              <p>{target.required_headcount} team member(s) needed</p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="empty-state">No staffing targets saved yet.</div>
                      )}
                    </form>
                    {pendingAvailabilityRequests.length > 0 ? (
                      <form className="schedule-sidebar-list" onSubmit={handleReviewAvailability}>
                        <strong>Pending Availability Requests</strong>
                        {pendingAvailabilityRequests.map((request) => {
                          const employee = employeeOptions.find((item) => item.id === request.employee_id);
                          return (
                            <button
                              className="entity-card entity-button"
                              key={request.id}
                              type="button"
                              onClick={() =>
                                setAvailabilityReviewForm({
                                  id: request.id,
                                  status: request.status,
                                  manager_response: request.manager_response ?? "",
                                })
                              }
                            >
                              <strong>{employee?.full_name ?? `Employee ${request.employee_id}`}</strong>
                              <p>
                                {request.weekday !== null
                                  ? `${weekdayLabel(request.weekday)} • ${request.start_time} - ${request.end_time}`
                                  : `${formatDate(request.start_date ?? "")} to ${formatDate(request.end_date ?? "")} • ${request.start_time} - ${request.end_time}`}
                              </p>
                              {request.note ? <p>{request.note}</p> : null}
                            </button>
                          );
                        })}
                        <select
                          value={availabilityReviewForm.status}
                          onChange={(event) => setAvailabilityReviewForm({ ...availabilityReviewForm, status: event.target.value })}
                        >
                          <option value="pending">Pending</option>
                          <option value="approved">Approved</option>
                          <option value="denied">Denied</option>
                        </select>
                        <textarea
                          placeholder="Optional manager response"
                          value={availabilityReviewForm.manager_response}
                          onChange={(event) => setAvailabilityReviewForm({ ...availabilityReviewForm, manager_response: event.target.value })}
                        />
                        <button className="primary-button" type="submit" disabled={!availabilityReviewForm.id}>
                          Save Availability Review
                        </button>
                      </form>
                    ) : null}
                    <div className="schedule-sidebar-list">
                      <strong>Publish Audit</strong>
                      {recentSchedulePublications.length > 0 ? (
                        recentSchedulePublications.map((publication) => (
                          <button
                            className="entity-card entity-button"
                            key={publication.id}
                            type="button"
                            onClick={() =>
                              setPublicationForm({
                                id: publication.id,
                                comment: publication.comment ?? "",
                              })
                            }
                          >
                            <strong>
                              {publication.action === "published" ? "Published" : "Unpublished"} • {formatWeekLabel(publication.week_start)}
                            </strong>
                            <p>{new Date(publication.created_at).toLocaleString()}</p>
                            <p>
                              {publication.published_by_name} • {publication.shift_count} shift snapshot • {publication.acknowledged_count} acknowledgment(s)
                            </p>
                            {publication.comment ? <p>Manager comment: {publication.comment}</p> : null}
                          </button>
                        ))
                      ) : (
                        <div className="empty-state">No publish history yet.</div>
                      )}
                    </div>
                    <div className="schedule-sidebar-list">
                      <strong>Snapshot Notes</strong>
                      <textarea
                        placeholder="Select a publish event to add a manager note"
                        value={publicationForm.comment}
                        onChange={(event) => setPublicationForm({ ...publicationForm, comment: event.target.value })}
                      />
                      <div className="action-row">
                        <button className="primary-button" type="button" disabled={!publicationForm.id} onClick={() => void handleSavePublicationComment()}>
                          Save Comment
                        </button>
                        <button
                          className="ghost-button"
                          type="button"
                          disabled={!publicationForm.id}
                          onClick={() => publicationForm.id && void handleRestorePublication(publicationForm.id)}
                        >
                          Restore Snapshot
                        </button>
                      </div>
                    </div>
                  </form>
                </div>
              ) : null}

              {adminTab === "notes" ? (
                <div className="admin-section">
                  <form className="stack-form" onSubmit={handleSubmitNote}>
                    <h4>{noteForm.id ? "Edit Manager Note" : "Add Manager Note"}</h4>
                    <select value={noteForm.employee_id} onChange={(event) => setNoteForm({ ...noteForm, employee_id: event.target.value })}>
                      <option value="all">All employees</option>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {employee.full_name}
                        </option>
                      ))}
                    </select>
                    <input placeholder="Title" value={noteForm.title} onChange={(event) => setNoteForm({ ...noteForm, title: event.target.value })} />
                    <textarea placeholder="Message for the shift team" value={noteForm.body} onChange={(event) => setNoteForm({ ...noteForm, body: event.target.value })} />
                    <label className="checkbox-row">
                      <input type="checkbox" checked={noteForm.is_active} onChange={(event) => setNoteForm({ ...noteForm, is_active: event.target.checked })} />
                      Active note
                    </label>
                    <label className="checkbox-row">
                      <input
                        type="checkbox"
                        checked={noteForm.show_at_clock_in}
                        onChange={(event) => setNoteForm({ ...noteForm, show_at_clock_in: event.target.checked })}
                      />
                      Show at clock-in
                    </label>
                    <div className="action-row">
                      <button className="primary-button" type="submit">
                        {noteForm.id ? "Save Note" : "Create Note"}
                      </button>
                      <button className="ghost-button" type="button" onClick={resetNoteForm}>
                        Clear
                      </button>
                      {noteForm.id ? (
                        <button className="danger-button" type="button" onClick={() => void handleDeleteNote()}>
                          Delete
                        </button>
                      ) : null}
                    </div>
                  </form>
                  <div className="scroll-list">
                    {notes.map((note) => {
                      const employee = employeeOptions.find((item) => item.id === note.employee_id);
                      return (
                        <button
                          className="entity-card entity-button"
                          key={note.id}
                          type="button"
                          onClick={() =>
                            setNoteForm({
                              id: note.id,
                              employee_id: note.employee_id === null ? "all" : String(note.employee_id),
                              title: note.title,
                              body: note.body,
                              is_active: note.is_active,
                              show_at_clock_in: note.show_at_clock_in,
                            })
                          }
                        >
                          <strong>{note.title}</strong>
                          <p>{note.body}</p>
                          <p>{employee ? employee.full_name : "All employees"}</p>
                          <p>{note.is_active ? "Active" : "Hidden"}</p>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {adminTab === "requests" ? (
                <div className="admin-section request-review-section">
                  <div className="request-review-rail">
                    <div className="panel request-overview-panel">
                      <div className="section-heading">
                        <div>
                          <p className="eyebrow">{requestBoardTab === "time_off" ? "Request Off" : "Shift Changes"}</p>
                          <h3>Review Queue</h3>
                        </div>
                        <p className="muted-copy">Managers can work through pending requests first, then check approved history.</p>
                      </div>
                      <div className="tab-row">
                        {(["time_off", "shift_changes"] as RequestBoardTab[]).map((tab) => (
                          <button
                            key={tab}
                            type="button"
                            className={tab === requestBoardTab ? "active-tab-button" : "ghost-button"}
                            onClick={() => setRequestBoardTab(tab)}
                          >
                            {tab === "time_off" ? "Request Off" : "Shift Changes"}
                          </button>
                        ))}
                      </div>
                      <div className="metric-grid compact-grid">
                        <div className="metric">
                          <span>{requestBoardTab === "time_off" ? pendingTimeOffRequests.length : pendingShiftChangeRequests.length}</span>
                          <p>Pending</p>
                        </div>
                        <div className="metric">
                          <span>{requestBoardTab === "time_off" ? approvedTimeOffRequests.length : approvedShiftChangeRequests.length}</span>
                          <p>Approved</p>
                        </div>
                      </div>
                      <div className="tab-row">
                        {(["pending", "approved"] as RequestQueueTab[]).map((tab) => (
                          <button
                            key={tab}
                            type="button"
                            className={tab === requestQueueTab ? "active-tab-button" : "ghost-button"}
                            onClick={() => setRequestQueueTab(tab)}
                          >
                            {tab === "pending"
                              ? `Pending (${requestBoardTab === "time_off" ? pendingTimeOffRequests.length : pendingShiftChangeRequests.length})`
                              : `Approved (${requestBoardTab === "time_off" ? approvedTimeOffRequests.length : approvedShiftChangeRequests.length})`}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="scroll-list request-list">
                      {requestBoardTab === "time_off" && visibleTimeOffRequests.length > 0 ? (
                        visibleTimeOffRequests.map((request) => {
                          const employee = employeeOptions.find((item) => item.id === request.employee_id);
                          return (
                            <button
                              className="entity-card entity-button request-card"
                              key={request.id}
                              type="button"
                              onClick={() =>
                                setRequestReviewForm({
                                  id: request.id,
                                  status: request.status,
                                  manager_response: request.manager_response ?? "",
                                })
                              }
                            >
                              <div className="request-card-header">
                                <strong>{employee?.full_name ?? `Employee ${request.employee_id}`}</strong>
                                <span className={`status-pill status-${request.status}`}>{request.status}</span>
                              </div>
                              <p>
                                {formatDate(request.start_date)} to {formatDate(request.end_date)}
                              </p>
                              <p>{request.reason}</p>
                              {request.manager_response ? <p>Manager reply: {request.manager_response}</p> : null}
                            </button>
                          );
                        })
                      ) : null}
                      {requestBoardTab === "shift_changes" && visibleShiftChangeRequests.length > 0 ? (
                        visibleShiftChangeRequests.map((request) => {
                          const shiftWindow = formatShiftWindow({
                            id: request.shift_id,
                            employee_id: request.requester_employee_id,
                            shift_date: request.shift_date,
                            start_at: request.shift_start_at,
                            end_at: request.shift_end_at,
                            role_label: null,
                            location_name: null,
                            is_published: true,
                            published_at: null,
                            published_by_name: null,
                          });
                          return (
                            <button
                              className="entity-card entity-button request-card"
                              key={request.id}
                              type="button"
                              onClick={() =>
                                setShiftChangeReviewForm({
                                  id: request.id,
                                  status: request.status,
                                  manager_response: request.manager_response ?? "",
                                  replacement_employee_id: request.replacement_employee_id ? String(request.replacement_employee_id) : "",
                                })
                              }
                            >
                              <div className="request-card-header">
                                <strong>{request.requester_name}</strong>
                                <span className={`status-pill status-${request.status}`}>{request.status}</span>
                              </div>
                              <p>
                                {request.request_type === "pickup" ? "Pickup Request" : "Swap Request"} • {shiftWindow.day}
                              </p>
                              <p>{shiftWindow.time}</p>
                              <p>{request.note}</p>
                              {request.replacement_employee_name ? <p>Replacement: {request.replacement_employee_name}</p> : null}
                              {request.manager_response ? <p>Manager reply: {request.manager_response}</p> : null}
                            </button>
                          );
                        })
                      ) : (
                        <div className="empty-state">
                          {requestBoardTab === "time_off"
                            ? requestQueueTab === "pending"
                              ? "No pending request-off reviews right now."
                              : "No approved request-off history yet."
                            : requestQueueTab === "pending"
                              ? "No pending shift change reviews right now."
                              : "No approved shift change history yet."}
                        </div>
                      )}
                    </div>
                  </div>

                  {requestBoardTab === "time_off" ? (
                    <form className="stack-form" onSubmit={handleReviewRequest}>
                      <h4>{requestReviewForm.id ? "Review Selected Request" : "Select a Request"}</h4>
                      <p className="muted-copy">
                        Choose a request from the list, then add an optional manager reply before saving the decision.
                      </p>
                      <select
                        value={requestReviewForm.status}
                        onChange={(event) => setRequestReviewForm({ ...requestReviewForm, status: event.target.value })}
                      >
                        <option value="pending">Pending</option>
                        <option value="approved">Approved</option>
                        <option value="denied">Denied</option>
                      </select>
                      <textarea
                        placeholder="Optional manager response"
                        value={requestReviewForm.manager_response}
                        onChange={(event) => setRequestReviewForm({ ...requestReviewForm, manager_response: event.target.value })}
                      />
                      <div className="action-row">
                        <button className="primary-button" type="submit" disabled={!requestReviewForm.id}>
                          Save Review
                        </button>
                        <button className="ghost-button" type="button" onClick={resetRequestReviewForm}>
                          Clear
                        </button>
                      </div>
                    </form>
                  ) : (
                    <form className="stack-form" onSubmit={handleReviewShiftChange}>
                      <h4>{shiftChangeReviewForm.id ? "Review Selected Shift Change" : "Select a Shift Change Request"}</h4>
                      <p className="muted-copy">Approve a replacement employee to hand off the shift, or deny the request with a reply.</p>
                      <select
                        value={shiftChangeReviewForm.status}
                        onChange={(event) => setShiftChangeReviewForm({ ...shiftChangeReviewForm, status: event.target.value })}
                      >
                        <option value="pending">Pending</option>
                        <option value="approved">Approved</option>
                        <option value="denied">Denied</option>
                      </select>
                      <select
                        value={shiftChangeReviewForm.replacement_employee_id}
                        onChange={(event) =>
                          setShiftChangeReviewForm({ ...shiftChangeReviewForm, replacement_employee_id: event.target.value })
                        }
                      >
                        <option value="">Select replacement employee</option>
                        {employeeOptions.map((employee) => (
                          <option key={employee.id} value={employee.id}>
                            {employee.full_name}
                          </option>
                        ))}
                      </select>
                      <textarea
                        placeholder="Optional manager response"
                        value={shiftChangeReviewForm.manager_response}
                        onChange={(event) =>
                          setShiftChangeReviewForm({ ...shiftChangeReviewForm, manager_response: event.target.value })
                        }
                      />
                      <div className="action-row">
                        <button className="primary-button" type="submit" disabled={!shiftChangeReviewForm.id}>
                          Save Review
                        </button>
                        <button
                          className="ghost-button"
                          type="button"
                          onClick={() => setShiftChangeReviewForm({ id: null, status: "pending", manager_response: "", replacement_employee_id: "" })}
                        >
                          Clear
                        </button>
                      </div>
                    </form>
                  )}
                </div>
              ) : null}

              {adminTab === "timesheets" ? (
                <div className="admin-section request-review-section">
                  <div className="request-review-rail">
                    <div className="panel request-overview-panel">
                      <div className="section-heading">
                        <div>
                          <p className="eyebrow">Payroll Review</p>
                          <h3>Timesheet Queue</h3>
                        </div>
                        <p className="muted-copy">Approve completed labor entries before payroll export and fix missing details when needed.</p>
                      </div>
                      <div className="metric-grid compact-grid">
                        <div className="metric">
                          <span>{openTimeEntries.length}</span>
                          <p>Open Punches</p>
                        </div>
                        <div className="metric">
                          <span>{pendingTimeEntries.length}</span>
                          <p>Pending Review</p>
                        </div>
                        <div className="metric">
                          <span>{approvedTimeEntries.length}</span>
                          <p>Approved</p>
                        </div>
                      </div>
                    </div>

                    <div className="scroll-list request-list">
                      {(pendingTimeEntries.length > 0 ? pendingTimeEntries : approvedTimeEntries).length > 0 ? (
                        (pendingTimeEntries.length > 0 ? pendingTimeEntries : approvedTimeEntries).map((entry) => {
                          const employee = employeeOptions.find((item) => item.id === entry.employee_id);
                          const clockIn = new Date(entry.clock_in_at);
                          const clockOut = entry.clock_out_at ? new Date(entry.clock_out_at) : null;
                          const hours = clockOut ? (clockOut.getTime() - clockIn.getTime()) / 36e5 : null;
                          return (
                            <button
                              className="entity-card entity-button request-card"
                              key={entry.id}
                              type="button"
                              onClick={() =>
                                setTimeEntryReviewForm({
                                  id: entry.id,
                                  approved: entry.approved,
                                  notes: entry.notes ?? "",
                                  clock_out_at: entry.clock_out_at ? new Date(entry.clock_out_at).toISOString().slice(0, 16) : "",
                                })
                              }
                            >
                              <div className="request-card-header">
                                <strong>{employee?.full_name ?? `Employee ${entry.employee_id}`}</strong>
                                <span className={entry.approved ? "publish-pill published-pill" : "publish-pill draft-pill"}>
                                  {entry.approved ? "Approved" : "Pending"}
                                </span>
                              </div>
                              <p>In: {clockIn.toLocaleString()}</p>
                              <p>{clockOut ? `Out: ${clockOut.toLocaleString()}` : "Still clocked in"}</p>
                              <p>{hours !== null ? `${hours.toFixed(2)} hours` : "Open shift"}</p>
                              {entry.notes ? <p>Notes: {entry.notes}</p> : null}
                            </button>
                          );
                        })
                      ) : (
                        <div className="empty-state">No timesheet entries need review right now.</div>
                      )}
                    </div>
                    {openTimeEntries.length > 0 ? (
                      <div className="schedule-sidebar-list">
                        <strong>Open Punches</strong>
                        {openTimeEntries.map((entry) => {
                          const employee = employeeOptions.find((item) => item.id === entry.employee_id);
                          return (
                            <div className="entity-card" key={entry.id}>
                              <strong>{employee?.full_name ?? `Employee ${entry.employee_id}`}</strong>
                              <p>In: {new Date(entry.clock_in_at).toLocaleString()}</p>
                              <p>Still clocked in</p>
                            </div>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>

                  <form className="stack-form" onSubmit={handleReviewTimeEntry}>
                    <h4>{timeEntryReviewForm.id ? "Review Selected Time Entry" : "Select a Time Entry"}</h4>
                    <p className="muted-copy">Approve the entry, add payroll notes, or enter a missing clock-out time before saving.</p>
                    <label className="checkbox-row">
                      <input
                        type="checkbox"
                        checked={timeEntryReviewForm.approved}
                        onChange={(event) => setTimeEntryReviewForm({ ...timeEntryReviewForm, approved: event.target.checked })}
                      />
                      Approved for payroll
                    </label>
                    <input
                      type="datetime-local"
                      value={timeEntryReviewForm.clock_out_at}
                      onChange={(event) => setTimeEntryReviewForm({ ...timeEntryReviewForm, clock_out_at: event.target.value })}
                    />
                    <textarea
                      placeholder="Optional payroll or manager notes"
                      value={timeEntryReviewForm.notes}
                      onChange={(event) => setTimeEntryReviewForm({ ...timeEntryReviewForm, notes: event.target.value })}
                    />
                    <div className="action-row">
                      <button className="primary-button" type="submit" disabled={!timeEntryReviewForm.id}>
                        Save Review
                      </button>
                      <button
                        className="ghost-button"
                        type="button"
                        onClick={() => setTimeEntryReviewForm({ id: null, approved: false, notes: "", clock_out_at: "" })}
                      >
                        Clear
                      </button>
                    </div>
                  </form>
                </div>
              ) : null}

              {adminTab === "integrations" ? (
                <div className="admin-section">
                  <form className="stack-form" onSubmit={(event) => event.preventDefault()}>
                    <h4>QuickBooks</h4>
                    <input placeholder="Company name" value={quickBooksForm.company_name} onChange={(event) => setQuickBooksForm({ ...quickBooksForm, company_name: event.target.value })} />
                    <input placeholder="Realm ID" value={quickBooksForm.realm_id} onChange={(event) => setQuickBooksForm({ ...quickBooksForm, realm_id: event.target.value })} />
                    <div className="split-row">
                      <input type="date" value={quickBooksForm.start_date} onChange={(event) => setQuickBooksForm({ ...quickBooksForm, start_date: event.target.value })} />
                      <input type="date" value={quickBooksForm.end_date} onChange={(event) => setQuickBooksForm({ ...quickBooksForm, end_date: event.target.value })} />
                    </div>
                    <div className="action-row">
                      <button className="ghost-button" type="button" onClick={() => void handleGenerateQuickBooksAuthUrl()}>
                        Get OAuth URL
                      </button>
                      <button className="primary-button" type="button" onClick={() => void handleConnectQuickBooks()}>
                        {quickBooksIntegration?.status === "connected" ? "Reconnect" : "Connect"}
                      </button>
                      {quickBooksIntegration ? (
                        <>
                          <button className="ghost-button" type="button" disabled={quickBooksIntegration.status !== "connected"} onClick={() => void handleExportLabor(quickBooksIntegration.id)}>
                            Export Labor
                          </button>
                          <button className="ghost-button" type="button" disabled={quickBooksIntegration.status !== "connected"} onClick={() => void handleRefreshQuickBooks(quickBooksIntegration.id)}>
                            Refresh Tokens
                          </button>
                          <button className="danger-button" type="button" onClick={() => void handleDisconnectIntegration(quickBooksIntegration.id)}>
                            Disconnect
                          </button>
                        </>
                      ) : null}
                    </div>
                    {exportSummary ? (
                      <div className="summary-card">
                        <strong>Last Export</strong>
                        <p>
                          {exportSummary.entries} entries, {exportSummary.hours} hours
                        </p>
                        <p>
                          {exportSummary.start_date} to {exportSummary.end_date}
                        </p>
                      </div>
                    ) : null}
                    {quickBooksAuth ? (
                      <div className="summary-card">
                        <strong>OAuth URL</strong>
                        <p>Open this URL in a browser after you set your QuickBooks client credentials.</p>
                        <a href={quickBooksAuth.authorization_url} target="_blank" rel="noreferrer">
                          Launch QuickBooks authorization
                        </a>
                        <p className="code-line">{quickBooksAuth.authorization_url}</p>
                      </div>
                    ) : null}
                    {quickBooksConfig ? (
                      <div className="summary-card">
                        <strong>OAuth Setup Status</strong>
                        <p>{quickBooksConfig.configured ? "QuickBooks client credentials are loaded." : "QuickBooks client credentials are not loaded yet."}</p>
                        <p>Environment: {quickBooksConfig.environment}</p>
                        <p>Redirect URI: {quickBooksConfig.redirect_uri}</p>
                        <p>Scopes: {quickBooksConfig.scopes.join(", ")}</p>
                        <p>
                          Client ID: {quickBooksConfig.client_id_present ? "present" : "missing"} | Client secret: {quickBooksConfig.client_secret_present ? "present" : "missing"}
                        </p>
                      </div>
                    ) : null}
                  </form>
                  <div className="scroll-list">
                    {quickBooksIntegration ? (
                      <div className="entity-card">
                        <strong>QuickBooks</strong>
                        <p>Status: {quickBooksIntegration.status}</p>
                        <p>Company: {(quickBooksIntegration.settings?.company_name as string | undefined) ?? "Not set"}</p>
                        <p>Realm: {(quickBooksIntegration.settings?.realm_id as string | undefined) ?? "Not set"}</p>
                        <p>Last sync: {quickBooksIntegration.last_synced_at ? new Date(quickBooksIntegration.last_synced_at).toLocaleString() : "Never"}</p>
                      </div>
                    ) : (
                      <div className="empty-state">Connect QuickBooks to simulate labor exports for accounting.</div>
                    )}
                  </div>
                </div>
              ) : null}
            </>
          ) : adminUser ? (
            <div className="empty-state">Loading admin data...</div>
          ) : (
            <div className="empty-state">Log in as an admin to manage employees, schedules, notes, and integrations.</div>
          )}
        </article>
      </section>
    </div>
  );
}
