import {readRecovery,changeRecovery,validSavedAt,type RecoveryCapture,type RecoveryRecord} from './saves.ts';
import {validFingerprint,type Fingerprint} from '../../../packages/contracts/src/fingerprint.ts';
import {CHECKPOINT_MAX_BYTES} from '../../../packages/contracts/src/checkpoint.ts';
import {sha256,text,integer} from '../../../packages/contracts/src/protocol-validation.ts';
import type {LocalPlayer} from './player.ts';

export function validRecovery(value:unknown):value is RecoveryCapture {
 const row=value as RecoveryCapture|undefined;
 return !!row&&validFingerprint(row.fingerprint)&&text(row.title,80)&&sha256(row.identity)&&sha256(row.hash)&&integer(row.frame,0,Number.MAX_SAFE_INTEGER)&&validSavedAt(row.savedAt)&&row.bytes instanceof ArrayBuffer&&row.bytes.byteLength>=72&&row.bytes.byteLength<=CHECKPOINT_MAX_BYTES;
}
/** One host session owns its timer, serialized exports and storage generation. */
export class HostRecoveryCapture {
 private active=true;private pending=false;private writing?:Promise<void>;private timer:ReturnType<typeof setInterval>;private stored:ReturnType<typeof readRecovery>;private last?:string;
 private player:LocalPlayer;private fingerprint:Fingerprint;private title:string;private current:()=>boolean;private feedback:(message:string)=>void;
 constructor(player:LocalPlayer,fingerprint:Fingerprint,title:string,current:()=>boolean,feedback:(message:string)=>void){
  this.player=player;this.fingerprint=fingerprint;this.title=title;this.current=current;this.feedback=feedback;
  this.stored=readRecovery();this.stored.catch(()=>{});this.timer=setInterval(()=>void this.capture(),30000);
 }
 stop(){this.active=false;this.pending=false;clearInterval(this.timer);}
 capture():Promise<void>{
  if(!this.active||!this.current())return Promise.resolve();
  this.pending=true;if(this.writing)return this.writing;
  this.writing=this.drain().finally(()=>{this.writing=undefined;if(this.pending&&this.active&&this.current())void this.capture();});return this.writing;
 }
 private async drain(){
  while(this.pending&&this.active&&this.current()){this.pending=false;await this.save();}
 }
 private async save(){
  const current=()=>this.active&&this.current();
  try{
   const stored=await this.stored;if(!current())return;
   const captured=await this.player.captureRecovery();if(!current()||!captured.frame)return;
   const key=`${captured.frame}:${captured.hash}`;
   if(key===this.last||stored.record?.captures[0]?.identity===captured.identity&&stored.record.captures[0].frame===captured.frame&&stored.record.captures[0].hash===captured.hash)return;
   const capture:RecoveryCapture={fingerprint:this.fingerprint,title:this.title,identity:captured.identity,frame:captured.frame,hash:captured.hash,bytes:captured.bytes,savedAt:Date.now()};
   const record=await changeRecovery(stored.record,stored.generation,capture,current);if(!current())return;
   this.stored=Promise.resolve({generation:stored.generation,record});this.last=key;this.feedback('');
  }catch(error){if(current()){this.stop();this.feedback(`Could not save automatic progress on this device. Your game can continue. ${error instanceof Error?error.message:''}`);}}
 }
}
export type RecoveryOffer={generation:number;record:RecoveryRecord};
export async function recoveryOffer():Promise<RecoveryOffer|undefined>{
 const {generation,record}=await readRecovery();
 if(!record)return;
 if(!Number.isSafeInteger(record.revision)||!Array.isArray(record.captures)||!record.captures.length||record.captures.length>2)throw Error('Saved recovery data is damaged. Load a game normally.');
 return {generation,record};
}
