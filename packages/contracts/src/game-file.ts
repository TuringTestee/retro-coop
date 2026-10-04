/** “Under 2 MB” is a strict decimal-byte limit, shared by chooser, drop and server. */
export const ZIP_ARCHIVE_LIMIT = 2_000_000;
export const isZipFile = (name:string) => /\.zip$/i.test(name);
