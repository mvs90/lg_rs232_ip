/* Fixed SCAP video-wall transaction; read, apply, verify, restore on failure. */
(function () {
  "use strict";
  var last=null;
  function valid(data){return data && typeof data.enabled==="boolean" && typeof data.naturalMode==="boolean" && ["row","column","tileId"].every(function(k){return typeof data[k]==="number" && data[k]===Math.floor(data[k]) && data[k]>=1;}) && data.row<=15 && data.column<=15 && data.tileId<=data.row*data.column;}
  function clean(data){return {enabled:data.enabled,row:data.row,column:data.column,tileId:data.tileId,naturalMode:data.naturalMode};}
  function same(a,b){return valid(a) && valid(b) && JSON.stringify(clean(a))===JSON.stringify(clean(b));}
  function call(method,parameters,done){
    var b=new window.PalmServiceBridge(),finished=false;
    function finish(raw){if(finished){return;}finished=true;clearTimeout(timer);b.onservicecallback=function(){};if(b.cancel){b.cancel();}var d;try{d=JSON.parse(raw);}catch(_){d={};}done(d);}
    var timer=setTimeout(function(){finish("{}");},3000);b.onservicecallback=finish;
    try{b.call("luna://com.webos.service.commercial.scapadapter/signage/"+method,JSON.stringify(parameters));}catch(_){finish("{}");}
  }
  window.LGVideoWall=function(ticket,done){
    if(!ticket || last===ticket.id){return;}last=ticket.id;
    if(typeof window.PalmServiceBridge!=="function" || document.hidden){done({ok:false,restored:true,reason:"unavailable"});return;}
    call("getTileInfo",{},function(before){
      if(before.returnValue!==true || !valid(before)){done({ok:false,restored:true,reason:"invalid_readback"});return;}
      var target=clean(before),settings=ticket.settings || {};
      ["enabled","row","column","tileId","naturalMode"].forEach(function(key){if(Object.prototype.hasOwnProperty.call(settings,key)){target[key]=settings[key];}});
      if(!valid(target)){done({ok:false,restored:true,reason:"invalid_geometry"});return;}
      if(same(before,target)){done({ok:true});return;}
      call("setTileInfo",{tileInfo:target},function(applied){
        call("getTileInfo",{},function(after){
          if(after.returnValue===true && same(after,target)){done({ok:true});return;}
          call("setTileInfo",{tileInfo:clean(before)},function(){call("getTileInfo",{},function(restored){done({ok:false,restored:restored.returnValue===true && same(restored,before),reason:applied.returnValue===true ? "verification_failed" : "native_rejected",error_code:typeof applied.errorCode==="number" ? applied.errorCode : null});});});
        });
      });
    });
  };
}());
