import {test} from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {randomUUID} from 'node:crypto';
import {mkdtemp,chmod,stat,rm,symlink} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {WebSocket} from 'ws';
import {createCoordinator,shutdown} from './server.ts';
import {Rooms} from './rooms.ts';
import {listenOperator,operatorRequest,operatorHandler,operatorSocket,type OperatorReply} from './operator.ts';

function confirmation(reply:OperatorReply) {assert.ok('confirmation' in reply);return reply.confirmation;}
const fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:0,submapper:0,region:'NTSC',bytes:24592}};
async function fixture(run:(t:{directory:string;url:string;operator:ReturnType<typeof createCoordinator>['operator'];advance:(ms:number)=>void;open:(address:string)=>Promise<{ws:WebSocket;events:any[];command:(value:object)=>Promise<any>}>})=>Promise<void>) {
 const directory=await mkdtemp(join(tmpdir(),'retro-operator-'));await chmod(directory,0o700);
 let now=1000;const server=createCoordinator({origins:['https://client.example'],trustedProxies:['127.0.0.1'],now:()=>now});
 const operator=await listenOperator(directory,server.operator),clients:WebSocket[]=[];
 server.listen(0,'127.0.0.1');await once(server,'listening');
 const url=`http://127.0.0.1:${(server.address() as {port:number}).port}`;
 const open=async(address:string)=>{
  const ws=new WebSocket(url.replace('http:','ws:')+'/ws',{origin:'https://client.example',headers:{'X-Forwarded-For':address}}),events:any[]=[];
  clients.push(ws);ws.on('error',()=>{});ws.on('message',raw=>events.push(JSON.parse(raw.toString())));
  await once(ws,'open');
  const command=(value:object)=>new Promise<any>((resolve,reject)=>{
   const requestId=randomUUID(),timer=setTimeout(()=>{ws.off('message',receive);reject(Error('response timeout'));},1000);
   function receive(raw:Buffer){const data=JSON.parse(raw.toString());if(data.type==='result' && data.requestId===requestId){clearTimeout(timer);ws.off('message',receive);resolve(data);}}
   ws.on('message',receive);ws.send(JSON.stringify({...value,requestId}));
  });
  return {ws,events,command};
 };
 try {await run({directory,url,operator:server.operator,advance:ms=>{now+=ms;},open});}
 finally {for(const ws of clients)ws.terminate();operator.closeAllConnections();await new Promise<void>(done=>operator.close(()=>done()));await shutdown(server);await rm(directory,{recursive:true,force:true});}
}
test('operator listener requires private owned directory and has no public HTTP or WebSocket command',async()=>{
 await fixture(async t=>{
  assert.equal((await stat(join(t.directory,'operator.sock'))).mode&0o777,0o600);
  assert.equal((await fetch(t.url+'/operator',{method:'POST',body:JSON.stringify({type:'list'})})).status,404);
  const attacker=await t.open('192.0.2.1'),closed=once(attacker.ws,'close');
  attacker.ws.send(JSON.stringify({type:'remove-room',roomId:'x'.repeat(32),requestId:randomUUID()}));assert.equal((await closed)[0],1008);
  const alias=t.directory+'-alias';await symlink(t.directory,alias);
  try {await assert.rejects(operatorSocket(alias),/0700/);}finally{await rm(alias);}
  await chmod(t.directory,0o755);await assert.rejects(operatorSocket(t.directory),/0700/);await chmod(t.directory,0o700);
  await assert.rejects(listenOperator(t.directory,()=>({})),/EADDRINUSE/);
  assert.ok('rooms' in await operatorRequest(t.directory,{type:'list'}));
 });
});
test('confirmed operator removal closes exact room and directory entry without disclosing private content',async()=>{
 await fixture(async t=>{
  const host=await t.open('192.0.2.1'),guest=await t.open('192.0.2.2'),viewer=await t.open('192.0.2.3');
  const auth=await host.command({type:'hello'});await guest.command({type:'hello'});await viewer.command({type:'hello'});await viewer.command({type:'directory'});
  const intent=randomUUID(),created=await host.command({type:'create',intent,visibility:'public',fingerprint}),room=created.data.room;
  await host.command({type:'confirmCreate',intent});await guest.command({type:'join',intent:randomUUID(),invite:room.invite});
  const listed=await operatorRequest(t.directory,{type:'list'});assert.ok('rooms' in listed);assert.equal(listed.rooms.length,1);
  for(const secret of [auth.data.session.token,room.invite,fingerprint.romSha256,fingerprint.coreSha256])assert.ok(!JSON.stringify(listed).includes(secret));
  const preview=await operatorRequest(t.directory,{type:'remove-room',roomId:room.id});assert.ok('description' in preview);assert.ok(preview.description.includes(room.id));
  assert.equal((await host.command({type:'heartbeat'})).ok,true);
  await operatorRequest(t.directory,{type:'confirm',confirmation:confirmation(preview)});
  await host.command({type:'heartbeat'});await guest.command({type:'heartbeat'});
  assert.ok(host.events.some(e=>e.type==='ended' && e.reason==='operator_removed'));assert.ok(guest.events.some(e=>e.type==='ended' && e.reason==='operator_removed'));
  assert.deepEqual((await viewer.command({type:'directory'})).data.directory,[]);
  await assert.rejects(operatorRequest(t.directory,{type:'confirm',confirmation:confirmation(preview)}),/already used/);
  assert.equal((await guest.command({type:'preview',invite:room.invite})).ok,false);
 });
});
test('address block revokes old token, targets canonical proxy client, rejects fresh connections and expires',async()=>{
 await fixture(async t=>{
  const blocked=await t.open('::ffff:c000:201'),other=await t.open('192.0.2.2');
  const token=(await blocked.command({type:'hello'})).data.session.token;await other.command({type:'hello'});
  const list=await operatorRequest(t.directory,{type:'list'});assert.ok('subjects' in list);const subject=list.subjects.find(s=>s.address==='192.0.2.1')!;assert.ok(subject);
  const preview=await operatorRequest(t.directory,{type:'block-address',subjectId:subject.id,seconds:60});
  const closed=once(blocked.ws,'close');await operatorRequest(t.directory,{type:'confirm',confirmation:confirmation(preview)});assert.equal((await closed)[0],4003);
  assert.equal((await other.command({type:'heartbeat'})).ok,true);
  const retry=await t.open('192.0.2.1'),denied=once(retry.ws,'close');
  retry.ws.send(JSON.stringify({type:'hello',requestId:randomUUID()}));assert.equal((await denied)[0],4003);assert.deepEqual(retry.events,[]);
  const subjects=await operatorRequest(t.directory,{type:'list'});assert.ok('subjects' in subjects);assert.equal(subjects.subjects.find(s=>s.id===subject.id)?.connections,0);
  t.advance(60_001);
  const after=await t.open('192.0.2.1');assert.equal((await after.command({type:'hello',token})).error,'session_expired');
  assert.equal((await after.command({type:'hello'})).ok,true);
 });
});
test('changed admission membership invalidates prepared block and malformed commands cannot mutate',async()=>{
 await fixture(async t=>{
  const first=await t.open('192.0.2.1');await first.command({type:'hello'});
  const list=await operatorRequest(t.directory,{type:'list'});assert.ok('subjects' in list);const id=list.subjects[0].id;
  const preview=await operatorRequest(t.directory,{type:'block-address',subjectId:id,seconds:60});
  const second=await t.open('192.0.2.1');await second.command({type:'hello'});
  await assert.rejects(operatorRequest(t.directory,{type:'confirm',confirmation:confirmation(preview)}),/changed/);
  for(const command of [{type:'block-address',subjectId:id,seconds:3601},{type:'block-address',subjectId:id,seconds:0},{type:'block-address',subjectId:id,seconds:60,address:'192.0.2.2'},{type:'confirm',confirmation:'x'.repeat(32)}])await assert.rejects(operatorRequest(t.directory,command));
  assert.equal((await first.command({type:'heartbeat'})).ok,true);assert.equal((await second.command({type:'heartbeat'})).ok,true);
 });
});
test('confirmation expires, consumes failed targets, and bounds pending requests',()=>{
 let now=0,removed=0;const room={id:'x'.repeat(32),label:'Room',visibility:'public',occupancy:1};
 const handle=operatorHandler({rooms:()=>[room],subjects:()=>[],remove:()=>{removed++;},block:()=>{}},()=>now);
 const preview=handle({type:'remove-room',roomId:room.id});now=30_000;
 assert.throws(()=>handle({type:'confirm',confirmation:confirmation(preview)}),/expired/);assert.equal(removed,0);
 for(let i=0;i<64;i++)handle({type:'remove-room',roomId:room.id});assert.throws(()=>handle({type:'remove-room',roomId:room.id}),/Too many/);
});
test('a stale transport cannot revoke a session that moved to another connection',()=>{
 const rooms=new Rooms(),oldSender=()=>{},currentSender=()=>{};
 const original=rooms.attach(undefined,oldSender,()=>{});rooms.attach(original.token,currentSender,()=>{});
 rooms.revoke(original.token,oldSender);
 assert.equal(rooms.handle(original.token,{type:'heartbeat',requestId:randomUUID()},currentSender) instanceof Object,true);
 rooms.revoke(original.token,currentSender);assert.throws(()=>rooms.attach(original.token,()=>{},()=>{}),/session_expired/);
});
test('CLI presents exact action and cancellation leaves target connected',async()=>{
 await fixture(async t=>{
  const client=await t.open('192.0.2.1');await client.command({type:'hello'});
  const list=await operatorRequest(t.directory,{type:'list'});assert.ok('subjects' in list);
  const child=spawn(process.execPath,['apps/coordinator/src/operator-cli.ts',t.directory,'block-address',list.subjects[0].id,'60'],{stdio:['pipe','pipe','pipe']});
  let stdout='',stderr='';child.stdout.on('data',data=>{stdout+=data;if(stdout.includes('Type CONFIRM'))child.stdin.end('cancel\n');});child.stderr.on('data',data=>{stderr+=data;});
  const timer=setTimeout(()=>child.kill('SIGKILL'),5000);
  try {assert.deepEqual(await once(child,'exit'),[0,null]);assert.equal(stderr,'');assert.match(stdout,/192\.0\.2\.1/);assert.match(stdout,/Cancelled\. No change applied/);assert.equal((await client.command({type:'heartbeat'})).ok,true);}finally{clearTimeout(timer);if(child.exitCode===null)child.kill('SIGKILL');}
 });
});
test('actual coordinator entry point enables only private operator socket and shuts it down',async()=>{
 const directory=await mkdtemp(join(tmpdir(),'retro-operator-entry-'));await chmod(directory,0o700);
 const child=spawn(process.execPath,['apps/coordinator/src/main.ts'],{env:{...process.env,COORDINATOR_STAGE:'local',COORDINATOR_PORT:'0',COORDINATOR_HOST:'127.0.0.1',COORDINATOR_OPERATOR_DIR:directory,COORDINATOR_ROM_DIR:join(directory,'roms'),COORDINATOR_TRUSTED_PROXIES:'',TURN_URLS:'',TURN_SECRET:''},stdio:['ignore','pipe','pipe']});
 const timer=setTimeout(()=>child.kill('SIGKILL'),5000);
 try {
  const output=String((await once(child.stdout,'data'))[0]),startup=JSON.parse(output);
  assert.equal(startup.event,'listening');assert.ok(!output.includes(directory));
  assert.ok('rooms' in await operatorRequest(directory,{type:'list'}));
  const ended=once(child,'exit');child.kill('SIGTERM');assert.deepEqual(await ended,[0,null]);
  await assert.rejects(operatorRequest(directory,{type:'list'}));
 } finally {clearTimeout(timer);if(child.exitCode===null)child.kill('SIGKILL');await rm(directory,{recursive:true,force:true});}
});
test('CLI escapes terminal direction controls in untrusted room labels',async()=>{
 await fixture(async t=>{
  const host=await t.open('192.0.2.1');await host.command({type:'hello'});
  const intent=randomUUID(),room=(await host.command({type:'create',intent,visibility:'public',fingerprint})).data.room;
  await host.command({type:'confirmCreate',intent});await host.command({type:'rename',roomId:room.id,label:'Room\u061c\u200e\u200f\u202e reversed'});
  const {stdout}=await promisify(execFile)(process.execPath,['apps/coordinator/src/operator-cli.ts',t.directory,'list'],{timeout:5000});
  assert.ok(!/\p{Bidi_Control}/u.test(stdout),'untrusted labels must not change terminal text direction');for(const hex of ['061c','200e','200f','202e'])assert.ok(stdout.includes('\\u'+hex));
  const child=spawn(process.execPath,['apps/coordinator/src/operator-cli.ts',t.directory,'remove-room',room.id],{stdio:['pipe','pipe','pipe']});
  let preview='';child.stdout.on('data',data=>{preview+=data;if(preview.includes('Type CONFIRM'))child.stdin.end('cancel\n');});
  const timer=setTimeout(()=>child.kill('SIGKILL'),5000);
  try {assert.deepEqual(await once(child,'exit'),[0,null]);assert.ok(!/\p{Bidi_Control}/u.test(preview));for(const hex of ['061c','200e','200f','202e'])assert.ok(preview.includes('\\u'+hex));assert.match(preview,/Cancelled/);}finally{clearTimeout(timer);if(child.exitCode===null)child.kill('SIGKILL');}
 });
});
