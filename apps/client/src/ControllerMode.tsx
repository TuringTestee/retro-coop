import React,{useEffect,useState} from 'react';
import {defaultControllers} from '../../../packages/contracts/src/gameplay.ts';
import type {RoomView,RoomRole} from '../../../packages/contracts/src/rooms.ts';
import type {RoomClient} from './room-client.ts';

const playerName=(room:RoomView,role:RoomRole)=>role==='host'?`${room.host} (host)`:`${room.guest??'Guest'} (guest)`;
export function ControllerOwnership({room}:{room:RoomView}) {
 const assignment=room.game?.controllers??defaultControllers;
 return <p data-testid="controller-ownership">{assignment.mode==='shared'?'Shared P1':'Separate P1/P2'} · P1: {playerName(room,assignment.p1)}{assignment.mode==='separate'?` · P2: ${playerName(room,assignment.p1==='host'?'guest':'host')}`:' · P2: no input'}</p>;
}

/** Optional session settings; names identify controller ownership independently of host authority. */
export function ControllerMode({room,act}:{room:RoomView;act:RoomClient['act']}) {
 const assignment=room.game?.controllers??defaultControllers,proposal=room.game?.controllerProposal;
 const [mode,setMode]=useState(assignment.mode),[p1,setP1]=useState<RoomRole>(assignment.p1);
 useEffect(()=>{setMode(assignment.mode);setP1(assignment.p1);},[assignment.mode,assignment.p1]);
 const name=(role:RoomRole)=>playerName(room,role);
 const context={peerEpoch:room.peer.epoch!,...(room.game?.epoch?{epoch:room.game.epoch}:{})};
 const available=!!room.guest&&room.peer.status==='connected'&&['waiting','paused','resume_ready'].includes(room.game?.status??'waiting')&&!proposal;
 return <section className="controller-mode" aria-labelledby="controller-heading" data-testid="controller-mode"><h3 id="controller-heading">Session controllers</h3>
  <p>Separate P1/P2 keeps the game’s native simultaneous or alternating turns. Single-player games do not become co-op. Shared P1 lets you take turns controlling a single-player game; P2 stays neutral.</p>

  {room.role==='host'&&<fieldset disabled={!available}><legend>Request controller assignment</legend>
   <label>Controller mode <select aria-label="Controller mode" value={mode} onChange={event=>setMode(event.target.value as typeof mode)}><option value="separate">Separate P1/P2</option><option value="shared">Shared P1</option></select></label>
   <label>P1 owner <select aria-label="P1 owner" value={p1} onChange={event=>setP1(event.target.value as RoomRole)}><option value="host">{name('host')}</option><option value="guest">{name('guest')}</option></select></label>
   <button onClick={()=>void act({type:'gameControllerPropose',...context,revision:assignment.revision,mode,p1})}>Request assignment</button>
   {assignment.mode==='shared'&&<button onClick={()=>void act({type:'gameControllerPropose',...context,revision:assignment.revision,mode:'shared',p1:assignment.p1==='host'?'guest':'host'})}>Pass controller</button>}
  </fieldset>}
  {!proposal&&<p>Changes require both connected players and a waiting or paused game. Both players accept, then prepare to resume; the host resumes shared play.</p>}
  {proposal&&<div role="group" aria-label="Controller request"><p role="status">Requested: {proposal.mode==='shared'?'Shared P1':'Separate P1/P2'}, P1: {name(proposal.p1)}. Both players must accept within 15 seconds. Previous ownership and progress stay intact if declined or cancelled.</p>
   <button disabled={proposal.accepted.includes(room.role)} onClick={()=>void act({type:'gameControllerRespond',...context,proposalId:proposal.id,accept:true})}>Accept assignment</button>
   <button onClick={()=>void act({type:'gameControllerRespond',...context,proposalId:proposal.id,accept:false})}>Decline assignment</button>
   {room.role==='host'&&<button onClick={()=>void act({type:'gameControllerCancel',...context,proposalId:proposal.id})}>Cancel assignment request</button>}
   <p role="status">Accepted: {proposal.accepted.map(name).join(', ')||'waiting for both players'}. Release held keys and gamepad buttons before resuming.</p>
  </div>}
 </section>;
}
