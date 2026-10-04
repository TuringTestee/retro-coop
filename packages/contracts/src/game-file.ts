/** “Under 2 MB” is a strict decimal-byte limit, shared by chooser, drop and server. */
export const ZIP_ARCHIVE_LIMIT = 2_000_000;
export const isZipFile = (name:string) => /\.zip$/i.test(name);
/** Preserve the existing title bound, including a safe result after a Unicode truncation. */
export function gameFileTitle(name:string) {return name.replace(/\.nes$/i,'').replace(/[\p{C}]/gu,'').trim().slice(0,80).replace(/[\p{C}]/gu,'')||'NES game';}
