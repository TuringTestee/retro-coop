import {isIP} from 'node:net';
/** Canonical keys prevent equivalent IP spellings from splitting an admission quota. */
function address(value:string):string|undefined {
 if(isIP(value)===4)return value;
 if(isIP(value)!==6 || value.includes('%'))return;
 const canonical=new URL(`http://[${value}]/`).hostname.slice(1,-1);
 const mapped=/^::ffff:([\da-f]+):([\da-f]+)$/.exec(canonical);
 if(!mapped)return canonical;
 const high=parseInt(mapped[1],16),low=parseInt(mapped[2],16);
 return `${high>>>8}.${high&255}.${low>>>8}.${low&255}`;
}
export function trustedProxyAddresses(values:string[]):string[] {
 return [...new Set(values.map(value=>{const normalized=address(value.trim());if(!normalized)throw Error('Trusted proxy must be a literal IP address');return normalized;}))];
}
/** One explicitly trusted proxy must overwrite X-Forwarded-For with its transport client IP. */
export function admissionAddress(remote:string|undefined,forwarded:string|string[]|undefined,trusted:ReadonlySet<string>):string|undefined {
 const peer=remote && address(remote);
 if(!peer)return;
 if(!trusted.has(peer))return peer;
 if(typeof forwarded!=='string' || forwarded.length>64)return;
 return address(forwarded);
}
