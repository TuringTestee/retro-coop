import test from 'node:test';
import assert from 'node:assert/strict';
import {connectionMetrics,connectionRoute} from './peer-route.ts';
test('selected Chrome and Firefox candidate pairs report the actual route',()=>{
 const entries=[{id:'pair',type:'candidate-pair',localCandidateId:'local',remoteCandidateId:'remote'}, {id:'local',type:'local-candidate',candidateType:'relay'}, {id:'remote',type:'remote-candidate',candidateType:'host'}];
 const report=(values:object[])=>new Map(values.map(value=>[(value as {id:string}).id,value])) as unknown as RTCStatsReport;
 assert.equal(connectionRoute(report([...entries,{id:'transport',type:'transport',selectedCandidatePairId:'pair'}])),'relay');
 assert.equal(connectionRoute(report([{...entries[0],selected:true},...entries.slice(1)])),'relay');
 assert.equal(connectionRoute(report([{...entries[0],selected:true},{...entries[1],candidateType:'srflx'},entries[2]])),'direct');
 assert.equal(connectionRoute(report(entries)),undefined,'an available relay is not necessarily the selected route');
 assert.equal(connectionRoute(report([{...entries[0],selected:true}])),undefined,'missing candidates must not claim a direct route');
 assert.deepEqual(connectionMetrics(report([{...entries[0],selected:true,currentRoundTripTime:0.042},{...entries[1],candidateType:'srflx'},entries[2]])),{route:'direct',pingMs:42});
 assert.deepEqual(connectionMetrics(report([{...entries[0],selected:true,currentRoundTripTime:-1},...entries.slice(1)])),{route:'relay',pingMs:undefined});
});
