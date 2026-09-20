import {useId} from 'react';
import {validPolicy,type ConnectionPolicy} from '../../../packages/contracts/src/peer.ts';
export function readConnectionPolicy():ConnectionPolicy {try {const value=sessionStorage.getItem('retro-coop-connection-policy');return validPolicy(value)?value:'standard';}catch{return 'standard';}}
export function rememberConnectionPolicy(policy:ConnectionPolicy) {try {sessionStorage.setItem('retro-coop-connection-policy',policy);}catch{}}
export function ConnectionPolicyControl({policy,change}:{policy:ConnectionPolicy;change:(policy:ConnectionPolicy)=>void}) {
 const id=useId();
 return <div className="connection-policy"><label htmlFor={id}>Connection privacy <select aria-label="Connection privacy" id={id} value={policy} onChange={event=>change(event.target.value as ConnectionPolicy)}><option value="standard">Standard</option><option value="relay">Relay only</option></select></label>
 <p className="hint">Standard may reveal your network address to the other player. Relay only uses an encrypted relay and depends on capacity. The service and relay operator still see connection metadata. If either player selects Relay only, both use it before exchanging peer candidates.</p></div>;
}
