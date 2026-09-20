/** Chrome exposes the selected pair through transport stats; Firefox marks the pair itself. */
export function connectionRoute(stats:RTCStatsReport):'direct'|'relay'|undefined {
 const pairs=new Set<string>();
 stats.forEach(report=>{
  if(report.type==='transport' && report.selectedCandidatePairId)pairs.add(report.selectedCandidatePairId);
  if(report.type==='candidate-pair' && report.selected===true)pairs.add(report.id);
 });
 const routes=new Set<'direct'|'relay'>();
 for(const id of pairs){
  const pair=stats.get(id),local=stats.get(pair?.localCandidateId),remote=stats.get(pair?.remoteCandidateId);
  if(local?.candidateType==='relay' || remote?.candidateType==='relay')routes.add('relay');
  else if(['host','srflx','prflx'].includes(local?.candidateType) && ['host','srflx','prflx'].includes(remote?.candidateType))routes.add('direct');
 }
 return routes.size===1?[...routes][0]:undefined;
}
