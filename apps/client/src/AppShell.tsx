import React from 'react';

export type ShellPage='main'|'lobbies'|'lobby'|'playing'|'local';
export function AppShell({page,title,guest,status,statusAction,attention=false,onIdentity,onHome,identityOpen=false,titleControl,identityControl,theme,onTheme,modal=false,blocker,tooSmall=false,children,back,actions}:{
 page:ShellPage;title:string;guest:string;status:string;statusAction?:React.ReactNode;attention?:boolean;onIdentity:()=>void;onHome:()=>void;identityOpen?:boolean;titleControl?:React.ReactNode;identityControl?:React.ReactNode;theme:'light'|'dark';onTheme:()=>void;modal?:boolean;blocker?:React.ReactNode;tooSmall?:boolean;children:React.ReactNode;back?:React.ReactNode;actions?:React.ReactNode;
}){
 return <main className={`rc-shell rc-page-${page}`} data-page={page}>
  <header className="rc-header" inert={modal||!!blocker} aria-hidden={modal||!!blocker}><button className="rc-logo" type="button" aria-label="Retro Coop" title="Back to Main Page" onClick={onHome}><span className="rc-logo-mark">R</span>RETRO<span>COOP</span></button><div className="rc-trail" title={title}>{titleControl??`/ ${title}`}</div><div className="rc-identity">{identityControl??<button type="button" aria-expanded={identityOpen} disabled={tooSmall} onClick={onIdentity}>Your name: {guest}<span aria-hidden="true">⌄</span></button>}</div><button className="rc-theme-switch" type="button" aria-label={`Switch to ${theme==='light'?'dark':'light'} mode`} title={`Switch to ${theme==='light'?'dark':'light'} mode`} onClick={onTheme}><span aria-hidden="true">{theme==='light'?'☾':'☀'}</span><span className="rc-theme-label">{theme==='light'?'Dark':'Light'}</span></button></header>
  <div className={`rc-status${attention?' attention':''}`} role="status" aria-live="polite" tabIndex={0} inert={modal||!!blocker} aria-hidden={modal||!!blocker}>{status&&<span className="rc-status-dot" aria-hidden="true"/>}<span className="rc-status-copy">{status}</span>{statusAction}</div>
  <div className="rc-stage" inert={!!blocker} aria-hidden={!!blocker}><div className={`rc-stage-content${tooSmall?' rc-stage-constrained':''}`} inert={tooSmall} aria-hidden={tooSmall}>{children}</div>{tooSmall&&<div className="rc-size-guard" role="alert"><strong>Make the window larger to continue.</strong><span>Enlarge this window or reduce browser zoom.{page==='lobby'||page==='playing'?' Your lobby stays open.':page==='local'?' Your game stays open.':''}</span></div>}</div>
  <footer className="rc-footer" inert={modal||!!blocker} aria-hidden={modal||!!blocker}><div className="rc-footer-back">{back}</div><div className="rc-footer-actions" inert={tooSmall} aria-hidden={tooSmall}>{actions}</div></footer>
  {blocker&&<div className="rc-dialog-layer">{blocker}</div>}
 </main>;
}
