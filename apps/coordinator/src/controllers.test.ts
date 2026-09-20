import {test} from 'node:test';
import assert from 'node:assert/strict';
import {GameSession} from './gameplay.ts';
import {parseGameCommand,type GameCommand,type GameEvent} from '../../../packages/contracts/src/gameplay.ts';
const peerEpoch='p'.repeat(32),hash='a'.repeat(64),requestId='r'.repeat(32);
function setup(){let now=0;const events:GameEvent[]=[];const game=new GameSession(()=>now,(_role,event)=>events.push(event));game.bind(peerEpoch);return {game,events,advance(){now+=15000;game.sweep();}};}
const proposal=(revision=0,epoch?:string):Extract<GameCommand,{type:'gameControllerPropose'}>=>({type:'gameControllerPropose',requestId,peerEpoch,epoch,revision,mode:'shared',p1:'guest'});
const offer=(controllerRevision=0)=>({type:'gameReady' as const,requestId,peerEpoch,frame:0,fresh:true,hash,delay:6,controllerRevision});
function respond(game:GameSession,accept=true){return {type:'gameControllerRespond' as const,requestId,peerEpoch,epoch:game.view().epoch,proposalId:game.view().controllerProposal!.id,accept};}
test('controller changes need current host proposal and both explicit acceptances before fresh readiness',()=>{
 const {game,events}=setup();game.ready('host',offer());
 assert.throws(()=>game.proposeControllers('guest',proposal()),/host_only/);
 assert.throws(()=>game.proposeControllers('host',{...proposal(),peerEpoch:'x'.repeat(32)}),/stale_game/);
 game.proposeControllers('host',proposal());assert.deepEqual(game.view().ready,[]);
 assert.throws(()=>game.proposeControllers('host',proposal(1)),/controller_change_unavailable/);
 assert.throws(()=>game.ready('guest',offer(1)),/controller_consent_pending/);
 const command=respond(game);game.respondControllers('guest',command);assert.equal(game.view().controllers?.p1,'host');
 game.respondControllers('guest',command);assert.deepEqual(game.view().controllerProposal?.accepted,['guest']);
 game.respondControllers('host',command);assert.equal(game.view().controllers?.p1,'guest');assert.equal(game.view().status,'paused');
 assert.throws(()=>game.respondControllers('host',command),/stale_controllers/);
 assert.throws(()=>game.ready('host',offer()),/stale_controllers/);
 game.ready('host',offer(1));assert.equal(game.view().status,'paused');game.ready('guest',offer(1));
 const epoch=game.view().epoch!;assert.equal(game.view().status,'starting');game.ack('host',epoch,hash);assert.equal(game.view().status,'starting');game.ack('guest',epoch,hash);
 assert.equal(game.view().status,'playing');assert.equal(events.filter(e=>e.type==='gameStart').at(-1)?.controllers?.p1,'guest');
 assert.throws(()=>game.proposeControllers('host',proposal(1,epoch)),/controller_change_unavailable/);
});
test('decline cancel timeout disconnect and replacement keep progress and cannot reuse consent',()=>{
 for(const action of ['decline','cancel','timeout','disconnect','replacement'] as const){
  const {game,advance}=setup();game.proposeControllers('host',proposal());const command=respond(game);game.respondControllers('host',command);
  if(action==='decline')game.respondControllers('guest',{...command,accept:false});
  if(action==='cancel') {assert.throws(()=>game.respondControllers('guest',{...command,type:'gameControllerCancel'}),/host_only/);game.respondControllers('host',{...command,type:'gameControllerCancel'});}
  if(action==='timeout')advance();if(action==='disconnect')game.bind(undefined);if(action==='replacement')game.resetControllers();
  assert.equal(game.view().controllerProposal,undefined,action);assert.equal(game.view().controllers?.p1,'host',action);assert.equal(game.view().status,'paused');assert.deepEqual(game.view().ready,[]);
  assert.throws(()=>game.respondControllers('guest',command),/stale_/);
 }
});
test('paused reassignment replaces epoch and cannot consume earlier readiness or start acknowledgement',()=>{
 const {game}=setup();game.ready('host',offer());game.ready('guest',offer());const epoch=game.view().epoch!;game.ack('host',epoch,hash);game.ack('guest',epoch,hash);
 game.pause(epoch,20,'user','host');game.pausedAt('host',epoch,20,hash);game.pausedAt('guest',epoch,20,hash);
 game.ready('host',{...offer(),frame:20,fresh:false},true);game.ready('guest',{...offer(),frame:20,fresh:false},true);
 game.proposeControllers('host',proposal(0,epoch));assert.throws(()=>game.resume('host',epoch),/resume_not_ready/);
 const command=respond(game);game.respondControllers('host',command);game.respondControllers('guest',command);
 game.ready('host',{...offer(1),frame:20,fresh:false},true);game.ready('guest',{...offer(1),frame:20,fresh:false},true);game.resume('host',epoch);
 assert.notEqual(game.view().epoch,epoch);assert.throws(()=>game.ack('guest',epoch,hash),/stale_game/);
});
test('wire commands reject forged fields malformed ownership revisions and extra claims',()=>{
 const valid=proposal();delete valid.epoch;assert.deepEqual(parseGameCommand(valid),valid);
 for(const patch of [{p1:'stranger'},{mode:'coop'},{revision:-1},{revision:0.5},{epoch:'bad'},{host:true}])assert.equal(parseGameCommand({...valid,...patch}),undefined);
 assert.ok(parseGameCommand(offer()));const initial={...offer()};delete (initial as {controllerRevision?:number}).controllerRevision;assert.ok(parseGameCommand(initial));
});
