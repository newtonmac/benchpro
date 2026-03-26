/* ═══════════════════════════════════════════════════════════════
   BenchPro Dashboard — fully online, runs via GitHub Actions
   ═══════════════════════════════════════════════════════════════ */

const OUR_DOMAIN = "benchdepot.com";
const KEYWORDS = ["workbench", "work bench", "workbenches", "work benches"];
const GH_OWNER = "newtonmac";
const GH_REPO = "benchpro";
const GH_WORKFLOW = "collect.yml";

let allRuns = [];
let currentKeyword = null;
let posChart = null;
let heatChart = null;
let pollTimer = null;

/* ═══════════════════════════════════════════════════════════════
   AUTH — simple password gate
   ═══════════════════════════════════════════════════════════════ */

async function sha256(text) {
    const data = new TextEncoder().encode(text);
    const buf = await crypto.subtle.digest("SHA-256", data);
    return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join("");
}

async function attemptLogin() {
    const input = document.getElementById("pw-input");
    const errEl = document.getElementById("pw-error");
    const pw = input.value.trim();
    if (!pw) return;

    const hash = await sha256(pw);
    try {
        const res = await fetch("data/auth.json");
        const auth = await res.json();
        if (hash === auth.hash) {
            sessionStorage.setItem("bp_auth", hash);
            showDashboard();
        } else {
            errEl.classList.remove("hidden");
            input.value = "";
            input.focus();
        }
    } catch {
        sessionStorage.setItem("bp_auth", hash);
        showDashboard();
    }
}

function logout() {
    sessionStorage.removeItem("bp_auth");
    document.getElementById("dashboard").classList.add("hidden");
    document.getElementById("login-screen").classList.remove("hidden");
    document.getElementById("pw-input").value = "";
    document.getElementById("pw-error").classList.add("hidden");
}

async function checkAuth() {
    const saved = sessionStorage.getItem("bp_auth");
    if (!saved) return false;
    try {
        const res = await fetch("data/auth.json");
        const auth = await res.json();
        return saved === auth.hash;
    } catch { return true; }
}

async function showDashboard() {
    document.getElementById("login-screen").classList.add("hidden");
    document.getElementById("dashboard").classList.remove("hidden");
    buildTabs();
    updateTokenStatus();
    await loadData();
}

/* ═══════════════════════════════════════════════════════════════
   GITHUB TOKEN — stored in localStorage (persists across sessions)
   ═══════════════════════════════════════════════════════════════ */

function getToken() {
    return localStorage.getItem("bp_gh_token") || "";
}

function openTokenModal() {
    document.getElementById("token-modal").classList.remove("hidden");
    document.getElementById("token-input").value = getToken();
    document.getElementById("token-error").classList.add("hidden");
    document.getElementById("token-input").focus();
}

function closeTokenModal() {
    document.getElementById("token-modal").classList.add("hidden");
}

function saveToken() {
    const input = document.getElementById("token-input");
    const errEl = document.getElementById("token-error");
    const val = input.value.trim();

    if (val && !val.startsWith("ghp_") && !val.startsWith("github_pat_")) {
        errEl.classList.remove("hidden");
        return;
    }

    localStorage.setItem("bp_gh_token", val);
    errEl.classList.add("hidden");
    closeTokenModal();
    updateTokenStatus();
}

function updateTokenStatus() {
    const el = document.getElementById("token-status");
    const token = getToken();
    if (token) {
        el.textContent = "✓ GitHub token connected";
        el.className = "token-status connected";
    } else {
        el.textContent = "No GitHub token — click to set up";
        el.className = "token-status";
    }
}

/* ═══════════════════════════════════════════════════════════════
   TRIGGER GITHUB ACTIONS — "Run Now" button
   ═══════════════════════════════════════════════════════════════ */

async function triggerRun() {
    const token = getToken();
    if (!token) {
        openTokenModal();
        return;
    }

    const btn = document.getElementById("btn-run");
    const statusBar = document.getElementById("run-status");
    const statusText = document.getElementById("run-status-text");
    const statusTime = document.getElementById("run-status-time");

    // Disable button + show running state
    btn.disabled = true;
    btn.classList.add("running");
    document.getElementById("run-icon").textContent = "⟳";
    document.getElementById("run-label").textContent = "Running...";

    statusBar.classList.remove("hidden", "done", "error");
    statusText.textContent = "Triggering GitHub Actions workflow...";
    statusTime.textContent = "0s";
    const startTime = Date.now();
    const tickTimer = setInterval(() => {
        statusTime.textContent = Math.floor((Date.now() - startTime) / 1000) + "s";
    }, 1000);

    try {
        // Step 1: Trigger the workflow
        const triggerRes = await fetch(
            `https://api.github.com/repos/${GH_OWNER}/${GH_REPO}/actions/workflows/${GH_WORKFLOW}/dispatches`,
            {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`,
                    Accept: "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                body: JSON.stringify({ ref: "main" }),
            }
        );

        if (!triggerRes.ok) {
            const errBody = await triggerRes.text();
            if (triggerRes.status === 401 || triggerRes.status === 403) {
                throw new Error("Token is invalid or missing Actions permission. Click ⚙ below to update.");
            }
            if (triggerRes.status === 404) {
                throw new Error("Workflow not found. Make sure .github/workflows/collect.yml is pushed to main.");
            }
            throw new Error(`GitHub API error ${triggerRes.status}: ${errBody}`);
        }

        statusText.textContent = "Workflow triggered — searching Google for your keywords...";

        // Step 2: Poll for the workflow run to appear then complete
        await pollWorkflow(token, statusText, startTime);

        // Step 3: Done! Reload data
        clearInterval(tickTimer);
        statusTime.textContent = Math.floor((Date.now() - startTime) / 1000) + "s";
        statusBar.classList.add("done");
        statusText.textContent = "✓ Search complete — fresh data loaded!";
        await loadData();

        // Auto-hide success bar after 10s
        setTimeout(() => { statusBar.classList.add("hidden"); }, 10000);

    } catch (err) {
        clearInterval(tickTimer);
        statusBar.classList.add("error");
        statusText.textContent = "✗ " + err.message;
    } finally {
        btn.disabled = false;
        btn.classList.remove("running");
        document.getElementById("run-icon").textContent = "▶";
        document.getElementById("run-label").textContent = "Run now";
    }
}

async function pollWorkflow(token, statusEl, startTime) {
    // Wait a moment for the run to register
    await sleep(3000);

    const headers = {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    };

    // Find the most recent run triggered after our start time
    const maxPoll = 60; // max ~5 minutes
    for (let i = 0; i < maxPoll; i++) {
        try {
            const res = await fetch(
                `https://api.github.com/repos/${GH_OWNER}/${GH_REPO}/actions/workflows/${GH_WORKFLOW}/runs?per_page=3`,
                { headers }
            );
            const data = await res.json();
            const runs = data.workflow_runs || [];

            // Find a run that started around when we triggered
            const recentRun = runs.find(r => {
                const created = new Date(r.created_at).getTime();
                return created >= startTime - 10000; // within 10s
            });

            if (recentRun) {
                const status = recentRun.status;
                const conclusion = recentRun.conclusion;

                if (status === "completed") {
                    if (conclusion === "success") {
                        // Wait a beat for GitHub Pages to update
                        await sleep(5000);
                        return;
                    } else {
                        throw new Error(`Workflow finished with status: ${conclusion}. Check Actions tab for details.`);
                    }
                }

                // Still running — update status text
                const steps = {
                    queued: "Waiting for a runner...",
                    in_progress: "Running — scraping Google results...",
                };
                statusEl.textContent = steps[status] || `Status: ${status}...`;
            }
        } catch (err) {
            if (err.message.includes("Workflow finished")) throw err;
            // Ignore transient fetch errors, keep polling
        }

        await sleep(5000);
    }

    throw new Error("Timed out waiting for workflow to finish. Check the Actions tab on GitHub.");
}

function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}

/* ═══════════════════════════════════════════════════════════════
   DATA LOADING — reads the static JSON from GitHub Pages
   ═══════════════════════════════════════════════════════════════ */

async function loadData() {
    try {
        const res = await fetch("data/results.json?t=" + Date.now());
        const data = await res.json();
        allRuns = data.runs || [];
    } catch { allRuns = []; }
    renderAll();
}

/* ═══════════════════════════════════════════════════════════════
   TABS
   ═══════════════════════════════════════════════════════════════ */

function buildTabs() {
    const c = document.getElementById("keyword-tabs");
    let h = "";
    KEYWORDS.forEach((kw, i) => {
        h += `<button class="tab ${i === 0 ? "active" : ""}" data-kw="${kw}" onclick="selectKW('${kw}', this)">${kw}</button>`;
    });
    h += `<button class="tab" data-kw="all" onclick="selectKW(null, this)">All</button>`;
    c.innerHTML = h;
    currentKeyword = KEYWORDS[0];
}

function selectKW(kw, btn) {
    currentKeyword = kw;
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    if (btn) btn.classList.add("active");
    renderResults();
}

/* ═══════════════════════════════════════════════════════════════
   HELPERS
   ═══════════════════════════════════════════════════════════════ */

function getDays() { return parseInt(document.getElementById("days-select").value); }
function cutoffDate(d) { return new Date(Date.now() - d * 86400000); }
function isOurs(d) { return (d || "").includes(OUR_DOMAIN); }

function timeAgo(iso) {
    if (!iso) return "—";
    const ms = Date.now() - new Date(iso).getTime();
    const m = Math.floor(ms / 60000);
    if (m < 1) return "just now";
    if (m < 60) return m + "m ago";
    const h = Math.floor(m / 60);
    if (h < 24) return h + "h ago";
    return Math.floor(h / 24) + "d ago";
}

function latestPerKW() {
    const latest = {};
    for (const r of allRuns) {
        if (!latest[r.keyword] || r.timestamp > latest[r.keyword].timestamp) latest[r.keyword] = r;
    }
    return Object.values(latest);
}

/* ═══════════════════════════════════════════════════════════════
   RENDER ALL
   ═══════════════════════════════════════════════════════════════ */

function renderAll() {
    renderStats();
    renderResults();
    renderCompetitors();
    renderPositionChart();
    renderHeatmap();
}

/* ── Status Cards + Alert ──────────────────────────────────── */

function renderStats() {
    const latest = latestPerKW();
    const cards = document.getElementById("status-cards");
    const banner = document.getElementById("alert-banner");
    const alertText = document.getElementById("alert-text");

    const lastTime = allRuns.length ? allRuns[allRuns.length - 1].timestamp : null;
    document.getElementById("last-updated").textContent =
        lastTime ? "Last: " + timeAgo(lastTime) : "No data";

    const ourPos = {};
    for (const run of latest) {
        for (const s of run.sponsored || []) {
            if (isOurs(s.domain)) ourPos[run.keyword] = s.position;
        }
    }

    let html = `
        <div class="status-card">
            <div class="label">Total data points</div>
            <div class="value">${allRuns.length}</div>
            <div class="detail">${KEYWORDS.length} keywords tracked</div>
        </div>`;

    for (const kw of KEYWORDS) {
        const pos = ourPos[kw];
        let cls = "bad", display = "—", detail = "Not found";
        if (pos !== undefined) {
            display = "#" + pos;
            cls = pos <= 3 ? "good" : pos <= 5 ? "warn" : "bad";
            detail = pos <= 3 ? "✓ Top 3" : "Below top 3";
        }
        html += `
            <div class="status-card">
                <div class="label">"${kw}" sponsored</div>
                <div class="value ${cls}">${display}</div>
                <div class="detail">${detail}</div>
            </div>`;
    }
    cards.innerHTML = html;

    if (!allRuns.length) { banner.classList.add("hidden"); return; }
    const posEntries = Object.entries(ourPos);
    const inTop3 = posEntries.filter(([, p]) => p <= 3);
    banner.classList.remove("hidden");

    if (posEntries.length === 0) {
        banner.classList.remove("good");
        alertText.textContent = `${OUR_DOMAIN} is NOT appearing in any sponsored results. Increase bids.`;
    } else if (inTop3.length === KEYWORDS.length) {
        banner.classList.add("good");
        alertText.textContent = `✓ ${OUR_DOMAIN} is in the top 3 sponsored spots for ALL keywords.`;
    } else {
        banner.classList.remove("good");
        const missing = KEYWORDS.filter(kw => !ourPos[kw] || ourPos[kw] > 3);
        alertText.textContent = `${OUR_DOMAIN} NOT in top 3 for: ${missing.map(k => '"' + k + '"').join(", ")}. Consider increasing bids.`;
    }
}

/* ── Results List ──────────────────────────────────────────── */

function renderResults() {
    const latest = latestPerKW();
    const spEl = document.getElementById("sponsored-list");
    const orgEl = document.getElementById("organic-list");

    const filtered = currentKeyword ? latest.filter(r => r.keyword === currentKeyword) : latest;

    if (!filtered.length) {
        spEl.innerHTML = '<div class="empty-state">No data — click "Run now"</div>';
        orgEl.innerHTML = '<div class="empty-state">No data</div>';
        return;
    }

    let allSp = [], allOrg = [];
    for (const run of filtered) {
        const label = filtered.length > 1 ? run.keyword : null;
        (run.sponsored || []).forEach(s => allSp.push({ ...s, _kw: label }));
        (run.organic || []).forEach(o => allOrg.push({ ...o, _kw: label }));
    }

    spEl.innerHTML = allSp.length ? allSp.map(rowHTML).join("") : '<div class="empty-state">No sponsored results found</div>';
    orgEl.innerHTML = allOrg.length ? allOrg.map(rowHTML).join("") : '<div class="empty-state">No organic results found</div>';
}

function rowHTML(item) {
    const ours = isOurs(item.domain);
    const kw = item._kw ? `<span class="kw-tag">${item._kw}</span>` : "";
    const tag = ours ? '<span class="tag-ours">★ US</span>' : "";
    return `
        <div class="result-row ${ours ? "is-ours" : ""}">
            <div class="pos-badge">${item.position}</div>
            <div class="result-info">
                <div class="result-domain">${item.domain || "unknown"} ${kw}</div>
                <div class="result-title">${item.title || ""}</div>
            </div>
            ${tag}
        </div>`;
}

/* ── Competitor Table ──────────────────────────────────────── */

function renderCompetitors() {
    const days = getDays();
    const cutoff = cutoffDate(days).toISOString();
    const tbody = document.getElementById("competitor-tbody");

    const stats = {};
    for (const run of allRuns) {
        if (run.timestamp < cutoff) continue;
        for (const s of run.sponsored || []) {
            const d = s.domain;
            if (!d) continue;
            if (!stats[d]) stats[d] = { count: 0, posSum: 0, keywords: new Set() };
            stats[d].count++;
            stats[d].posSum += s.position;
            stats[d].keywords.add(run.keyword);
        }
    }

    const sorted = Object.entries(stats)
        .map(([domain, s]) => ({ domain, count: s.count, avg: s.posSum / s.count, keywords: [...s.keywords] }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 15);

    if (!sorted.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No data yet</td></tr>';
        return;
    }

    const maxC = sorted[0].count;
    tbody.innerHTML = sorted.map(r => {
        const ours = isOurs(r.domain);
        const barW = Math.round((r.count / maxC) * 80);
        return `<tr>
            <td class="domain-cell ${ours ? "is-ours" : ""}">${r.domain}${ours ? " ★" : ""}</td>
            <td><div class="bar-cell"><div class="bar-fill" style="width:${barW}px"></div><span class="bar-value">${r.count}</span></div></td>
            <td style="font-family:var(--font-mono);font-size:12px;color:${r.avg <= 3 ? "var(--accent)" : "var(--text-muted)"}">${r.avg.toFixed(1)}</td>
            <td><div class="kw-tags">${r.keywords.map(k => '<span class="kw-tag">' + k + '</span>').join("")}</div></td>
        </tr>`;
    }).join("");
}

/* ── Position Chart ────────────────────────────────────────── */

function renderPositionChart() {
    const days = getDays();
    const cutoff = cutoffDate(days).toISOString();
    const ctx = document.getElementById("position-chart").getContext("2d");

    const spByKw = {}, orgByKw = {};
    for (const run of allRuns) {
        if (run.timestamp < cutoff) continue;
        for (const s of run.sponsored || []) {
            if (!isOurs(s.domain)) continue;
            (spByKw[run.keyword] = spByKw[run.keyword] || []).push({ x: new Date(run.timestamp), y: s.position });
        }
        for (const o of run.organic || []) {
            if (!isOurs(o.domain)) continue;
            (orgByKw[run.keyword] = orgByKw[run.keyword] || []).push({ x: new Date(run.timestamp), y: o.position });
        }
    }

    const datasets = [];
    const gold = ["#d29922", "#e3b341", "#b08800", "#f0c050"];
    const blue = ["#58a6ff", "#79c0ff", "#388bfd", "#a5d6ff"];
    let i = 0;
    for (const [kw, pts] of Object.entries(spByKw)) {
        datasets.push({ label: kw + " (Sponsored)", data: pts, borderColor: gold[i % 4], backgroundColor: gold[i % 4] + "33", borderWidth: 2, pointRadius: 3, tension: 0.3 });
        i++;
    }
    i = 0;
    for (const [kw, pts] of Object.entries(orgByKw)) {
        datasets.push({ label: kw + " (Organic)", data: pts, borderColor: blue[i % 4], backgroundColor: blue[i % 4] + "33", borderWidth: 2, borderDash: [4, 4], pointRadius: 3, tension: 0.3 });
        i++;
    }

    if (posChart) posChart.destroy();
    posChart = new Chart(ctx, {
        type: "line", data: { datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: "bottom", labels: { color: "#7d8590", font: { family: "'JetBrains Mono'", size: 10 } } } },
            scales: {
                x: { type: "time", time: { unit: days <= 7 ? "hour" : "day" }, grid: { color: "#21262d" }, ticks: { color: "#484f58", font: { size: 10 } } },
                y: { reverse: true, min: 1, max: 10, grid: { color: "#21262d" }, ticks: { color: "#484f58", font: { family: "'JetBrains Mono'", size: 10 }, stepSize: 1, callback: v => "#" + v }, title: { display: true, text: "Position (lower = better)", color: "#484f58" } },
            },
        },
    });
}

/* ── Heatmap ───────────────────────────────────────────────── */

function renderHeatmap() {
    const days = getDays();
    const cutoff = cutoffDate(days).toISOString();
    const ctx = document.getElementById("heatmap-chart").getContext("2d");

    const hourCounts = new Array(24).fill(0);
    for (const run of allRuns) {
        if (run.timestamp < cutoff) continue;
        const hour = new Date(run.timestamp).getHours();
        for (const s of run.sponsored || []) {
            if (!isOurs(s.domain)) hourCounts[hour]++;
        }
    }

    const labels = Array.from({ length: 24 }, (_, h) => (h % 12 || 12) + (h >= 12 ? "PM" : "AM"));

    if (heatChart) heatChart.destroy();
    heatChart = new Chart(ctx, {
        type: "bar",
        data: { labels, datasets: [{ label: "Competitor ad appearances", data: hourCounts, backgroundColor: "rgba(210,153,34,0.5)", borderColor: "#d29922", borderWidth: 1, borderRadius: 3 }] },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: "bottom", labels: { color: "#7d8590", font: { family: "'JetBrains Mono'", size: 10 } } } },
            scales: {
                x: { grid: { color: "#21262d" }, ticks: { color: "#484f58", font: { size: 10 } } },
                y: { grid: { color: "#21262d" }, ticks: { color: "#484f58", font: { size: 10 } }, title: { display: true, text: "Total ad appearances", color: "#484f58" } },
            },
        },
    });
}

/* ── Auto-refresh data every 5 min ─────────────────────────── */

setInterval(loadData, 5 * 60 * 1000);

/* ── Init ──────────────────────────────────────────────────── */

document.addEventListener("DOMContentLoaded", async () => {
    if (await checkAuth()) showDashboard();
});
