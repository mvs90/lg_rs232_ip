/* ES5 / Chromium 53. One external video plane; no framework or screenshot loop. */
(function () {
  "use strict";
  var VERSION = "1.17.0", video = null, sourceNode = null, videoSource = null;
  var selectedView = null, dashboardSelected = false, pipSelected = false, mediaSelected = false, design = null, designer = null, currentContent = null, sceneKey = null, serverOffset = 0;
  var hdmiFit = "contain";
  var idleHdmi = null, revision = null, inputRequest = null, inputAck = null;
  var animateHdmi = false;
  var captureBusy = false, lastCapture = null, cancelCapture = null;
  var active = null, dismissed = null, expires = 0, lastSuccess = Date.now();
  var acknowledged = false, ackBusy = false, heartbeatBusy = false, stopped = false;
  var pollXHR = null, pollTimer = null, cardsSignature = null, wasVisible = !document.hidden;
  var startupChecked = false, startupNoticeTimer = null;
  function el(id) { return document.getElementById(id); }
  function text(id, value) { var node = el(id); if (node.textContent !== value) { node.textContent = value; } }
  function layout(value) { if (document.body.className !== value) { document.body.className = value; } }
  function hideStartupNotice() {
    clearTimeout(startupNoticeTimer); startupNoticeTimer = null;
    el("startup-notice").hidden = true;
  }
  function startupConnection(connected) {
    if (connected) { hideStartupNotice(); }
    else if (!startupChecked && !document.hidden) {
      el("startup-notice").hidden = false;
      startupNoticeTimer = window.setTimeout(hideStartupNotice, 5000);
    }
    startupChecked = true;
  }
  function request(method, path, data, done, timeout) {
    var xhr = new XMLHttpRequest(), finished = false;
    function finish(value) {
      if (finished) { return; } finished = true;
      xhr.onload = xhr.onerror = xhr.ontimeout = null;
      if (value) { lastSuccess = Date.now(); }
      done(value);
    }
    xhr.open(method, path, true); xhr.timeout = timeout || (method === "GET" ? 30000 : 5000);
    if (data) { xhr.setRequestHeader("Content-Type", "application/json"); }
    xhr.onload = function () {
      var result = null;
      if (xhr.status === 200) { try { result = JSON.parse(xhr.responseText); } catch (_) {} }
      finish(result);
    };
    xhr.onerror = xhr.ontimeout = function () { finish(null); };
    xhr.send(data ? JSON.stringify(data) : null);
    return xhr;
  }
  function event(value, done) { return request("POST", "event", value, done || function () {}); }
  function ensureHdmi(source) {
    if (!/^ext:\/\/hdmi:[1-4]$/.test(source)) { throw new Error("HDMI input missing"); }
    if (!video) {
      video = document.createElement("video"); video.autoplay = true;
      sourceNode = document.createElement("source"); sourceNode.type = "service/webos-external";
      sourceNode.src = source; video.appendChild(sourceNode); el("hdmi-slot").appendChild(video);
    } else if (videoSource !== source) {
      // Reuse the decoder element; only an explicit HDMI selection reloads its source.
      video.pause(); sourceNode.src = source; video.load();
      var playing = video.play(); if (playing && playing.catch) { playing.catch(function () {}); }
    }
    video.style.objectFit = hdmiFit;
    videoSource = source;
  }
  function releaseHdmi() {
    if (!video) { return; }
    video.pause(); sourceNode.removeAttribute("src"); video.load();
    el("hdmi-slot").removeChild(video); video = sourceNode = videoSource = null;
  }
  function heartbeat() {
    if (heartbeatBusy || stopped) { return; } heartbeatBusy = true;
    event({type:"hello", version:VERSION, bridge:typeof window.PalmServiceBridge === "function",
      offline:window.LGOffline ? window.LGOffline.status() : {},
      startup_design:window.LGStartupDesign ? window.LGStartupDesign.status() : {},
      camera:designer ? designer.cameraStatus() : {mode:"inactive",ready:false},
      rendering:{width:window.innerWidth,height:window.innerHeight,pixel_ratio:window.devicePixelRatio || 1,screen_width:window.screen.width,screen_height:window.screen.height},
      visible:!document.hidden, layout_scene:sceneKey, layout_revision:design ? design.revision : null, hdmi_ready:!!(video && video.videoWidth && video.videoHeight && !video.error),
      capture:typeof window.PalmServiceBridge === "function"}, function () { heartbeatBusy = false; });
  }
  function capture(ticket) {
    if (!ticket || ticket.id === lastCapture || captureBusy || document.hidden || stopped || typeof window.PalmServiceBridge !== "function") { return; }
    captureBusy = true; lastCapture = ticket.id;
    var finished = false, timer, xhr = null, b = new window.PalmServiceBridge();
    function finish(ok, silent) {
      if (finished) { return; } finished = true; clearTimeout(timer); captureBusy = false; cancelCapture = null;
      b.onservicecallback = function () {};
      if (b.cancel) { b.cancel(); }
      if (xhr) { xhr.onload = xhr.onerror = xhr.ontimeout = null; if (!ok) { xhr.abort(); } }
      if (!ok && !silent) { event({type:"capture_error", id:ticket.id}); }
      b = xhr = null;
    }
    cancelCapture = function () { finish(false, true); };
    timer = setTimeout(function () { finish(false); }, 3000);
    b.onservicecallback = function (raw) {
      if (finished || xhr) { return; }
      try {
        var result = JSON.parse(raw);
        if (result.returnValue !== true || result.encoding !== "base64" || typeof result.data !== "string" || result.data.length > 7 * 1024 * 1024) { finish(false); return; }
        var decoded = atob(result.data), bytes = new Uint8Array(decoded.length), i;
        result = raw = null;
        if (bytes.length > 5 * 1024 * 1024) { finish(false); return; }
        for (i = 0; i < bytes.length; i++) { bytes[i] = decoded.charCodeAt(i); }
        decoded = null;
        xhr = new XMLHttpRequest(); xhr.open("POST", "frame?id=" + encodeURIComponent(ticket.id), true); xhr.timeout = 3000;
        xhr.setRequestHeader("Content-Type", "image/jpeg");
        xhr.onload = function () { finish(xhr.status === 200); };
        xhr.onerror = xhr.ontimeout = function () { finish(false); }; xhr.send(bytes.buffer);
      } catch (_) { finish(false); }
    };
    try { b.call("luna://com.webos.service.commercial.signage.storageservice/captureScreen", JSON.stringify({save:false,width:Math.round(ticket.height * 16 / 9),height:ticket.height})); }
    catch (_) { finish(false); }
  }
  function cards(items) {
    var signature = JSON.stringify(items);
    if (signature === cardsSignature) { return; } cardsSignature = signature;
    var parent = el("cards"), i, node;
    for (i = 0; i < items.length; i++) {
      node = parent.children[i];
      if (!node) {
        node = document.createElement("div"); node.className = "card";
        var label = document.createElement("div"), value = document.createElement("div"), unit = document.createElement("span");
        label.className = "label"; value.className = "value"; unit.className = "unit";
        value.appendChild(document.createTextNode("")); value.appendChild(unit);
        node.appendChild(label); node.appendChild(value); parent.appendChild(node);
      }
      if (node.children[0].textContent !== items[i].name) { node.children[0].textContent = items[i].name; }
      if (node.children[1].firstChild.nodeValue !== items[i].value + " ") { node.children[1].firstChild.nodeValue = items[i].value + " "; }
      if (node.children[1].children[0].textContent !== items[i].unit) { node.children[1].children[0].textContent = items[i].unit; }
    }
    while (parent.children.length > items.length) { parent.removeChild(parent.lastChild); }
  }
  function renderDesign(content) {
    // HDMI inputs share an editable scene; keep the existing native video plane.
    if (!design || !design.config.enabled || !window.LGLayoutRenderer || (!content && !selectedView && !dashboardSelected && !pipSelected && !mediaSelected && (!idleHdmi || !design.config.scenes.hdmi_full))) {
      if (designer) { designer.clear(); designer = null; sceneKey = null; }
      sceneKey = !content && idleHdmi ? "signal" : null;
      return false;
    }
    if (!designer) { designer = new window.LGLayoutRenderer(el("layout-root"), el("hdmi-slot"), false); }
    var key;
    if (content) { key = content.layout || "fullscreen"; }
    else if (selectedView && design.config.scenes[selectedView]) { key = selectedView; }
    else if (dashboardSelected) { key = "dashboard"; }
    else if (mediaSelected) { key = "media_view"; }
    else if (pipSelected) { key = "pip_view"; }
    else { key = "hdmi_full"; }
    var baseKey = selectedView || (dashboardSelected ? "dashboard" : mediaSelected ? "media_view" : pipSelected ? "pip_view" : idleHdmi ? "hdmi_full" : null);
    var baseScene = baseKey && design.config.scenes[baseKey];
    var changedScene=sceneKey!==null && sceneKey!==key;
    sceneKey = key;
    layout("designed");
    designer.render(design.config.scenes[key], design.values, {animateWidgets:changedScene && (animateHdmi || !!content), cameraUrls:function(item) {var query="?view="+encodeURIComponent(key)+"&id="+encodeURIComponent(item.id);return {info:"camera.json"+query,image:"camera.jpg"+query,test:"test-stream.m3u8"};}, animateHdmi:animateHdmi && !content, onHdmiSettled:function () {window.requestAnimationFrame(acknowledgeInput);}, message:content, timezone:design.timezone, sun:design.sun, hideHdmi:!!baseScene && !baseScene.elements.some(function (item) { return item.kind === "hdmi"; }), mediaUrl:function(entity,id,size) {return "cover.jpg?entity="+encodeURIComponent(entity)+"&v="+encodeURIComponent(id)+"&size="+(size || 640);}, imageUrl:function(id) {return "background.jpg?id="+id;}, now:new Date(Date.now()+serverOffset)});
    return true;
  }
  function clear(message) {
    if (idleHdmi) { ensureHdmi(idleHdmi); } else { releaseHdmi(); }
    if (active) { dismissed = active; }
    active = null; expires = 0; acknowledged = false;
    currentContent = null;
    if (renderDesign(null)) { return; }
    layout(idleHdmi ? "hdmi" : "idle");
    text("title", "Display bereit"); text("message", ""); text("status", message);
    cards([]); text("countdown", "");
  }
  function acknowledge() {
    if (!active || acknowledged || ackBusy) { return; }
    var id = active; ackBusy = true;
    event({type:"rendered", id:id}, function (result) {
      ackBusy = false; if (active === id && result) { acknowledged = true; }
    });
  }
  function render(content) {
    if (idleHdmi) { ensureHdmi(idleHdmi); }
    if (!content || content.id === dismissed) { clear("Keine aktive Anzeige"); return; }
    var changed = active !== content.id;
    currentContent = content;
    if (changed) { active = content.id; expires = Date.now() + content.duration * 1000; acknowledged = false; }
    acknowledged = acknowledged || content.rendered;
    if (design && !idleHdmi && content.hdmi) { ensureHdmi(content.hdmi); }
    if (renderDesign(content)) {
      if (changed || !acknowledged) { window.requestAnimationFrame(function () { window.requestAnimationFrame(acknowledge); }); }
      return;
    }
    layout(content.layout || "fullscreen"); text("status", content.cards.length ? "Deine Übersicht" : "Benachrichtigung");
    text("title", content.title); text("message", content.message); cards(content.cards);
    if (content.layout === "overlay" || content.layout === "pip") { ensureHdmi(content.hdmi); }
    else if (!idleHdmi) { releaseHdmi(); }
    // The layout is usable even when HDMI has no signal. Signal readiness is diagnostic.
    if (changed || !acknowledged) {
      window.requestAnimationFrame(function () { window.requestAnimationFrame(acknowledge); });
    }
  }
  function acknowledgeInput() {
    if (!inputRequest || inputAck === inputRequest || (designer && designer.hdmiAnimation)) { return; }
    var id = inputRequest;
    event({type:"input_applied", id:id}, function (result) { if (result && inputRequest === id) { inputAck = id; } });
  }
  function poll() {
    if (stopped) { return; }
    pollXHR = request("GET", "state" + (revision === null ? "" : "?since=" + encodeURIComponent(revision)), null, function (data) {
      pollXHR = null;
      if (stopped) { return; }
      startupConnection(!!data);
      if (data) {
        if (data.version !== VERSION || (window.LGOffline && window.LGOffline.status().enabled !== (data.offline_enabled===true))) { if(window.LGOffline){window.LGOffline.update();}else{window.location.reload();} pollTimer=window.setTimeout(poll,2000); return; }
        if(window.LGStartupDesign){window.LGStartupDesign.sync(data.startup_design_version);}
        text("connection", "Mit Home Assistant verbunden");
        var first = revision === null;
        animateHdmi = !!(data.input_request && data.input_request !== inputRequest && data.input_transition === "smooth" && !first && idleHdmi && idleHdmi === data.idle_hdmi);
        revision = data.revision; idleHdmi = data.idle_hdmi || null; inputRequest = data.input_request;
        hdmiFit = data.hdmi_fit === "fill" ? "fill" : "contain";
        if(window.LGOffline){window.LGOffline.remember(idleHdmi,hdmiFit);}
        design = data.layout || null; selectedView = data.selected_view || null; dashboardSelected = data.dashboard === true; pipSelected = data.pip === true; mediaSelected = data.media_view === true;
        // A previous dashboard must not cover HDMI while a new HDMI start waits
        // for its acknowledgement. The saved scene changes only on the server.
        if (data.startup && data.startup.view === "hdmi_full") { selectedView = null; dashboardSelected = pipSelected = mediaSelected = false; }
        if (design && design.now) { serverOffset = new Date(design.now).getTime() - Date.now(); }
        try {
          render(data.content);
          if (window.LGStartup) { window.LGStartup.apply(data.startup, sceneKey); }
          animateHdmi = false;
          if (inputRequest) { window.requestAnimationFrame(acknowledgeInput); }
        } catch (_) { if (window.LGStartup) { window.LGStartup.hide(); } event({type:"error", id:active}); clear("Anzeige fehlgeschlagen"); }
        if (first) { heartbeat(); }
        if(data.diagnostics && window.LGPlatform){var diagnosticId=data.diagnostics.id;(data.diagnostics.operation==="video_wall" ? window.LGVideoWall : window.LGPlatform.sample)(data.diagnostics,function(result){event({type:"diagnostics",id:diagnosticId,result:result});});}
        // Paint commands first; a frame is collected only for an outstanding HA ticket.
        if (data.capture) { window.setTimeout(function () { capture(data.capture); }, 50); }
      } else { if (window.LGStartup) { window.LGStartup.hide(); } text("connection", "Verbindung unterbrochen"); }
      pollTimer = window.setTimeout(poll, data ? 0 : 2000);
    }, startupChecked ? 30000 : 5000);
  }
  var tickTimer = window.setInterval(function () {
    if (active && (Date.now() >= expires || Date.now() - lastSuccess > 15000)) { clear("Anzeige beendet"); }
    if (active) {
      var now = new Date(); text("clock", ("0" + now.getHours()).slice(-2) + ":" + ("0" + now.getMinutes()).slice(-2));
      text("countdown", Math.max(0, Math.ceil((expires - Date.now()) / 1000)) + " s"); acknowledge();
    }
    acknowledgeInput();
    if (designer) {
      // Clocks/progress advance locally without changing the selected source.
      designer.tick(new Date(Date.now()+serverOffset));
    }
  }, 1000);
  var heartbeatTimer = window.setInterval(heartbeat, 5000);
  function stop() {
    hideStartupNotice();
    if (window.LGStartup) { window.LGStartup.hide(); }
    if(window.LGPlatform){window.LGPlatform.close();}
    if (designer) { designer.cancelHdmiAnimation(); designer.stopCameras(); }
    stopped = true; clearTimeout(pollTimer); clearInterval(tickTimer); clearInterval(heartbeatTimer);
    if (pollXHR) { pollXHR.abort(); pollXHR = null; }
    if (cancelCapture) { cancelCapture(); }
  }
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { wasVisible = true; }
    else if (wasVisible && window.PalmSystem) { heartbeat(); stop(); window.close(); }
  });
  window.addEventListener("pagehide", stop);
  window.addEventListener("resize", function () { if (designer) { renderDesign(currentContent); } });
  var boot=window.LGOffline && window.LGOffline.restore();
  if(boot){idleHdmi=boot.hdmi;hdmiFit=boot.fit;clear("Offline HDMI");}
  poll();
}());
