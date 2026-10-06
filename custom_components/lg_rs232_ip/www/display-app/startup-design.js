/* ES5. Offline-only content, one atomic scoped record, one bounded image. */
(function () {
  "use strict";
  var key="lg-display-startup-v1:"+window.location.pathname, bundle=null, cached=false;
  var pending=null, wanted=null, retryAt=0, root=null, renderer=null, clockTimer=null;
  var MAX=1200000, hex=/^#[0-9a-fA-F]{6}$/, digest=/^[a-f0-9]{64}$/;
  function number(value,low,high) {return typeof value==="number" && isFinite(value) && value>=low && value<=high;}
  function valid(value) {
    if(!value || value.schema!==1 || !digest.test(value.version) || typeof value.timezone!=="string" || value.timezone.length>100){return false;}
    var s=value.scene, ids={};
    if(!s || ["solid","aurora","dawn","ocean","sand","midnight","gradient","image"].indexOf(s.background)<0 || !hex.test(s.color) || !hex.test(s.accent) || !number(s.gradient_angle,0,360) || !number(s.image_dim,0,.9) || ["cover","contain"].indexOf(s.image_fit)<0 || typeof s.image_id!=="string" || (s.image_id && !digest.test(s.image_id)) || s.media_background_enabled || s.media_background_entity || !Array.isArray(s.elements) || s.elements.length>16){return false;}
    if(value.image!==null && (typeof value.image!=="string" || value.image.length>1050000 || !/^data:image\/jpeg;base64,[A-Za-z0-9+/=]+$/.test(value.image))){return false;}
    if(s.background==="image" && s.image_id && !value.image){return false;}
    return s.elements.every(function (item) {
      if(!item || !/^[a-zA-Z0-9_-]{1,40}$/.test(item.id) || ids[item.id] || ["clock","text"].indexOf(item.kind)<0 || item.entity_id){return false;}ids[item.id]=true;
      return ["color","background"].every(function(k){return hex.test(item[k]);}) && ["label","text"].every(function(k){return typeof item[k]==="string" && item[k].length<=(k==="text"?2000:100);}) && typeof item.show_label==="boolean" && ["sans","serif","mono"].indexOf(item.font)>=0 && ["left","center","right"].indexOf(item.align)>=0 && number(item.x,0,100) && number(item.y,0,100) && number(item.width,2,100) && number(item.height,2,100) && item.x+item.width<=100.01 && item.y+item.height<=100.01 && number(item.font_size,1,18) && number(item.opacity,0,1) && number(item.radius,0,80);
    });
  }
  try {var saved=window.localStorage.getItem(key);if(saved && saved.length<=MAX){var parsed=JSON.parse(saved);if(valid(parsed)){bundle=parsed;cached=true;}}} catch (_) {}
  function stop() {clearTimeout(clockTimer);clockTimer=null;root=null;if(renderer){renderer.clear();renderer=null;}}
  function tick() {
    clearTimeout(clockTimer);clockTimer=null;
    if(!root || !renderer || document.hidden){return;}
    renderer.tick(new Date());
    if(bundle.scene.elements.some(function (item) {return item.kind==="clock";})){clockTimer=setTimeout(tick,60000-Date.now()%60000+20);}
  }
  function paint() {
    if(!root || !bundle || !window.LGLayoutRenderer){return false;}
    if(!renderer){renderer=new window.LGLayoutRenderer(root,document.createElement("div"),false);}
    root.hidden=false;
    renderer.render(bundle.scene,{}, {timezone:bundle.timezone,now:new Date(),imageUrl:function () {return bundle.image;}});
    tick();return true;
  }
  function sync(version) {
    if(!digest.test(version || "") || (bundle && bundle.version===version) || (pending && wanted===version) || (wanted===version && Date.now()<retryAt)){return;}
    if(pending){pending.onload=pending.onerror=pending.ontimeout=null;pending.abort();}
    wanted=version;var request=pending=new XMLHttpRequest();
    request.open("GET","startup-design",true);request.timeout=8000;
    function fail() {if(pending===request){pending=null;retryAt=Date.now()+30000;}}
    request.onerror=request.ontimeout=fail;
    request.onload=function () {
      if(pending!==request){return;}
      try {
        if(request.status!==200 || request.responseText.length>MAX){fail();return;}
        var next=JSON.parse(request.responseText);
        if(!valid(next) || next.version!==wanted){fail();return;}
        bundle=next;cached=false;
        try {window.localStorage.setItem(key,JSON.stringify(bundle));cached=true;} catch (_) {}
        pending=null;retryAt=0;
        if(root){paint();document.getElementById("startup-fallback").hidden=true;}
      } catch (_) {fail();}
    };
    request.send();
  }
  window.LGStartupDesign={sync:sync,render:function (node) {root=node;return paint();},stop:stop,status:function () {return {version:bundle ? bundle.version:null,cached:cached,image_cached:!!(cached && bundle && bundle.image)};}};
  document.addEventListener("visibilitychange",tick);
  window.addEventListener("resize",function () {if(root){paint();}});
  window.addEventListener("pagehide",function () {stop();if(pending){pending.abort();pending=null;}});
}());
