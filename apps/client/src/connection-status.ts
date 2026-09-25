import type {RoomState} from './room-client.ts';

export function connectionStatus(state:RoomState) {
 const status=state.room?.peer.status;
 if(status==='relay_unavailable') return 'Relay service is unavailable. Stay in the room or retry; Relay only will not switch to direct.';
 if(status==='relay_capacity') return 'Relay capacity is full. Stay in the room or retry; Relay only will not switch to direct.';
 if(status==='connected'&&state.connection?.route==='relay') return state.room?.peer.policy==='relay'?'Relay only is on. Connected through the relay.':'Direct connection unavailable. Relay keeps you playing together.';
 return (state.connection?.status ?? 'No peer connection.')+(state.connection?.route ? ` Route: ${state.connection.route}.`:'');
}
