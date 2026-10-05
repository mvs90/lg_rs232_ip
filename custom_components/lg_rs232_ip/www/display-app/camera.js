/* ES5, one additional decoder. Work exists only while its widget is visible. */
(function () {
  "use strict";
  function Camera(node, item, urls) {
    this.node=node; this.item=item; this.urls=urls; this.timers=[]; this.closed=false;
    this.box=document.createElement("div"); this.box.className="lg-camera-picture";
    node.appendChild(this.box);
    var self=this;
    this.visibility=function () {self.stop();if(!document.hidden){self.start();}};
    document.addEventListener("visibilitychange",this.visibility);
    if(!document.hidden){this.start();}
  }
  Camera.prototype.later=function (fn, delay) {
    var self=this, timer=window.setTimeout(function () {
      var index=self.timers.indexOf(timer);if(index!==-1){self.timers.splice(index,1);}
      if(!self.closed && !document.hidden){fn();}
    },delay);this.timers.push(timer);return timer;
  };
  Camera.prototype.stop=function () {
    this.generation=(this.generation || 0)+1;
    this.timers.forEach(function (timer) {window.clearTimeout(timer);});this.timers=[];
    if(this.xhr){this.xhr.abort();this.xhr=null;}
    if(this.image){this.image.onload=this.image.onerror=null;this.image.removeAttribute("src");this.image=null;}
    if(this.video){this.video.onerror=this.video.onloadeddata=null;this.video.pause();this.video.removeAttribute("src");this.video.load();this.video=null;}
    while(this.box.firstChild){this.box.removeChild(this.box.firstChild);}
  };
  Camera.prototype.close=function () {
    this.closed=true;this.stop();document.removeEventListener("visibilitychange",this.visibility);
    this.node.removeChild(this.box);
  };
  Camera.prototype.status=function (value) {this.node._detail.textContent=value;};
  Camera.prototype.start=function () {
    var self=this, generation=this.generation;
    this.status("Verbinden …");
    if(this.item.camera_source === "test"){this.stream(this.urls.test);return;}
    if(!this.item.entity_id){this.status("Kamera auswählen");return;}
    if(this.item.camera_mode === "snapshot"){this.snapshots();return;}
    var xhr=this.xhr=new XMLHttpRequest();xhr.open("GET",this.urls.info,true);xhr.timeout=12000;
    function complete() {
      if(self.closed || generation!==self.generation){return;}self.xhr=null;
      var data;try{data=JSON.parse(xhr.responseText);}catch(_){data={};}
      if(xhr.status===200 && typeof data.stream === "string" && data.stream.indexOf("/api/hls/")===0){self.stream(data.stream);}
      else{self.fallback();}
    }
    xhr.onload=complete;xhr.onerror=complete;xhr.ontimeout=complete;xhr.send();
  };
  Camera.prototype.fallback=function () {
    var self=this;this.stop();
    if(this.closed || document.hidden){return;}
    if(this.item.camera_source!=="test" && this.item.camera_mode!=="stream"){this.snapshots();}
    else{this.status("Stream nicht verfügbar");}
    // One retry per minute, no repeated decoder construction on HA state polls.
    this.later(function () {self.stop();self.start();},60000);
  };
  Camera.prototype.stream=function (url) {
    var self=this, video=this.video=document.createElement("video"), generation=this.generation;
    video.autoplay=true;video.muted=true;video.loop=true;video.setAttribute("muted","");video.setAttribute("playsinline","");
    video.style.objectFit=this.item.camera_fit || "contain";this.box.appendChild(video);
    video.onloadeddata=function () {if(generation===self.generation){self.status("");}};
    video.onerror=function () {if(generation===self.generation){self.fallback();}};
    video.src=url;var promise=video.play();if(promise && promise.catch){promise.catch(function () {if(generation===self.generation){self.fallback();}});}
    var last=-1, stalled=0;
    function check() {
      if(generation!==self.generation){return;}
      if(video.currentTime===last || video.readyState<2){stalled+=5;}else{stalled=0;last=video.currentTime;}
      if(stalled>=15){self.fallback();return;}self.later(check,5000);
    }
    this.later(check,5000);
  };
  Camera.prototype.snapshots=function () {
    var self=this, generation=this.generation, image=this.image=document.createElement("img"), waiting=false;
    image.alt="Kamerabild";image.style.objectFit=this.item.camera_fit || "contain";image.style.visibility="hidden";this.box.appendChild(image);
    this.status("Einzelbilder …");
    function next(ok) {
      if(generation!==self.generation || !waiting){return;}waiting=false;
      window.clearTimeout(watchdog);var timerIndex=self.timers.indexOf(watchdog);if(timerIndex!==-1){self.timers.splice(timerIndex,1);}
      if(ok && image.naturalWidth){image.style.visibility="visible";self.status("");}
      else{image.style.visibility="hidden";self.status("Kamera nicht verfügbar");}
      self.later(load,ok ? Math.max(1,self.item.camera_interval || 2)*1000 : 10000);
    }
    var watchdog;
    function load() {
      if(waiting){return;}waiting=true;
      image.onload=function () {next(true);};image.onerror=function () {next(false);};
      image.src=self.urls.image+"&t="+Date.now();watchdog=self.later(function () {next(false);},12000);
    }
    load();
  };
  window.LGCamera=Camera;
}());
