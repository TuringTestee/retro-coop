/** Admission for the pinned mapper-225 FCS state, before its in-place OSS loader runs.
 * Layout comes from a trusted fresh instance; no offsets/sizes supplied by a peer
 * drive allocations. Numeric ranges follow upstream state.c, ppu.c, input.c,
 * sound.c and boards/225.c at the pinned revision, not a sample's current values.
 */
export const FCE_STATE_LIMIT=2*1024*1024;
type Field={tag:string;offset:number;length:number;chunk:number};
function layout(bytes:Uint8Array):Field[]{
 if(bytes.length<16||bytes.length>FCE_STATE_LIMIT||String.fromCharCode(...bytes.subarray(0,3))!=='FCS'||bytes[3]!==255)throw Error('Invalid OSS state header');
 const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
 if(view.getUint32(4,true)!==bytes.length-16||view.getUint32(8,true)!==9900||bytes.subarray(12,16).some(v=>v!==0))throw Error('Invalid OSS state size or version');
 const fields:Field[]=[];let offset=16,previous=0;
 while(offset<bytes.length){
  if(offset+5>bytes.length)throw Error('Truncated OSS state chunk');
  const chunk=bytes[offset],length=view.getUint32(offset+1,true);offset+=5;
  if(![1,2,3,4,5,16].includes(chunk)||chunk<=previous||length>bytes.length-offset)throw Error('Invalid OSS state chunk');
  previous=chunk;const end=offset+length;const seen=new Set<string>();
  while(offset<end){
   if(offset+8>end)throw Error('Truncated OSS state field');
   const tag=String.fromCharCode(...bytes.subarray(offset,offset+4)),size=view.getUint32(offset+4,true);offset+=8;
   if(seen.has(tag)||size>end-offset)throw Error('Duplicate or truncated OSS state field');
   seen.add(tag);fields.push({tag,offset,length:size,chunk});offset+=size;
  }
 }
 if(previous!==16)throw Error('Incomplete OSS state');
 return fields;
}
const ranges:Record<string,[number,number,boolean?]>={
 JAMM:[0,1],IQLB:[0,0xbe3],ICoa:[-2048,2048,true],ICou:[-1024,1024,true],
 KOOK:[0,1],DEAD:[0,2],XOFF:[0,7],VTGL:[0,1],RADD:[0,32767],TADD:[0,32767],LSTS:[0,1],
 FHCN:[-2048,715920,true],FCNT:[0,3],ENCH:[0,31],IQFM:[0,3],NREG:[0,32767],TRIM:[0,1],TRIC:[0,127],
 E0SP:[0,15],E1SP:[0,15],E2SP:[0,15],E0MO:[0,3],E1MO:[0,3],E2MO:[0,3],
 E0D1:[0,16],E1D1:[0,16],E2D1:[0,16],E0DV:[0,15],E1DV:[0,15],E2DV:[0,15],
 LEN0:[0,254,true],LEN1:[0,254,true],LEN2:[0,254,true],LEN3:[0,254,true],
 CRF1:[0,2047,true],CRF2:[0,2047,true],SIRQ:[0,255],
 '5ACC':[-10000,10000,true],'5BIT':[0,7],'5ADD':[0,32767],'5SIZ':[0,4081,true],
 '5VDM':[0,1],'5VSP':[0,1],RWDA:[0,127],
 // LQ phase counters are fixed-point periods: pulse <=2048*2*2^17,
 // triangle <=2048*2^17, noise <=4068*2^17 (sound.c RDo*).
 SAC1:[-1048576,536870912,true],SAC2:[-1048576,536870912,true],
 RCD1:[0,7,true],RCD2:[0,7,true],TRIS:[0,31,true],
 TACC:[-1048576,268435456,true],NACC:[-1048576,533725184,true],
 CBC1:[0,15],CBC2:[0,15],CBC3:[0,15],CBC4:[0,15],CBC5:[0,15],
 SNTS:[0,1048576],TSOF:[0,1048576],WLC1:[0,2048,true],WLC2:[0,2048,true],WLC3:[0,2048,true],WLC4:[0,2048,true],TCOU:[0,45],
 PRG:[0,127],CHR:[0,127],MODE:[0,1],MIRR:[0,1]
};
const rawFields=new Set(['PC','A','X','Y','S','P','DB','RAM','MooP','TSBS','NTAR','PRAM','SPRA','PPUR','PSPL','VBUF','PGEN','JYRB','JOYS','PSG','SWEE','SWCT','5SHF','5SZL','5ADL','5FMT','FAC1','FAC2','FAC3','WAVE','PROT','TBTG']);
export class FceStateSchema{
 private readonly fields:Field[];
 constructor(private readonly template:Uint8Array){
  this.fields=layout(template);
  if(this.fields.some(f=>!ranges[f.tag.replace(/\0+$/,'')]&&!rawFields.has(f.tag.replace(/\0+$/,''))))throw Error('Unaudited OSS state profile');
 }
 validate(bytes:Uint8Array){
  if(bytes.length!==this.template.length)throw Error('OSS state geometry changed');
  const candidate=layout(bytes);
  if(candidate.length!==this.fields.length)throw Error('Incomplete OSS state fields');
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  for(let index=0;index<candidate.length;index++){
   const field=candidate[index],expected=this.fields[index];
   if(field.tag!==expected.tag||field.chunk!==expected.chunk||field.offset!==expected.offset||field.length!==expected.length)throw Error('OSS state schema changed');
   const tag=field.tag.replace(/\0+$/,'');const range=ranges[tag];
   if(range){
    const [min,max,signed]=range;const value=field.length===1?bytes[field.offset]:field.length===2?view.getUint16(field.offset,true):signed?view.getInt32(field.offset,true):view.getUint32(field.offset,true);
    if(![1,2,4].includes(field.length)||value<min||value>max)throw Error('Invalid OSS hardware field '+tag);
   }
   if(tag==='IQLB'&&(view.getUint32(field.offset,true)&~0xbe3))throw Error('Invalid OSS interrupt flags');
   // ReadGP increments an 8-bit read counter even after bit 8. Subsequent
   // accesses mask it before shifting, so the complete byte range is valid.
   const arrayMax=tag==='PROT'?15:tag==='PRAM'?63:tag==='SWEE'?128:tag==='SWCT'?8:undefined;
   if(arrayMax!==undefined&&bytes.subarray(field.offset,field.offset+field.length).some(v=>v>arrayMax))throw Error('Invalid OSS hardware array '+tag);
   if(tag==='SWEE'&&bytes.subarray(field.offset,field.offset+field.length).some(v=>v!==0&&v!==128))throw Error('Invalid OSS sweep flag');
   if(tag==='TBTG'&&bytes.subarray(field.offset,field.offset+field.length).some((v,i)=>v!==this.template[field.offset+i]))throw Error('Invalid OSS turbo state');
   if(tag.startsWith('FAC')){
    const accumulator=view.getBigInt64(field.offset,true);
    // filter.c multiplies signed fixed-point accumulators by coefficients
    // <=65536; this retains ample audio headroom without signed overflow.
    if(accumulator<-(1n<<40n)||accumulator>(1n<<40n))throw Error('Invalid OSS audio accumulator');
   }
   if(tag==='WAVE')for(let i=0;i<field.length;i+=4){const sample=view.getInt32(field.offset+i,true);if(sample<-(1<<28)||sample>(1<<28))throw Error('Invalid OSS audio history');}
   // Byte arrays are bounded cartridge/CPU/PPU/controller RAM. TSBS is the
   // absolute 64-bit clock; FAC*/WAVE are signed filter accumulators, never
   // allocation lengths or hardware indices. The upstream frame runner remains
   // isolated behind memory and execution limits even after structural admission.
  }
  const field=(name:string)=>candidate.find(f=>f.tag===name)!;
  const stamp=field('SNTS'),offset=field('TSOF');
  // sound.c: trunc((19687500*65536/11)/(48000*16)). Loading a larger
  // combined phase is sanitized upstream; reject it rather than change state.
  if(view.getUint32(stamp.offset,true)+view.getUint32(offset.offset,true)>=152727)throw Error('Invalid OSS audio clock relationship');
 }
}
