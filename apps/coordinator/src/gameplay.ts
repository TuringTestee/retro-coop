import {randomBytes} from 'node:crypto';
import {gameplayLimits,type GameCommand,type GameEvent,type GameView,type ControllerAssignment,type RoleTransaction,type CheckpointPurpose} from '../../../packages/contracts/src/gameplay.ts';
type Offer=Extract<GameCommand,{type:'gameReady'}>;
type Member={id:string;connected:boolean;loaded:boolean;hostTransport:boolean;allLinksReady:boolean};
type Transfer={id:string;recipient:string;purpose:CheckpointPurpose;frame?:number;hash?:string;sending:boolean;deadline:number;catchingUp?:boolean};
const id=()=>randomBytes(24).toString('base64url');
/** Room-owned authority and barriers. Every occupant gates initial Start; owners alone gate live play. */
export class GameSession {
 private host='';private members=new Map<string,Member>();private offers=new Map<string,Offer>();private acks=new Set<string>();private required:string[]=[];
 private roomRevision?:number;
 private hasPlayed=false;private transfers=new Map<string,Transfer>();private deadline=0;private hash?:string;private frame=0;private proposed?:ControllerAssignment;
 private state:GameView={controllers:{owners:[null,null],revision:0},ready:[],startRequested:false,status:'waiting'};
 private now:()=>number;private send:(member:string,event:GameEvent)=>void;private commitRoles:(pending:RoleTransaction)=>ControllerAssignment;
 constructor(now:()=>number,send:(member:string,event:GameEvent)=>void,commitRoles:(pending:RoleTransaction)=>ControllerAssignment){this.now=now;this.send=send;this.commitRoles=commitRoles;}
 view():GameView{return {...this.state,ready:[...this.offers.keys()],frame:this.frame};}
 private all(event:GameEvent){for(const member of this.members.keys())this.send(member,event);}
 private owners(assignment=this.state.controllers){return [...new Set([this.host,...assignment.owners.filter((owner):owner is string=>!!owner)])];}
 configure(host:string,members:Member[],controllers:ControllerAssignment,revision?:number){
  const previous=this.members;this.host=host;this.members=new Map(members.map(member=>[member.id,member]));
  if(!this.state.pending)this.state.controllers=controllers;
  if(!this.state.epoch){
   if(this.roomRevision!==undefined&&revision!==undefined&&revision!==this.roomRevision)this.offers.clear();
   for(const [member,offer] of this.offers)if(!this.available(member)||offer.revision!==this.state.controllers.revision||offer.roomRevision!==(revision??this.roomRevision??0))this.offers.delete(member);
  }
  if(revision!==undefined)this.roomRevision=revision;
  const changed=[...previous.values()].some(old=>!this.members.has(old.id)||old.connected&&!this.members.get(old.id)!.connected||old.hostTransport&&!this.members.get(old.id)!.hostTransport);
  for(const transfer of [...this.transfers.values()])if(!this.available(transfer.recipient))this.cancelTransfer(transfer,'Connection changed. Retry synchronization.');
  if((changed||revision!==undefined&&this.state.pending?.revision!==revision)&&this.state.pending)this.failTransaction('Membership changed. Previous roles and game progress are preserved.');
  if(this.state.status==='starting'&&(!this.hasPlayed?[...this.members.keys()].some(member=>!this.available(member)):this.required.some(owner=>!this.available(owner))))this.stop('A prepared member disconnected. Previous progress is preserved; prepare again when everyone is connected.');
  if(this.state.status==='playing'&&this.owners().some(owner=>!this.available(owner)))this.freeze('A controller owner disconnected. Game progress is preserved.');
 }
 private available(member:string){const value=this.members.get(member);return !!value?.connected&&value.loaded&&(this.hasPlayed?member===this.host||value.hostTransport:value.allLinksReady);}
 private checkRevision(revision:number){if(revision!==this.state.controllers.revision)throw Error('stale_controllers');}
 private initialReady(){return this.members.has(this.host)&&[...this.members.keys()].every(member=>this.available(member)&&this.offers.get(member)?.revision===this.state.controllers.revision&&this.offers.get(member)?.roomRevision===(this.roomRevision??0));}
 requestStart(){
  if(this.state.startRequested)return;
  if(this.state.epoch)throw Error('game_already_started');
  if(!this.initialReady())throw Error('game_prerequisites');
  this.state.startRequested=true;this.deadline=this.now()+gameplayLimits.barrierMs;
  this.prepareIfReady();
 }
 private prepareIfReady(){
  if(this.state.pending)return;
  if(!this.hasPlayed&&this.state.startRequested&&!this.initialReady())return;
  const required=this.owners();if(required.some(member=>!this.offers.has(member)||!this.available(member)))return;
  const authority=this.offers.get(this.host)!;
  if(!this.hasPlayed){
   if(!this.state.startRequested&&!this.state.epoch)return;
   if(required.some(member=>{const offer=this.offers.get(member)!;return !offer.fresh||offer.frame!==0||offer.hash!==authority.hash;})){this.stop('Initial states differ. Prepare fresh matching games; existing progress is preserved.','failed');return;}
   this.begin(authority.frame,authority.hash);return;
  }
  if([...this.transfers.values()].some(transfer=>transfer.purpose==='controller'))return;
  this.frame=authority.frame;this.hash=authority.hash;
  const mismatched=required.filter(member=>member!==this.host&&(this.offers.get(member)!.frame!==authority.frame||this.offers.get(member)!.hash!==authority.hash));
  if(mismatched.length){for(const member of mismatched)this.capture(member,'controller');return;}
  this.state={...this.state,status:'resume_ready',reason:'The paused game is synchronized. The host can resume.'};
 }
 private begin(frame:number,hash:string){
  for(const transfer of [...this.transfers.values()])this.cancelTransfer(transfer,'Game epoch is changing. Synchronize again.');
  this.frame=frame;this.hash=hash;this.required=this.owners();this.acks.clear();this.deadline=this.now()+gameplayLimits.barrierMs;
  this.state={...this.state,status:'starting',reason:undefined,epoch:id(),delay:Math.max(gameplayLimits.delayDefault,...this.required.map(member=>this.offers.get(member)?.delay??gameplayLimits.delayDefault))};
  const context={epoch:this.state.epoch!,authority:this.host,frame,hash,delay:this.state.delay!,controllers:this.state.controllers};
  for(const member of this.required)this.send(member,{type:'gamePrepare',...context});
 }
 private freeze(reason:string){
  if(!this.state.epoch)throw Error('game_not_playing');
  if(this.state.pending)for(const transfer of [...this.transfers.values()])this.cancelTransfer(transfer,'Game roles are changing. Synchronize again.');
  this.offers.clear();this.acks.clear();this.state={...this.state,status:'pausing',reason};this.deadline=this.now()+gameplayLimits.barrierMs;
  this.send(this.host,{type:'gameFreeze',epoch:this.state.epoch!,reason});
 }
 requestRoles(pending:RoleTransaction,owners:ControllerAssignment){
  if(this.state.pending)throw Error('role_change_pending');
  if(!this.state.epoch)throw Error('game_not_playing');
  this.state.pending=pending;this.proposed=owners;this.freeze('Changing roles at the last completed frame.');
 }
 private failTransaction(reason:string){
  for(const transfer of [...this.transfers.values()])this.cancelTransfer(transfer,reason);
  if(this.state.pending)this.state.pending={...this.state.pending,status:'failed',reason};
  this.state.status='paused';this.state.reason=reason;this.offers.clear();this.all({type:'gameStop',epoch:this.state.epoch,reason});
 }
 private finishTransaction(){
  const pending=this.state.pending;if(!pending||pending.status!=='synchronizing'||this.transfers.size)return;
  if(this.owners(this.proposed).some(member=>!this.available(member))){this.failTransaction('A proposed controller is unavailable. Retry or cancel the role change.');return;}
  try{this.state.controllers=this.commitRoles(pending);}catch{this.failTransaction('Room membership or slots changed. Previous roles and game progress are preserved.');return;}this.state.pending=undefined;this.proposed=undefined;
  this.begin(this.frame,this.hash!);
 }
 private capture(recipient:string,purpose:CheckpointPurpose){
  if(!this.available(recipient)||recipient===this.host)throw Error('game_prerequisites');
  if([...this.transfers.values()].some(transfer=>transfer.recipient===recipient))return;
  if(this.transfers.size>=4)throw Error('synchronization_busy');
  const transfer:Transfer={id:id(),recipient,purpose,sending:false,deadline:this.now()+gameplayLimits.checkpointMs};this.transfers.set(transfer.id,transfer);
  this.send(this.host,{type:'gameCapture',epoch:this.state.epoch!,transferId:transfer.id,recipient,purpose});
 }
 private cancelTransfer(transfer:Transfer,reason:string){
  this.transfers.delete(transfer.id);const event:GameEvent={type:'gameSyncStop',epoch:this.state.epoch!,transferId:transfer.id,reason};this.send(this.host,event);this.send(transfer.recipient,event);
 }
 handle(member:string,command:GameCommand){
  if(!this.members.has(member))throw Error('membership_changed');
  if(command.type==='gameReady'){
   this.checkRevision(command.revision);if(command.roomRevision!==(this.roomRevision??0))throw Error('room_changed');if(this.state.pending||['playing','starting','pausing'].includes(this.state.status)||!this.available(member))throw Error('game_prerequisites');
   this.offers.set(member,command);this.prepareIfReady();return;
  }
  if(command.type==='gameObserve'){
   this.checkRevision(command.revision);if(this.state.status!=='playing'||this.owners().includes(member))throw Error('game_prerequisites');this.capture(member,'observer');return;
  }
  if(command.type==='gameUnready'){
   this.checkRevision(command.revision);const transfers=[...this.transfers.values()].filter(transfer=>member===this.host||transfer.recipient===member);
   if(this.state.pending&&(member===this.host||this.owners(this.proposed).includes(member)||transfers.some(transfer=>transfer.purpose==='controller'))){this.failTransaction('Synchronization cancelled. Previous roles and game progress are preserved.');return;}
   if(transfers.some(transfer=>transfer.purpose==='controller'))this.stop('Synchronization cancelled. Game progress is preserved.');
   else {for(const transfer of transfers)this.cancelTransfer(transfer,'Synchronization cancelled. Game progress is preserved.');this.offers.delete(member);if((!this.state.epoch||this.owners().includes(member))&&(this.state.startRequested||this.state.status==='starting'))this.stop('Preparation cancelled. Members must prepare again.');}return;
  }
  if(command.type==='gameRoleCancel'||command.type==='gameRoleRetry'){
   if(member!==this.host||this.state.pending?.id!==command.transactionId)throw Error('stale_controllers');
   if(command.type==='gameRoleCancel'){this.state.pending=undefined;this.proposed=undefined;this.stop('Role change cancelled. Previous roles and game progress are preserved.');}
   else {this.state.pending.status='freezing';this.state.pending.reason=undefined;this.freeze('Retrying the role change at the preserved frame.');}return;
  }
  if(!('epoch' in command)||command.epoch!==this.state.epoch)throw Error('stale_game');
  if(command.type==='gamePause'){
   if(!this.owners().includes(member))throw Error('controller_only');if(this.state.status==='playing')this.freeze(`Play paused (${command.reason}).`);return;
  }
  if(command.type==='gameFrozen'){
   if(member!==this.host||this.state.status!=='pausing'||command.frame<this.frame)throw Error('stale_game');
   this.frame=command.frame;this.hash=command.hash;this.state.status='paused';
   this.all({type:'gamePauseAt',epoch:command.epoch,frame:this.frame,reason:this.state.reason!});
   if(this.state.pending){
    this.state.pending.status='synchronizing';
    const proposed=this.owners(this.proposed);if(proposed.some(owner=>!this.available(owner))){this.failTransaction('A proposed controller needs a matching game and connection. Retry when ready, or cancel.');return;}
    for(const owner of proposed)if(owner!==this.host)this.capture(owner,'controller');this.finishTransaction();
   }return;
  }
  if(command.type==='gameAck'){
   if(this.state.status!=='starting'||!this.required.includes(member)||command.hash!==this.hash)throw Error('stale_game');this.acks.add(member);
   if(this.required.every(owner=>this.acks.has(owner))){this.hasPlayed=true;this.state.status='playing';this.state.reason=undefined;this.state.startRequested=false;
    for(const owner of this.required)this.send(owner,{type:'gameStart',epoch:command.epoch,authority:this.host,frame:this.frame,hash:this.hash!,delay:this.state.delay!,controllers:this.state.controllers});
   }return;
  }
  if(command.type==='gameResume'){if(member!==this.host||this.state.status!=='resume_ready')throw Error('resume_not_ready');this.begin(this.frame,this.hash!);return;}
  if(command.type==='gamePaused')return;
  if(command.type==='gameAbort'){
   if(!this.owners().includes(member)){for(const transfer of [...this.transfers.values()])if(transfer.recipient===member)this.cancelTransfer(transfer,'Observer synchronization failed. Retry.');return;}
   this.stop(`Play paused (${command.reason}). Prepare again; game progress is preserved.`,'failed');return;
  }
  if(!('transferId' in command))throw Error('invalid_game');
  const transfer=this.transfers.get(command.transferId);if(!transfer)throw Error('stale_checkpoint');
  if(command.type==='gameCaptured'){
   if(member!==this.host||transfer.frame!==undefined||transfer.purpose==='controller'&&(command.frame!==this.frame||command.hash!==this.hash))throw Error('stale_checkpoint');
   transfer.frame=command.frame;transfer.hash=command.hash;
   const event:GameEvent={type:'gameCheckpoint',epoch:command.epoch,transferId:transfer.id,sender:this.host,recipient:transfer.recipient,purpose:transfer.purpose,frame:command.frame,hash:command.hash};this.send(this.host,event);this.send(transfer.recipient,event);return;
  }
  if(member!==transfer.recipient&&!(command.type==='gameCheckpointFailed'&&member===this.host))throw Error('stale_checkpoint');
  if(command.type==='gameCheckpointReady'){
   if(transfer.frame===undefined)throw Error('stale_checkpoint');if(!transfer.sending){transfer.sending=true;this.send(this.host,{type:'gameCheckpointSend',epoch:command.epoch,transferId:transfer.id,recipient:member});}return;
  }
  if(command.type==='gameCheckpointAck'){
   if(!transfer.sending||command.frame!==transfer.frame||command.hash!==transfer.hash)throw Error('stale_checkpoint');
   if(transfer.purpose==='observer'){if(transfer.catchingUp)return;transfer.catchingUp=true;transfer.deadline=this.now()+gameplayLimits.catchupMs;this.send(this.host,{type:'gameCatchup',epoch:command.epoch,transferId:transfer.id,recipient:member,frame:command.frame});}
   else {this.transfers.delete(transfer.id);const offer=this.offers.get(member);this.offers.set(member,{type:'gameReady',requestId:id(),revision:this.state.controllers.revision,roomRevision:this.roomRevision??0,delay:offer?.delay??gameplayLimits.delayDefault,frame:command.frame,hash:command.hash,fresh:false});if(this.state.pending)this.finishTransaction();else this.prepareIfReady();}return;
  }
  if(command.type==='gameObserved'){if(!transfer.catchingUp||command.frame<transfer.frame!)throw Error('stale_checkpoint');this.transfers.delete(transfer.id);return;}
  if(command.type==='gameCheckpointFailed'){this.cancelTransfer(transfer,'Synchronization failed. Progress is preserved; retry.');if(transfer.purpose==='controller'){if(this.state.pending)this.failTransaction('Synchronization failed. Retry or cancel the role change.');else this.stop('Synchronization failed. Progress is preserved; prepare again.','failed');}}
 }
 stop(reason:string,status:GameView['status']='paused'){
  for(const transfer of [...this.transfers.values()])this.cancelTransfer(transfer,reason);this.offers.clear();this.acks.clear();this.state={...this.state,status,reason,startRequested:false};this.all({type:'gameStop',epoch:this.state.epoch,reason});
 }
 sweep(){let changed=false;for(const transfer of [...this.transfers.values()])if(this.now()>=transfer.deadline){this.cancelTransfer(transfer,'Synchronization timed out. Retry without leaving the room.');if(transfer.purpose==='controller'){if(this.state.pending)this.failTransaction('Synchronization timed out. Retry or cancel.');else this.stop('Synchronization timed out. Prepare again.','failed');}changed=true;}
  if((this.state.startRequested||['starting','pausing'].includes(this.state.status))&&this.now()>=this.deadline){if(this.state.pending)this.failTransaction('The completed frame could not be confirmed. Previous roles are preserved.');else this.stop('Preparation timed out. Retry; progress is preserved.','failed');changed=true;}return changed;}
}
