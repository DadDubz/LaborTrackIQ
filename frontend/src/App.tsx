import { FormEvent, useEffect, useState } from "react";

type Shift = {
  id: number;
  employee_id: number;
  shift_date: string;
  start_at: string;
  end_at: string;
  role_label: string | null;
  location_name: string | null;
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
  active_employees: number;
  currently_clocked_in: number;
  report_recipients: number;
  connected_integrations: number;
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

type AdminTab = "employees" | "schedules" | "notes" | "integrations";

const API_BASE = "http://127.0.0.1:8000/api";

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

export default function App() {
  const [organizationId, setOrganizationId] = useState("1");
  const [employeeNumber, setEmployeeNumber] = useState("1001");
  const [pinCode, setPinCode] = useState("1234");
  const [clockData, setClockData] = useState<ClockLookupResponse | null>(null);
  const [clockStatus, setClockStatus] = useState("Ready for clock-in");
  const [clockError, setClockError] = useState("");
  const [isClockLoading, setIsClockLoading] = useState(false);

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
  const [adminTab, setAdminTab] = useState<AdminTab>("employees");
  const [setupMessage, setSetupMessage] = useState("Preparing demo workspace...");
  const [exportSummary, setExportSummary] = useState<QuickBooksActionResponse["export_summary"] | null>(null);

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

  async function loadAdminData(accessToken: string, orgId: string) {
    try {
      const [summaryData, userData, shiftData, noteData, integrationData] = await Promise.all([
        apiFetch(`/organizations/${orgId}/dashboard-summary`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/users`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/shifts`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/notes`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/integrations`, {}, accessToken),
      ]);
      setSummary(summaryData as DashboardSummary);
      setEmployees(userData as User[]);
      setShifts(shiftData as Shift[]);
      setNotes(noteData as Note[]);
      setIntegrations(integrationData as Integration[]);
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

  function resetEmployeeForm() {
    setEmployeeForm(emptyEmployeeForm);
  }

  function resetShiftForm() {
    setShiftForm(emptyShiftForm);
  }

  function resetNoteForm() {
    setNoteForm(emptyNoteForm);
  }

  async function handleScheduleLookup(event: FormEvent) {
    event.preventDefault();
    setIsClockLoading(true);
    setClockError("");
    try {
      const data = (await apiFetch(
        "/clock/lookup",
        {
          method: "POST",
          body: JSON.stringify({
            organization_id: Number(organizationId),
            employee_number: employeeNumber,
            pin_code: pinCode,
            source: "tablet",
          }),
        },
        "",
      )) as ClockLookupResponse;
      setClockData(data);
      setClockStatus(`Welcome ${data.employee_name}. Schedule loaded.`);
    } catch (error) {
      setClockError(error instanceof Error ? error.message : "Unable to load schedule.");
    } finally {
      setIsClockLoading(false);
    }
  }

  async function handleClockToggle() {
    setIsClockLoading(true);
    setClockError("");
    try {
      const data = (await apiFetch(
        "/clock/in-out",
        {
          method: "POST",
          body: JSON.stringify({
            organization_id: Number(organizationId),
            employee_number: employeeNumber,
            pin_code: pinCode,
            source: "tablet",
          }),
        },
        "",
      )) as ClockResponse;
      setClockData(data);
      setClockStatus(`${data.employee_name} ${data.status.replace("_", " ")} successfully.`);
      if (token) {
        await loadAdminData(token, organizationId);
      }
    } catch (error) {
      setClockError(error instanceof Error ? error.message : "Unable to clock in or out.");
    } finally {
      setIsClockLoading(false);
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
      await refreshAdminData(response.message);
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to connect QuickBooks.");
    }
  }

  async function handleDisconnectIntegration(integrationId: number) {
    setAdminError("");
    setExportSummary(null);
    try {
      const response = (await apiFetch(`/integrations/${integrationId}/disconnect`, {
        method: "POST",
      })) as QuickBooksActionResponse;
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

  const displayedShifts = clockData?.schedule ?? [];
  const displayedNotes = clockData?.notes ?? [];
  const employeeOptions = employees.filter((employee) => employee.role === "employee");
  const quickBooksIntegration = integrations.find((integration) => integration.provider === "quickbooks");

  return (
    <div className="app-shell">
      <section className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">LaborTrackIQ</p>
          <h1>Tablet Time Clock Built for Fast Shift Starts</h1>
          <p className="hero-text">
            Employees can clock in, check schedules, and see manager notes from a shared tablet while admins manage
            schedules, labor records, and accounting syncs in one place.
          </p>
          <p className="status-strip">{setupMessage}</p>
        </div>

        <form className="clock-card" onSubmit={handleScheduleLookup}>
          <h2>Clock Terminal</h2>
          <div className="terminal-fields">
            <label>
              Organization ID
              <input value={organizationId} onChange={(event) => setOrganizationId(event.target.value)} />
            </label>
            <label>
              Employee Number
              <input value={employeeNumber} onChange={(event) => setEmployeeNumber(event.target.value)} />
            </label>
            <label>
              PIN
              <input type="password" value={pinCode} onChange={(event) => setPinCode(event.target.value)} />
            </label>
          </div>
          <div className="terminal-actions">
            <button className="primary-button" type="button" onClick={() => void handleClockToggle()} disabled={isClockLoading}>
              {isClockLoading ? "Working..." : "Clock In / Out"}
            </button>
            <button className="secondary-button" type="submit" disabled={isClockLoading}>
              View Schedule
            </button>
          </div>
          <div className="note-banner">{clockError || clockStatus}</div>
        </form>
      </section>

      <section className="dashboard-grid">
        <article className="panel">
          <div className="panel-heading">
            <p className="eyebrow">Upcoming</p>
            <h3>Schedule</h3>
          </div>
          <div className="list">
            {displayedShifts.length > 0 ? (
              displayedShifts.map((shift) => {
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
              <div className="empty-state">Load an employee schedule to show upcoming shifts.</div>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <p className="eyebrow">Manager Notes</p>
            <h3>Shift Messages</h3>
          </div>
          <div className="notes">
            {displayedNotes.length > 0 ? (
              displayedNotes.map((note) => (
                <div className="note-card" key={note.id}>
                  <strong>{note.title}</strong>
                  <p>{note.body}</p>
                </div>
              ))
            ) : (
              <div className="empty-state">Clock in or load a schedule to see manager notes.</div>
            )}
          </div>
        </article>

        <article className="panel admin-panel admin-panel-expanded">
          <div className="panel-heading">
            <p className="eyebrow">Admin View</p>
            <h3>Operations Console</h3>
          </div>

          {!adminUser ? (
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
                {(["employees", "schedules", "notes", "integrations"] as AdminTab[]).map((tab) => (
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
              </div>

              {adminTab === "employees" ? (
                <div className="admin-section">
                  <form className="stack-form" onSubmit={handleSubmitEmployee}>
                    <h4>{employeeForm.id ? "Edit Employee" : "Add Employee"}</h4>
                    <input
                      placeholder="Full name"
                      value={employeeForm.full_name}
                      onChange={(event) => setEmployeeForm({ ...employeeForm, full_name: event.target.value })}
                    />
                    <input
                      placeholder="Email"
                      value={employeeForm.email}
                      onChange={(event) => setEmployeeForm({ ...employeeForm, email: event.target.value })}
                    />
                    <input
                      placeholder="Employee number"
                      value={employeeForm.employee_number}
                      onChange={(event) => setEmployeeForm({ ...employeeForm, employee_number: event.target.value })}
                    />
                    <input
                      placeholder="PIN"
                      value={employeeForm.pin_code}
                      onChange={(event) => setEmployeeForm({ ...employeeForm, pin_code: event.target.value })}
                    />
                    <input
                      placeholder="Job title"
                      value={employeeForm.job_title}
                      onChange={(event) => setEmployeeForm({ ...employeeForm, job_title: event.target.value })}
                    />
                    <label className="checkbox-row">
                      <input
                        type="checkbox"
                        checked={employeeForm.is_active}
                        onChange={(event) => setEmployeeForm({ ...employeeForm, is_active: event.target.checked })}
                      />
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
                <div className="admin-section">
                  <form className="stack-form" onSubmit={handleSubmitShift}>
                    <h4>{shiftForm.id ? "Edit Shift" : "Add Shift"}</h4>
                    <select
                      value={shiftForm.employee_id}
                      onChange={(event) => setShiftForm({ ...shiftForm, employee_id: event.target.value })}
                    >
                      <option value="">Select employee</option>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {employee.full_name}
                        </option>
                      ))}
                    </select>
                    <input
                      type="date"
                      value={shiftForm.shift_date}
                      onChange={(event) => setShiftForm({ ...shiftForm, shift_date: event.target.value })}
                    />
                    <div className="split-row">
                      <input
                        type="time"
                        value={shiftForm.start_time}
                        onChange={(event) => setShiftForm({ ...shiftForm, start_time: event.target.value })}
                      />
                      <input
                        type="time"
                        value={shiftForm.end_time}
                        onChange={(event) => setShiftForm({ ...shiftForm, end_time: event.target.value })}
                      />
                    </div>
                    <input
                      placeholder="Location"
                      value={shiftForm.location_name}
                      onChange={(event) => setShiftForm({ ...shiftForm, location_name: event.target.value })}
                    />
                    <input
                      placeholder="Role label"
                      value={shiftForm.role_label}
                      onChange={(event) => setShiftForm({ ...shiftForm, role_label: event.target.value })}
                    />
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
                  </form>
                  <div className="scroll-list">
                    {shifts.map((shift) => {
                      const window = formatShiftWindow(shift);
                      const employee = employeeOptions.find((item) => item.id === shift.employee_id);
                      return (
                        <button
                          className="entity-card entity-button"
                          key={shift.id}
                          type="button"
                          onClick={() => {
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
                          }}
                        >
                          <strong>{employee?.full_name ?? `Employee ${shift.employee_id}`}</strong>
                          <p>{window.day}</p>
                          <p>{window.time}</p>
                          <p>{shift.role_label ?? shift.location_name ?? "Scheduled shift"}</p>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {adminTab === "notes" ? (
                <div className="admin-section">
                  <form className="stack-form" onSubmit={handleSubmitNote}>
                    <h4>{noteForm.id ? "Edit Manager Note" : "Add Manager Note"}</h4>
                    <select
                      value={noteForm.employee_id}
                      onChange={(event) => setNoteForm({ ...noteForm, employee_id: event.target.value })}
                    >
                      <option value="all">All employees</option>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {employee.full_name}
                        </option>
                      ))}
                    </select>
                    <input
                      placeholder="Title"
                      value={noteForm.title}
                      onChange={(event) => setNoteForm({ ...noteForm, title: event.target.value })}
                    />
                    <textarea
                      placeholder="Message for the shift team"
                      value={noteForm.body}
                      onChange={(event) => setNoteForm({ ...noteForm, body: event.target.value })}
                    />
                    <label className="checkbox-row">
                      <input
                        type="checkbox"
                        checked={noteForm.is_active}
                        onChange={(event) => setNoteForm({ ...noteForm, is_active: event.target.checked })}
                      />
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

              {adminTab === "integrations" ? (
                <div className="admin-section">
                  <form className="stack-form" onSubmit={(event) => event.preventDefault()}>
                    <h4>QuickBooks</h4>
                    <input
                      placeholder="Company name"
                      value={quickBooksForm.company_name}
                      onChange={(event) => setQuickBooksForm({ ...quickBooksForm, company_name: event.target.value })}
                    />
                    <input
                      placeholder="Realm ID"
                      value={quickBooksForm.realm_id}
                      onChange={(event) => setQuickBooksForm({ ...quickBooksForm, realm_id: event.target.value })}
                    />
                    <div className="split-row">
                      <input
                        type="date"
                        value={quickBooksForm.start_date}
                        onChange={(event) => setQuickBooksForm({ ...quickBooksForm, start_date: event.target.value })}
                      />
                      <input
                        type="date"
                        value={quickBooksForm.end_date}
                        onChange={(event) => setQuickBooksForm({ ...quickBooksForm, end_date: event.target.value })}
                      />
                    </div>
                    <div className="action-row">
                      <button className="primary-button" type="button" onClick={() => void handleConnectQuickBooks()}>
                        {quickBooksIntegration?.status === "connected" ? "Reconnect" : "Connect"}
                      </button>
                      {quickBooksIntegration ? (
                        <>
                          <button
                            className="ghost-button"
                            type="button"
                            disabled={quickBooksIntegration.status !== "connected"}
                            onClick={() => void handleExportLabor(quickBooksIntegration.id)}
                          >
                            Export Labor
                          </button>
                          <button
                            className="danger-button"
                            type="button"
                            onClick={() => void handleDisconnectIntegration(quickBooksIntegration.id)}
                          >
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
                  </form>
                  <div className="scroll-list">
                    {quickBooksIntegration ? (
                      <div className="entity-card">
                        <strong>QuickBooks</strong>
                        <p>Status: {quickBooksIntegration.status}</p>
                        <p>
                          Company: {(quickBooksIntegration.settings?.company_name as string | undefined) ?? "Not set"}
                        </p>
                        <p>
                          Realm: {(quickBooksIntegration.settings?.realm_id as string | undefined) ?? "Not set"}
                        </p>
                        <p>
                          Last sync: {quickBooksIntegration.last_synced_at ? new Date(quickBooksIntegration.last_synced_at).toLocaleString() : "Never"}
                        </p>
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
