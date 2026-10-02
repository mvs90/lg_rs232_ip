/* ES5 / Chromium 53: intentionally no modern HA frontend or external SDK. */
(function () {
  "use strict";
  var video = null, videoSource = null, idleHdmi = null, revision = null;
  var captureBusy = false, lastCapture = null, bridge = null;
  var active = null, expires = 0, lastSuccess = 0;
  var wasVisible = !document.hidden;
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { wasVisible = true; }
    else if (wasVisible && window.PalmSystem) { heartbeat(); window.close(); }
  });
  function el(id) { return document.getElementById(id); }
  function text(id, value) { el(id).textContent = value; }
  function request(method, path, data, done) {
    var xhr = new XMLHttpRequest();
    xhr.open(method, path, true); xhr.timeout = 5000;
    if (data) { xhr.setRequestHeader("Content-Type", "application/json"); }
    xhr.onload = function () {
      if (xhr.status !== 200) { done(null); return; }
      try { done(JSON.parse(xhr.responseText)); } catch (_) { done(null); }
    };
    xhr.onerror = xhr.ontimeout = function () { done(null); };
    xhr.send(data ? JSON.stringify(data) : null);
  }
  function event(value) { request("POST", "event", value, function () {}); }
  function ensureHdmi(source) {
    if (!/^ext:\/\/hdmi:[1-4]$/.test(source)) { throw new Error("HDMI input missing"); }
    if (videoSource !== source) {
      el("hdmi-slot").textContent = "";
      video = document.createElement("video"); video.autoplay = true;
      var child = document.createElement("source"); child.type = "service/webos-external"; child.src = source;
      video.appendChild(child); el("hdmi-slot").appendChild(video); videoSource = source;
    }
  }
  function heartbeat() {
    event({type:"hello", version:"1.1.0", bridge:typeof window.PalmServiceBridge === "function",
      visible:!document.hidden, hdmi_ready:!!(video && video.videoWidth && video.videoHeight && !video.error),
      capture:typeof window.PalmServiceBridge === "function"});
  }
  function capture(ticket) {
    if (!ticket || ticket.id === lastCapture || captureBusy || document.hidden || typeof window.PalmServiceBridge !== "function") { return; }
    captureBusy = true; lastCapture = ticket.id;
    var finished = false, timer, b = bridge = new window.PalmServiceBridge();
    function fail() {
      if (finished) { return; } finished = true; captureBusy = false; clearTimeout(timer);
      if (b.cancel) { b.cancel(); } bridge = null;
      event({type:"capture_error", id:ticket.id});
    }
    timer = setTimeout(fail, 3000);
    b.onservicecallback = function(raw) {
      if (finished) { return; }
      try {
        var result = JSON.parse(raw);
        if (result.returnValue !== true || result.encoding !== "base64" || typeof result.data !== "string" || result.data.length > 7 * 1024 * 1024) { fail(); return; }
        var decoded = atob(result.data), bytes = new Uint8Array(decoded.length), i;
        if (bytes.length > 5 * 1024 * 1024) { fail(); return; }
        for (i=0; i<bytes.length; i++) { bytes[i] = decoded.charCodeAt(i); }
        var xhr = new XMLHttpRequest(); xhr.open("POST", "frame?id=" + encodeURIComponent(ticket.id), true); xhr.timeout = 3000;
        xhr.setRequestHeader("Content-Type", "image/jpeg");
        xhr.onload = function() { finished = true; captureBusy = false; clearTimeout(timer); bridge = null; };
        xhr.onerror = xhr.ontimeout = fail; xhr.send(bytes.buffer);
      } catch (_) { fail(); }
    };
    try { b.call("luna://com.webos.service.commercial.signage.storageservice/captureScreen", JSON.stringify({save:false,width:Math.round(ticket.height * 16 / 9),height:ticket.height})); }
    catch (_) { fail(); }
  }
  function clear(message) {
    if (idleHdmi) { ensureHdmi(idleHdmi); }
    else { el("hdmi-slot").textContent = ""; video = null; videoSource = null; }
    active = null; expires = 0; document.body.className = idleHdmi ? "hdmi" : "idle";
    text("title", "Display bereit"); text("message", ""); text("status", message);
    el("cards").textContent = ""; text("countdown", "");
  }
  function render(content) {
    if (!content) { clear("Keine aktive Anzeige"); return; }
    var changed = active !== content.id;
    active = content.id; expires = Date.now() + (changed ? content.duration : content.remaining) * 1000;
    document.body.className = content.layout || "fullscreen"; text("status", content.cards.length ? "Deine Übersicht" : "Benachrichtigung");
    text("title", content.title); text("message", content.message); el("cards").textContent = "";
    content.cards.forEach(function (item) {
      var card = document.createElement("div"), label = document.createElement("div"), value = document.createElement("div"), unit = document.createElement("span");
      card.className = "card"; label.className = "label"; value.className = "value"; unit.className = "unit";
      label.textContent = item.name; value.textContent = item.value + " "; unit.textContent = item.unit;
      value.appendChild(unit); card.appendChild(label); card.appendChild(value); el("cards").appendChild(card);
    });
    if (content.layout === "overlay" || content.layout === "pip") {
      ensureHdmi(content.hdmi);
      if (video.error) { throw new Error("HDMI unavailable"); }
      // Metadata may arrive before the external video plane actually becomes ready.
      if (!video.videoWidth || !video.videoHeight) { return; }
    } else if (video && !idleHdmi) { el("hdmi-slot").textContent = ""; video = null; videoSource = null; }
    if (changed || !content.rendered) {
      window.requestAnimationFrame(function () { window.requestAnimationFrame(function () {
        if (active === content.id) { event({type:"rendered", id:content.id}); }
      }); });
    }
  }
  function poll() {
    request("GET", "state" + (revision === null ? "" : "?since=" + encodeURIComponent(revision)), null, function (data) {
      if (data) {
        if (data.version !== "1.1.0") { window.location.reload(); return; }
        lastSuccess = Date.now(); text("connection", "Mit Home Assistant verbunden");
        var first = revision === null;
        revision = data.revision;
        idleHdmi = data.idle_hdmi || null;
        if (first) { heartbeat(); }
        capture(data.capture);
        try { render(data.content); } catch (_) { event({type:"error", id:active}); clear("Anzeige fehlgeschlagen"); }
      } else { text("connection", "Verbindung unterbrochen"); }
      window.setTimeout(poll, data ? 50 : 2000);
    });
  }
  window.setInterval(function () {
    var now = new Date(); text("clock", ("0" + now.getHours()).slice(-2) + ":" + ("0" + now.getMinutes()).slice(-2));
    if (active && (Date.now() >= expires || Date.now() - lastSuccess > 15000)) { clear("Anzeige beendet"); }
    if (active) { text("countdown", Math.max(0, Math.ceil((expires - Date.now()) / 1000)) + " s"); }
  }, 500);
  window.setInterval(heartbeat, 5000);
  poll();
}());
