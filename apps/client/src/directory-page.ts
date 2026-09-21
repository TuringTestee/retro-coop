export const DIRECTORY_PAGE_SIZE=4;
export function pageCount(length:number,size=DIRECTORY_PAGE_SIZE){return Math.max(1,Math.ceil(length/size));}
export function clampPage(page:number,length:number,size=DIRECTORY_PAGE_SIZE){return Math.min(Math.max(0,page),pageCount(length,size)-1);}
export function pageRows<T>(rows:readonly T[],page:number,size=DIRECTORY_PAGE_SIZE){const current=clampPage(page,rows.length,size);return{page:current,pages:pageCount(rows.length,size),rows:rows.slice(current*size,current*size+size)};}
