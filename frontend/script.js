
"use strict";

/* =========================================
   HR RECRUITMENT MANAGEMENT SYSTEM
   Frontend JavaScript
========================================= */

const API_BASE = "http://127.0.0.1:8001";

const STORAGE = {
  token: "hr_token",
  role: "hr_role",
  email: "hr_email",
  name: "hr_name"
};

let currentUser = null;
let currentTab = "overview";

/* ---------- DOM helpers ---------- */

const $ = (selector) => document.querySelector(selector);

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[char]);
}

function getToken() {
  return localStorage.getItem(STORAGE.token);
}

function getRole() {
  return (localStorage.getItem(STORAGE.role) || "").toUpperCase();
}

function toast(message, type = "info") {
  let container = $("#toast-container");

  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  const item = document.createElement("div");
  item.className = `toast ${type === "error" ? "error" : type === "success" ? "success" : ""}`;
  item.textContent = message;
  container.appendChild(item);

  window.setTimeout(() => item.remove(), 4000);
}

function showLoading(target, message = "Loading...") {
  if (target) {
    target.innerHTML = `<div class="loading">${escapeHTML(message)}</div>`;
  }
}

/* ---------- API helper ---------- */

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const isFormData = options.body instanceof FormData;

  if (options.body !== undefined && !isFormData) {
    headers.set("Content-Type", "application/json");
  }

  let response;

  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers
    });
  } catch (error) {
    throw new Error(
      "Cannot connect to the backend. Start FastAPI on port 8001 and check the API URL."
    );
  }

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";
  let data;

  if (contentType.includes("application/json")) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    let message = "";

    if (typeof data === "string") {
      message = data;
    } else if (data?.detail) {
      message = typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail);
    } else {
      message = JSON.stringify(data);
    }

    throw new Error(message || `Request failed (${response.status})`);
  }

  return data;
}

function apiGet(path) {
  return api(path);
}

function apiPost(path, body) {
  return api(path, {
    method: "POST",
    body: JSON.stringify(body)
  });
}

function apiPut(path, body) {
  return api(path, {
    method: "PUT",
    body: JSON.stringify(body)
  });
}

function apiPatch(path, body) {
  return api(path, {
    method: "PATCH",
    body: JSON.stringify(body)
  });
}

function apiDelete(path) {
  return api(path, { method: "DELETE" });
}

/* ---------- Authentication ---------- */

/*
  Expected form IDs:
  #login-form
  #register-form
  #auth-section
  #app-section

  Expected login fields:
  #login-email
  #login-password

  Expected registration fields:
  #register-name
  #register-email
  #register-password
  #register-role
*/

async function login(event) {
  event?.preventDefault();

  const email = $("#login-email")?.value.trim();
  const password = $("#login-password")?.value;

  if (!email || !password) {
    toast("Enter your email and password.", "error");
    return;
  }

  const button = $("#login-submit");
  if (button) button.disabled = true;

  try {
    const result = await apiPost("/auth/login", {
      email,
      password
    });

    const token =
      result.access_token ||
      result.token;

    if (!token) {
      throw new Error(
        "The login response did not contain an access token. Check /auth/login in Swagger."
      );
    }

    localStorage.setItem(STORAGE.token, token);
    localStorage.setItem(STORAGE.email, email);

    /*
      Do not guess the user's role from the email.
      The backend must return the role, or expose an authenticated
      endpoint such as /auth/me.
    */

    let user = result.user || result;

    if (!user.role) {
      try {
        user = await apiGet("/auth/me");
      } catch {
        localStorage.removeItem(STORAGE.token);
        throw new Error(
          "Login succeeded, but the frontend could not determine your role. Check whether /auth/login returns role/user details or whether /auth/me exists."
        );
      }
    }

    const role = String(user.role || "").toUpperCase();

    if (!["HR", "CANDIDATE"].includes(role)) {
      localStorage.removeItem(STORAGE.token);
      throw new Error("The backend returned an unsupported user role.");
    }

    localStorage.setItem(STORAGE.role, role);
    localStorage.setItem(
      STORAGE.name,
      user.full_name || user.name || email
    );

    currentUser = user;

    showApplication();
    await loadTab("overview");
    toast("Login successful.", "success");
  } catch (error) {
    toast(error.message, "error");
  } finally {
    if (button) button.disabled = false;
  }
}

async function register(event) {
  event?.preventDefault();

  const fullName = $("#register-name")?.value.trim();
  const email = $("#register-email")?.value.trim();
  const password = $("#register-password")?.value;
  const role = $("#register-role")?.value || "CANDIDATE";
  const phone = $("#register-phone")?.value.trim() || null;

  if (!fullName || !email || !password) {
    toast("Complete all required registration fields.", "error");
    return;
  }

  if (password.length < 8) {
    toast("Use a password with at least 8 characters.", "error");
    return;
  }

  if (!["CANDIDATE", "HR"].includes(role.toUpperCase())) {
    toast("Invalid role selected.", "error");
    return;
  }

  /*
    SECURITY:
    Public registration should not allow anyone to create an HR account.
    Ideally the backend forces public registrations to CANDIDATE and
    creates HR accounts through a protected administrator process.
  */

  if (role.toUpperCase() === "HR") {
    toast(
      "HR registration must be performed through your protected backend/admin process.",
      "error"
    );
    return;
  }

  try {
    await apiPost("/auth/register", {
      full_name: fullName,
      email,
      password,
      role: "CANDIDATE",
      phone
    });

    toast("Registration successful. Please log in.", "success");

    const loginEmail = $("#login-email");
    if (loginEmail) loginEmail.value = email;

    showAuthMode("login");
  } catch (error) {
    toast(error.message, "error");
  }
}

function logout() {
  localStorage.removeItem(STORAGE.token);
  localStorage.removeItem(STORAGE.role);
  localStorage.removeItem(STORAGE.email);
  localStorage.removeItem(STORAGE.name);

  currentUser = null;
  currentTab = "overview";

  showAuthMode("login");
  toast("You have logged out.", "success");
}

function showAuthMode(mode) {
  const auth = $("#auth-section");
  const app = $("#app-section");
  const loginForm = $("#login-form");
  const registerForm = $("#register-form");

  if (auth) auth.classList.remove("hidden");
  if (app) app.classList.add("hidden");

  if (loginForm) {
    loginForm.classList.toggle("hidden", mode !== "login");
  }

  if (registerForm) {
    registerForm.classList.toggle("hidden", mode !== "register");
  }
}

function showApplication() {
  $("#auth-section")?.classList.add("hidden");
  $("#app-section")?.classList.remove("hidden");

  const name = $("#current-user-name");
  if (name) {
    name.textContent = localStorage.getItem(STORAGE.name) || "User";
  }

  const role = $("#current-user-role");
  if (role) role.textContent = getRole();

  document.querySelectorAll("[data-role]").forEach((element) => {
    const allowedRoles = element.dataset.role
      .split(",")
      .map((value) => value.trim().toUpperCase());

    element.classList.toggle(
      "hidden",
      !allowedRoles.includes(getRole())
    );
  });
}

/* ---------- Navigation ---------- */

/*
  Each navigation button should use:
  data-tab="overview"
  data-tab="jobs"
  data-tab="applications"
  etc.

  The page needs a #page-content container.
*/

async function loadTab(tab) {
  currentTab = tab;

  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.classList.toggle(
      "active",
      button.dataset.tab === tab
    );
  });

  const content = $("#page-content");

  if (!content) {
    console.error("Missing #page-content in index.html");
    return;
  }

  showLoading(content);

  try {
    switch (tab) {
      case "overview":
        await renderOverview(content);
        break;

      case "jobs":
        await renderJobs(content);
        break;

      case "applications":
        await renderApplications(content);
        break;

      case "profile":
        await renderProfile(content);
        break;

      case "candidates":
        await renderCandidates(content);
        break;

      case "interviews":
        await renderInterviews(content);
        break;

      case "notifications":
        await renderNotifications(content);
        break;

      default:
        content.innerHTML = `
          <div class="card">
            <h2>Page not found</h2>
            <p>Choose a page from the navigation menu.</p>
          </div>`;
    }
  } catch (error) {
    content.innerHTML = `
      <div class="card">
        <h2>Unable to load this page</h2>
        <p>${escapeHTML(error.message)}</p>
        <p class="muted">
          Check your backend route and response in
          <a href="${API_BASE}/docs" target="_blank" rel="noopener">Swagger</a>.
        </p>
        <button class="btn btn-primary" onclick="loadTab('${escapeHTML(tab)}')">
          Try again
        </button>
      </div>`;
  }
}

/* ---------- Formatting helpers ---------- */

function formatStatus(status) {
  return String(status || "Unknown")
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusBadge(status) {
  const value = String(status || "").toLowerCase();

  let color = "";
  if (["active", "selected", "hired", "shortlisted"].includes(value)) {
    color = "badge-success";
  } else if (["rejected", "closed"].includes(value)) {
    color = "badge-danger";
  } else if (["under_review", "interview_scheduled", "draft"].includes(value)) {
    color = "badge-warning";
  } else {
    color = "badge-info";
  }

  return `<span class="badge ${color}">${escapeHTML(formatStatus(status))}</span>`;
}

function asArray(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.results)) return data.results;
  if (Array.isArray(data?.data)) return data.data;
  return [];
}

function statCard(label, value) {
  return `
    <div class="stat-card">
      <div class="stat-label">${escapeHTML(label)}</div>
      <div class="stat-value">${escapeHTML(value ?? 0)}</div>
    </div>`;
}

function pageHeader(title, description, action = "") {
  return `
    <div class="page-header">
      <div>
        <h1>${escapeHTML(title)}</h1>
        <p class="subtitle">${escapeHTML(description)}</p>
      </div>
      ${action}
    </div>`;
}

/* ---------- Dashboard ---------- */

/*
  These dashboard routes must exist in your backend.
  If they do not, implement them or replace them with actual routes.
*/

async function renderOverview(container) {
  const role = getRole();

  const path = role === "HR"
    ? "/dashboard/hr"
    : "/dashboard/candidate";

  const data = await apiGet(path);
  const summary = data.summary || data;

  let html = pageHeader(
    role === "HR" ? "HR Dashboard" : "Candidate Dashboard",
    role === "HR"
      ? "Manage vacancies and recruitment activity."
      : "Explore jobs and follow your applications."
  );

  if (role === "HR") {
    html += `<div class="stats-grid">
      ${statCard("Total Jobs", summary.total_jobs)}
      ${statCard("Active Jobs", summary.active_jobs)}
      ${statCard("Applications", summary.total_applications)}
      ${statCard("Candidates", summary.total_candidates)}
    </div>`;
  } else {
    html += `<div class="stats-grid">
      ${statCard("My Applications", summary.total_applications)}
      ${statCard("Shortlisted", summary.shortlisted_applications)}
      ${statCard("Interviews", summary.total_interviews)}
      ${statCard("Profile Completion", `${summary.profile_completion_percentage ?? 0}%`)}
    </div>`;
  }

  html += `
    <div class="card">
      <h3>Quick actions</h3>
      <div class="button-row">
        <button class="btn btn-primary" data-tab="jobs">View Jobs</button>
        <button class="btn btn-secondary" data-tab="applications">Applications</button>
        <button class="btn btn-secondary" data-tab="notifications">Notifications</button>
      </div>
    </div>`;

  container.innerHTML = html;
}

/* ---------- Jobs ---------- */

async function renderJobs(container) {
  const isHR = getRole() === "HR";
  const jobs = asArray(await apiGet("/jobs/"));

  container.innerHTML = `
    ${pageHeader(
      isHR ? "Job Management" : "Available Jobs",
      isHR ? "Create and manage job vacancies." : "Explore vacancies and apply for suitable roles.",
      isHR
        ? '<button class="btn btn-primary" id="new-job-button">+ Post Job</button>'
        : ""
    )}
    <div class="filters">
      <input id="job-search" placeholder="Search by title, department or skills">
      <select id="job-type-filter">
        <option value="">All employment types</option>
        <option value="FULL_TIME">Full time</option>
        <option value="PART_TIME">Part time</option>
        <option value="CONTRACT">Contract</option>
        <option value="INTERNSHIP">Internship</option>
      </select>
    </div>
    <div class="jobs-grid" id="jobs-list"></div>`;

  const list = $("#jobs-list");

  function drawJobs() {
    const search = ($("#job-search")?.value || "").toLowerCase();
    const type = $("#job-type-filter")?.value || "";

    const filtered = jobs.filter((job) => {
      const text = [
        job.title,
        job.department,
        job.location,
        job.required_skills
      ].join(" ").toLowerCase();

      const active = isHR || String(job.status || "ACTIVE").toUpperCase() === "ACTIVE";

      return active && text.includes(search) &&
        (!type || String(job.employment_type || "").toUpperCase() === type);
    });

    if (!filtered.length) {
      list.innerHTML = `
        <div class="card empty-state">
          <h3>No jobs found</h3>
          <p>Try another search or check back later.</p>
        </div>`;
      return;
    }

    list.innerHTML = filtered.map((job) => `
      <article class="job-card">
        <div class="card-header">
          <div>
            <h3>${escapeHTML(job.title)}</h3>
            <div class="muted">${escapeHTML(job.department || "General")}</div>
          </div>
          ${statusBadge(job.status || "ACTIVE")}
        </div>
        <div class="job-meta">
          <span>${escapeHTML(job.location || "Location not specified")}</span>
          <span>${escapeHTML(formatStatus(job.employment_type))}</span>
          <span>${escapeHTML(job.vacancies ?? 1)} opening(s)</span>
        </div>
        <p class="job-description">${escapeHTML(job.description || "No description provided.")}</p>
        <p><strong>Required skills:</strong> ${escapeHTML(job.required_skills || "Not specified")}</p>
        <div class="job-footer">
          <span class="muted">
            ${job.salary_min != null ? escapeHTML(job.salary_min) : "Salary"} 
            ${job.salary_max != null ? " – " + escapeHTML(job.salary_max) : ""}
          </span>
          <div class="button-row">
            ${isHR
              ? `<button class="btn btn-secondary btn-sm" data-edit-job="${escapeHTML(job.id)}">Edit</button>
                 <button class="btn btn-danger btn-sm" data-delete-job="${escapeHTML(job.id)}">Delete</button>`
              : `<button class="btn btn-primary btn-sm" data-apply-job="${escapeHTML(job.id)}">Apply Now</button>`
            }
          </div>
        </div>
      </article>`).join("");
  }

  drawJobs();

  $("#job-search")?.addEventListener("input", drawJobs);
  $("#job-type-filter")?.addEventListener("change", drawJobs);

  $("#new-job-button")?.addEventListener("click", () => openJobForm());

  list.addEventListener("click", async (event) => {
    const edit = event.target.closest("[data-edit-job]");
    const remove = event.target.closest("[data-delete-job]");
    const apply = event.target.closest("[data-apply-job]");

    if (edit) {
      const job = jobs.find((item) => String(item.id) === edit.dataset.editJob);
      if (job) openJobForm(job);
    }

    if (remove) {
      await deleteJob(remove.dataset.deleteJob);
    }

    if (apply) {
      await applyForJob(apply.dataset.applyJob);
    }
  });
}

function openJobForm(job = {}) {
  const editing = job.id != null;

  const overlay = document.createElement("div");
  overlay.className = "modal-backdrop";

  overlay.innerHTML = `
    <div class="modal">
      <div class="card-header">
        <h2>${editing ? "Edit Job" : "Post a Job"}</h2>
        <button class="btn btn-secondary" id="close-job-modal">Close</button>
      </div>
      <form id="job-form">
        <div class="form-grid">
          <div class="form-group">
            <label for="job-title">Job title *</label>
            <input id="job-title" required value="${escapeHTML(job.title)}">
          </div>
          <div class="form-group">
            <label for="job-department">Department</label>
            <input id="job-department" value="${escapeHTML(job.department)}">
          </div>
          <div class="form-group">
            <label for="job-location">Location</label>
            <input id="job-location" value="${escapeHTML(job.location)}">
          </div>
          <div class="form-group">
            <label for="job-type">Employment type</label>
            <select id="job-type">
              ${["FULL_TIME", "PART_TIME", "CONTRACT", "INTERNSHIP"].map((type) =>
                `<option value="${type}" ${job.employment_type === type ? "selected" : ""}>${formatStatus(type)}</option>`
              ).join("")}
            </select>
          </div>
          <div class="form-group">
            <label for="job-exp-min">Minimum experience (years)</label>
            <input id="job-exp-min" type="number" min="0" value="${escapeHTML(job.experience_min ?? 0)}">
          </div>
          <div class="form-group">
            <label for="job-exp-max">Maximum experience (years)</label>
            <input id="job-exp-max" type="number" min="0" value="${escapeHTML(job.experience_max ?? 0)}">
          </div>
          <div class="form-group">
            <label for="job-salary-min">Minimum salary</label>
            <input id="job-salary-min" type="number" min="0" value="${escapeHTML(job.salary_min ?? "")}">
          </div>
          <div class="form-group">
            <label for="job-salary-max">Maximum salary</label>
            <input id="job-salary-max" type="number" min="0" value="${escapeHTML(job.salary_max ?? "")}">
          </div>
          <div class="form-group">
            <label for="job-vacancies">Vacancies</label>
            <input id="job-vacancies" type="number" min="1" value="${escapeHTML(job.vacancies ?? 1)}">
          </div>
          <div class="form-group">
            <label for="job-status">Status</label>
            <select id="job-status">
              <option value="DRAFT">Draft</option>
              <option value="ACTIVE" ${job.status === "ACTIVE" ? "selected" : ""}>Active</option>
              <option value="CLOSED" ${job.status === "CLOSED" ? "selected" : ""}>Closed</option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label for="job-skills">Required skills</label>
          <input id="job-skills" value="${escapeHTML(job.required_skills)}">
        </div>
        <div class="form-group">
          <label for="job-description">Description</label>
          <textarea id="job-description">${escapeHTML(job.description)}</textarea>
        </div>
        <div class="form-group">
          <label for="job-responsibilities">Responsibilities</label>
          <textarea id="job-responsibilities">${escapeHTML(job.responsibilities)}</textarea>
        </div>
        <div class="form-group">
          <label for="job-qualifications">Qualifications</label>
          <textarea id="job-qualifications">${escapeHTML(job.qualifications)}</textarea>
        </div>
        <div class="form-actions">
          <button type="button" class="btn btn-secondary" id="cancel-job">Cancel</button>
          <button type="submit" class="btn btn-primary">Save Job</button>
        </div>
      </form>
    </div>`;

  document.body.appendChild(overlay);

  const close = () => overlay.remove();

  $("#close-job-modal", overlay)?.addEventListener("click", close);
  $("#cancel-job", overlay)?.addEventListener("click", close);

  $("#job-form", overlay).addEventListener("submit", async (event) => {
    event.preventDefault();

    const optionalNumber = (id) => {
      const value = $(`#${id}`, overlay).value;
      return value === "" ? null : Number(value);
    };

    const payload = {
      title: $("#job-title", overlay).value.trim(),
      department: $("#job-department", overlay).value.trim() || null,
      location: $("#job-location", overlay).value.trim() || null,
      employment_type: $("#job-type", overlay).value,
      experience_min: optionalNumber("job-exp-min"),
      experience_max: optionalNumber("job-exp-max"),
      salary_min: optionalNumber("job-salary-min"),
      salary_max: optionalNumber("job-salary-max"),
      vacancies: Number($("#job-vacancies", overlay).value || 1),
      status: $("#job-status", overlay).value,
      required_skills: $("#job-skills", overlay).value.trim() || null,
      description: $("#job-description", overlay).value.trim() || null,
      responsibilities: $("#job-responsibilities", overlay).value.trim() || null,
      qualifications: $("#job-qualifications", overlay).value.trim() || null
    };

    try {
      if (editing) {
        await apiPut(`/jobs/${job.id}`, payload);
      } else {
        await apiPost("/jobs/", payload);
      }

      close();
      toast("Job saved successfully.", "success");
      await loadTab("jobs");
    } catch (error) {
      toast(error.message, "error");
    }
  });
}

async function deleteJob(id) {
  if (!confirm("Are you sure you want to delete this job?")) return;

  try {
    await apiDelete(`/jobs/${id}`);
    toast("Job deleted.", "success");
    await loadTab("jobs");
  } catch (error) {
    toast(error.message, "error");
  }
}

/* ---------- Applications ---------- */

async function renderApplications(container) {
  const isHR = getRole() === "HR";
  const path = isHR ? "/hr/applications/" : "/applications/";
  const applications = asArray(await apiGet(path));

  container.innerHTML = `
    ${pageHeader(
      isHR ? "All Applications" : "My Applications",
      isHR ? "Review applicants and update their status." : "Track the progress of your applications."
    )}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Job</th>
            ${isHR ? "<th>Candidate</th>" : ""}
            <th>Status</th>
            <th>Applied</th>
            ${isHR ? "<th>Update status</th>" : ""}
          </tr>
        </thead>
        <tbody>
          ${applications.length ? applications.map((app) => `
            <tr>
              <td>${escapeHTML(app.id)}</td>
              <td>${escapeHTML(app.job_title || app.job?.title || `Job #${app.job_id}`)}</td>
              ${isHR ? `<td>${escapeHTML(app.candidate_name || app.candidate?.full_name || app.candidate_id || "—")}</td>` : ""}
              <td>${statusBadge(app.status)}</td>
              <td>${escapeHTML(app.created_at ? new Date(app.created_at).toLocaleDateString() : "—")}</td>
              ${isHR ? `
                <td>
                  <select data-app-status="${escapeHTML(app.id)}">
                    ${["APPLIED","UNDER_REVIEW","SHORTLISTED","REJECTED","INTERVIEW_SCHEDULED","SELECTED","HIRED"].map((status) =>
                      `<option value="${status}" ${app.status === status ? "selected" : ""}>${formatStatus(status)}</option>`
                    ).join("")}
                  </select>
                  <button class="btn btn-primary btn-sm" data-save-status="${escapeHTML(app.id)}">Save</button>
                </td>` : ""}
            </tr>`).join("") : `
            <tr><td colspan="${isHR ? 6 : 4}">No applications found.</td></tr>`}
        </tbody>
      </table>
    </div>`;

  if (isHR) {
    container.querySelectorAll("[data-save-status]").forEach((button) => {
      button.addEventListener("click", async () => {
        const id = button.dataset.saveStatus;
        const select = container.querySelector(`[data-app-status="${id}"]`);

        try {
          await apiPatch(`/applications/${id}/status`, {
            status: select.value
          });
          toast("Application status updated.", "success");
          await loadTab("applications");
        } catch (error) {
          toast(error.message, "error");
        }
      });
    });
  }
}

async function applyForJob(jobId) {
  const coverLetter = prompt("Enter a short cover letter (optional):") || "";

  try {
    await apiPost("/applications/", {
      job_id: Number(jobId),
      cover_letter: coverLetter
    });

    toast("Application submitted successfully.", "success");
  } catch (error) {
    toast(error.message, "error");
  }
}

/* ---------- Candidate profile ---------- */

async function renderProfile(container) {
  if (getRole() !== "CANDIDATE") {
    container.innerHTML = `<div class="card">Candidate profiles are available only to candidate accounts.</div>`;
    return;
  }

  /*
    This assumes GET /dashboard/candidate returns a candidate_id.
    Verify the actual response shape in Swagger.
  */

  const dashboard = await apiGet("/dashboard/candidate");
  const candidateId = dashboard.candidate_id || dashboard.candidate?.id;

  if (!candidateId) {
    container.innerHTML = `
      <div class="card">
        <h2>Candidate profile not found</h2>
        <p>Create a candidate profile using your backend's candidate endpoint first.</p>
      </div>`;
    return;
  }

  const candidate = await apiGet(`/candidates/${candidateId}`);

  container.innerHTML = `
    ${pageHeader("My Profile", "Keep your information and skills up to date.")}
    <div class="card">
      <form id="profile-form">
        <div class="form-grid">
          <div class="form-group">
            <label for="profile-qualification">Qualification</label>
            <input id="profile-qualification" value="${escapeHTML(candidate.qualification)}">
          </div>
          <div class="form-group">
            <label for="profile-experience">Experience (years)</label>
            <input id="profile-experience" type="number" min="0" step="0.5" value="${escapeHTML(candidate.experience_years ?? 0)}">
          </div>
        </div>
        <div class="form-group">
          <label for="profile-skills">Skills</label>
          <textarea id="profile-skills">${escapeHTML(candidate.skills)}</textarea>
        </div>
        <button class="btn btn-primary" type="submit">Save Profile</button>
      </form>
    </div>
    <div class="card">
      <h3>Resume</h3>
      <p class="muted">Upload a PDF resume if your backend supports the resume endpoint.</p>
      <form id="resume-form">
        <div class="form-group">
          <label for="resume-file">Choose PDF resume</label>
          <input id="resume-file" type="file" accept=".pdf,application/pdf" required>
        </div>
        <button class="btn btn-primary" type="submit">Upload Resume</button>
      </form>
    </div>`;

  $("#profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    try {
      await apiPut(`/candidates/${candidateId}`, {
        qualification: $("#profile-qualification").value.trim(),
        experience_years: Number($("#profile-experience").value || 0),
        skills: $("#profile-skills").value.trim()
      });

      toast("Profile updated.", "success");
    } catch (error) {
      toast(error.message, "error");
    }
  });

  $("#resume-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    const file = $("#resume-file").files[0];

    if (!file) {
      toast("Choose a PDF file first.", "error");
      return;
    }

    if (file.type !== "application/pdf") {
      toast("Please upload a PDF file.", "error");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      await api("/resumes/upload", {
        method: "POST",
        body: formData
      });

      toast("Resume uploaded.", "success");
    } catch (error) {
      toast(error.message, "error");
    }
  });
}

/* ---------- HR candidate search ---------- */

async function renderCandidates(container) {
  if (getRole() !== "HR") {
    container.innerHTML = `<div class="card">This page is for HR users.</div>`;
    return;
  }

  const candidates = asArray(await apiGet("/hr/candidates/"));

  container.innerHTML = `
    ${pageHeader("Candidates", "Search candidate profiles and review skills.")}
    <div class="filters">
      <input id="candidate-search" placeholder="Search by name, qualification or skills">
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>ID</th><th>Name</th><th>Qualification</th><th>Experience</th><th>Skills</th></tr>
        </thead>
        <tbody id="candidate-table-body"></tbody>
      </table>
    </div>`;

  const tbody = $("#candidate-table-body");

  function draw() {
    const term = $("#candidate-search").value.toLowerCase();

    const filtered = candidates.filter((candidate) =>
      [
        candidate.full_name,
        candidate.name,
        candidate.qualification,
        candidate.skills
      ].join(" ").toLowerCase().includes(term)
    );

    tbody.innerHTML = filtered.length ? filtered.map((candidate) => `
      <tr>
        <td>${escapeHTML(candidate.id)}</td>
        <td>${escapeHTML(candidate.full_name || candidate.name || "—")}</td>
        <td>${escapeHTML(candidate.qualification || "—")}</td>
        <td>${escapeHTML(candidate.experience_years ?? 0)} years</td>
        <td>${escapeHTML(candidate.skills || "—")}</td>
      </tr>`).join("") : `<tr><td colspan="5">No candidates found.</td></tr>`;
  }

  $("#candidate-search").addEventListener("input", draw);
  draw();
}

/* ---------- Interviews ---------- */

async function renderInterviews(container) {
  const isHR = getRole() === "HR";
  const path = isHR ? "/interviews/" : "/interviews/my";
  const interviews = asArray(await apiGet(path));

  container.innerHTML = `
    ${pageHeader("Interviews", "Review scheduled interviews and their status.")}
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>ID</th><th>Application</th><th>Scheduled at</th><th>Mode</th><th>Status</th></tr>
        </thead>
        <tbody>
          ${interviews.length ? interviews.map((item) => `
            <tr>
              <td>${escapeHTML(item.id)}</td>
              <td>${escapeHTML(item.application_id ?? "—")}</td>
              <td>${escapeHTML(item.scheduled_at ? new Date(item.scheduled_at).toLocaleString() : "—")}</td>
              <td>${escapeHTML(item.mode || "—")}</td>
              <td>${statusBadge(item.status)}</td>
            </tr>`).join("") : `<tr><td colspan="5">No interviews found.</td></tr>`}
        </tbody>
      </table>
    </div>`;
}

/* ---------- Notifications ---------- */

async function renderNotifications(container) {
  const notifications = asArray(await apiGet("/notifications/"));

  container.innerHTML = `
    ${pageHeader("Notifications", "Updates about your recruitment activity.")}
    <div>
      ${notifications.length ? notifications.map((item) => `
        <article class="notification ${item.is_read ? "" : "unread"}">
          <h3>${escapeHTML(item.title || "Notification")}</h3>
          <p>${escapeHTML(item.message || item.body || "")}</p>
          <small>${escapeHTML(item.created_at ? new Date(item.created_at).toLocaleString() : "")}</small>
          ${!item.is_read ? `<div style="margin-top:10px">
            <button class="btn btn-secondary btn-sm" data-read-notification="${escapeHTML(item.id)}">Mark as read</button>
          </div>` : ""}
        </article>`).join("") : `
        <div class="card empty-state">
          <h3>No notifications</h3>
          <p>You're all caught up.</p>
        </div>`}
    </div>`;

  container.querySelectorAll("[data-read-notification]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await apiPatch(`/notifications/${button.dataset.readNotification}/read`, {});
        toast("Notification marked as read.", "success");
        await loadTab("notifications");
      } catch (error) {
        toast(error.message, "error");
      }
    });
  });
}

/* ---------- Startup ---------- */

document.addEventListener("DOMContentLoaded", () => {
  $("#login-form")?.addEventListener("submit", login);
  $("#register-form")?.addEventListener("submit", register);

  $("#logout-button")?.addEventListener("click", logout);

  $("#show-login")?.addEventListener("click", () => showAuthMode("login"));
  $("#show-register")?.addEventListener("click", () => showAuthMode("register"));

  document.addEventListener("click", (event) => {
    const tabButton = event.target.closest("[data-tab]");

    if (tabButton) {
      event.preventDefault();
      loadTab(tabButton.dataset.tab);
    }
  });

  if (getToken() && getRole()) {
    showApplication();
    loadTab("overview");
  } else {
    showAuthMode("login");
  }
});