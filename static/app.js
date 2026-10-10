const $ = (s) => document.querySelector(s);

const SAMPLES = {
  scam: {
    text: `Dear Candidate,

Congratulations! You have been selected for the Web Development Internship at Zentrova Skillnet Solutions Pvt Ltd. No interview required, this is a direct selection based on your profile.

To confirm your seat, pay the refundable registration fee of Rs 2,999 within 24 hours. Limited seats only. After payment, send a screenshot with your Aadhaar card and bank details on WhatsApp to +91 98XXXXXX10.

You will get an internship certificate and can earn Rs 1500 per day.

Regards,
HR Team
zentrova.hr2026@gmail.com`,
    company: "",
    email: "",
  },
  real: {
    text: `Hi Manas,

Thanks for taking the time to interview with us last week. We're happy to offer you a Software Engineering Intern role at Razorpay, working with the Payments Platform team in Bengaluru.

Your manager will reach out with onboarding details. Please review the attached offer letter and reply to confirm.

Best,
Talent Team, Razorpay
careers@razorpay.com`,
    company: "",
    email: "",
  },
};

const COLORS = { high: "var(--red)", medium: "var(--amber)", low: "var(--green)" };
const ICON = { red: "!", amber: "?", green: "✓", neutral: "–", error: "×" };

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function stepEl(step) {
  const el = document.createElement("div");
  el.className = "step pending";
  el.id = `step-${step.id}`;
  el.innerHTML = `
    <div class="step-head">
      <span class="dot"></span>
      <span class="step-title">${esc(step.title)}</span>
      <span class="engine">${esc(step.engine)}</span>
    </div>
    <div class="summary">Checking…</div>`;
  return el;
}

function fillStep(r) {
  const el = $(`#step-${r.id}`);
  if (!el) return;
  el.className = `step ${r.signal}`;
  el.querySelector(".dot").textContent = ICON[r.signal] || "";
  const cached = r.cached ? '<span class="cached">(cached)</span>' : "";
  el.querySelector(".summary").innerHTML = esc(r.summary) + cached;
  if (r.evidence && r.evidence.length) {
    const items = r.evidence.map((e) => {
      const title = e.link ? `<a href="${esc(e.link)}" target="_blank" rel="noopener">${esc(e.title || e.link)}</a>` : `<strong>${esc(e.title)}</strong>`;
      const src = e.source ? `<span class="src"> · ${esc(e.source)}</span>` : "";
      const snip = e.snippet ? `<span class="snip">${esc(e.snippet)}</span>` : "";
      return `<li>${title}${src}${snip}</li>`;
    });
    el.insertAdjacentHTML("beforeend", `<ul class="ev">${items.join("")}</ul>`);
  }
}

function showVerdict(v) {
  const box = $("#verdict");
  box.className = `card verdict ${v.level}`;
  $("#score").textContent = v.score;
  const bar = $("#gauge-bar");
  bar.style.stroke = COLORS[v.level];
  bar.style.strokeDashoffset = String(327 - (327 * v.score) / 100);
  $("#headline").textContent = v.headline + (v.incomplete ? ` (${v.incomplete} check(s) failed)` : "");
  $("#reasons").innerHTML =
    v.red.map((t) => `<li class="bad">${esc(t)}</li>`).join("") +
    v.green.map((t) => `<li class="good">${esc(t)}</li>`).join("");
  $("#advice").innerHTML = v.advice.map((t) => `<li>${esc(t)}</li>`).join("");

  if (v.impersonation) {
    $("#banner").textContent = v.impersonation;
    $("#banner").classList.remove("hidden");
  }
  const s = v.stats || {};
  $("#stats").textContent = `${s.sources} sources checked · ${s.results} search results analysed · ${s.seconds}s`;

  lastVerdict = v;
  $("#share").classList.toggle("hidden", v.level === "low");
}

let lastVerdict = null;

function warningText(v) {
  const name = v.company || "this company";
  const lines = [
    `⚠️ Internship scam alert: "${name}"`,
    v.impersonation ? `Someone is pretending to be ${name}. ${v.impersonation.split(": ")[1] || ""}` : `OfferCheck risk score: ${v.score}/100 (${v.headline}).`,
    ...v.red.slice(0, 3).map((r) => `• ${r}`),
    "",
    "Never pay any fee for an internship and don't share Aadhaar/PAN/bank details.",
    "Report fraud: cybercrime.gov.in or call 1930.",
  ];
  return lines.join("\n");
}

$("#share-btn").addEventListener("click", async () => {
  if (!lastVerdict) return;
  const text = warningText(lastVerdict);
  try {
    await navigator.clipboard.writeText(text);
    $("#copied").classList.remove("hidden");
    setTimeout(() => $("#copied").classList.add("hidden"), 2500);
  } catch {
    /* clipboard can be blocked; WhatsApp link below still works */
  }
  window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, "_blank", "noopener");
});

function reset() {
  $("#results").classList.remove("hidden");
  $("#verdict").className = "card verdict";
  $("#score").textContent = "–";
  $("#gauge-bar").style.strokeDashoffset = "327";
  $("#gauge-bar").style.stroke = "var(--neutral)";
  $("#headline").textContent = "Gathering evidence";
  $("#who").textContent = "Investigating…";
  $("#reasons").innerHTML = "";
  $("#advice").innerHTML = "";
  $("#steps").innerHTML = "";
  $("#stats").textContent = "";
  $("#banner").classList.add("hidden");
  $("#share").classList.add("hidden");
  lastVerdict = null;
}

function handle(ev) {
  if (ev.type === "start") {
    $("#who").textContent = ev.company ? `Company: ${ev.company}${ev.email ? " · " + ev.email : ""}` : "Company not detected";
    if (ev.company && !$("#company").value) $("#company").value = ev.company;
    if (ev.email && !$("#email").value) $("#email").value = ev.email;
    ev.steps.forEach((s) => $("#steps").appendChild(stepEl(s)));
  } else if (ev.type === "step") {
    fillStep(ev);
  } else if (ev.type === "verdict") {
    showVerdict(ev);
    document.querySelectorAll(".step.pending").forEach((el) => el.remove());
  } else if (ev.type === "error") {
    $("#headline").textContent = ev.message;
  }
}

async function run() {
  const text = $("#text").value.trim();
  if (text.length < 10) {
    $("#text").focus();
    return;
  }
  reset();
  const btn = $("#go");
  btn.disabled = true;
  btn.textContent = "Investigating…";
  try {
    const resp = await fetch("/api/investigate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, company: $("#company").value.trim() || null, email: $("#email").value.trim() || null }),
    });
    if (!resp.ok) throw new Error(`Server error ${resp.status}`);
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (line) handle(JSON.parse(line));
      }
    }
  } catch (err) {
    $("#headline").textContent = `Something went wrong: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Investigate";
  }
}

$("#go").addEventListener("click", run);
document.querySelectorAll("[data-sample]").forEach((b) =>
  b.addEventListener("click", () => {
    const s = SAMPLES[b.dataset.sample];
    $("#text").value = s.text;
    $("#company").value = s.company;
    $("#email").value = s.email;
    run();
  })
);
