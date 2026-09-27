import type {RoomState} from './room-client.ts';

/** Report individual links without treating one failed member as a failed room. */
export function connectionStatus(state:RoomState) {
 const room=state.room;
 if(!room)return state.connection?.status??'No room connection.';
 const peers=room.peers,connected=peers.filter(peer=>peer.status==='connected');
 if(!peers.length)return state.connected?(room.occupancy>1?'Preparing member connections…':'No other members are connected.'): 'Room service disconnected. Reconnect to check membership.';
 const failures=peers.filter(peer=>['failed','relay_unavailable','relay_capacity'].includes(peer.status));
 const pending=peers.length-connected.length-failures.length;
 const name=(member:string)=>room.slots.find(slot=>slot.member?.id===member)?.member?.nickname??'Member';
 const parts:string[]=[];
 if(!state.connected)parts.push('Room service disconnected; existing member links may remain active.');
 parts.push(`${connected.length}/${peers.length} member connections ready.`);
 if(pending)parts.push(`${pending} connecting.`);
 for(const peer of failures){const reason=peer.status==='relay_unavailable'?'relay service unavailable':peer.status==='relay_capacity'?'relay capacity full':'connection failed';parts.push(`${name(peer.member)}: ${reason}. Retry this connection in Connection and session settings.`);if(peer.policy==='relay')parts.push('Relay only will not switch to direct.');}
 if(connected.length&&state.connection?.route==='relay')parts.push(peers.length===1?(peers[0].policy==='relay'?'Relay only is on. Connected through the relay.':'Direct connection unavailable. Relay keeps you playing together.'):'At least one member connection uses the relay.');
 else if(connected.length&&state.connection?.route==='direct')parts.push('Connected member links use the direct route.');
 return parts.join(' ');
}
