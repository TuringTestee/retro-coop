import React,{useLayoutEffect,useRef,useState,type HTMLAttributes,type RefObject} from 'react';

export function useOverflowFocus<T extends HTMLElement>(ref:RefObject<T|null>) {
 const [overflow,setOverflow]=useState(false);
 useLayoutEffect(()=>{const node=ref.current;if(!node)return;const measure=()=>setOverflow(node.scrollHeight>node.clientHeight+1||node.scrollWidth>node.clientWidth+1);const resize=new ResizeObserver(measure);resize.observe(node);const mutation=new MutationObserver(measure);mutation.observe(node,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['open','hidden','class','style']});measure();return()=>{resize.disconnect();mutation.disconnect();};},[ref]);
 return overflow?0:undefined;
}
/** Only overflowing text regions enter the keyboard order; empty space never does. */
export function ScrollRegion({children,...props}:HTMLAttributes<HTMLDivElement>) {
 const ref=useRef<HTMLDivElement>(null),tabIndex=useOverflowFocus(ref);
 return <div {...props} ref={ref} tabIndex={tabIndex}>{children}</div>;
}

/** Browsers may leave a partly visible focused control at a scroll edge.
 * Reveal its whole outline in each scroll owner, without moving page regions. */
export function useFocusVisibility() {
 useLayoutEffect(()=>{let frame=0;const reveal=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{const target=document.activeElement;if(!(target instanceof HTMLElement)||!target.closest('.tool-page'))return;const style=getComputedStyle(target),margin=Math.max(0,parseFloat(style.outlineWidth)||0)+Math.max(0,parseFloat(style.outlineOffset)||0)+1;
  for(let owner=target.parentElement;owner;owner=owner.parentElement){const overflow=getComputedStyle(owner),box=owner.getBoundingClientRect(),bounds=target.getBoundingClientRect();const left=box.left+owner.clientLeft,top=box.top+owner.clientTop,right=left+owner.clientWidth,bottom=top+owner.clientHeight;
   if(/auto|scroll/.test(overflow.overflowX)&&owner.scrollWidth>owner.clientWidth){if(bounds.left-margin<left)owner.scrollLeft+=bounds.left-margin-left;else if(bounds.right+margin>right)owner.scrollLeft+=bounds.right+margin-right;}
   if(/auto|scroll/.test(overflow.overflowY)&&owner.scrollHeight>owner.clientHeight){if(bounds.top-margin<top)owner.scrollTop+=bounds.top-margin-top;else if(bounds.bottom+margin>bottom)owner.scrollTop+=bounds.bottom+margin-bottom;}
  }
 });};document.addEventListener('focusin',reveal);return()=>{cancelAnimationFrame(frame);document.removeEventListener('focusin',reveal);};},[]);
}
