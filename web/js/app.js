/* Hair & Scalp Care Advisor - front end. Plain JavaScript, no build step.
   Talks to the FastAPI service on the same origin: /predict, /health, /stats.
   No inline styles and no outside requests: the page works under the strict Content-Security-Policy the service sends. */
(function () {
  "use strict";
  var SLOTS = { front: ["balding"], crown: ["dryness", "dandruff", "low_density"] };
  var OK_TYPES = ["image/jpeg", "image/png", "image/webp"];
  var MAX_BYTES = 10 * 1024 * 1024;        // the service refuses anything larger
  var SHRINK_ABOVE = 9 * 1024 * 1024;      // only photos this big are shrunk on the phone; everything else is sent untouched
  var SHRINK_SIDE = 2048;
  var TIMEOUT_MS = 90 * 1000;
  var RETRY_CODES = ["network", "timeout", "server_error", "other"];
  var S = { lang: "en", i18n: null, files: { front: null, crown: null }, urls: {}, last: null, busy: false, health: null };

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function t(key, vars) {
    var d = S.i18n && (S.i18n[S.lang][key] != null ? S.i18n[S.lang][key] : S.i18n.en[key]);
    if (d == null) return key;
    if (typeof d === "string" && vars) Object.keys(vars).forEach(function (k) { d = d.split("{" + k + "}").join(vars[k]); });
    return d;
  }
  function has(key) { return S.i18n && S.i18n.en[key] != null; }
  function smooth() { return matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"; }

  /* ---------- icons (shape + words, never colour alone) ---------- */
  var ICON = {
    possible: '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="7" fill="none" stroke="currentColor" stroke-width="2"/><path d="M9 2a7 7 0 0 1 0 14z" fill="currentColor"/></svg>',
    none_seen: '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M3.5 9.5l3.5 3.5 7.5-8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    unsure: '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M6.5 6.8a2.6 2.6 0 1 1 3.6 2.4c-.8.4-1.1.9-1.1 1.8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="9" cy="14.2" r="1.2" fill="currentColor"/></svg>',
    unsuitable: '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M4.5 4.5l9 9M13.5 4.5l-9 9" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>'
  };
  var PCICON = { match: ICON.none_seen, partial: ICON.unsure, mismatch: ICON.unsuitable };

  /* ---------- language ---------- */
  function applyStatic() {
    document.documentElement.lang = S.lang;
    $$("[data-i18n]").forEach(function (n) { n.textContent = t(n.getAttribute("data-i18n")); });
    $$("[data-i18n-aria]").forEach(function (n) { n.setAttribute("aria-label", t(n.getAttribute("data-i18n-aria"))); });
    $$("[data-i18n-list]").forEach(function (n) {
      var items = t(n.getAttribute("data-i18n-list"));
      n.innerHTML = (Array.isArray(items) ? items : []).map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("");
    });
    $$(".lang button").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-lang") === S.lang ? "true" : "false"); });
    document.title = t("app_title");
    renderHint(); renderAccuracy(); renderStats(); renderVersion(); renderModels(); renderHealthPanel();
    if (S.last && $("#results")) renderResults(S.last);
    ["front", "crown"].forEach(function (s) { var p = $("#slot-" + s + " .pcheck"); if (p && !p.hidden && S.last) showPhotoCheck(s); });
    var e = $("#error"); if (e && !e.hidden && e.dataset.code) $("#error-text").textContent = errText(e.dataset.code);
    $$("[data-msg]").forEach(function (m) { if (!m.hidden && m.dataset.code) m.textContent = errText(m.dataset.code); });
  }
  function setLang(l) { S.lang = l; try { localStorage.setItem("lang", l); } catch (e) {} applyStatic(); }

  /* ---------- photo slots ---------- */
  /* A photo is checked the moment it is chosen, so a wrong file is explained next to the photo and not after "Check". */
  function slotMessage(slot, code) {
    var m = $("#slot-" + slot + " [data-msg]"); if (!m) return;
    if (!code) { m.hidden = true; m.textContent = ""; delete m.dataset.code; return; }
    m.dataset.code = code; m.textContent = errText(code); m.hidden = false;
  }
  /* Big phone photos (over 9 MB) are scaled down here, on the device, so they are not refused. The picture is redrawn as
     plain pixels, which also leaves behind any location data stored in the original file. Smaller photos are sent untouched. */
  function shrink(file) {
    if (!window.createImageBitmap) return Promise.reject(new Error("unsupported"));
    return createImageBitmap(file).then(function (bmp) {
      var scale = Math.min(1, SHRINK_SIDE / Math.max(bmp.width, bmp.height));
      var c = document.createElement("canvas");
      c.width = Math.max(1, Math.round(bmp.width * scale)); c.height = Math.max(1, Math.round(bmp.height * scale));
      c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
      if (bmp.close) bmp.close();
      return new Promise(function (resolve, reject) {
        c.toBlob(function (b) { if (b && b.size <= MAX_BYTES) resolve(new File([b], "photo.jpg", { type: "image/jpeg" })); else reject(new Error("still too large")); }, "image/jpeg", 0.92);
      });
    });
  }
  function prepare(file) {
    if (OK_TYPES.indexOf((file.type || "").toLowerCase()) < 0) return Promise.reject("unsupported_type");
    if (!file.size) return Promise.reject("empty_file");
    if (file.size <= SHRINK_ABOVE) return Promise.resolve(file);
    return shrink(file).catch(function () { return Promise.reject("too_large"); });
  }
  function setFile(slot, file) {
    var box = $("#slot-" + slot), drop = $(".drop", box);
    if (S.urls[slot]) { URL.revokeObjectURL(S.urls[slot]); delete S.urls[slot]; }
    S.files[slot] = file;
    var pre = $(".preview", drop), rm = $("[data-remove]", box);
    if (file) {
      S.urls[slot] = URL.createObjectURL(file);
      pre.src = S.urls[slot]; pre.hidden = false; drop.classList.add("has-photo"); rm.hidden = false;
    } else {
      pre.removeAttribute("src"); pre.hidden = true; drop.classList.remove("has-photo"); rm.hidden = true;
    }
    $(".pcheck", box).hidden = true;
    slotMessage(slot, null);
    renderHint();
  }
  function choose(slot, file) {
    if (S.busy || !file) return;
    prepare(file).then(function (ok) { setFile(slot, ok); }, function (code) { slotMessage(slot, code); });
  }
  function renderHint() {
    if (!$("#run")) return;
    var n = (S.files.front ? 1 : 0) + (S.files.crown ? 1 : 0);
    $("#run").disabled = S.busy || n === 0;
    $("#run-label").textContent = S.busy ? t("checking") : t("btn_check");
    var hint = $("#run-hint");
    hint.hidden = !(S.busy || n === 0);
    hint.textContent = t(S.busy ? "checking_hint" : "empty_hint");
    $("#opt-heat").disabled = S.busy;
    $$("[data-remove]").forEach(function (b) { b.disabled = S.busy; });
    document.body.classList.toggle("has-photo", n > 0 || S.busy);
    var c = $("#check"); if (c) c.setAttribute("aria-busy", S.busy ? "true" : "false");
  }
  function wireSlots() {
    if (!$("#run")) return;
    $$(".photo-card").forEach(function (box) {
      var slot = box.dataset.slot, drop = $(".drop", box);
      $$("[data-pick]", box).forEach(function (inp) {
        inp.addEventListener("change", function () { if (inp.files[0]) choose(slot, inp.files[0]); inp.value = ""; });
      });
      $("[data-remove]", box).addEventListener("click", function () { if (!S.busy) setFile(slot, null); });
      drop.addEventListener("click", function () { if (!S.busy) $("[data-pick=gallery]", box).click(); });
      drop.addEventListener("keydown", function (e) { if ((e.key === "Enter" || e.key === " ") && !S.busy) { e.preventDefault(); $("[data-pick=gallery]", box).click(); } });
      ["dragenter", "dragover"].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add("over"); }); });
      ["dragleave", "drop"].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove("over"); }); });
      drop.addEventListener("drop", function (e) { var f = e.dataTransfer && e.dataTransfer.files[0]; if (f) choose(slot, f); });
    });
  }
  function focusSlot(slot) {
    var box = $("#slot-" + slot); if (!box) return;
    box.scrollIntoView({ behavior: smooth(), block: "center" });
    $(".drop", box).focus({ preventScroll: true });
  }

  /* ---------- calling the service ---------- */
  function errText(code) { var k = "err_" + code; return has(k) ? t(k) : t("err_other"); }
  function showError(code) {
    var e = $("#error"); e.dataset.code = code; $("#error-text").textContent = errText(code);
    $("#retry").hidden = RETRY_CODES.indexOf(code) < 0;
    e.hidden = false; e.scrollIntoView({ behavior: smooth(), block: "nearest" });
  }
  function extOf(file) { return { "image/png": "png", "image/webp": "webp" }[file.type] || "jpg"; }
  function run() {
    if (S.busy) return;
    var fd = new FormData(), n = 0;
    ["front", "crown"].forEach(function (s) { if (S.files[s]) { fd.append(s, S.files[s], s + "." + extOf(S.files[s])); n++; } });   // neutral names: the original file name is never sent
    if (!n) return;
    fd.append("heatmap", $("#opt-heat").checked ? "true" : "false");
    $("#error").hidden = true;
    S.busy = true; renderHint();
    ["front", "crown"].forEach(function (s) { if (S.files[s]) $("#slot-" + s + " .drop").classList.add("scanning"); });
    var ctl = new AbortController(), timer = setTimeout(function () { ctl.abort(); }, TIMEOUT_MS);
    return fetch("/predict", { method: "POST", body: fd, signal: ctl.signal }).then(function (r) {
      return r.json().then(function (j) { return { ok: r.ok, body: j }; }, function () { return { ok: false, body: {} }; });
    }).then(function (res) {
      if (!res.ok) { showError((res.body.error && res.body.error.code) || "other"); return; }
      S.last = res.body;
      ["front", "crown"].forEach(showPhotoCheck);
      renderResults(res.body);
      var r = $("#results"); r.scrollIntoView({ behavior: smooth(), block: "start" });
      r.focus({ preventScroll: true });
      loadStats();
    }).catch(function (e) { showError(e && e.name === "AbortError" ? "timeout" : "network"); }).then(function () {
      clearTimeout(timer);
      S.busy = false; $$(".drop").forEach(function (d) { d.classList.remove("scanning"); }); renderHint();
    });
  }

  /* ---------- results ---------- */
  function showPhotoCheck(slot) {
    var box = $("#slot-" + slot + " .pcheck");
    var sr = S.last && S.last.slots.filter(function (x) { return x.slot === slot; })[0];
    if (!sr || !S.files[slot]) { box.hidden = true; return; }
    var st = sr.check.status;
    var flags = sr.check.flags.map(function (f) { return "<li>" + esc(t("why_" + f)) + "</li>"; }).join("");
    box.className = "pcheck pcheck-" + st;
    box.innerHTML = PCICON[st] + "<div><b>" + esc(t("pc_title")) + "</b>" + esc(t("pc_" + st)) + (flags ? "<ul>" + flags + "</ul>" : "") + "</div>";
    box.hidden = false;
  }
  function meter(rel) {
    var n = { good: 3, limited: 2, low: 1 }[rel] || 1;
    return '<div class="meter meter-' + rel + '" aria-hidden="true">' + [1, 2, 3].map(function (i) { return '<i class="' + (i <= n ? "on" : "") + '"></i>'; }).join("") + "</div>";
  }
  function fmt(x) { return x == null ? "–" : Number(x).toFixed(2); }
  function whyList(c) {
    var seen = {};
    return c.reasons.filter(function (r) { if (seen[r] || !has("why_" + r)) return false; seen[r] = 1; return true; });
  }
  // One plain-language finding per condition: what the AI saw, what it means, what to do next.
  function finding(c, showRel) {
    var rel = showRel ? '<p class="f-rel">' + meter(c.reliability) + "<span>" + esc(t("rel_" + c.reliability)) + "</span></p>" : "";
    return '<article class="finding finding-' + c.verdict + '"><div class="f-top"><h4 class="f-name">' + esc(t("cond_" + c.condition)) + '</h4><span class="chip chip-' + c.verdict + '">' + ICON[c.verdict] + esc(t("v_" + c.verdict)) + "</span></div>" +
      '<p class="f-mean">' + esc(t("m_" + c.verdict)) + '</p><p class="f-what">' + esc(t("what_" + c.condition)) + "</p>" + rel +
      '<p class="f-next">' + esc(t("next_" + c.verdict)) + "</p></article>";
  }
  // Technical detail for the collapsed "About this result" block (research information is kept, just out of the way).
  function techRow(c) {
    var why = whyList(c), nums = "";
    if (c.probability != null) {
      nums = '<p class="nums"><span>' + esc(t("adv_score")) + ": <b>" + fmt(c.probability) + "</b></span><span>" + esc(t("adv_line")) + ": <b>" + fmt(c.threshold) + "</b></span><span>" +
        esc(t("adv_spread")) + ": <b>" + fmt(c.spread) + "</b></span><span>" + esc(t("adv_views")) + ": <b>" + c.views_positive + "/" + c.n_views + "</b></span></p>";
    }
    var heat = c.heatmap ? '<div class="heat"><img src="' + S.urlOf(c) + '" alt=""><img src="' + c.heatmap + '" alt="' + esc(t("heat_title")) + '"><p>' + esc(t("adv_cam_warn")) + "</p></div>" : "";
    return '<div class="tech-row"><div class="tech-name">' + esc(t("cond_" + c.condition)) + '<span class="chip chip-' + c.verdict + '">' + ICON[c.verdict] + esc(t("v_" + c.verdict)) + "</span></div>" +
      '<div class="tech-body"><p class="muted-line">' + esc(t("rel_" + c.reliability)) + "</p>" + (why.length ? "<ul>" + why.map(function (r) { return "<li>" + esc(t("why_" + r)) + "</li>"; }).join("") + "</ul>" : "") + nums + heat + "</div></div>";
  }
  S.urlOf = function (c) { return S.urls[c.slot] || ""; };

  function careLines(j) {
    return j.advice.map(function (k) {
      if (k.indexOf("retake:") === 0) return t("retake", { label: t("cond_" + k.split(":")[1]) });
      if (k.indexOf("tip:") === 0) return t("tip_" + k.split(":")[1]);
      return t(k);
    });
  }
  function summaryGroups(j) {
    var g = { possible: [], unsure: [], none_seen: [], unsuitable: [] };
    j.slots.forEach(function (s) { s.conditions.forEach(function (c) { g[c.verdict].push(t("cond_" + c.condition)); }); });
    return g;
  }
  var RES_ART = '<svg viewBox="0 0 400 360" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><rect width="400" height="360" fill="#D8A38B"/><path d="M0 0 H400 V360 H0Z" fill="#23382A"/><path d="M110 0 C90 105 130 190 96 360 H270 C236 250 275 110 250 0Z" fill="#D8A38B"/><path d="M132 0 C114 100 151 200 125 360M157 0 C143 100 174 215 153 360M188 0 C171 105 201 210 183 360M219 0 C201 110 229 230 214 360M246 0 C226 115 258 220 244 360" stroke="#A9B79D" stroke-width="2" fill="none"/><path d="M0 0H115C100 115 122 236 93 360H0Z M270 0H400V360H300C278 235 302 120 270 0Z" fill="#1D2D22"/></svg>';
  function headlineKey(g) {
    if (g.possible.length) return "possible";
    if (g.none_seen.length && !g.unsure.length && !g.unsuitable.length) return "none_seen";
    if (g.unsuitable.length && !g.none_seen.length && !g.unsure.length) return "unsuitable";
    return "unsure";
  }
  function summaryAside(j) {
    var h = '<aside class="photo-summary"><div class="eyebrow">' + esc(t("res_photos")) + "</div>";
    ["front", "crown"].forEach(function (s) {
      var added = !!S.files[s] && j.slots.some(function (x) { return x.slot === s; });
      h += '<div class="slotbox"><div class="mini-photo">' + (S.urls[s] && S.files[s] ? '<img alt="" src="' + S.urls[s] + '">' : "<span>–</span>") + "</div><p>" + esc(t(s + "_title")) + "<br><strong>" + esc(t(added ? "photo_added" : "photo_none")) + "</strong></p></div>";
    });
    return h + '<button type="button" class="textbtn" id="review-photos">' + esc(t("review_photos")) + "</button></aside>";
  }
  function careItems(j) {
    return j.advice.map(function (k) {
      var n;
      if (k.indexOf("retake:") === 0) { n = k.split(":")[1]; return { title: t("cond_" + n), text: t("retake", { label: t("cond_" + n) }), kind: "retake" }; }
      if (k.indexOf("tip:") === 0) { n = k.split(":")[1]; return { title: t("cond_" + n), text: t("tip_" + n), kind: "tip" }; }
      return { title: "", text: t(k), kind: "note" };
    });
  }
  function slotBlock(slot, sr) {
    var sec = el("section", "slot-res");
    var head = el("div", "slot-head", "<h3>" + esc(t(slot + "_result")) + "</h3>");
    if (sr && S.files[slot]) {
      var rt = el("button", "btn-link", esc(t("retake_this"))); rt.type = "button"; rt.addEventListener("click", function () { focusSlot(slot); });
      head.appendChild(rt);
    }
    sec.appendChild(head);
    if (!sr) {
      sec.appendChild(el("div", "skipped", esc(t("not_checked_slot")) + " (" + esc(SLOTS[slot].map(function (n) { return t("cond_" + n); }).join(", ")) + ")"));
      return sec;
    }
    // Same reliability for every condition of a photo: say it once. Otherwise show it on each finding.
    var rels = {}; sr.conditions.forEach(function (c) { rels[c.reliability] = 1; });
    var refused = sr.conditions.every(function (c) { return c.verdict === "unsuitable"; });
    var shared = !refused && Object.keys(rels).length === 1 ? sr.conditions[0].reliability : null;
    if (shared) sec.appendChild(el("p", "slot-rel", meter(shared) + "<span>" + esc(t("rel_" + shared)) + "</span>"));
    var grid = el("div", "findings");
    grid.innerHTML = sr.conditions.map(function (c) { c.slot = slot; return finding(c, !refused && !shared); }).join("");
    sec.appendChild(grid);
    return sec;
  }
  function careBlock(j) {
    var wrap = el("section", "care-wrap");
    wrap.appendChild(el("h2", null, esc(t("care_title"))));
    wrap.appendChild(el("p", "care-lead", esc(t("care_lead"))));
    var grid = el("div", "care-grid");
    careItems(j).forEach(function (it) {
      grid.appendChild(el("article", "care-card care-" + it.kind, (it.title ? "<h3>" + esc(it.title) + "</h3>" : "") + "<p>" + esc(it.text) + "</p>"));
    });
    wrap.appendChild(grid);
    return wrap;
  }
  function helpBlock() {
    var h = el("section", "help");
    h.innerHTML = "<h2>" + esc(t("help_title")) + "</h2><div><p>" + esc(t("help_lead")) + "</p><ul>" +
      ["help_1", "help_2", "help_3", "help_4"].map(function (k) { return "<li>" + esc(t(k)) + "</li>"; }).join("") + "</ul></div>";
    return h;
  }
  function aboutBlock(j) {
    var d = el("details", "about");
    var h = "<summary>" + esc(t("about_title")) + '</summary><div class="about-body"><p>' + esc(t("adv_intro")) + "</p>";
    j.slots.forEach(function (sr) {
      if (!S.files[sr.slot]) return;
      var st = sr.check.status;
      h += '<section class="about-slot"><h3>' + esc(t(sr.slot + "_result")) + '</h3><p class="about-pc about-pc-' + st + '"><b>' + esc(t("pc_title")) + ":</b> " + esc(t("pc_" + st)) + "</p>" +
        sr.conditions.map(function (c) { c.slot = sr.slot; return techRow(c); }).join("") + "</section>";
    });
    h += '<p class="about-links"><a href="details.html#limits">' + esc(t("limits_link")) + '</a> · <a href="details.html">' + esc(t("nav_performance")) + "</a></p></div>";
    d.innerHTML = h;
    return d;
  }
  function renderResults(j) {
    var root = $("#results"); root.innerHTML = ""; root.hidden = false;
    document.body.classList.add("has-results");
    var g = summaryGroups(j), hk = headlineKey(g);
    var names = (g.possible.length ? g.possible : g[hk] || []).join(", ");
    // A. main result
    var hero = el("div", "results-hero");
    hero.innerHTML = '<div class="results-copy"><div class="eyebrow">' + esc(t("res_eyebrow")) + "</div><h1>" + esc(t("res_h_" + hk)) + "</h1><p>" + esc(t("res_s_" + hk)) +
      (names && hk === "possible" ? " " + esc(names) + "." : "") + '</p><div class="result-meta">' + esc(t("res_meta")) + '</div></div><div class="results-art">' + RES_ART + "</div>";
    root.appendChild(hero);
    var lay = el("div", "results-layout"); lay.innerHTML = summaryAside(j);
    var main = el("div", "result-main");
    // B. what it means
    var fh = el("div", "sec-intro", "<h2>" + esc(t("find_title")) + "</h2><p>" + esc(t("find_lead")) + "</p>");
    main.appendChild(fh);
    ["front", "crown"].forEach(function (slot) {
      main.appendChild(slotBlock(slot, j.slots.filter(function (x) { return x.slot === slot; })[0]));
    });
    main.appendChild(careBlock(j));   // C. what you can do
    main.appendChild(helpBlock());    // D. when to get professional help
    main.appendChild(aboutBlock(j));  // E. technical information, collapsed
    var act = el("div", "res-actions");
    var dl = el("button", "btn btn-quiet", esc(t("summary_dl"))); dl.type = "button"; dl.addEventListener("click", downloadSummary);
    var so = el("button", "btn btn-quiet", esc(t("start_over"))); so.type = "button"; so.addEventListener("click", startOver);
    act.appendChild(dl); act.appendChild(so); main.appendChild(act);
    main.appendChild(el("p", "small-note", esc(t("foot"))));
    lay.appendChild(main); root.appendChild(lay);
    var rv = $("#review-photos"); if (rv) rv.addEventListener("click", function () { $("#check").scrollIntoView({ behavior: smooth(), block: "start" }); });
  }
  function downloadSummary() {
    var j = S.last; if (!j) return;
    var lines = [t("summary_title"), ""];
    j.slots.forEach(function (s) { s.conditions.forEach(function (c) { lines.push("- " + t("cond_" + c.condition) + ": " + t("v_" + c.verdict) + " (" + t("rel_" + c.reliability) + ")"); }); });
    lines.push("", t("untested_banner")); lines.push.apply(lines, [""].concat(careLines(j))); lines.push("", t("foot"));
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" }));
    a.download = "hair_care_summary.txt"; a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }
  function startOver() {
    setFile("front", null); setFile("crown", null); S.last = null;
    var r = $("#results"); r.hidden = true; r.innerHTML = ""; $("#error").hidden = true;
    document.body.classList.remove("has-results");
    $("#check").scrollIntoView({ behavior: smooth(), block: "start" });
  }

  /* ---------- accuracy (details page) ---------- */
  function renderAccuracy() {
    var host = $("#acc"); if (!host) return; host.innerHTML = "";
    var d = S.accuracy;
    if (!d || !d.items) { host.textContent = t("acc_none"); return; }
    var lo = 0.5, hi = 1.0, pct = function (x) { return (Math.min(Math.max(x, lo), hi) - lo) / (hi - lo) * 100; };
    d.items.forEach(function (it) {
      var sub = it.single_source ? t("acc_single") : (it.n ? t("acc_n", { n: it.n, pos: it.pos }) : "");
      var row = el("div", "acc-row");
      row.innerHTML = '<div class="nm">' + esc(t("cond_" + it.name)) + '<span class="sub">' + esc(sub) + "</span></div>" +
        '<div class="track" role="img" aria-label="' + esc(t("cond_" + it.name) + ": AUROC " + it.auroc.toFixed(2) + " (" + it.lo.toFixed(2) + "–" + it.hi.toFixed(2) + ")") + '">' +
        '<span class="bar"></span><span class="dot"></span><span class="val">' + it.auroc.toFixed(2) + "</span></div>";
      // positions are set through the DOM (not a style attribute), which the content policy allows
      var bar = $(".bar", row), dot = $(".dot", row), val = $(".val", row);
      bar.style.left = pct(it.lo) + "%"; bar.style.width = (pct(it.hi) - pct(it.lo)) + "%";
      dot.style.left = pct(it.auroc) + "%"; val.style.left = pct(it.auroc) + "%";
      host.appendChild(row);
    });
    host.appendChild(el("div", "acc-axis", "<span>" + esc(t("acc_axis_lo")) + "</span><span>" + esc(t("acc_axis_hi")) + "</span>"));
  }

  /* ---------- service stats + version ---------- */
  function loadStats() {
    if (!$("#stats")) return;
    fetch("/stats").then(function (r) { return r.json(); }).then(function (j) { S.stats = j; S.statsFail = false; S.statsAt = new Date(); renderStats(); })
      .catch(function () { S.statsFail = true; renderStats(); });
  }
  function renderStats() {
    var host = $("#stats"); if (!host) return; host.innerHTML = ""; var s = S.stats;
    if (S.statsFail && !s) { host.appendChild(el("div", "stat-empty", "<dt>" + esc(t("mon_unreachable")) + "</dt>")); return; }
    if (!s || !s.requests) { host.appendChild(el("div", "stat-empty", "<dt>" + esc(t("mon_none")) + "</dt>")); return; }
    var share = s.share_outside_trained_type == null ? "–" : Math.round(s.share_outside_trained_type * 100) + "%";
    var lat = s.latency_ms || {};
    var med = lat.median != null ? lat.median + " ms" : "–", p95 = lat.p95 != null ? lat.p95 + " ms" : "–";
    [["mon_requests", s.requests], ["mon_failed", s.failed], ["mon_photos", s.photos_checked], ["mon_outside", share], ["mon_median", med], ["mon_p95", p95]].forEach(function (p) {
      host.appendChild(el("div", null, "<dt>" + esc(t(p[0])) + "</dt><dd>" + esc(p[1]) + "</dd>"));
    });
    var up = $("#updated"); if (up && S.statsAt) up.textContent = t("mon_updated") + " " + S.statsAt.toLocaleTimeString();
  }
  function renderModels() {
    var host = $("#model-table"); if (!host) return;
    var h = S.health;
    if (!h) { host.textContent = t("mon_unreachable"); return; }
    host.innerHTML = '<table class="data-table"><thead><tr><th>' + esc(t("ver_model")) + "</th><th>" + esc(t("ver_task")) + "</th><th>" + esc(t("ver_version")) + "</th></tr></thead><tbody>" +
      h.models.map(function (m) { return "<tr><td>" + esc(t(m.slot + "_title")) + "</td><td>" + esc(m.classes.map(function (c) { return t("cond_" + c); }).join(", ")) + "</td><td>" + esc(m.model_version || "–") + "</td></tr>"; }).join("") + "</tbody></table>";
  }
  function renderHealthPanel() {
    var host = $("#health-panel"); if (!host) return;
    var h = S.health;
    if (!h) { host.innerHTML = '<p class="notice notice-bad">' + esc(t("mon_unreachable")) + "</p>"; return; }
    var rows = [["mon_status", t(h.status === "ok" ? "mon_ok" : "mon_degraded")], ["mon_appver", h.app_version],
      ["mon_phone", t(h.phone_validated ? "mon_yes" : "mon_no")]].concat(h.models.map(function (m) {
      return [t(m.slot + "_title"), (m.loaded ? t("loaded") : t("missing")) + " · " + (m.model_version || "–")];
    }));
    host.innerHTML = '<table class="data-table"><tbody>' + rows.map(function (r) { return "<tr><th>" + esc(has(r[0]) ? t(r[0]) : r[0]) + "</th><td>" + esc(r[1]) + "</td></tr>"; }).join("") + "</tbody></table>";
  }
  function renderVersion() {
    var h = S.health; $("#ver").textContent = h ? t("footer_ver", { v: h.app_version }) : "";
    var w = $("#server-warn");
    if (w) {
      if (h && h.status !== "ok") {
        var miss = h.models.filter(function (m) { return !m.loaded; }).map(function (m) { return m.slot; });
        w.textContent = t("err_model_missing") + " (" + miss.join(", ") + ")"; w.hidden = false;
      } else w.hidden = true;
    }
    var un = $("#untested"); if (un) un.hidden = h ? h.phone_validated !== false : false;
  }
  function loadHealth() { fetch("/health").then(function (r) { return r.json(); }).then(function (j) { S.health = j; renderVersion(); renderModels(); renderHealthPanel(); }).catch(function () { renderModels(); renderHealthPanel(); }); }

  /* ---------- start ---------- */
  function init() {
    wireSlots();
    if ($("#run")) $("#run").addEventListener("click", run);
    var rt = $("#retry"); if (rt) rt.addEventListener("click", run);
    var rf = $("#refresh"); if (rf) rf.addEventListener("click", function () { loadStats(); loadHealth(); });
    $$(".lang button").forEach(function (b) { b.addEventListener("click", function () { setLang(b.getAttribute("data-lang")); }); });
    var saved = null; try { saved = localStorage.getItem("lang"); } catch (e) {}
    if (saved === "th" || saved === "en") S.lang = saved;
    else if ((navigator.language || "").toLowerCase().indexOf("th") === 0) S.lang = "th";
    Promise.all([
      fetch("data/i18n.json").then(function (r) { return r.json(); }),
      fetch("data/accuracy.json").then(function (r) { return r.json(); }).catch(function () { return null; })
    ]).then(function (v) {
      S.i18n = v[0]; S.accuracy = v[1]; applyStatic(); loadHealth(); loadStats();
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
