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
 for(const peer of failures)parts.push(`Could not connect to ${name(peer.member)}. Retry this connection or leave the room.`);
 return parts.join(' ');
}
