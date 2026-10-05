import React from "react";
import { bindingLabel, type Controls } from "./controls.ts";

/** Non-controller shortcuts remain beside Sound and Voice, without duplicate NES art. */
export function GameShortcuts({
  controls,
  local,
  pauseActionLabel,
}: {
  controls: Controls;
  local: boolean;
  pauseActionLabel?: string;
}) {
  const assigned = new Set(Object.values(controls.keyboard).flat());
  const talk =
    controls[controls.device ? "gamepad" : "keyboard"].pushToTalk
      .map(bindingLabel)
      .join(" / ") || "Unbound";
  return (
    <div className="rc-tool-stack" aria-label="Game shortcuts">
      <p>Talk: {talk}</p>
      {!controls.device && (
        <p>
          {!assigned.has("KeyA") && "A rapid A"}
          {!assigned.has("KeyD") && " · D rapid B"}
        </p>
      )}
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
        {!assigned.has("KeyQ") && (
          <span>
            <strong>Q</strong> Save
          </span>
        )}
        {local && !assigned.has("KeyE") && (
          <span>
            <strong>E</strong> Load
          </span>
        )}
      </div>
    </div>
  );
}
