export function roomAdmissionMessage(status:string,retryAfterMs?:number) {
 if(retryAfterMs)return `Too many tries. Try again in ${Math.ceil(retryAfterMs/1000)} seconds.`;
 return /password|closed|unavailable|expired|full/i.test(status)?status:'';
}
