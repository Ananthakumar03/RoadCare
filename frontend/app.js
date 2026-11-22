const $ = (id) => document.getElementById(id);
let me = null;
let charts = [];

const API_BASE_URL = "http://127.0.0.1:5001";

async function api(url, options = {}) {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    credentials: "include",
    ...options
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.error || "Something went wrong.");
  }

  return data;
}
function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2800);
}
function showPage(name) {

    const pages = document.querySelectorAll(".page");

    // Hide all pages
    pages.forEach(page => {
        page.classList.remove("active");
    });

    // Show selected page
    const selectedPage = $(name + "-page");

    if (!selectedPage) {
        console.error("Page not found:", name);
        return;
    }

    selectedPage.classList.add("active");

    // Update navigation buttons
    document.querySelectorAll(".nav-link").forEach(button => {
        button.classList.toggle(
            "active",
            button.dataset.page === name
        );
    });

    // Refresh selected portal
    if (name === "citizen") {
        refreshCitizenView();
    }

    if (name === "admin") {
        refreshAdminView();
    }

    if (name === "analytics") {
        refreshAnalyticsView();
    }

    // Load heatmap when its page is opened
    if (name === "heatmap") {
        loadRoadImpactHeatmap();
    }
}
document.querySelectorAll("[data-page]").forEach(b => b.addEventListener("click", () => showPage(b.dataset.page)));
document.querySelectorAll("[data-go]").forEach(b => b.addEventListener("click", () => showPage(b.dataset.go)));

function updateUserArea() {
  $("user-area").innerHTML = me
    ? `<span>${escapeHtml(me.name)} · ${escapeHtml(me.role)}</span> <button class="btn small secondary" id="logout-btn">Logout</button>`
    : `<span class="muted">Not logged in</span>`;
  const logout = $("logout-btn");
  if (logout) logout.addEventListener("click", async () => {
    await api("/api/logout", { method: "POST" });
    me = null; updateUserArea(); refreshCitizenView(); refreshAdminView(); refreshAnalyticsView();
    toast("Logged out successfully.");
  });
}
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[ch]));
}
async function loadMe() {
  try { me = (await api("/api/me")).user; } catch { me = null; }
  updateUserArea();
  refreshCitizenView(); refreshAdminView(); refreshAnalyticsView();
}


function refreshCitizenView() {
    const loggedIn = me && me.role === "citizen";

    // Hide login and registration after login
    $("auth-panel").classList.toggle("hidden", !!loggedIn);

    // Show complaint workspace after login
    $("citizen-workspace").classList.toggle("hidden", !loggedIn);

    if (loggedIn) {
        loadMyComplaints();
        applySelectedRoadProblem();
    }
}


function refreshAdminView() {
  const isAdmin = me && me.role === "admin";
  $("admin-login-panel").classList.toggle("hidden", !!isAdmin);
  $("admin-workspace").classList.toggle("hidden", !isAdmin);
  if (isAdmin) loadAdminData();
}
function refreshAnalyticsView() {
  const isAdmin = me && me.role === "admin";
  $("analytics-locked").classList.toggle("hidden", !!isAdmin);
  $("analytics-workspace").classList.toggle("hidden", !isAdmin);
  if (isAdmin) loadAnalytics();
}
$("register-form").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    const data = await api("/api/register", { method:"POST", body:new FormData(e.target) });
    me = data.user; updateUserArea(); e.target.reset(); refreshCitizenView(); toast(data.message);
  } catch (err) { toast(err.message); }
});
$("citizen-login-form").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    const data = await api("/api/login", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(Object.fromEntries(new FormData(e.target))) });
    me = data.user; updateUserArea(); e.target.reset(); refreshCitizenView(); toast(data.message);
  } catch (err) { toast(err.message); }
});
$("admin-login-form").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    const data = await api("/api/login", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(Object.fromEntries(new FormData(e.target))) });
    if (data.user.role !== "admin") { await api("/api/logout", {method:"POST"}); throw new Error("This account is not an administrator."); }
    me = data.user; updateUserArea(); e.target.reset(); refreshAdminView(); refreshAnalyticsView(); toast("Administrator login successful.");
  } catch (err) { toast(err.message); }
});
$("complaint-form").addEventListener("submit", async e => {
  e.preventDefault();
  const msg = $("complaint-message"); msg.textContent = ""; msg.className = "message";
  try {
    const data = await api("/api/complaints", {method:"POST", body:new FormData(e.target)});
    msg.textContent = data.message + " Complaint ID: RC-" + data.complaint_id;
    msg.classList.add("success"); e.target.reset(); loadMyComplaints();
  } catch (err) { msg.textContent = err.message; msg.classList.add("error"); }
});
async function loadMyComplaints() {
  try {
    const data = await api("/api/complaints");
    $("my-complaints").innerHTML = data.complaints.length ? data.complaints.map(c => `
      <article class="complaint-item"><h3>RC-${c.id} · ${escapeHtml(c.title)}</h3>
      <p>${escapeHtml(c.road_name)} · ${escapeHtml(c.area)} · ${escapeHtml(c.damage_type)}</p>
      <span class="status">${escapeHtml(c.status)}</span>
      ${c.admin_note ? `<p>Admin note: ${escapeHtml(c.admin_note)}</p>` : ""}
      ${c.photo_url ? `<p><a href="${c.photo_url}" target="_blank" rel="noopener">View uploaded photo</a></p>` : ""}
      </article>`).join("") : `<div class="empty-state">You have not submitted any complaints yet.</div>`;
  } catch (err) { $("my-complaints").textContent = err.message; }
}
$("refresh-citizen").addEventListener("click", loadMyComplaints);
async function loadAdminData() {
  try {
    const [complaints, analytics] = await Promise.all([api("/api/complaints"), api("/api/analytics")]);
    $("admin-total").textContent = analytics.total;
    $("admin-pending").textContent = analytics.pending;
    $("admin-resolved").textContent = analytics.resolved;
    $("admin-table").innerHTML = complaints.complaints.length ? complaints.complaints.map(c => `
      <tr><td>RC-${c.id}</td><td><b>${escapeHtml(c.title)}</b><br><span class="muted">${escapeHtml(c.road_name)}</span>${c.photo_url ? `<br><a href="${c.photo_url}" target="_blank" rel="noopener">Photo</a>` : ""}</td>
      <td>${escapeHtml(c.area)}</td><td>${c.severity}/5</td><td>${escapeHtml(c.citizen_name || "")}</td>
      <td><span class="status">${escapeHtml(c.status)}</span></td>
      <td><select id="status-${c.id}">${["Submitted","Verified","Repair in Progress","Resolved","Rejected"].map(s => `<option ${s===c.status?"selected":""}>${s}</option>`).join("")}</select>
      <input id="note-${c.id}" placeholder="Admin note" value="${escapeHtml(c.admin_note || "")}">
      <button class="update-btn" data-update="${c.id}">Save</button></td></tr>`).join("") : `<tr><td colspan="7" class="empty-state">No citizen complaints have been submitted yet.</td></tr>`;
    document.querySelectorAll("[data-update]").forEach(btn => btn.addEventListener("click", () => updateComplaint(btn.dataset.update)));
  } catch (err) { toast(err.message); }
}
async function updateComplaint(id) {
  try {
    await api(`/api/complaints/${id}`, {method:"PATCH", headers:{"Content-Type":"application/json"}, body:JSON.stringify({
      status:$(`status-${id}`).value, admin_note:$(`note-${id}`).value
    })});
    toast("Complaint updated."); loadAdminData(); loadAnalytics();
  } catch (err) { toast(err.message); }
}
$("refresh-admin").addEventListener("click", loadAdminData);
function drawChart(id, type, labels, values, label) {
  const canvas = $(id);
  const existing = Chart.getChart(canvas);
  if (existing) existing.destroy();
  new Chart(canvas, {
    type, data:{labels, datasets:[{label, data:values, borderWidth:2, borderRadius: type==="bar" ? 6 : 0, tension:.3}]},
    options:{responsive:true, maintainAspectRatio:false, plugins:{legend:{display:type==="doughnut"}}}
  });
}
async function loadAnalytics() {
  try {
    const data = await api("/api/analytics");
    $("analytics-total").textContent = data.total;
    $("analytics-pending").textContent = data.pending;
    $("analytics-resolved").textContent = data.resolved;
    drawChart("area-chart","bar",data.by_area.map(x=>x.label),data.by_area.map(x=>x.value),"Complaints");
    drawChart("severity-chart","doughnut",data.by_severity.map(x=>x.label),data.by_severity.map(x=>x.value),"Complaints");
    drawChart("month-chart","line",data.by_month.map(x=>x.label),data.by_month.map(x=>x.value),"Complaints");
    $("priority-table").innerHTML = data.priorities.length ? data.priorities.map(p => `
      <tr><td>${escapeHtml(p.title)} (RC-${p.id})</td><td>${escapeHtml(p.area)}</td><td><b>${p.score}/100</b></td>
      <td><span class="status">${p.level}</span></td><td>${escapeHtml(p.status)}</td></tr>`).join("") : `<tr><td colspan="5" class="empty-state">Submit sample complaints to see analytics and priority recommendations.</td></tr>`;
  } catch (err) { toast(err.message); }
}
$("refresh-admin").addEventListener("click", loadAnalytics);
loadMe();

// ---------------------------------
// CURRENT GPS LOCATION + AUTO ADDRESS
// ---------------------------------

const locationButton = $("get-location-btn");
const locationMessage = $("location-message");
const latitudeInput = $("latitude");
const longitudeInput = $("longitude");
const roadNameInput = $("road-name");
const areaInput = $("area");

if (locationButton) {
    locationButton.addEventListener("click", function () {

        if (!navigator.geolocation) {
            locationMessage.textContent =
                "Your browser does not support GPS location.";
            return;
        }

        locationButton.disabled = true;
        locationButton.textContent = "Getting location...";
        locationMessage.textContent =
            "Please allow location permission.";

        navigator.geolocation.getCurrentPosition(

            async function (position) {

                const latitude = position.coords.latitude;
                const longitude = position.coords.longitude;

                // Fill GPS coordinates
                latitudeInput.value = latitude;
                longitudeInput.value = longitude;

                locationMessage.textContent =
                    "GPS captured. Finding your address...";

                try {

                    // Convert GPS coordinates into address
                   const url =
    `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${latitude}&lon=${longitude}&zoom=18&addressdetails=1&accept-language=en`;

                    const response = await fetch(url);

                    if (!response.ok) {
                        throw new Error("Address lookup failed.");
                    }

                    const data = await response.json();
                    const address = data.address || {};

                    // Find area / locality
                    const area =
                        address.suburb ||
                        address.neighbourhood ||
                        address.residential ||
                        address.village ||
                        address.town ||
                        address.city_district ||
                        address.city ||
                        address.county ||
                        "";

                    // Find road name
                    const road =
                        address.road ||
                        address.pedestrian ||
                        address.footway ||
                        address.residential ||
                        "";

                    // Find nearby landmark, if available
                    const landmark =
                        address.amenity ||
                        address.building ||
                        address.shop ||
                        address.tourism ||
                        address.leisure ||
                        address.historic ||
                        "";

                    // Fill Road name / landmark
                    if (roadNameInput) {
                        if (road && landmark) {
                            roadNameInput.value =
                                road + " near " + landmark;
                        } else if (road) {
                            roadNameInput.value = road;
                        } else if (landmark) {
                            roadNameInput.value = landmark;
                        } else {
                            roadNameInput.value =
                                data.name || data.display_name || "";
                        }
                    }

                    // Fill Area / locality
                    if (areaInput) {
                        areaInput.value = area;
                    }

                    if (area || road || landmark) {
                        locationMessage.textContent =
                            "GPS and address details filled successfully!";
                    } else {
                        locationMessage.textContent =
                            "GPS captured, but address details were not available. Please enter them manually.";
                    }

                } catch (error) {

                    locationMessage.textContent =
                        "GPS captured, but address lookup failed. Please enter area and landmark manually.";

                }

                locationButton.textContent =
                    "📍 Location Captured";

                locationButton.disabled = false;

                console.log("Latitude:", latitude);
                console.log("Longitude:", longitude);
                console.log("GPS accuracy:", position.coords.accuracy, "meters");
            },

            function (error) {

                let message = "Unable to get your location.";

                if (error.code === 1) {
                    message =
                        "Location permission denied. Allow location access.";
                } else if (error.code === 2) {
                    message =
                        "Location unavailable. Please try again.";
                } else if (error.code === 3) {
                    message =
                        "Location request timed out. Please try again.";
                }

                locationMessage.textContent = message;
                locationButton.textContent =
                    "📍 Use My Current Location";
                locationButton.disabled = false;
            },

            {
                enableHighAccuracy: true,
                timeout: 20000,
                maximumAge: 0
            }
        );
    });
}

// ---------------------------------
// ROAD PROBLEM IMAGE CLICK
// ---------------------------------

let selectedRoadProblem = "";

function applySelectedRoadProblem() {
    if (!selectedRoadProblem) return;

    const damageDropdown = $("damage-type");

    if (damageDropdown) {
        damageDropdown.value = selectedRoadProblem;
    }

    const complaintForm = $("complaint-form");

    if (complaintForm) {
        complaintForm.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }
}

document.querySelectorAll("[data-damage-type]").forEach(card => {

    card.addEventListener("click", function () {

        selectedRoadProblem = this.dataset.damageType;

        showPage("citizen");

        if (me && me.role === "citizen") {
            applySelectedRoadProblem();
        }

    });

});

// ---------------------------------
// CITIZEN LOGIN / REGISTER PAGE SWITCH
// ---------------------------------

const showRegisterBtn = document.getElementById("show-register-btn");
const showLoginBtn = document.getElementById("show-login-btn");

const citizenLoginPanel = document.getElementById("citizen-login-panel");
const citizenRegisterPanel = document.getElementById("citizen-register-panel");

if (showRegisterBtn) {
    showRegisterBtn.addEventListener("click", function () {
        citizenLoginPanel.classList.add("hidden");
        citizenRegisterPanel.classList.remove("hidden");
    });
}

if (showLoginBtn) {
    showLoginBtn.addEventListener("click", function () {
        citizenRegisterPanel.classList.add("hidden");
        citizenLoginPanel.classList.remove("hidden");
    });
}
// ---------------------------------
// SHOW / HIDE PASSWORD
// ---------------------------------

document.querySelectorAll(".toggle-password").forEach(button => {

    button.addEventListener("click", function () {

        const passwordInput = this.parentElement.querySelector(".password-input");

        if (passwordInput.type === "password") {
            passwordInput.type = "text";
            this.textContent = "🙈";
            this.setAttribute("aria-label", "Hide password");
        } else {
            passwordInput.type = "password";
            this.textContent = "👁";
            this.setAttribute("aria-label", "Show password");
        }

    });

});
function clearRoadCareLoginFields() {

    // Citizen email and password clear
    const citizenForm = document.getElementById("citizen-login-form");

    if (citizenForm) {
        citizenForm.querySelectorAll("input").forEach(input => {
            input.value = "";
        });
    }

    // Admin password clear; email remains unchanged
    const adminPassword = document.querySelector(
        '#admin-login-form input[name="password"]'
    );

    if (adminPassword) {
        adminPassword.value = "";
    }
}

window.addEventListener("load", clearRoadCareLoginFields);
window.addEventListener("pageshow", clearRoadCareLoginFields);
// ---------------------------------
// ROAD IMPACT HEATMAP
// ---------------------------------

let roadImpactMap = null;
let heatmapLayer = null;
let heatmapLoaded = false;

async function loadRoadImpactHeatmap() {

    const mapContainer = $("roadHeatmap");

    if (!mapContainer || typeof L === "undefined") {
        console.error("Map container or Leaflet library not found.");
        return;
    }

    // Create map only once
    if (!roadImpactMap) {

        roadImpactMap = L.map("roadHeatmap").setView(
            [11.3410, 77.7172],
            11
        );

        L.tileLayer(
            "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            {
                attribution: "&copy; OpenStreetMap contributors"
            }
        ).addTo(roadImpactMap);

        heatmapLayer = L.layerGroup().addTo(roadImpactMap);
    }

    // Fix map display when page becomes visible
    setTimeout(() => {
        roadImpactMap.invalidateSize();
    }, 200);

    // Avoid loading duplicate markers
    if (heatmapLoaded) return;

    try {

        const response = await fetch(
            `${API_BASE_URL}/api/road-impact-heatmap`,
            {
                credentials: "include"
            }
        );

        if (!response.ok) {
            throw new Error("API error: " + response.status);
        }

        const data = await response.json();

        $("heatmapLocations").textContent =
            data.total_locations;

        $("heatmapComplaints").textContent =
            data.total_mapped_complaints;

        const highImpact = data.heatmap.filter(
            item => item.impact_level === "High"
        ).length;

        $("heatmapHighImpact").textContent = highImpact;

        data.heatmap.forEach(item => {

            const color =
                item.impact_level === "High" ? "red" :
                item.impact_level === "Medium" ? "orange" :
                "green";

            L.circleMarker(
                [item.latitude, item.longitude],
                {
                    radius: 10,
                    color: color,
                    fillColor: color,
                    fillOpacity: 0.7
                }
            )
            .addTo(heatmapLayer)
            .bindPopup(`
                <b>${escapeHtml(item.area)}</b><br>
                Impact: ${escapeHtml(item.impact_level)}<br>
                Score: ${item.impact_score}<br>
                Complaints: ${item.complaint_count}<br>
                Accidents: ${item.total_accidents}
            `);
        });

        if (data.heatmap.length > 0) {

            const bounds = data.heatmap.map(item => [
                item.latitude,
                item.longitude
            ]);

            roadImpactMap.fitBounds(
                bounds,
                { padding: [30, 30] }
            );
        }

        heatmapLoaded = true;

    } catch (error) {

        console.error("Heatmap loading failed:", error);

        mapContainer.textContent =
            "Unable to load heatmap. Please check admin login and API.";
    }
}