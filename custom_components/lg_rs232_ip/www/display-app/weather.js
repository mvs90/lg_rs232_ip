/* Local ES5 weather artwork. Only the current symbol animates; forecasts stay still. */
(function () {
  "use strict";
  var SVG='<svg viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">';
  var SUN='<g class="wx-rays" stroke="#f9cb65" stroke-width="3" stroke-linecap="round"><path d="M40 9v7m0 48v7M9 40h7m48 0h7M18 18l5 5m34 34l5 5M18 62l5-5m34-34l5-5"/></g><circle cx="40" cy="40" r="16" fill="#ffd77d"/>';
  var MOON='<path d="M53 12A28 28 0 1 0 69 54 27 27 0 0 1 53 12" fill="#d4e7ff"/><circle cx="61" cy="23" r="2" fill="#f7eccb"/><circle cx="69" cy="34" r="1.5" fill="#f7eccb"/>';
  var CLOUD='<path class="wx-cloud" d="M20 58h40a13 13 0 0 0 1-26 21 21 0 0 0-39-3 15 15 0 0 0-2 29Z" fill="#ecf4fc" stroke="#93aabd" stroke-width="1.5"/>';
  var DROP='<g class="wx-drops" stroke="#79bfff" stroke-width="3" stroke-linecap="round"><path d="m25 64-3 7m19-7-3 7m19-7-3 7"/></g>';
  var SNOW='<g class="wx-drops" fill="#d8eeff"><circle cx="25" cy="67" r="2.7"/><circle cx="40" cy="72" r="2.7"/><circle cx="55" cy="67" r="2.7"/></g>';
  var TYPES={sun:SUN,moon:MOON,cloud:CLOUD,partly:SUN+CLOUD,nightcloud:MOON+CLOUD,rain:CLOUD+DROP,snow:CLOUD+SNOW,storm:CLOUD+'<path d="m43 46-13 18h10l-4 13 16-21H41l6-10" fill="#ffc45c"/>',fog:CLOUD+'<path d="M13 66h53M20 73h40" stroke="#b9cedb" stroke-width="3" stroke-linecap="round"/>',wind:'<g stroke="#b1d6e8" stroke-width="4" fill="none" stroke-linecap="round"><path d="M9 31h43c18 0 18-22 3-22M9 43h58c11 0 11 15 1 15M18 56h23c13 0 13 16 0 16"/></g>'};
  var CONDITIONS={sunny:"Sonnig",clear:"Klar","clear-night":"Klare Nacht",cloudy:"Bewölkt",partlycloudy:"Wolkig",rainy:"Regen",pouring:"Starker Regen",snowy:"Schnee","snowy-rainy":"Schneeregen",fog:"Nebel",windy:"Windig","windy-variant":"Windig",lightning:"Gewitter","lightning-rainy":"Gewitter",hail:"Hagel",exceptional:"Ungewöhnliches Wetter"};
  function type(condition,day) {
    if (condition === "sunny" || condition === "clear" || condition === "clear-night") {return day === false ? "moon" : "sun";}
    if (condition === "partlycloudy") {return day === false ? "nightcloud" : "partly";}
    if (condition === "rainy" || condition === "pouring") {return "rain";}
    if (condition === "snowy" || condition === "snowy-rainy" || condition === "hail") {return "snow";}
    if (condition === "lightning" || condition === "lightning-rainy") {return "storm";}
    if (condition === "fog") {return "fog";}
    if (condition === "windy" || condition === "windy-variant") {return "wind";}
    return "cloud";
  }
  function icon(node,condition,day,animated) {
    var key=type(condition,day);
    if (node._wxType !== key) {node.innerHTML=SVG+TYPES[key]+'</svg>';node._wxType=key;}
    var cls="lg-weather-icon"+(animated ? " wx-animated" : "");if (node.className !== cls) {node.className=cls;}
  }
  function mix(a,b,t) {return "rgb("+a.map(function(v,i){return Math.round(v+(b[i]-v)*t);}).join(",")+")";}
  function sky(sun) {
    sun=sun || {};var e=typeof sun.elevation === "number" ? sun.elevation : (sun.is_daytime ? 30 : -18),r=sun.rising;
    var stops=[-18,-6,0,12,40],tops=[[8,16,38],[25,31,66],r?[58,69,105]:[66,43,92],[38,104,151],[36,126,176]],bottoms=[[21,35,61],[79,58,91],r?[226,153,123]:[201,119,135],[159,197,210],[168,216,226]],i=0;
    while(i<stops.length-2 && e>stops[i+1]){i++;}
    var t=Math.max(0,Math.min(1,(e-stops[i])/(stops[i+1]-stops[i]))),x=typeof sun.azimuth === "number" ? Math.round(sun.azimuth/360*80+10) : 65;
    return "radial-gradient(ellipse at "+x+"% "+Math.round(Math.max(15,75-e))+"%,rgba(255,205,155,"+Math.round((Math.max(0,1-Math.abs(e-3)/22)*.2+(e>0?.06:0))*1000)/1000+"),transparent 65%),linear-gradient(160deg,"+mix(tops[i],tops[i+1],t)+","+mix(bottoms[i],bottoms[i+1],t)+")";
  }
  function set(node,value){value=String(value==null?"":value);if(node.textContent!==value){node.textContent=value;}}
  function child(parent,cls){var el=document.createElement("div");el.className=cls;parent.appendChild(el);return el;}
  function period(value,hourly,timezone){
    var date=new Date(value);if(isNaN(date.getTime())){return "";}
    try{return hourly?date.toLocaleTimeString("de-DE",{hour:"2-digit",minute:"2-digit",timeZone:timezone}):date.toLocaleDateString("de-DE",{weekday:"short",day:"2-digit",timeZone:timezone});}catch(_){return "";}
  }
  function render(node,item,data,options){
    if(!node._weatherIcon){node._weatherIcon=child(node,"lg-weather-icon");}
    var valid=data && data.state!=="unknown" && data.state!=="unavailable",sun=options.sun,day=sun?sun.is_daytime:data && data.state!=="clear-night";
    node._weatherIcon.style.display=valid?"block":"none";
    if(!valid){while(node._list.firstChild){node._list.removeChild(node._list.firstChild);}return;}
    icon(node._weatherIcon,data.state,day,item.animate!==false);
    var mode=item.forecast_type || "daily", forecasts=data.forecasts || {}, entries=(forecasts[mode] || (mode==="daily"?data.forecast:[]) || []).slice(0,item.forecast_count || 4);
    if(mode==="current"){entries=[];}
    var list=node._list;
    for(var i=0;i<entries.length;i++){
      var row=list.children[i],entry=entries[i];
      if(!row || row.className!=="lg-forecast-period"){
        if(row){list.removeChild(row);}
        row=document.createElement("div");row.className="lg-forecast-period";list.insertBefore(row,list.children[i] || null);
        child(row,"lg-period-time");child(row,"lg-weather-icon");child(row,"lg-period-temp");child(row,"lg-period-low");child(row,"lg-period-rain");
      }
      set(row.children[0],period(entry.datetime,mode==="hourly",options.timezone));
      icon(row.children[1],entry.condition,mode==="daily"?true:entry.is_daytime,false);
      set(row.children[2],entry.temperature ? entry.temperature+"°" : "–");
      set(row.children[3],mode==="daily" && entry.templow ? entry.templow+"°" : "");
      set(row.children[4],entry.precipitation_probability!=="" && entry.precipitation_probability!=null ? entry.precipitation_probability+" %" : "");
    }
    while(list.children.length>entries.length){list.removeChild(list.lastChild);}
    if(mode!=="current" && !entries.length){set(node._detail,(CONDITIONS[data.state] || data.state)+" · "+(mode==="hourly"?"Stundenprognose":"Tagesprognose")+" nicht verfügbar");}
  }
  window.LGWeather={sky:sky,render:render,icon:icon};
}());
