export function roomAdmissionMessage(error:{code?:string;message:string}|undefined,retryAfterMs?:number) {
 if(retryAfterMs)return `Too many tries. Try again in ${Math.ceil(retryAfterMs/1000)} seconds.`;
 return error?.message??'';
}
