// Controlled device fixture shared by local controls and multiplayer pause probes.
window.padButtons=[];window.padAxes=[0,0];window.padConnected=true;
navigator.getGamepads=()=>padConnected ? [{id:'Diagnostic controller',index:0,connected:true,
 buttons:Array.from({length:16},(_,i)=>({pressed:padButtons.includes(i),touched:false,value:padButtons.includes(i)?1:0})),axes:padAxes}] : [];
