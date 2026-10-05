import type {SaveLoadView} from '../../../packages/contracts/src/gameplay.ts';

/** The caller selects required participants and owns focus and background dimming. */
export function SharedLoadDialog({load,host,accepted,busy,error,onDecision,onCancel}:{
 load:SaveLoadView;host:boolean;accepted:boolean;busy:boolean;error?:string;
 onDecision(accept:boolean):void;onCancel():void;
}){
 const deciding=load.phase==='consent'&&!host&&!accepted;
 const message=load.phase==='freezing'?'Pausing the game.':load.phase==='consent'?deciding?'The host wants to replace the current progress.':'Waiting for the other players.':load.phase==='staging'?'Preparing saved progress.':load.phase==='committing'?'Loading saved progress.':load.reason??'Keeping the previous progress. The game will stay paused.';
 return <div className="rc-dialog-card" role="alertdialog" aria-modal="true" aria-labelledby="rc-shared-load-title" aria-describedby="rc-shared-load-detail">
  <h2 id="rc-shared-load-title">Load saved game?</h2>
  <p>Saved {new Date(load.savedAt).toLocaleString()}</p>
  <p id="rc-shared-load-detail">{message}</p>
  {error&&<p role="alert">{error}</p>}
  <div className="rc-dialog-actions">
   {host&&load.phase!=='rolling_back'&&<button disabled={busy} onClick={onCancel}>Cancel load</button>}
   {!host&&load.phase==='consent'&&<button disabled={busy} onClick={()=>onDecision(false)}>Keep current</button>}
   {deciding&&<button disabled={busy} onClick={()=>onDecision(true)}>Load game</button>}
  </div>
 </div>;
}
