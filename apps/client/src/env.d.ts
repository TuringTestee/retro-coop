/// <reference types="vite/client" />
declare module 'virtual:catalog' {import type {CatalogId} from '../../../packages/contracts/src/catalog.ts';export const catalogAvailability:Record<CatalogId,boolean>;}
