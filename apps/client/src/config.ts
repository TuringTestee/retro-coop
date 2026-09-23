// Only PUBLIC_ variables are exposed by Vite. Coordinator environment stays server-side.
const endpoint = import.meta.env?.PUBLIC_COORDINATOR_URL || '/coordinator';
export const clientConfig = Object.freeze({coordinatorUrl: endpoint});
