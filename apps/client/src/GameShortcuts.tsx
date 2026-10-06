import React from "react";
import { bindingLabel, type Controls } from "./controls.ts";

/** Non-controller shortcuts remain beside Sound and Voice, without duplicate NES art. */
export function GameShortcuts({
  controls,
  pauseActionLabel,onSave,onLoad,busy,host,
}: {
  controls: Controls;
  pauseActionLabel?: string;onSave?:()=>void;onLoad?:()=>void;busy?:boolean;host:boolean;
}) {
  const assigned = new Set(Object.values(controls.keyboard).flat());
  const talk =
    controls.keyboard.pushToTalk
      .map(bindingLabel)
      .join(" / ") || "Unbound";
  return (
    <div className="rc-tool-stack" aria-label="Game shortcuts">
      <p>Talk: {talk}</p>
      {(
        <p>
          {!assigned.has("KeyA") && "A rapid A"}
          {!assigned.has("KeyD") && " · D rapid B"}
        </p>
      )}
      <div className="rc-tool-actions"><button disabled={busy} onClick={onSave}>Save{!assigned.has('KeyQ')?' (Q)':''}</button><button disabled={busy||!host} onClick={onLoad}>Load{host&&!busy&&!assigned.has('KeyE')?' (E)':''}</button></div>
      {!host&&<p>Only the host can load saved progress.</p>}
      <div className="rc-shortcuts" aria-label="Other shortcuts">
        {pauseActionLabel && !assigned.has("KeyP") && (
          <span>
            <strong>P</strong> {pauseActionLabel}
          </span>
        )}
        {!assigned.has("KeyM") && (
          <span>
            <strong>M</strong> Mute
          </span>
        )}

      </div>
    </div>
  );
}
