import {randomBytes} from 'node:crypto';
import {defaultControllers,gameplayLimits,type GameRole,type GameCommand,type GameEvent,type GameView} from '../../../packages/contracts/src/gameplay.ts';
type Offer=Extract<GameCommand,{type:'gameReady'}>;
/** Owns only the acknowledged game barrier; Rooms owns all membership and publication. */
export class GameSession {
 private offers=new Map<GameRole,Offer>();
 private acks=new Set<GameRole>();
 private peerEpoch?:string;
 private deadline=0;
 private hash?:string;
 private pauseFrame?:number;
 private paused=new Map<GameRole,{frame:number;hash:string}>();
 private state:GameView={status:'waiting',controllers:{...defaultControllers}};
 private controllerDeadline=0;
 private now:()=>number;private send:(role:GameRole,event:GameEvent)=>void;
 constructor(now:()=>number,send:(role:GameRole,event:GameEvent)=>void) {this.now=now;this.send=send;}
 view():GameView {return {...this.state,ready:[...this.offers.keys()]};}
 private broadcast(event:GameEvent) {this.send('host',event);this.send('guest',event);}
 bind(peerEpoch:string|undefined) {
  if(peerEpoch===this.peerEpoch) return false;
  const active=this.peerEpoch!==undefined;this.peerEpoch=peerEpoch;this.offers.clear();this.acks.clear();
  if(active) this.stop('Connection changed. Shared play is paused; retry requires your action.');
  return active;
 }
 ready(role:GameRole,offer:Offer,established=false) {
  if(this.state.controllerProposal)throw Error('controller_consent_pending');
  if((offer.controllerRevision??0)!==this.state.controllers!.revision)throw Error('stale_controllers');
  if(!this.peerEpoch||offer.peerEpoch!==this.peerEpoch) throw Error('stale_game');
  if(['playing','starting','pausing'].includes(this.state.status)) throw Error('game_already_started');
  this.offers.set(role,offer);
  if(!established&&role==='guest'&&!this.offers.has('host')) this.send('host',{type:'gameInspect',peerEpoch:this.peerEpoch});
  const host=this.offers.get('host'),guest=this.offers.get('guest');if(!host||!guest) return;
  if(!established&&(!host.fresh||host.frame!==0)) {this.stop('The host has made progress. Shared late join is not available yet; the original game is preserved.','late_join');return;}
  if((!established&&(!guest.fresh||guest.frame!==0))||host.frame!==guest.frame||host.hash!==guest.hash) {this.stop('Initial machine states differ. Choose a fresh matching game or cancel.','failed');return;}
  if(established){this.state={...this.state,status:'resume_ready',reason:undefined};return;}
  this.begin(host,guest);
 }
 resume(role:GameRole,epoch:string) {if(role!=='host'||this.state.status!=='resume_ready'||epoch!==this.state.epoch)throw Error('resume_not_ready');this.begin(this.offers.get('host')!,this.offers.get('guest')!);}
 private begin(host:Offer,guest:Offer) {
  this.hash=host.hash;this.acks.clear();this.deadline=this.now()+gameplayLimits.barrierMs;
  this.state={...this.state,status:'starting',reason:undefined,epoch:randomBytes(24).toString('base64url'),delay:Math.max(host.delay,guest.delay)};
  this.broadcast({type:'gamePrepare',peerEpoch:this.peerEpoch!,epoch:this.state.epoch!,hash:this.hash,delay:this.state.delay!,controllers:this.state.controllers});
 }
 ack(role:GameRole,epoch:string,hash:string):boolean {
  if(this.state.status!=='starting'||epoch!==this.state.epoch||hash!==this.hash) throw Error('stale_game');
  this.acks.add(role);if(this.acks.size!==2) return false;
  this.state={...this.state,status:'playing'};
  this.broadcast({type:'gameStart',peerEpoch:this.peerEpoch!,epoch,delay:this.state.delay!,controllers:this.state.controllers});return true;
 }
 pause(epoch:string,frame:number,reason:string,role:GameRole) {
  if(epoch!==this.state.epoch)throw Error('stale_game');
  if(this.state.status==='pausing')return;
  if(this.state.status!=='playing')throw Error('game_not_playing');
  this.pauseFrame=frame;this.paused.clear();this.deadline=this.now()+gameplayLimits.barrierMs;
  this.state={...this.state,status:'pausing',reason:`${role==='host'?'Host':'Guest'} requested pause (${reason}).`};
  this.broadcast({type:'gamePauseAt',epoch,frame,reason:this.state.reason!});
 }
 pausedAt(role:GameRole,epoch:string,frame:number,hash:string) {
  if(this.state.status!=='pausing'||epoch!==this.state.epoch||frame!==this.pauseFrame)throw Error('stale_game');
  this.paused.set(role,{frame,hash});if(this.paused.size!==2)return;
  if(this.paused.get('host')!.hash!==this.paused.get('guest')!.hash){this.stop('Pause states differ. Shared play remains paused; checkpoint recovery is not available yet.','failed');return;}
  this.stop(`${this.state.reason} Both players are paused at the same frame.`);
 }
 stop(reason:string,status:GameView['status']='paused') {this.offers.clear();this.acks.clear();this.state={...this.state,status,reason,controllerProposal:undefined};this.broadcast({type:'gameStop',epoch:this.state.epoch,reason});}
 private controllerContext(command:{peerEpoch:string;epoch?:string}) {
  if(!this.peerEpoch||command.peerEpoch!==this.peerEpoch||command.epoch!==this.state.epoch)throw Error('stale_game');
 }
 proposeControllers(role:GameRole,command:Extract<GameCommand,{type:'gameControllerPropose'}>) {
  this.controllerContext(command);
  if(role!=='host')throw Error('host_only');
  if(!['waiting','paused','resume_ready'].includes(this.state.status)||this.state.controllerProposal)throw Error('controller_change_unavailable');
  if(command.revision!==this.state.controllers!.revision)throw Error('stale_controllers');
  this.stop('Controller change requested. Both players must accept before preparing to resume.');
  const revision=this.state.controllers!.revision+1;
  this.state.controllers={...this.state.controllers!,revision};
  this.state.controllerProposal={id:randomBytes(24).toString('base64url'),mode:command.mode,p1:command.p1,revision,accepted:[]};
  this.controllerDeadline=this.now()+gameplayLimits.consentMs;
 }
 respondControllers(role:GameRole,command:Extract<GameCommand,{type:'gameControllerRespond'|'gameControllerCancel'}>) {
  this.controllerContext(command);const proposal=this.state.controllerProposal;
  if(!proposal||proposal.id!==command.proposalId)throw Error('stale_controllers');
  if(command.type==='gameControllerCancel'&&role!=='host')throw Error('host_only');
  if(command.type==='gameControllerCancel'||!command.accept){this.stop('Controller change declined or cancelled. Previous ownership and game progress are preserved.');return;}
  if(!proposal.accepted.includes(role))proposal.accepted.push(role);
  if(proposal.accepted.length===2){this.state.controllers={mode:proposal.mode,p1:proposal.p1,revision:proposal.revision};this.stop('Controller assignment accepted. Release held buttons; both players must prepare before the host resumes.');}
 }
 /** A departed guest cannot leave controller ownership or consent for a replacement. */
 resetControllers() {this.state.controllers={...defaultControllers,revision:this.state.controllers!.revision+1};this.stop('Membership changed. Controller assignment reset; shared play remains paused.');}
 sweep() {if(this.state.controllerProposal&&this.now()>=this.controllerDeadline){this.stop('Controller request timed out. Previous ownership and progress are preserved.');return true;}if(['starting','pausing'].includes(this.state.status)&&this.now()>=this.deadline) {this.stop('Shared start timed out. Retry or cancel; the original game is preserved.','failed');return true;}return false;}
}
