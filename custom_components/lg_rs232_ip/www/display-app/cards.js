/* ES5 card artwork and state rendering; no icon font, framework or remote URL. */
(function(){
  "use strict";
  var ICONS={play:'<path d="M7 4 20 12 7 20Z" fill="currentColor" stroke="none"/>',pause:'<path d="M6 4h4v16H6zM14 4h4v16h-4z" fill="currentColor" stroke="none"/>',music:'<path d="M9 18V5l11-2v13M9 9l11-2"/><ellipse cx="6" cy="18" rx="3" ry="2"/><ellipse cx="17" cy="16" rx="3" ry="2"/>',light:'<path d="M9 18h6m-5 3h4M8 14a7 7 0 1 1 8 0l-1 2H9Z"/>',temperature:'<path d="M10 14V5a2 2 0 0 1 4 0v9a5 5 0 1 1-4 0Z"/><path d="M12 8v10"/>',humidity:'<path d="M12 2S5 10 5 15a7 7 0 0 0 14 0c0-5-7-13-7-13Z"/>',air:'<path d="M3 7h11a3 3 0 1 0-3-3M3 12h15a3 3 0 1 1-3 3M3 17h5a3 3 0 1 1-3 3"/>',door:'<path d="M5 22V3h14v19M8 22V5l8-2v19M12 12h1"/>',window:'<path d="M3 3h18v18H3Zm9 0v18M3 12h18"/>',presence:'<circle cx="12" cy="7" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3"/>',energy:'<path d="m14 2-9 12h7l-2 8 9-12h-7Z"/>',battery:'<path d="M3 7h16v10H3Zm16 3h3v4h-3M7 10v4m4-4v4m4-4v4"/>',lock:'<rect x="5" y="10" width="14" height="12" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4M12 15v3"/>',climate:'<path d="M12 2v20M3 7l18 10M3 17 21 7M8 4l4 4 4-4M8 20l4-4 4 4"/>',blinds:'<path d="M3 3h18v18H3Zm0 4h18M3 11h18M3 15h18M3 19h18"/>',plug:'<path d="M8 2v6m8-6v6M5 8h14v3a7 7 0 0 1-14 0ZM12 18v4"/>',check:'<circle cx="12" cy="12" r="9"/><path d="m7 12 3 3 7-7"/>',alert:'<path d="m12 2 10 19H2Zm0 6v6m0 3v1"/>'};
  var STATES={playing:"Wiedergabe",paused:"Pausiert",buffering:"Wird geladen",idle:"Bereit",on:"Ein",off:"Aus",standby:"Standby",unavailable:"Nicht verfügbar",unknown:"Unbekannt",open:"Offen",closed:"Geschlossen",opening:"Öffnet",closing:"Schließt",locked:"Verriegelt",unlocked:"Entriegelt",jammed:"Blockiert",heat:"Heizen",cool:"Kühlen",auto:"Automatik",heat_cool:"Automatik",dry:"Entfeuchten",fan_only:"Lüften",cleaning:"Reinigt",docked:"Ladestation",returning:"Kehrt zurück"};
  function text(node,value){value=String(value==null?"":value);if(node.textContent!==value){node.textContent=value;}}
  function child(node,cls){var el=document.createElement("div");el.className=cls;node.appendChild(el);return el;}
  function svg(node,key){if(node._iconKey===key){return;}node._iconKey=key;node.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(ICONS[key]||ICONS.check)+'</svg>';}
  function status(data){
    data=data||{};var domain=data.domain,dc=data.device_class,state=data.state||"unavailable",active=state==="on",tone="neutral",icon="check",label=STATES[state]||state,detail="";
    if(domain==="sensor"){
      icon={temperature:"temperature",humidity:"humidity",carbon_dioxide:"air",pm25:"air",pm10:"air",volatile_organic_compounds:"air",power:"energy",energy:"energy",battery:"battery",voltage:"energy",illuminance:"light"}[dc]||"check";
    }else if(domain==="binary_sensor"){
      icon={door:"door",window:"window",opening:"door",motion:"presence",occupancy:"presence",presence:"presence",smoke:"alert",gas:"alert",moisture:"humidity",problem:"alert",safety:"alert",battery:"battery",power:"energy",plug:"plug",connectivity:"plug"}[dc]||"check";
      if(state==="on"||state==="off"){
        if(["door","window","opening"].indexOf(dc)>=0){label=active?"Offen":"Geschlossen";tone=active?"warning":"good";}
        else if(["smoke","gas","moisture","problem","safety","battery"].indexOf(dc)>=0){label=active?(dc==="battery"?"Niedrig":"Erkannt"):"In Ordnung";tone=active?"alert":"good";}
        else if(["motion","occupancy","presence"].indexOf(dc)>=0){label=active?"Erkannt":"Frei";tone=active?"active":"neutral";}
        else if(dc==="connectivity"){label=active?"Verbunden":"Getrennt";tone=active?"good":"warning";}
      }
    }else{
      icon={light:"light",switch:"plug",climate:"climate",cover:"blinds",lock:"lock",fan:"air",humidifier:"humidity",vacuum:"check"}[domain]||"check";
      if(active||state==="heat"||state==="cool"||state==="cleaning"){tone="active";}
      if(domain==="lock"){tone=state==="locked"?"good":state==="unlocked"?"warning":"neutral";}
      if(state==="jammed"){tone="alert";}
      if(domain==="light"&&active&&typeof data.brightness==="number"){detail=Math.round(data.brightness/255*100)+" % Helligkeit";}
      if(domain==="climate"&&typeof data.current_temperature==="number"){detail=data.current_temperature+"°"+(typeof data.temperature==="number"?" · Ziel "+data.temperature+"°":"");}
      if(domain==="cover"&&typeof data.current_position==="number"){detail=data.current_position+" % geöffnet";}
      if(domain==="fan"&&active&&typeof data.percentage==="number"){detail=data.percentage+" %";}
    }
    if(state==="unavailable"||state==="unknown"){tone="neutral";detail="";}
    return {icon:icon,tone:tone,value:label+(data.unit&&state!=="unavailable"&&state!=="unknown"?" "+data.unit:""),detail:detail};
  }
  function renderStatus(node,item,data){
    if(!node._statusIcon){node._statusIcon=child(node,"lg-status-icon");node._statusBadge=child(node,"lg-status-badge");}
    var value=status(data);svg(node._statusIcon,value.icon);var tone=item.status_coloring===false?"neutral":value.tone;
    node.setAttribute("data-tone",tone);var color={neutral:"#9caec0",good:"#91d7b8",warning:"#f2c26f",alert:"#ff918d",active:item.accent_color||"#79e5c0"}[tone];node._statusIcon.style.color=color;node._statusBadge.style.background=color;
    text(node._value,data?value.value:"–");text(node._detail,data?value.detail:"Entität auswählen");
  }
  function timeLabel(seconds){seconds=Math.max(0,Math.floor(seconds||0));return (seconds>=3600?Math.floor(seconds/3600)+":"+("0"+Math.floor(seconds/60)%60).slice(-2):Math.floor(seconds/60))+":"+("0"+seconds%60).slice(-2);}
  function art(node,item,data,options){
    var key=item.show_cover!==false&&data&&data.artwork,area=node._mediaArt,img=node._mediaImage;
    var visibility=item.show_cover===false?"none":"block";if(area.style.display!==visibility){area.style.display=visibility;}
    if(key!==node._artKey){node._artKey=key;node._artRetry=0;node._artUrl=null;area.classList.remove("loaded");img.removeAttribute("src");}
    if(!key||!options.mediaUrl||node._artRetry>Date.now()){return;}
    var pixels=Math.max(area.clientWidth,area.clientHeight)*(window.devicePixelRatio || 1);
    var url=options.mediaUrl(item.entity_id,key,window.LGArtworkSize ? window.LGArtworkSize(pixels) : 640);if(!url){return;}
    if(url!==node._artUrl||node._artRetry){node._artUrl=url;var retry=node._artRetry;node._artRetry=0;img.src=url+(retry&&url.indexOf("blob:")!==0?"&retry="+Math.floor(Date.now()/30000):"");}
  }
  function renderMedia(node,item,data,options){
    if(!node._mediaArt){
      node._mediaArt=child(node,"lg-media-art");node._mediaPlaceholder=child(node._mediaArt,"lg-media-placeholder");svg(node._mediaPlaceholder,"music");
      node._mediaImage=document.createElement("img");node._mediaImage.alt="";node._mediaArt.appendChild(node._mediaImage);node._mediaShade=child(node,"lg-media-shade");
      node._mediaImage.onload=function(){node._mediaArt.classList.add("loaded");node._artRetry=0;};
      node._mediaImage.onerror=function(){node._mediaArt.classList.remove("loaded");node._artRetry=Date.now()+30000;};
      node._mediaAlbum=child(node,"lg-media-album");node._mediaProgress=child(node,"lg-media-progress");node._mediaPlayback=child(node._mediaProgress,"lg-media-playback");node._mediaPlayback.setAttribute("role","img");node._mediaBar=child(node._mediaProgress,"lg-media-bar");node._mediaFill=child(node._mediaBar,"lg-media-fill");node._mediaElapsed=child(node._mediaProgress,"lg-media-elapsed");node._mediaDuration=child(node._mediaProgress,"lg-media-duration");node._mediaVolume=child(node,"lg-media-volume");
    }
    var state=data?data.state:"unavailable",valid=data&&["off","standby","unavailable","unknown"].indexOf(state)<0;
    node.setAttribute("data-media-style",item.media_style||"compact");node.setAttribute("data-cover",item.show_cover===false?"off":"on");node.setAttribute("data-playing",state==="playing"?"true":"false");
    node._mediaFill.style.background=item.accent_color||"#79e5c0";
    text(node._value,valid?(data.media_title||data.source||data.name||"Keine Titelinformationen"):data?(data.name||item.label||"Mediaplayer"):"Deine Musik");
    text(node._detail,valid?(data.media_artist||data.app_name||""):"");text(node._mediaAlbum,valid?(data.media_album_name||""):"");
    text(node._mediaVolume,item.show_volume!==false&&valid?(data.is_volume_muted?"Stumm":typeof data.volume_level==="number"?"Lautstärke "+Math.round(data.volume_level*100)+" %":""):"");
    geometry(node,item);tickMedia(node,item,data,options);
  }
  function geometry(node,item){
    if(!node._mediaArt){return;}var size=item.media_style==='poster'?'100%':Math.round(Math.min(node.clientWidth*(item.media_style==='stage' ? .44 : .32),node.clientHeight*(item.media_style==='stage' ? .94 : .76)))+"px";
    if(node._mediaArt.style.width!==size){node._mediaArt.style.width=size;node._mediaArt.style.height=size;node._mediaArt.style.paddingBottom="0";}
  }
  function tickMedia(node,item,data,options){
    if(!node._mediaArt){return;}art(node,item,data,options);
    var duration=data&&data.media_duration,pos=data&&data.media_position,visible=item.show_progress!==false&&typeof duration==="number"&&duration>0&&typeof pos==="number"&&["playing","paused","buffering"].indexOf(data.state)>=0;
    var showIcon=visible&&item.show_playback_icon===true&&["playing","paused"].indexOf(data.state)>=0;
    var icon=showIcon?data.state:"";
    if(node._playbackState!==icon){
      node._playbackState=icon;node._mediaProgress.setAttribute("data-playback-icon",showIcon?"true":"false");node._mediaPlayback.style.display=showIcon?"block":"none";
      if(showIcon){svg(node._mediaPlayback,icon==="playing"?"play":"pause");node._mediaPlayback.setAttribute("aria-label",STATES[icon]);}
      else{node._mediaPlayback.removeAttribute("aria-label");}
    }
    var display=visible?"block":"none";if(node._mediaProgress.style.display!==display){node._mediaProgress.style.display=display;}if(!visible){return;}
    var updated=new Date(data.media_position_updated_at).getTime(),now=(options.now||new Date()).getTime();if(data.state==="playing"&&isFinite(updated)&&updated>0){pos+=Math.max(0,(now-updated)/1000);}
    pos=Math.min(duration,Math.max(0,pos));var width=Math.round(pos/duration*1000)/10+"%";if(node._mediaFill.style.width!==width){node._mediaFill.style.width=width;}
    text(node._mediaElapsed,timeLabel(pos));text(node._mediaDuration,timeLabel(duration));
  }
  window.LGCards={geometry:geometry,status:status,renderStatus:renderStatus,renderMedia:renderMedia,tickMedia:tickMedia};
}());
