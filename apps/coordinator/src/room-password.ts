import {randomBytes,scrypt,timingSafeEqual} from 'node:crypto';

export type PasswordVerifier={salt:Buffer;digest:Buffer};
const WORK_FACTOR={N:16_384,r:8,p:1,maxmem:64*1024*1024} as const;

/** Bounds concurrent KDF work and queued requests without blocking the event loop. */
export class PasswordWork {
 private active=0;
 private queue:(()=>void)[]=[];
 private async run<T>(work:()=>Promise<T>):Promise<T>{
  if(this.active>=2){
   if(this.queue.length>=8)throw Error('password_work_full');
   await new Promise<void>(resolve=>this.queue.push(resolve));
  }
  this.active++;
  try{return await work();}
  finally{this.active--;this.queue.shift()?.();}
 }
 private derive(password:string,salt:Buffer):Promise<Buffer>{return new Promise((resolve,reject)=>scrypt(password,salt,32,WORK_FACTOR,(error,key)=>error?reject(error):resolve(key)));}
 async create(password:string):Promise<PasswordVerifier>{return this.run(async()=>{const salt=randomBytes(16);return {salt,digest:await this.derive(password,salt)};});}
 async verify(password:string,verifier:PasswordVerifier):Promise<boolean>{return this.run(async()=>{const actual=await this.derive(password,verifier.salt);return timingSafeEqual(actual,verifier.digest);});}
}
