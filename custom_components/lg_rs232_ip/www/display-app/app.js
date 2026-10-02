/* ES5 / Chromium 53: intentionally no modern HA frontend or external SDK. */
(function () {
  "use strict";
  var video = null, videoSource = null;
  var active = null, expires = 0, lastSuccess = 0, lastHello = 0;
  var wasVisible = !document.hidden;
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { wasVisible = true; }
    else if (wasVisible && window.PalmSystem) { window.close(); }
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
  function clear(message) {
    el("hdmi-slot").textContent = ""; video = null; videoSource = null;
    active = null; expires = 0; document.body.className = "idle";
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
      if (!/^ext:\/\/hdmi:[1-4]$/.test(content.hdmi)) { throw new Error("HDMI input missing"); }
      if (videoSource !== content.hdmi) {
        el("hdmi-slot").textContent = "";
        video = document.createElement("video"); video.autoplay = true;
        var source = document.createElement("source"); source.type = "service/webos-external"; source.src = content.hdmi;
        video.appendChild(source); el("hdmi-slot").appendChild(video); videoSource = content.hdmi;
      }
      if (video.error) { throw new Error("HDMI unavailable"); }
      // Metadata may arrive before the external video plane actually becomes ready.
      if (!video.videoWidth || !video.videoHeight) { return; }
    } else if (video) { el("hdmi-slot").textContent = ""; video = null; videoSource = null; }
    if (changed || !content.rendered) {
      window.requestAnimationFrame(function () { window.requestAnimationFrame(function () {
        if (active === content.id) { event({type:"rendered", id:content.id}); }
      }); });
    }
  }
  function poll() {
    request("GET", "state", null, function (data) {
      if (data) {
        if (data.version !== "1.0.0") { window.location.reload(); return; }
        lastSuccess = Date.now(); text("connection", "Mit Home Assistant verbunden");
        if (Date.now() - lastHello > 10000) {
          lastHello = Date.now();
          event({type:"hello", version:"1.0.0", bridge:typeof window.PalmServiceBridge === "function"});
        }
        try { render(data.content); } catch (_) { event({type:"error", id:active}); clear("Anzeige fehlgeschlagen"); }
      } else { text("connection", "Verbindung unterbrochen"); }
      window.setTimeout(poll, 2000);
    });
  }
  window.setInterval(function () {
    var now = new Date(); text("clock", ("0" + now.getHours()).slice(-2) + ":" + ("0" + now.getMinutes()).slice(-2));
    if (active && (Date.now() >= expires || Date.now() - lastSuccess > 15000)) { clear("Anzeige beendet"); }
    if (active) { text("countdown", Math.max(0, Math.ceil((expires - Date.now()) / 1000)) + " s"); }
  }, 500);
  poll();
}());
