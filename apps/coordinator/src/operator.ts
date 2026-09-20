import {randomBytes} from 'node:crypto';
import {createServer,request,type Server} from 'node:http';
import {lstat,realpath,chmod} from 'node:fs/promises';
import {isAbsolute,join,resolve} from 'node:path';
import {object,keys,token,integer} from '../../../packages/contracts/src/protocol-validation.ts';

export type OperatorRoom={id:string;label:string;visibility:string;occupancy:number};
export type OperatorSubject={id:string;address:string;connections:number;revision:number;blockedUntil?:number};
export type OperatorOwners={rooms():OperatorRoom[];subjects():OperatorSubject[];remove(id:string):void;block(id:string,revision:number,seconds:number):void};
export type OperatorReply={rooms:OperatorRoom[];subjects:OperatorSubject[]}|{confirmation:string;description:string;expires:number}|{done:true};
/** One-use, expiring confirmation binds an operator's preview to its exact target. */
export function operatorHandler(owners:OperatorOwners,now=Date.now) {
 const pending=new Map<string,{expires:number;apply:()=>void}>();
 return (value:unknown):OperatorReply=>{
  for(const [id,item] of pending)if(item.expires<=now())pending.delete(id);
  if(!object(value))throw Error('Invalid operator request');
  if(value.type==='list' && keys(value,['type']))return {rooms:owners.rooms(),subjects:owners.subjects()};
  if(value.type==='confirm' && keys(value,['type','confirmation']) && token(value.confirmation)) {
   const id=value.confirmation as string,item=pending.get(id);pending.delete(id);
   if(!item)throw Error('Confirmation expired or already used');
   item.apply();return {done:true};
  }
  let description:string,apply:()=>void;
  if(value.type==='remove-room' && keys(value,['type','roomId']) && token(value.roomId)) {
   const room=owners.rooms().find(room=>room.id===value.roomId);
   if(!room)throw Error('Room is no longer available');
   description=`Remove room ${JSON.stringify(room.label)} (${room.id}) for both players`;
   apply=()=>owners.remove(room.id);
  } else if(value.type==='block-address' && keys(value,['type','subjectId','seconds']) && token(value.subjectId) && integer(value.seconds,1,3600)) {
   const subject=owners.subjects().find(subject=>subject.id===value.subjectId && subject.connections>0);
   if(!subject)throw Error('Admission subject is no longer connected');
   const seconds=value.seconds as number;
   description=`Disconnect and block address ${subject.address} (${subject.id}, ${subject.connections} connections) for ${seconds} seconds; this affects everyone sharing that address`;
   apply=()=>owners.block(subject.id,subject.revision,seconds);
  } else throw Error('Invalid operator request');
  if(pending.size>=64)throw Error('Too many pending confirmations; wait 30 seconds');
  const confirmation=randomBytes(32).toString('base64url'),expires=now()+30_000;
  pending.set(confirmation,{expires,apply});return {confirmation,description,expires};
 };
}

/** OS authentication: only the service UID (and privileged root) may traverse this directory. */
export async function operatorSocket(directory:string) {
 if(!isAbsolute(directory) || typeof process.getuid!=='function')throw Error('Operator directory requires an absolute path on a Unix host');
 const path=resolve(directory),info=await lstat(path);
 if(!info.isDirectory() || info.isSymbolicLink() || info.uid!==process.getuid() || (info.mode&0o777)!==0o700 || await realpath(path)!==path)throw Error('Operator directory must be owned by the service user, mode 0700, without symlinks');
 return join(path,'operator.sock');
}
export async function listenOperator(directory:string,handle:(value:unknown)=>unknown):Promise<Server> {
 const socketPath=await operatorSocket(directory);
 const server=createServer((req,res)=>{
  res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');
  if(req.method!=='POST' || req.url!=='/operator') {res.writeHead(404).end(JSON.stringify({error:'Not found'}));req.resume();return;}
  let size=0;const chunks:Buffer[]=[];
  req.on('error',()=>{});
  req.on('data',(chunk:Buffer)=>{size+=chunk.length;if(size>4096) {res.writeHead(413).end(JSON.stringify({error:'Request too large'}));req.destroy();}else chunks.push(chunk);});
  req.on('end',()=>{
   if(res.writableEnded)return;
   try {res.end(JSON.stringify(handle(JSON.parse(Buffer.concat(chunks).toString('utf8')))));}
   catch(error) {res.writeHead(400).end(JSON.stringify({error:error instanceof Error?error.message:'Operator request failed'}));}
  });
 });
 server.requestTimeout=5000;server.headersTimeout=5000;server.setTimeout(5000,socket=>socket.destroy());server.maxConnections=8;
 await new Promise<void>((done,fail)=>{server.once('error',fail);server.listen(socketPath,()=>{server.removeListener('error',fail);done();});});
 try {await chmod(socketPath,0o600);}catch(error){await new Promise<void>(done=>server.close(()=>done()));throw error;}
 return server;
}
export async function operatorRequest(directory:string,value:unknown):Promise<OperatorReply> {
 const socketPath=await operatorSocket(directory),body=JSON.stringify(value);
 return new Promise((done,fail)=>{
  const req=request({socketPath,path:'/operator',method:'POST',headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(body)},timeout:5000},res=>{
   const chunks:Buffer[]=[];let size=0;
   res.on('error',fail);res.on('data',(chunk:Buffer)=>{size+=chunk.length;if(size>1024*1024)res.destroy(Error('Operator response too large'));else chunks.push(chunk);});
   res.on('end',()=>{try {const value=JSON.parse(Buffer.concat(chunks).toString('utf8'));if(res.statusCode!==200)throw Error(value.error??'Operator request failed');done(value);}catch(error){fail(error);}});
  });
  req.on('error',fail);req.on('timeout',()=>req.destroy(Error('Operator request timed out')));req.end(body);
 });
}
