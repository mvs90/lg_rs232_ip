/* Legacy LG Chromium supports AppCache. Modern browsers safely report unsupported. */
(function () {
  "use strict";
  var root=document.documentElement, enabled=root.hasAttribute("manifest"), cache=window.applicationCache;
  var key="lg-display-hdmi-v1", scope=window.location.pathname, restored=null, updateTimer=null, updating=false;
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
  function reload() {if(updateTimer){clearTimeout(updateTimer);updateTimer=null;}window.location.reload();}
  if(enabled && cache){
    cache.addEventListener("updateready",function () {if(updating){try{cache.swapCache();}catch(_){}reload();}});
    cache.addEventListener("obsolete",reload);
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
    update:function () {
      if(!enabled || !cache || cache.status===0){reload();return;}
      if(updating){return;}updating=true;
      if(cache.status===4){try{cache.swapCache();}catch(_){}reload();return;}
      // Avoid reloading a stale cached app repeatedly while its update downloads.
      updateTimer=setTimeout(reload,30000);
      try {cache.update();} catch (_) {}
    }
  };
}());
