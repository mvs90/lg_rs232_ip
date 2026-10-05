/* Read-only whitelist. One operation at a time, only on an explicit HA request. */
(function () {
  "use strict";
  var active=null,last=null;
  function close(){if(active){active.cancel();active=null;}}
  window.LGPlatform={close:close,sample:function(ticket,done){
    if(!ticket || !ticket.id || ticket.id===last || active || document.hidden){return;}
    last=ticket.id;
    if(typeof window.PalmServiceBridge!=="function"){done({});return;}
    var base="luna://com.webos.service.commercial.scapadapter", result={}, timer=null, bridge=null, closed=false;
    var operations=[["usage",base+"/getSystemUsageInfo",{cpus:true,memory:true}],["sensors",base+"/deviceInfo/getSensorValues",{}],["tile",base+"/signage/getTileInfo",{}]];
    function cancel(){closed=true;clearTimeout(timer);if(bridge){bridge.onservicecallback=function(){};if(bridge.cancel){bridge.cancel();}}}
    active={cancel:cancel};
    function next(){
      if(closed){return;}
      if(!operations.length){active=null;done(result);return;}
      var op=operations.shift(),finished=false;bridge=new window.PalmServiceBridge();
      function finish(raw){
        if(finished || closed){return;}finished=true;clearTimeout(timer);bridge.onservicecallback=function(){};if(bridge.cancel){bridge.cancel();}
        var data;try{data=JSON.parse(raw);}catch(_){data={};}
        // Keep the entire request below the paired event's 4096-byte limit.
        if(op[0]==="usage" && data.returnValue===true){var memory={},cpus=[];
          ["total","used","free","buffer","cached"].forEach(function(k){if(data.memory && typeof data.memory[k]==="number"){memory[k]=data.memory[k];}});
          if(Array.isArray(data.cpus)){data.cpus.slice(0,8).forEach(function(c){var times={};["user","nice","sys","idle","irq"].forEach(function(k){if(c && c.times && typeof c.times[k]==="number"){times[k]=c.times[k];}});cpus.push({times:times});});}
          result.usage={returnValue:true,memory:memory,cpus:cpus};}
        else if(op[0]==="sensors" && data.returnValue===true){var s=result.sensors={returnValue:true};["temperature","backlight","illuminance","humidity","rotation","fan","checkscreen"].forEach(function(k){if(typeof data[k]==="number" || (typeof data[k]==="string" && data[k].length<=32)){s[k]=data[k];}});}
        else if(op[0]==="tile" && data.returnValue===true){result.tile={returnValue:true,enabled:data.enabled,row:data.row,column:data.column,tileId:data.tileId,naturalMode:data.naturalMode};}
        next();
      }
      timer=setTimeout(function(){finish("{}");},3000);
      bridge.onservicecallback=finish;
      try{bridge.call(op[1],JSON.stringify(op[2]));}catch(_){finish("{}");}
    }
    next();
  }};
}());
