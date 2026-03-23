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
};

type User = {
  id: number;
  full_name: string;
  email: string | null;
  role: string;
  employee_number: string | null;
  job_title: string | null;
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

type AdminTab = "employees" | "schedules" | "notes";

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
  const [adminTab, setAdminTab] = useState<AdminTab>("employees");
  const [setupMessage, setSetupMessage] = useState("Preparing demo workspace...");

  const [newEmployee, setNewEmployee] = useState({
    full_name: "",
    email: "",
    employee_number: "",
    pin_code: "",
    job_title: "",
  });
  const [newShift, setNewShift] = useState({
    employee_id: "",
    shift_date: "",
    start_time: "09:00",
    end_time: "17:00",
    location_name: "Main Store",
    role_label: "",
  });
  const [newNote, setNewNote] = useState({
    employee_id: "all",
    title: "",
    body: "",
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
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail ?? "Request failed.");
    }
    return data;
  }

  async function loadAdminData(accessToken: string, orgId: string) {
    try {
      const [summaryData, userData, shiftData, noteData] = await Promise.all([
        apiFetch(`/organizations/${orgId}/dashboard-summary`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/users`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/shifts`, {}, accessToken),
        apiFetch(`/organizations/${orgId}/notes`, {}, accessToken),
      ]);
      setSummary(summaryData as DashboardSummary);
      setEmployees(userData as User[]);
      setShifts(shiftData as Shift[]);
      setNotes(noteData as Note[]);
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to load admin data.");
    }
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
        void loadAdminData(token, organizationId);
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
    setAdminMessage("Signed out.");
    window.localStorage.removeItem("labortrackiq_token");
    window.localStorage.removeItem("labortrackiq_user");
    window.localStorage.removeItem("labortrackiq_org");
  }

  async function handleCreateEmployee(event: FormEvent) {
    event.preventDefault();
    setAdminError("");
    try {
      await apiFetch("/users", {
        method: "POST",
        body: JSON.stringify({
          organization_id: Number(organizationId),
          full_name: newEmployee.full_name,
          email: newEmployee.email || null,
          role: "employee",
          employee_number: newEmployee.employee_number,
          pin_code: newEmployee.pin_code,
          job_title: newEmployee.job_title || null,
        }),
      });
      setNewEmployee({ full_name: "", email: "", employee_number: "", pin_code: "", job_title: "" });
      setAdminMessage("Employee created.");
      await loadAdminData(token, organizationId);
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to create employee.");
    }
  }

  async function handleCreateShift(event: FormEvent) {
    event.preventDefault();
    setAdminError("");
    try {
      await apiFetch("/shifts", {
        method: "POST",
        body: JSON.stringify({
          organization_id: Number(organizationId),
          employee_id: Number(newShift.employee_id),
          shift_date: newShift.shift_date,
          start_at: toIsoDateTime(newShift.shift_date, newShift.start_time),
          end_at: toIsoDateTime(newShift.shift_date, newShift.end_time),
          location_name: newShift.location_name || null,
          role_label: newShift.role_label || null,
        }),
      });
      setNewShift({
        employee_id: "",
        shift_date: "",
        start_time: "09:00",
        end_time: "17:00",
        location_name: "Main Store",
        role_label: "",
      });
      setAdminMessage("Shift created.");
      await loadAdminData(token, organizationId);
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to create shift.");
    }
  }

  async function handleCreateNote(event: FormEvent) {
    event.preventDefault();
    setAdminError("");
    try {
      await apiFetch("/notes", {
        method: "POST",
        body: JSON.stringify({
          organization_id: Number(organizationId),
          employee_id: newNote.employee_id === "all" ? null : Number(newNote.employee_id),
          title: newNote.title,
          body: newNote.body,
          is_active: true,
          show_at_clock_in: true,
        }),
      });
      setNewNote({ employee_id: "all", title: "", body: "" });
      setAdminMessage("Manager note created.");
      await loadAdminData(token, organizationId);
    } catch (error) {
      setAdminError(error instanceof Error ? error.message : "Unable to create note.");
    }
  }

  const displayedShifts = clockData?.schedule ?? [];
  const displayedNotes = clockData?.notes ?? [];
  const employeeOptions = employees.filter((employee) => employee.role === "employee");

  return (
    <div className="app-shell">
      <section className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">LaborTrackIQ</p>
          <h1>Tablet Time Clock Built for Fast Shift Starts</h1>
          <p className="hero-text">
            Employees can clock in, check schedules, and see manager notes from a shared tablet while admins manage
            schedules and labor operations in one place.
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

        <article className="panel admin-panel">
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
                <button className={adminTab === "employees" ? "tab active-tab" : "tab"} type="button" onClick={() => setAdminTab("employees")}>
                  Employees
                </button>
                <button className={adminTab === "schedules" ? "tab active-tab" : "tab"} type="button" onClick={() => setAdminTab("schedules")}>
                  Schedules
                </button>
                <button className={adminTab === "notes" ? "tab active-tab" : "tab"} type="button" onClick={() => setAdminTab("notes")}>
                  Notes
                </button>
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
                  <form className="stack-form" onSubmit={handleCreateEmployee}>
                    <h4>Add Employee</h4>
                    <input placeholder="Full name" value={newEmployee.full_name} onChange={(event) => setNewEmployee({ ...newEmployee, full_name: event.target.value })} />
                    <input placeholder="Email" value={newEmployee.email} onChange={(event) => setNewEmployee({ ...newEmployee, email: event.target.value })} />
                    <input placeholder="Employee number" value={newEmployee.employee_number} onChange={(event) => setNewEmployee({ ...newEmployee, employee_number: event.target.value })} />
                    <input placeholder="PIN" value={newEmployee.pin_code} onChange={(event) => setNewEmployee({ ...newEmployee, pin_code: event.target.value })} />
                    <input placeholder="Job title" value={newEmployee.job_title} onChange={(event) => setNewEmployee({ ...newEmployee, job_title: event.target.value })} />
                    <button className="primary-button" type="submit">
                      Create Employee
                    </button>
                  </form>
                  <div className="scroll-list">
                    {employeeOptions.map((employee) => (
                      <div className="entity-card" key={employee.id}>
                        <strong>{employee.full_name}</strong>
                        <p>{employee.job_title ?? "No job title set"}</p>
                        <p>
                          #{employee.employee_number ?? "No number"} {employee.email ? `• ${employee.email}` : ""}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {adminTab === "schedules" ? (
                <div className="admin-section">
                  <form className="stack-form" onSubmit={handleCreateShift}>
                    <h4>Add Shift</h4>
                    <select value={newShift.employee_id} onChange={(event) => setNewShift({ ...newShift, employee_id: event.target.value })}>
                      <option value="">Select employee</option>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {employee.full_name}
                        </option>
                      ))}
                    </select>
                    <input type="date" value={newShift.shift_date} onChange={(event) => setNewShift({ ...newShift, shift_date: event.target.value })} />
                    <div className="split-row">
                      <input type="time" value={newShift.start_time} onChange={(event) => setNewShift({ ...newShift, start_time: event.target.value })} />
                      <input type="time" value={newShift.end_time} onChange={(event) => setNewShift({ ...newShift, end_time: event.target.value })} />
                    </div>
                    <input placeholder="Location" value={newShift.location_name} onChange={(event) => setNewShift({ ...newShift, location_name: event.target.value })} />
                    <input placeholder="Role label" value={newShift.role_label} onChange={(event) => setNewShift({ ...newShift, role_label: event.target.value })} />
                    <button className="primary-button" type="submit">
                      Create Shift
                    </button>
                  </form>
                  <div className="scroll-list">
                    {shifts.map((shift) => {
                      const window = formatShiftWindow(shift);
                      const employee = employeeOptions.find((item) => item.id === shift.employee_id);
                      return (
                        <div className="entity-card" key={shift.id}>
                          <strong>{employee?.full_name ?? `Employee ${shift.employee_id}`}</strong>
                          <p>{window.day}</p>
                          <p>{window.time}</p>
                          <p>{shift.role_label ?? shift.location_name ?? "Scheduled shift"}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {adminTab === "notes" ? (
                <div className="admin-section">
                  <form className="stack-form" onSubmit={handleCreateNote}>
                    <h4>Add Manager Note</h4>
                    <select value={newNote.employee_id} onChange={(event) => setNewNote({ ...newNote, employee_id: event.target.value })}>
                      <option value="all">All employees</option>
                      {employeeOptions.map((employee) => (
                        <option key={employee.id} value={employee.id}>
                          {employee.full_name}
                        </option>
                      ))}
                    </select>
                    <input placeholder="Title" value={newNote.title} onChange={(event) => setNewNote({ ...newNote, title: event.target.value })} />
                    <textarea placeholder="Message for the shift team" value={newNote.body} onChange={(event) => setNewNote({ ...newNote, body: event.target.value })} />
                    <button className="primary-button" type="submit">
                      Create Note
                    </button>
                  </form>
                  <div className="scroll-list">
                    {notes.map((note) => {
                      const employee = employeeOptions.find((item) => item.id === note.employee_id);
                      return (
                        <div className="entity-card" key={note.id}>
                          <strong>{note.title}</strong>
                          <p>{note.body}</p>
                          <p>{employee ? employee.full_name : "All employees"}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}
            </>
          ) : adminUser ? (
            <div className="empty-state">Loading admin data...</div>
          ) : (
            <div className="empty-state">Log in as an admin to manage employees, schedules, and notes.</div>
          )}
        </article>
      </section>
    </div>
  );
}
