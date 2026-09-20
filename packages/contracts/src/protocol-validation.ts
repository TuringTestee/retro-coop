/** Structural helpers shared by bounded coordinator protocol schemas. */
export function object(value:unknown): value is Record<string,unknown> {return !!value && typeof value==='object' && !Array.isArray(value);}
export function keys(value:Record<string,unknown>,required:string[],optional:string[] = []) {return required.every(key=>Object.hasOwn(value,key)) && Object.keys(value).every(key=>required.includes(key) || optional.includes(key));}
export const text = (value:unknown,max:number) => typeof value==='string' && value.trim().length>0 && value.length<=max && !/[\u0000-\u001f\u007f]/u.test(value);
export const token = (value:unknown) => typeof value==='string' && /^[A-Za-z0-9_-]{22,64}$/.test(value);
export const integer = (value:unknown,min:number,max:number) => typeof value==='number' && Number.isSafeInteger(value) && value>=min && value<=max;

export const sha256=(value:unknown):value is string=>typeof value==='string' && /^[a-f0-9]{64}$/.test(value);
