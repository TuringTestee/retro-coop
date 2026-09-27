import React,{useLayoutEffect,useRef,useState,type HTMLAttributes} from 'react';

/** A bounded text region becomes keyboard-scrollable only when it overflows. */
export function ScrollRegion({children,...props}:HTMLAttributes<HTMLDivElement>) {
 const ref=useRef<HTMLDivElement>(null),[overflow,setOverflow]=useState(false);
 useLayoutEffect(()=>{const node=ref.current!;const measure=()=>setOverflow(node.scrollHeight>node.clientHeight+1||node.scrollWidth>node.clientWidth+1);measure();const resize=new ResizeObserver(measure),mutation=new MutationObserver(measure);resize.observe(node);for(const child of node.children)resize.observe(child);mutation.observe(node,{childList:true,subtree:true,characterData:true});return()=>{resize.disconnect();mutation.disconnect();};},[children]);
 return <div {...props} ref={ref} tabIndex={overflow?0:undefined}>{children}</div>;
}
