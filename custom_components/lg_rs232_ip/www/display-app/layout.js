/* Shared ES5 renderer: used by both the panel preview and Chromium 53 on the LG. */
(function () {
  "use strict";
  var FONTS = {sans:"Arial, sans-serif",serif:"Georgia, serif",mono:"monospace"};
  var CONDITIONS = {sunny:"Sonnig",clear:"Klar", "clear-night":"Klare Nacht",cloudy:"Bewölkt",partlycloudy:"Wolkig",rainy:"Regen",pouring:"Starker Regen",snowy:"Schnee",fog:"Nebel",windy:"Windig",lightning:"Gewitter","lightning-rainy":"Gewitter"};
  function rgba(hex, opacity) { return "rgba("+parseInt(hex.slice(1,3),16)+","+parseInt(hex.slice(3,5),16)+","+parseInt(hex.slice(5,7),16)+","+opacity+")"; }
  function background(scene, options) {
    options=options || {};
    if(scene.background === "solar" && window.LGWeather){return window.LGWeather.sky(options.sun);}
    if(scene.background === "gradient"){return "linear-gradient("+(scene.gradient_angle || 0)+"deg,"+scene.color+","+scene.accent+")";}
    if(scene.background === "image" && scene.image_id && options.imageUrl){var url=options.imageUrl(scene.image_id);if(url){return "linear-gradient(rgba(0,0,0,"+scene.image_dim+"),rgba(0,0,0,"+scene.image_dim+")),url(\""+url+"\") center / "+scene.image_fit+" no-repeat "+scene.color;}}
    var color = scene.color, accent = scene.accent;
    var styles = {
      solid:color,
      aurora:"radial-gradient(ellipse at 82% 8%,"+rgba(accent,.3)+",transparent 55%),radial-gradient(ellipse at 10% 95%,#26395b,transparent 65%),linear-gradient(125deg,"+color+",#08151e)",
      dawn:"radial-gradient(ellipse at 95% 0%,"+rgba(accent,.58)+",transparent 65%),linear-gradient(145deg,"+color+",#553b52 70%,#bd7866)",
      ocean:"radial-gradient(ellipse at 95% 85%,"+rgba(accent,.35)+",transparent 55%),linear-gradient(145deg,"+color+",#114a60)",
      sand:"radial-gradient(ellipse at 2% 0%,#fffdf7,transparent 80%),linear-gradient(130deg,"+color+",#d7cbb6)",
      midnight:"radial-gradient(ellipse at 88% 0%,"+rgba(accent,.14)+",transparent 60%),linear-gradient(135deg,"+color+",#060b12)"
    };
    return styles[scene.background] || color;
  }
  function style(node, key, value) {
    if (!node._lgStyle) { node._lgStyle = {}; }
    if (node._lgStyle[key] !== value) { node.style[key] = value; node._lgStyle[key] = value; }
  }
  function text(node, value) { value = String(value || ""); if (node.textContent !== value) { node.textContent = value; } }
  function child(parent, name) { var node = document.createElement("div"); node.className = "lg-"+name; parent.appendChild(node); return node; }
  function dateText(value, timezone, withTime) {
    if (!value) { return ""; }
    if (value.length === 10) { timezone="UTC"; }
    var date = new Date(value.length === 10 ? value+"T12:00:00Z" : value);
    if (isNaN(date.getTime())) { return String(value); }
    try { return date.toLocaleDateString("de-DE", {weekday:"short",day:"2-digit",month:"2-digit",timeZone:timezone}) + (withTime && value.length > 10 ? " · "+date.toLocaleTimeString("de-DE",{hour:"2-digit",minute:"2-digit",timeZone:timezone}) : ""); }
    catch (_) { return date.toLocaleDateString(); }
  }
  function rows(node, values) {
    var i, row;
    for (i=0; i<values.length; i++) {
      row = node.children[i];
      if (!row) { row = child(node,"row"); row.appendChild(document.createElement("small")); row.appendChild(document.createElement("span")); }
      text(row.children[0],values[i][0]); text(row.children[1],values[i][1]);
    }
    while (node.children.length > values.length) { node.removeChild(node.lastChild); }
  }
  function Renderer(root, hdmi, preview) {
    this.root = root; this.hdmi = hdmi; this.preview = !!preview; this.nodes = {}; this.scene = null; this.data = null; this.options = null;
  }
  Renderer.prototype.cancelHdmiAnimation = function () {
    if (!this.hdmiAnimation) { return; }
    window.cancelAnimationFrame(this.hdmiAnimation.frame);
    window.clearTimeout(this.hdmiAnimation.timer);
    this.hdmiAnimation = null;
  };
  Renderer.prototype.hdmiGeometry = function (rect) {
    this.hdmiRect = rect;
    var self=this;
    ["left","top","width","height"].forEach(function (key) { style(self.hdmi,key,rect[key]+"%"); });
  };
  Renderer.prototype.moveHdmi = function (rect, animate) {
    var self=this, current=this.hdmiAnimation;
    function equal(a,b) {return a && a.left===b.left && a.top===b.top && a.width===b.width && a.height===b.height;}
    // Camera tickets and data refreshes must not restart an in-flight move.
    if (current && equal(current.to,rect)) { return; }
    this.cancelHdmiAnimation();
    var from=this.hdmiRect;
    if (!animate || !this.hdmiVisible || !from || equal(from,rect) || document.hidden || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches)) {
      this.hdmiGeometry(rect); return;
    }
    // Native external-video planes need real geometry, not a transformed texture.
    // At most 30 small geometry updates/sec for 700 ms; no screenshot or decoder copy.
    var motion={to:rect,start:Date.now(),last:0,frame:null,timer:null,done:this.options.onHdmiSettled};
    this.hdmiAnimation=motion;
    function finish() {
      if (self.hdmiAnimation!==motion) { return; }
      self.cancelHdmiAnimation(); self.hdmiGeometry(rect);
      style(self.hdmi,"zIndex",self.hdmiZ);
      if (motion.done) { motion.done(); }
    }
    function step() {
      if (self.hdmiAnimation!==motion) { return; }
      var now=Date.now(), progress=Math.min(1,(now-motion.start)/700);
      if (progress>=1) { finish(); return; }
      if (now-motion.last>=1000/30) {
        motion.last=now;
        var eased=progress*progress*(3-2*progress), value={};
        ["left","top","width","height"].forEach(function (key) {value[key]=from[key]+(rect[key]-from[key])*eased;});
        self.hdmiGeometry(value);
      }
      motion.frame=window.requestAnimationFrame(step);
    }
    motion.frame=window.requestAnimationFrame(step);
    // Finish even if the browser suspends animation frames; never strand the OSD guard.
    motion.timer=window.setTimeout(finish,1000);
  };
  function artworkSize(pixels) {return pixels>1280 ? 2160 : pixels>640 ? 1280 : 640;}
  function coverBackgrounds(image) {
    // One 32 x 32 sample per new cover, never per frame or progress update.
    // The scoped HA artwork endpoint and editor blob URLs are same-origin.
    var canvas=document.createElement("canvas"); canvas.width=32; canvas.height=32;
    var context=canvas.getContext("2d"); context.drawImage(image,0,0,32,32);
    var pixels=context.getImageData(0,0,32,32).data;
    // Find the first content on each side, skipping only entirely black outer
    // rows/columns. A small tolerance handles compression; dark colours above
    // it and black areas inside the picture still participate in the average.
    var left=32,top=32,right=0,bottom=0,x,y,i;
    for(y=0;y<32;y++){for(x=0;x<32;x++){
      i=(y*32+x)*4;
      if(Math.max(pixels[i],pixels[i+1],pixels[i+2])>8){
        left=Math.min(left,x);right=Math.max(right,x+1);
        top=Math.min(top,y);bottom=Math.max(bottom,y+1);
      }
    }}
    // A wholly black cover has no inner boundary; keep its actual colours.
    if(right<=left || bottom<=top){left=top=0;right=bottom=32;}
    var stripX=Math.min(4,right-left),stripY=Math.min(4,bottom-top);
    function average(x1,y1,x2,y2) {
      var r=0,g=0,b=0,n=0,x,y,i;
      for(y=y1;y<y2;y++){for(x=x1;x<x2;x++){i=(y*32+x)*4;r+=pixels[i];g+=pixels[i+1];b+=pixels[i+2];n++;}}
      return "rgb("+Math.round(r/n)+","+Math.round(g/n)+","+Math.round(b/n)+")";
    }
    function gradient(left,right,top,bottom) {
      return "radial-gradient(ellipse at 0% 50%,"+left+",transparent 75%),radial-gradient(ellipse at 100% 50%,"+right+",transparent 75%),linear-gradient(180deg,"+top+","+bottom+")";
    }
    // Prepare both from one small sample. Whole-cover halves include every
    // pixel, including the center, while retaining the image's colour direction.
    return {
      edges:gradient(average(left,top,left+stripX,bottom),average(right-stripX,top,right,bottom),average(left,top,right,top+stripY),average(left,bottom-stripY,right,bottom)),
      cover:gradient(average(0,0,16,32),average(16,0,32,32),average(0,0,32,16),average(0,16,32,32))
    };
  }
  Renderer.prototype.clearCover = function () {
    var cover=this.cover;if(!cover){return;}
    cover.image.onload=cover.image.onerror=null;cover.image.removeAttribute("src");
    this.root.removeChild(cover.node);this.cover=null;
  };
  Renderer.prototype.renderCover = function () {
    var scene=this.scene,data=this.data[scene.media_background_entity],self=this;
    if(!scene.media_background_enabled || !data || data.state!=="playing" || !data.artwork || !this.options.mediaUrl){this.clearCover();return;}
    var size=(scene.media_background_fit === "center" || scene.media_background_fit === "colors") ? 640 : artworkSize(this.root.clientHeight*(window.devicePixelRatio || 1));
    var key=scene.media_background_entity+"/"+data.artwork+"/"+size,cover=this.cover;
    if(cover && cover.key!==key){this.clearCover();cover=null;}
    if(!cover){
      var node=child(this.root,"cover-background"),image=document.createElement("img");
      image.alt="";node.appendChild(image);
      cover={key:key,node:node,image:image,shade:child(node,"cover-shade"),url:"",retryAt:0,ready:false};this.cover=cover;
    }
    var fit=scene.media_background_fit || "contain";
    cover.node.setAttribute("data-fit",fit);
    style(cover.shade,"background","rgba(0,0,0,"+(scene.media_background_dim === undefined ? .35 : scene.media_background_dim)+")");
    if(cover.ready){this.coverGeometry();return;}
    if(cover.url || Date.now()<cover.retryAt){return;}
    var url=this.options.mediaUrl(scene.media_background_entity,data.artwork,size);
    if(!url){return;}cover.url=url;
    cover.image.onload=function () {
      if(self.cover!==cover){return;}
      if(!cover.image.naturalWidth){cover.image.onerror();return;}
      try {
        var artworkKey=scene.media_background_entity+"/"+data.artwork;
        if(self.paletteKey!==artworkKey){self.coverPalettes=coverBackgrounds(cover.image);self.paletteKey=artworkKey;}
        cover.palettes=self.coverPalettes;
      }
      catch(_){cover.palettes=null;}
      cover.ready=true;cover.node.classList.add("loaded");self.coverGeometry();
    };
    cover.image.onerror=function () {
      if(self.cover!==cover){return;}
      cover.url="";cover.retryAt=Date.now()+30000;
      cover.image.removeAttribute("src");
    };
    cover.image.src=url;
  };
  Renderer.prototype.coverGeometry = function () {
    var cover=this.cover;if(!cover || !cover.ready){return;}
    var mode=this.scene.media_background_color_source === "cover" ? "cover" : "edges";
    style(cover.node,"background",cover.palettes ? cover.palettes[mode] : this.scene.color);
    var image=cover.image,fit=this.scene.media_background_fit || "contain";
    if(fit === "colors"){return;}
    if(fit === "center"){
      // Design coordinates keep the Studio preview and a 1080p/4K panel alike.
      // Preserve decoded cover size within the 1920 x 1080 design, never upscale.
      var scale=Math.min(1,1920/image.naturalWidth,1080/image.naturalHeight);
      style(image,"width",(image.naturalWidth*scale/1920*100)+"%");
      style(image,"height",(image.naturalHeight*scale/1080*100)+"%");
    } else {style(image,"width","100%");style(image,"height","100%");}
    style(image,"objectFit",fit === "stretch" ? "fill" : "contain");
  };
  Renderer.prototype.removeNode = function (node) {
    if(node._camera){node._camera.close();}
    this.root.removeChild(node);
  };
  Renderer.prototype.cameraStatus = function () {
    var result={mode:"inactive",ready:false},self=this;
    Object.keys(this.nodes).forEach(function (key) {
      var camera=self.nodes[key]._camera;
      if(camera){var media=camera.video || camera.image;result={mode:camera.video ? "stream" : "snapshot",ready:!!(media && (media.videoWidth || media.naturalWidth) && !media.error),width:media ? media.videoWidth || media.naturalWidth || 0 : 0,height:media ? media.videoHeight || media.naturalHeight || 0 : 0};}
    });return result;
  };
  Renderer.prototype.stopCameras = function () {
    var self=this;Object.keys(this.nodes).forEach(function (key) {var node=self.nodes[key];if(node._camera){node._camera.close();node._camera=null;node._cameraKey=null;}});
  };
  Renderer.prototype.render = function (scene, data, options) {
    this.scene = scene; this.data = data || {}; this.options = options || {};
    var root=this.root, height=root.clientHeight || 720, wanted={}, found=false, self=this;
    var hdmiItem=scene.elements.filter(function (item) {return item.kind === "hdmi";})[0];
    root.classList.add("lg-scene"); style(root,"background",background(scene, this.options));
    this.renderCover();
    Object.keys(this.nodes).forEach(function (id) {
      var node=self.nodes[id];
      if(node._camera && !scene.elements.some(function (item) {return item.id===id && item.kind==="camera";})){node._camera.close();node._camera=null;}
    });
    scene.elements.forEach(function (item,index) {
      var node, hdmi=item.kind === "hdmi";
      if (hdmi) { if(self.options.hideHdmi){return;} node=self.hdmi; found=true; }
      else {
        node=self.nodes[item.id];
        if (node && node._lgKind !== item.kind) { self.removeNode(node); delete self.nodes[item.id]; node=null; }
        if (!node) {
          node=child(root,"widget lg-"+item.kind); node.dataset.layoutId=item.id; node._lgKind=item.kind;
          node._label=child(node,"label"); node._value=child(node,"value"); node._detail=child(node,"detail"); node._list=child(node,"list"); self.nodes[item.id]=node;
        }
        wanted[item.id]=true;
      }
      if (!node) { return; }
      style(node,"visibility","visible"); style(node,"display",hdmi && !self.preview ? "block" : "flex");
      style(node,"position","absolute");
      if (hdmi) {
        self.hdmiZ=String(index+1);
        self.moveHdmi({left:item.x,top:item.y,width:item.width,height:item.height},self.options.animateHdmi === true);
        self.hdmiVisible=true;
        style(node,"zIndex",self.hdmiAnimation ? "32" : self.hdmiZ);
      } else {
        style(node,"left",item.x+"%"); style(node,"top",item.y+"%"); style(node,"width",item.width+"%"); style(node,"height",item.height+"%"); style(node,"zIndex",String(index+1));
      }
      style(node,"fontSize",(height*item.font_size/100)+"px");
      if (hdmi) { return; }
      style(node,"color",item.color); style(node,"background",item.kind === "camera" && !self.preview ? "transparent" : item.kind === "weather" && item.weather_style === "sky" && window.LGWeather ? window.LGWeather.sky(self.options.sun) : rgba(item.background,item.kind === "weather" && item.weather_style === "minimal" ? 0 : item.opacity));
      style(node,"borderRadius",(height*item.radius/1080)+"px"); style(node,"padding",(height*.018)+"px "+(height*.026)+"px");
      style(node,"textAlign",item.align); style(node,"fontFamily",FONTS[item.font]);
      style(node._label,"fontSize",(height*.014)+"px");
      if(item.kind === "camera"){
        text(node._label,item.show_label ? item.label || "Kamera" : "");text(node._value,"");
        style(node._label,"display",item.show_label ? "block" : "none");
        if(self.preview){text(node._value,"◉");text(node._detail,item.camera_source === "entity" ? item.entity_id || "Kamera auswählen" : item.camera_source === "multicast" ? "UDP-Multicast" : "Lokaler Teststream");}
        else if(window.LGCamera && self.options.cameraUrls){
          var cameraItem=item;
          if(hdmiItem && !self.options.hideHdmi && item.camera_source === "entity" && item.camera_mode === "auto" && item.x<hdmiItem.x+hdmiItem.width && hdmiItem.x<item.x+item.width && item.y<hdmiItem.y+hdmiItem.height && hdmiItem.y<item.y+item.height){
            cameraItem={};Object.keys(item).forEach(function (key) {cameraItem[key]=item[key];});cameraItem.camera_mode="snapshot";
          }
          var urls=self.options.cameraUrls(item), cameraKey=JSON.stringify([item.camera_source,item.multicast_url,item.entity_id,cameraItem.camera_mode,item.camera_interval,item.camera_fit,urls]);
          if(node._cameraKey!==cameraKey){if(node._camera){node._camera.close();}node._camera=new window.LGCamera(node,cameraItem,urls);node._cameraKey=cameraKey;}
        }
      } else {self.fill(node,item);}
      if(item.kind !== "camera" && self.options.animateWidgets && !(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches)){
        node.classList.remove("lg-widget-enter");void node.offsetWidth;node.classList.add("lg-widget-enter");
      }
      if(item.kind === "media" && window.LGCards){window.LGCards.geometry(node,item);}
    });
    Object.keys(this.nodes).forEach(function (key) { if (!wanted[key]) { self.removeNode(self.nodes[key]); delete self.nodes[key]; } });
    if (!found && this.hdmi) {
      this.cancelHdmiAnimation(); this.hdmiVisible=false; this.hdmiRect=null;
      style(this.hdmi,"visibility","hidden"); style(this.hdmi,"display","block");
      style(this.hdmi,"width","100%"); style(this.hdmi,"height","100%");
    }
  };
  Renderer.prototype.fill = function (node,item) {
    var data=this.data[item.entity_id], value="", detail="", list=[], label=item.label, timezone=this.options.timezone || "Europe/Berlin";
    var now=this.options.now || new Date();
    // Camera tickets can arrive frequently. Unchanged widgets do no formatting
    // or DOM work; only a clock's minute and its selected data invalidate it.
    var fillKey=JSON.stringify([item,data,timezone,item.kind === "clock" ? Math.floor(now.getTime()/60000) : null,item.kind === "message" ? this.options.message : null,item.kind === "weather" ? this.options.sun : null]);
    if (node._fillKey === fillKey) { return; } node._fillKey=fillKey;
    if (item.kind === "clock") {
      var clockKey=Math.floor(now.getTime()/60000)+"/"+timezone;
      if (this.clockKey !== clockKey) {
      try { value=now.toLocaleTimeString("de-DE",{hour:"2-digit",minute:"2-digit",timeZone:timezone}); detail=now.toLocaleDateString("de-DE",{weekday:"long",day:"numeric",month:"long",timeZone:timezone}); }
      catch (_) { value=("0"+now.getHours()).slice(-2)+":"+("0"+now.getMinutes()).slice(-2); detail=now.toLocaleDateString(); }
      this.clockKey=clockKey; this.clockValue=value; this.clockDetail=detail;
      } else { value=this.clockValue; detail=this.clockDetail; }
    } else if (item.kind === "text") { value=item.text; }
    else if (item.kind === "message") {
      var message=this.options.message || {title:"Home Assistant",message:"Deine Benachrichtigung erscheint hier."};
      value=message.title; detail=message.message;
      if (message.cards && message.cards.length) { list=message.cards.slice(0,6).map(function (card) {return [card.name,card.value+" "+card.unit];}); }
    } else if (!item.entity_id) { value="–"; detail="Entität auswählen"; }
    else if (!data || data.state === "unavailable" || data.state === "unknown") { value="–"; detail="Nicht verfügbar"; }
    else if (item.kind === "weather") {
      value=(data.temperature || "–")+" "+(data.temperature_unit || "°C");
      detail=(CONDITIONS[data.state] || data.state)+(data.humidity ? " · "+data.humidity+" %" : "");

    } else if (item.kind === "calendar") {
      value=(data.events || []).length ? "" : "Keine Termine";
      list=(data.events || []).slice(0,6).map(function (row) {return [dateText(row.start,timezone,true),row.summary];});
    } else {
      var states={on:"Ein",off:"Aus",home:"Zuhause",not_home:"Unterwegs",open:"Offen",closed:"Geschlossen",locked:"Verriegelt",unlocked:"Entriegelt"};
      value=(states[data.state] || data.state)+(data.unit ? " "+data.unit : "");
    }
    text(node._label,item.show_label ? label || (data && data.name) || "" : "");
    style(node._label,"display",node._label.textContent ? "block" : "none");
    text(node._value,value); text(node._detail,detail+(data && data.stale ? " · Letzter Stand" : "")); if(item.kind !== "weather"){rows(node._list,list);}
    if(item.kind === "media" && window.LGCards){window.LGCards.renderMedia(node,item,data,this.options);}
    if(item.kind === "status" && window.LGCards){window.LGCards.renderStatus(node,item,data);}
    if(item.kind === "weather" && window.LGWeather){window.LGWeather.render(node,item,data,this.options);}
  };
  Renderer.prototype.tick = function (now) {
    if (!this.scene) { return; } this.options.now=now;
    var self=this; this.scene.elements.forEach(function (item) {if (item.kind === "clock" && self.nodes[item.id]) {self.fill(self.nodes[item.id],item);}if(item.kind === "media" && self.nodes[item.id] && window.LGCards){window.LGCards.tickMedia(self.nodes[item.id],item,self.data[item.entity_id],self.options);}});
  };
  Renderer.prototype.clear = function () {
    this.cancelHdmiAnimation(); this.hdmiVisible=false; this.hdmiRect=null;
    this.clearCover();
    var self=this; Object.keys(this.nodes).forEach(function (key) {self.removeNode(self.nodes[key]);}); this.nodes={}; this.scene=null;
    this.root.classList.remove("lg-scene"); this.root.style.background=""; this.root._lgStyle={};
    if (this.hdmi) {this.hdmi.removeAttribute("style"); this.hdmi._lgStyle={};}
  };
  window.LGArtworkSize=artworkSize;
  window.LGLayoutRenderer=Renderer;
  window.LGLayoutBackground=background;
}());
