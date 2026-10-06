/* ES5. One early request, no stored intent, animation loop or native toast. */
(function () {
  "use strict";
  var node = document.getElementById("startup-screen"), timer = null;
  var current = null, dismissed = null, mainReady = false, xhr = new XMLHttpRequest();
  function hide() {
    clearTimeout(timer); timer = null;
    if (current) { dismissed = current; }
    if(window.LGStartupDesign){window.LGStartupDesign.stop();}
    current = null; node.hidden = true; document.body.removeAttribute("data-starting");
  }
  function show(intent, scene) {
    if (!intent || !intent.id || intent.view === "hdmi_full" || intent.view === scene || !(intent.remaining > 0) || document.hidden) { hide(); return; }
    if (intent.id === dismissed || intent.id === current) { return; }
    hide(); current = intent.id;
    document.getElementById("startup-target").textContent = String(intent.label || "Ansicht").slice(0, 100) + " wird gestartet …";
    node.hidden = false; document.body.setAttribute("data-starting", "true");
    var designed=window.LGStartupDesign && window.LGStartupDesign.render(document.getElementById("startup-canvas"));
    document.getElementById("startup-fallback").hidden=!!designed;document.getElementById("startup-canvas").hidden=!designed;
    timer = window.setTimeout(hide, Math.min(intent.remaining, 90) * 1000);
  }
  window.LGStartup = {
    apply: function (intent, scene) {
      mainReady = true; xhr.abort(); show(intent, scene);
    },
    hide: function () { mainReady = true; xhr.abort(); hide(); },
    active: function () { return current !== null; }
  };
  xhr.open("GET", "startup", true); xhr.timeout = 3000;
  xhr.onload = function () {
    if (mainReady || xhr.status !== 200) { return; }
    try { var data=JSON.parse(xhr.responseText);if(window.LGStartupDesign){window.LGStartupDesign.sync(data.design_version);}show(data.startup, null); } catch (_) {}
  };
  xhr.send();
  document.addEventListener("visibilitychange", function () { if (document.hidden) { hide(); } });
  window.addEventListener("pagehide", function () { mainReady = true; xhr.abort(); hide(); });
}());
