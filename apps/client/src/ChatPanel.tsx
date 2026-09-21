import React,{useEffect,useLayoutEffect,useRef,useState} from 'react';
import {CHAT_LIMITS,validChatText} from '../../../packages/contracts/src/chat.ts';
import type {ChatState} from './chat-client.ts';
export function ChatPanel({state,connected,onDraft,onSend,onDiscard}:{state:ChatState;connected:boolean;onDraft:(text:string)=>void;onSend:()=>void;onDiscard:()=>void}) {
 const [typing,setTyping]=useState(false),[now,setNow]=useState(Date.now);
 useEffect(()=>{setNow(Date.now());if(!state.outbox?.retryAt) return;const timer=setInterval(()=>setNow(Date.now()),250);return ()=>clearInterval(timer);},[state.outbox?.retryAt]);
 const wait=Math.max(0,Math.ceil(((state.outbox?.retryAt ?? 0)-now)/1000));
 const log=useRef<HTMLOListElement>(null),follow=useRef(true);
 const [unread,setUnread]=useState(false);
 useLayoutEffect(()=>{if(!state.messages.length){follow.current=true;setUnread(false);}if(follow.current && log.current) log.current.scrollTop=log.current.scrollHeight;else setUnread(true);},[state.messages.at(-1)?.id]);
 const count=[...state.draft].length;
 return <section className="chat-panel" aria-labelledby="chat-heading">
  <h3 id="chat-heading">Room chat</h3>
  <p className="hint">Chat is temporary; messages from before you joined aren't shown.</p>
  <ol ref={log} onScroll={()=>{const element=log.current!;follow.current=element.scrollHeight-element.clientHeight-element.scrollTop<24;if(follow.current) setUnread(false);}} role="log" aria-label="Room messages" aria-live="polite" aria-relevant="additions text">{state.messages.map(message=><li key={message.id}><strong>{message.nickname} ({message.sender})</strong><p>{message.text}</p></li>)}</ol>
  {unread && <button onClick={()=>{follow.current=true;log.current!.scrollTop=log.current!.scrollHeight;setUnread(false);}}>New messages · Jump to latest</button>}
  <form onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget as Node))setTyping(false);}} onSubmit={event=>{event.preventDefault();if(validChatText(state.draft) && !state.outbox){setTyping(false);onSend();}}}>
   <label htmlFor="chat-message">Chat message</label><textarea id="chat-message" value={state.draft} readOnly={!!state.outbox} onChange={event=>onDraft(event.target.value)} onFocus={()=>setTyping(true)} aria-describedby="chat-help"/>
   <p id="chat-help" className="hint">{typing ? 'Typing in chat · game input released. Focus the game screen to play.' : 'Focus the game screen to play.'} {count>=450 && `${count}/${CHAT_LIMITS.characters} characters`}</p>
   {count>CHAT_LIMITS.characters && <p role="status">Messages can contain at most {CHAT_LIMITS.characters} characters.</p>}
   {!state.outbox && <button disabled={!validChatText(state.draft)} type="submit">Send message</button>}
   {state.outbox && <div role="status">{state.sending ? 'Sending…' : <>Not sent or delivery unconfirmed. {state.outbox.error} {wait ? `Retry in ${wait} seconds.`:''} <button type="button" disabled={!connected || wait>0} onClick={onSend}>Retry message</button> <button type="button" onClick={onDiscard}>Discard message</button></>}</div>}
  </form>
  {!connected && <p role="status">Chat disconnected. Reconnect rooms, then retry any unsent message.</p>}
 </section>;
}
