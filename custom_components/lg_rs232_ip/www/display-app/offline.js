/* ES5. Keep the running HDMI app alive when HA removes its AppCache manifest. */
(function () {
  "use strict";
  var root=document.documentElement, enabled=root.hasAttribute("manifest"), cache=window.applicationCache;
  var key="lg-display-hdmi-v1", scope=window.location.pathname, restored=null;
  var updateTimer=null, updating=false, checking=null, expected=null, nextAttempt=0, closed=false;
  var valid=function (value) {return typeof value==="string" && /^ext:\/\/hdmi:[1-4]$/.test(value);};
  function forget() {try {window.localStorage.removeItem(key);} catch (_) {}}
  function read() {
    if(!enabled){forget();return null;}
    var value;
    try {value=JSON.parse(window.localStorage.getItem(key));} catch (_) {}
    if(value && value.scope===scope && valid(value.hdmi)){return value;}
    var hdmi=root.getAttribute("data-offline-hdmi");
    return valid(hdmi) ? {hdmi:hdmi,fit:"contain"} : null;
  }
  function cancel() {
    clearTimeout(updateTimer); updateTimer=null; updating=false;
    if(checking){checking.onload=checking.onerror=checking.ontimeout=null;checking.abort();checking=null;}
  }
  function unavailable() {
    cancel(); nextAttempt=Date.now()+30000;
    var event=document.createEvent("Event");event.initEvent("lg-app-unavailable",false,false);document.dispatchEvent(event);
  }
  function checkResource(path, accept, done) {
    if(closed || !updating){return;}
    var xhr=new XMLHttpRequest(); checking=xhr;
    xhr.open("GET",path+"?_lg_reload="+Date.now(),true);xhr.timeout=3000;
    xhr.onload=function () {
      if(checking!==xhr || closed){return;}checking=null;
      var type=xhr.getResponseHeader("Content-Type") || "", ok=false;
      try {ok=xhr.status===200 && xhr.responseText.length<512*1024 && accept(xhr.responseText,type);}catch(_){}
      if(ok){done();}else{unavailable();}
    };
    xhr.onerror=xhr.ontimeout=function () {if(checking===xhr){checking=null;unavailable();}};
    xhr.send();
  }
  function checkedReload() {
    if(!updating || checking || closed){return;}
    clearTimeout(updateTimer);updateTimer=null;
    // Bypass cached resources: never navigate to a 404, login page or partial app.
    checkResource("index.html",function (html,type) {
      return type.indexOf("text/html")===0 && html.indexOf('id="hdmi-slot"')!==-1 && html.indexOf('src="app.js"')!==-1 &&
        html.indexOf('data-app-version="'+expected.version+'"')!==-1 &&
        (expected.studio_version===undefined || html.indexOf('data-studio-version="'+(expected.studio_version || "")+'"')!==-1) &&
        (expected.offline_enabled===undefined || (html.indexOf('manifest="offline.appcache"')!==-1)===expected.offline_enabled);
    },function () {
      checkResource("app.js",function (body,type) {return type.indexOf("javascript")!==-1 && body.indexOf('VERSION = "'+expected.version+'"')!==-1;},function () {
        checkResource("app.css",function (body,type) {return type.indexOf("text/css")===0 && body.indexOf("body.hdmi")!==-1;},function () {
          checkResource("offline.js",function (body,type) {return type.indexOf("javascript")!==-1 && body.indexOf("window.LGOffline=")!==-1;},function () {
            if(closed || !updating){return;}
            if(enabled && cache && cache.status===4){try{cache.swapCache();}catch(_){unavailable();return;}}
            cancel();closed=true;window.location.reload();
          });
        });
      });
    });
  }
  if(enabled && cache){
    cache.addEventListener("updateready",checkedReload);
    // 404/410 during unload obsoletes the cache, not the in-memory app.
    cache.addEventListener("obsolete",unavailable);
    cache.addEventListener("error",function () {if(updating){unavailable();}});
    cache.addEventListener("noupdate",function () {if(updating){cancel();nextAttempt=Date.now()+30000;}});
  }
  window.LGOffline={
    restore:function () {restored=read();return restored;},
    remember:function (hdmi,fit) {
      if(!enabled){return;}
      if(!valid(hdmi)){forget();return;}
      var value=JSON.stringify({scope:scope,hdmi:hdmi,fit:fit==="fill" ? "fill" : "contain"});
      // No sensor values, layouts or images; write only when the input changes.
      try {if(window.localStorage.getItem(key)!==value){window.localStorage.setItem(key,value);}} catch (_) {}
    },
    status:function () {return {enabled:enabled,supported:!!cache,cache_status:cache ? cache.status : 0,restored_hdmi:!!restored};},
    cancel:cancel,
    close:function () {closed=true;cancel();},
    update:function (state) {
      if(closed || updating || Date.now()<nextAttempt){return;}
      expected=state || {version:root.getAttribute("data-app-version")};
      if(!expected.version){return;}
      updating=true;
      if(!enabled || !cache || cache.status===0 || cache.status===4 || cache.status===5){checkedReload();return;}
      // A failed or stalled cache update keeps HDMI alive; it never forces reload.
      updateTimer=setTimeout(unavailable,30000);
      try {cache.update();} catch (_) {unavailable();}
    }
  };
  window.addEventListener("pagehide",window.LGOffline.close);
}());
