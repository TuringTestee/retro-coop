const raf=requestAnimationFrame.bind(window),cancel=cancelAnimationFrame.bind(window),pending=new Map();let held=true,id=0;
    window.requestAnimationFrame=fn=>held?(pending.set(++id,fn),id):raf(fn);
    window.cancelAnimationFrame=n=>held?pending.delete(n):cancel(n);
    window.releaseFrames=()=>{held=false;for(const fn of pending.values())raf(fn);pending.clear()};
    window.proof={hashes:[],rooms:[],frames:[],frameCount:0,sentHashes:[],timing:{workerMs:0,workerMax:0,frameGaps:[]}};
    proof.events=[];proof.pacing=[];let epochAt=0,epochFrames=0,epochStartFrame=0;
    const note=(kind,detail={})=>{proof.events.push({at:Math.round(performance.now()),kind,...detail});if(proof.events.length>128)proof.events.shift()};
    setInterval(()=>{if(epochAt){proof.pacing.push({at:Math.round(performance.now()-epochAt),frames:epochFrames});if(proof.pacing.length>64)proof.pacing.shift()}},1000);
    proof.admission={received:{input:0,frame:0},lead:{},lateInputs:0,lateInputWaitMs:0,maxInputGapMs:0,hashMs:0,hashMaxMs:0,hashCount:0,nonceRttMs:[]};
    let workerPending=false,lastInputAt=0,hashAt=0;const probes=new Map();
    const observeChannel=channel=>channel.addEventListener('message',({data})=>{let packet;try{packet=JSON.parse(data)}catch{return}const now=performance.now();
      if(packet.type==='transportReply'&&probes.has(packet.nonce)){proof.admission.nonceRttMs.push(now-probes.get(packet.nonce));probes.delete(packet.nonce);}
      if((packet.kind==='input'||packet.kind==='frame')&&packet.epoch===proof.activeEpoch){proof.admission.received[packet.kind]++;const lead=packet.kind==='frame'?packet.frame-epochStartFrame-epochFrames:undefined;if(lead!==undefined)proof.admission.lead[lead]=(proof.admission.lead[lead]||0)+1;if(lastInputAt)proof.admission.maxInputGapMs=Math.max(proof.admission.maxInputGapMs,now-lastInputAt);lastInputAt=now;if(lead===0&&!workerPending&&lastFrame){proof.admission.lateInputs++;proof.admission.lateInputWaitMs+=now-lastFrame;}}
    });
    const P=RTCPeerConnection;window.RTCPeerConnection=class extends P{constructor(...a){super(...a);this.addEventListener('datachannel',({channel})=>observeChannel(channel));for(const event of ['connectionstatechange','iceconnectionstatechange','icegatheringstatechange'])this.addEventListener(event,()=>note(event,{connection:this.connectionState,ice:this.iceConnectionState,gathering:this.iceGatheringState}));}createDataChannel(...a){const channel=super.createDataChannel(...a);observeChannel(channel);return channel;}};
    const ds=RTCDataChannel.prototype.send;RTCDataChannel.prototype.send=function(data){if(typeof data==='string'){let d=JSON.parse(data);if(d.type==='transportProbe')probes.set(d.nonce,performance.now());
      if(d.kind==='input'&&window.gameFault==='drop-input')return;
      if(d.kind==='hash'&&window.gameFault==='drop-hash')return;
      if(d.kind==='hash'&&window.gameFault==='bad-hash'){d={...d,hash:'0'.repeat(64)};data=JSON.stringify(d);window.gameFault=undefined;}
      if((d.kind==='input'||d.kind==='frame')&&window.gameFault==='old-epoch'){ds.call(this,JSON.stringify({...d,epoch:'obsolete'.repeat(4)}));window.gameFault=undefined;}
      if(d.kind==='input'&&window.gameFault==='stale-assignment'){d={...d,revision:d.revision+1};data=JSON.stringify(d);window.gameFault=undefined;}
      if(d.kind==='input'&&window.gameFault==='duplicate-input'){ds.call(this,data);window.gameFault=undefined;}
      if(d.kind==='hash')proof.sentHashes.push(d);}return ds.call(this,data)};
    let lastFrame=0,workerStart=0;
    // A rejected candidate must not replace the active emulator used by native probes.
    const W=Worker,liveWorkers=new Set();window.Worker=class extends W{terminate(){liveWorkers.delete(this);if(window.currentWorker===this)window.currentWorker=[...liveWorkers].at(-1);super.terminate()}postMessage(data,...rest){if(data.type==='state-hash'){hashAt=performance.now();const target=proof.finalHashDelay;if(target?.frame!==undefined&&target.requestId===undefined&&proof.frames.at(-1)?.frame+1===target.frame)target.requestId=data.requestId;}if(data.type==='frame'&&data.epoch){workerStart=performance.now();workerPending=true;}return super.postMessage(data,...rest)}constructor(...a){super(...a);liveWorkers.add(this);window.currentWorker??=this;this.addEventListener('message',event=>{const {data}=event;
// Hold one real native hash response; neither its frame nor hash is changed.
if(data.type==='state-hash'&&data.requestId===proof.finalHashDelay?.requestId&&!event.hashDelivered){proof.finalHashDelay.response={requestId:data.requestId,...data.info};proof.delayedHashes=(proof.delayedHashes||0)+1;event.stopImmediatePropagation();setTimeout(()=>{const delayed=new MessageEvent('message',{data});Object.defineProperty(delayed,'hashDelivered',{value:true});this.dispatchEvent(delayed)},proof.finalHashDelay.delayMs??500);return;}
if(data.type==='state-hash'&&proof.finalHashDelay&&proof.finalHashDelay.frame===undefined&&proof.room?.game.status==='playing'&&data.info.frame%120===0&&data.info.frame>proof.finalHashDelay.armedFrame)proof.finalHashDelay.periodic.push({requestId:data.requestId,...data.info});
// Diagnostic delivery delay leaves the native frame and its inputs unchanged.
if(data.type==='frame'&&data.epoch&&window.workerFloorMs&&!event.floorDelivered){const remaining=window.workerFloorMs-(performance.now()-workerStart);if(remaining>0){event.stopImmediatePropagation();const receipt={epoch:data.epoch,frame:data.frame,heldAt:performance.now()};proof.workerDelay=receipt;setTimeout(()=>{const delayed=new MessageEvent('message',{data});Object.defineProperty(delayed,'floorDelivered',{value:true});this.dispatchEvent(delayed);receipt.deliveredAt=performance.now()},remaining);return;}}
if(data.type==='ready')proof.fps=data.fps;if(data.type==='state-history'&&data.requestId===900002)proof.localHistory=data.info;if(data.type==='state-exported'&&[900000,900001].includes(data.requestId))proof[data.requestId===900000?'controllerRam':'chatRam']=JSON.parse(new TextDecoder().decode(data.bytes.slice(72))).hardware.wram.slice(0,2);if(data.type==='state-hash'){const elapsed=performance.now()-hashAt;proof.admission.hashMs+=elapsed;proof.admission.hashMaxMs=Math.max(proof.admission.hashMaxMs,elapsed);proof.admission.hashCount++;proof.hashes.push(data.info);}if(data.type==='frame'&&data.epoch){workerPending=false;epochFrames++;if(window.scriptKey&&(data.frame+1)%60===0){window.dispatchEvent(new KeyboardEvent((data.frame+1)%120===0?'keyup':'keydown',{code:window.scriptKey}));proof.scriptedInputs=(proof.scriptedInputs||0)+1;}const now=performance.now(),elapsed=now-workerStart;proof.timing.workerMs+=elapsed;proof.timing.workerMax=Math.max(proof.timing.workerMax,elapsed);if(lastFrame){const bucket=Math.min(200,Math.round(now-lastFrame));proof.timing.frameGaps[bucket]=(proof.timing.frameGaps[bucket]||0)+1}lastFrame=now;proof.frameCount++;proof.frames.push({epoch:data.epoch,frame:data.frame});if(proof.frames.length>12)proof.frames.shift()}})}};
    const peerMembers=new Map(),requiredPairs=new Set();proof.stopEvents=[];
    const activeOwner=member=>!!member&&!!proof.room&&(member===proof.room.hostMembership||proof.room.game?.controllers?.owners?.includes(member));
    const requiredPeer=pairId=>!peerMembers.has(pairId)||proof.room?.chatMembership!==proof.room?.hostMembership&&peerMembers.get(pairId)===proof.room?.hostMembership;
    const stop=(type,pairId,reason)=>{
      const required=type!=='peerStop'&&type!=='peerFailed'||requiredPeer(pairId);
      proof.stopEvents.push({type,pairId,member:peerMembers.get(pairId),required,reason,at:Math.round(performance.now())});
      if(required)proof.workloadStopped=true;
    };
    const S=WebSocket;window.WebSocket=class extends S{
      send(data){
        const value=JSON.parse(data);
        if(value.type==='gameAbort'||value.type==='peerFailed')stop(value.type,value.pairId,value.reason);
        if(['join','joinCode','leave','gamePause','gameAbort','peerFailed','heartbeat'].includes(value.type))note('send',{type:value.type,reason:value.reason,frame:value.frame,sinceStart:epochAt?Math.round(performance.now()-epochAt):undefined,epochFrames});
        if(value.type==='gameReady')proof.gameReadies=(proof.gameReadies||0)+1;
        if(value.type==='gameAck'&&window.dropGameAck){proof.droppedAcks=(proof.droppedAcks||0)+1;return;}
        return super.send(data);
      }
      constructor(...a){
        super(...a);proof.roomSocket=this;
        this.addEventListener('close',e=>{stop('socketClose',undefined,e.code);note('socket-close',{code:e.code})});
        this.addEventListener('message',event=>{
          const {data}=event,e=JSON.parse(data);
          if(e.type==='peerPrepare')peerMembers.set(e.pairId,e.member);
          if(e.type==='gamePauseAt'&&proof.finalHashDelay&&proof.finalHashDelay.frame===undefined){proof.finalHashDelay.frame=e.frame;proof.finalHashDelay.epoch=e.epoch;}
          if(e.type==='peerStop'||e.type==='gameStop')stop(e.type,e.pairId,e.reason);
          if(e.type==='gameStart')proof.workloadStopped=false;
          if(['peerStop','gameStop','gamePauseAt','gameStart'].includes(e.type))note('receive',{type:e.type,pairId:e.pairId,member:peerMembers.get(e.pairId),required:e.type==='peerStop'?requiredPeer(e.pairId):undefined,reason:e.reason});
          if(e.type==='gameStart'&&window.delayStart){window.delayStart=false;proof.delayedStarts=(proof.delayedStarts||0)+1;event.stopImmediatePropagation();setTimeout(()=>this.dispatchEvent(new MessageEvent('message',{data})),250);return;}
          if(e.type==='gameStart'){proof.activeEpoch=e.epoch;lastInputAt=0;lastFrame=0;epochAt=performance.now();epochFrames=0;epochStartFrame=e.frame??0;}
          if(e.type==='room'){
            proof.room=e.room;proof.rooms.push({established:e.room.established,status:e.room.game?.status});
            for(const peer of e.room.peers??[]){peerMembers.set(peer.pairId,peer.member);if(activeOwner(peer.member))requiredPairs.add(peer.pairId);}
          }
        });
      }
    };
