// Read-only demo shim, inlined by scripts/build_demo_site.py ahead of the UI script.
// Serves the UI's /api/* calls from the snapshot files under snap/; refuses writes.
(function () {
  const realFetch = window.fetch.bind(window);
  const MSG = "Not available in the read-only demo. Run DocPipe locally to try this (see the README on GitHub).";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const norm = (q) => String(q || "").toLowerCase().split(/\s+/).filter(Boolean).join(" ").replace(/\?+$/, "").trim();
  const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json" } });
  const text = (s, status = 200) => new Response(s, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  const cache = {};
  const load = (f) => (cache[f] = cache[f] || realFetch("snap/" + f).then((r) => r.json()));
  async function key(s) {
    const h = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(s));
    return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
  }
  function refuse() {
    try { toast(MSG); } catch (e) { /* toast not ready */ }
    return text(MSG, 403);
  }
  async function find(query, limit) {
    const idx = await load("kb/index.json");
    const terms = norm(query).split(" ").filter((t) => t.length > 1);
    if (!terms.length) return [];
    const hits = Object.entries(idx).map(([uri, t]) => {
      const hay = (uri + " " + t).toLowerCase();
      const n = terms.filter((w) => hay.includes(w)).length;
      const m = uri.match(/__([0-9a-f]{16})(?:\/|$)/);
      return { uri, score: n / terms.length, doc_id: m ? m[1] : null };
    }).filter((h) => h.score > 0);
    return hits.sort((a, b) => b.score - a.score || a.uri.length - b.uri.length).slice(0, limit || 10);
  }
  async function agentReplay(question) {
    const runs = await load("agent.json"), rec = runs[norm(question)];
    if (!rec) {
      const list = Object.values(runs).map((r) => "• " + r.question).join("\n");
      return text("The demo only replays recorded agent runs. Pick one of the suggested questions:\n" + list, 404);
    }
    const enc = new TextEncoder();
    const body = new ReadableStream({
      async start(c) {
        let prev = 0;
        for (const { t, ev } of rec.events) {
          await sleep(Math.min(Math.max(t - prev, 0), 2) * 450); prev = t;
          if (ev.type === "done") ev.seconds = `${ev.seconds} (recorded run)`;
          c.enqueue(enc.encode(JSON.stringify(ev) + "\n"));
        }
        c.close();
      },
    });
    return new Response(body, { headers: { "Content-Type": "application/x-ndjson" } });
  }

  window.fetch = async function (input, init = {}) {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    const p = url.pathname, method = (init.method || "GET").toUpperCase();
    if (!p.startsWith("/api/")) return realFetch(input, init);
    let m;
    if (method === "GET") {
      const simple = { "/api/status": "status.json", "/api/monitor": "monitor.json", "/api/jobs": "jobs.json",
        "/api/tree": "tree.json", "/api/documents": "documents.json", "/api/kb/tree": "kb/tree.json" };
      if (simple[p]) return realFetch("snap/" + simple[p]);
      if ((m = p.match(/^\/api\/jobs\/([\w-]+)\/events$/))) {
        const r = await realFetch(`snap/jobs/${m[1]}.json`); return r.ok ? r : json([]);
      }
      if ((m = p.match(/^\/api\/documents\/([0-9a-f]{16})(\/history|\/fulltext)?$/))) {
        const f = m[2] === "/history" ? `${m[1]}.history.json` : m[2] === "/fulltext" ? `${m[1]}.fulltext.txt` : `${m[1]}.json`;
        const r = await realFetch("snap/doc/" + f);
        return r.ok ? r : text("document not in the demo snapshot", 404);
      }
      if (p === "/api/kb/read") {
        const r = await realFetch(`snap/kb/read/${await key(url.searchParams.get("uri") || "")}.txt`);
        return r.ok ? r : text("This node is not in the demo snapshot.", 404);
      }
      if (p === "/api/agent/status") return json({ ok: true, detail: "recorded runs (demo)" });
      return text(MSG, 404);
    }
    if (method === "POST") {
      const body = typeof init.body === "string" ? JSON.parse(init.body || "{}") : {};
      if (p === "/api/kb/find") return json(await find(body.query, body.limit));
      if (p === "/api/ask") {
        const saved = await load("ask.json"), hit = saved[norm(body.question)];
        if (hit) return json(hit.answer);
        return text("The demo only has recorded answers. Try one of the suggested questions:\n" +
          Object.values(saved).map((s) => "• " + s.question).join("\n"), 404);
      }
      if (p === "/api/agent/ask") return agentReplay(body.question);
    }
    return refuse();
  };

  // page images left out of the snapshot (long public reports) show a placeholder
  window.addEventListener("error", (e) => {
    const t = e.target;
    if (t && t.tagName === "IMG" && t.src.includes("/snap/page/") && !t.dataset.missing) {
      t.dataset.missing = "1"; t.src = "snap/nopage.svg";
    }
  }, true);

  let pdfs = {};
  realFetch("snap/pdfs.json").then((r) => r.json()).then((j) => { pdfs = j; }).catch(() => {});
  window.pdfHref = (id) => (pdfs[id] ? `snap/pdf/${id}.pdf` : "snap/nopdf.html");

  document.addEventListener("DOMContentLoaded", async () => {
    const kill = document.getElementById("kill");
    if (kill) { kill.disabled = true; kill.title = MSG; }
    const qRow = document.getElementById("q") && document.getElementById("q").parentElement;
    if (!qRow) return;
    const saved = await load("ask.json").catch(() => ({}));
    const chips = document.createElement("div");
    chips.className = "row small"; chips.style.marginTop = "8px";
    chips.innerHTML = '<span class="muted">Try:</span>';
    for (const s of Object.values(saved)) {
      const b = document.createElement("button");
      b.className = "chip"; b.textContent = s.question;
      b.onclick = () => { document.getElementById("q").value = s.question; document.getElementById("q-go").click(); };
      chips.appendChild(b);
    }
    qRow.insertAdjacentElement("afterend", chips);
  });
})();
