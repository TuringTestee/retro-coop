import { createPortal } from "react-dom";
import React, { useEffect, useRef, useState } from "react";
import {
  actions,
  bindingLabel,
  conflict,
  labels,
  validControls,
  type Action,
  type Controls,
} from "./controls.ts";
import {
  VirtualContacts,
  boundedOrigin,
  directionMask,
} from "./virtual-controls.ts";

const directionGlyphs = { up: "↑", left: "←", down: "↓", right: "→" } as const;

export function Controller({
  controls,
  inputFallback=false,
  covered,
  enabled,
  playing,
  editRequest,
  resetKey,
  onMask,
  onChange,
  onEditing,
  onRequestEdit,
  editorHost,
  phone,
  storageIssue,
}: {
  controls: Controls;
  inputFallback?: boolean;
  covered: boolean;
  enabled: boolean;
  playing: boolean;
  editRequest: number;
  resetKey: string;
  onMask: (mask: number) => void;
  onChange: (controls: Controls, current: () => boolean) => Promise<boolean>;
  onEditing: (editing: boolean) => void;
  onRequestEdit: () => void;
  editorHost: React.RefObject<HTMLDivElement | null>;
  phone: boolean;
  storageIssue?: string;
}) {
  const contacts = useRef(new VirtualContacts()),
    pointers = useRef(
      new Map<number, { generation: number; x: number; y: number }>(),
    );
  const maskCallback = useRef(onMask);
  maskCallback.current = onMask;
  const [mask, setMask] = useState(0),
    [dot, setDot] = useState({ x: 0, y: 0 }),
    [draft, setDraft] = useState<Controls | null>(null),
    [capture, setCapture] = useState<Action>("a"),
    [binding, setBinding] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const editorGeneration = useRef(0), lastEditRequest = useRef(editRequest);
  const endEdit = () => {
    ++editorGeneration.current;
    setSaving(false);
    setBinding(null);
    setDraft(null);
  };
  const beginEdit = () => {
    ++editorGeneration.current;
    setSaving(false);
    setBinding(null);
    setDraft(structuredClone(controls));
  };
  useEffect(() => () => { ++editorGeneration.current; }, []);
  const captureBox = useRef<HTMLDivElement>(null),
    root = useRef<HTMLDivElement>(null);
  const clear = () => {
    contacts.current.clear();
    pointers.current.clear();
    setMask(0);
    setDot({ x: 0, y: 0 });
    maskCallback.current(0);
  };
  const publish = () => {
    const next = contacts.current.mask();
    setMask(next);
    maskCallback.current(next);
  };
  useEffect(() => {
    clear();
  }, [enabled, resetKey, !!draft]);
  useEffect(() => {
    onEditing(!!draft);
    return () => onEditing(false);
  }, [!!draft]);
  useEffect(() => {
    if (lastEditRequest.current === editRequest) return;
    lastEditRequest.current = editRequest;
    if (editRequest) beginEdit(); else endEdit();
  }, [editRequest]);
  useEffect(() => {
    if (draft) captureBox.current?.focus();
  }, [!!draft, capture]);

  useEffect(() => {
    const hidden = () => {
        if (document.hidden) clear();
      },
      focus = () => {
        const active = document.activeElement;
        if (
          !root.current?.contains(active) &&
          !active?.matches('canvas[aria-label="NES game screen"]')
        )
          clear();
      };
    window.addEventListener("blur", clear);
    window.addEventListener("resize", clear);
    document.addEventListener("visibilitychange", hidden);
    document.addEventListener("focusin", focus);
    return () => {
      window.removeEventListener("blur", clear);
      window.removeEventListener("resize", clear);
      document.removeEventListener("visibilitychange", hidden);
      document.removeEventListener("focusin", focus);
      maskCallback.current(0);
    };
  }, []);
  const start = (
    event: React.PointerEvent<HTMLElement>,
    bit: number,
    pad = false,
  ) => {
    event.stopPropagation();
    if (!enabled || draft || event.button !== 0) return;
    event.preventDefault();
    event.currentTarget.focus();
    event.currentTarget.setPointerCapture(event.pointerId);
    const rect = event.currentTarget.getBoundingClientRect(),
      x = boundedOrigin(event.clientX, rect.x + rect.width / 2),
      y = boundedOrigin(event.clientY, rect.y + rect.height / 2);
    const generation = contacts.current.begin(
      event.pointerId,
      pad ? directionMask(event.clientX - x, event.clientY - y) : bit,
    );
    pointers.current.set(event.pointerId, { generation, x, y });
    publish();
  };
  const move = (event: React.PointerEvent<HTMLElement>) => {
    const held = pointers.current.get(event.pointerId);
    if (!held) return;
    event.stopPropagation();
    const x = event.clientX - held.x,
      y = event.clientY - held.y;
    contacts.current.update(
      event.pointerId,
      held.generation,
      directionMask(x, y),
    );
    const radius = Math.max(
        0,
        (event.currentTarget.getBoundingClientRect().width - 44) / 2,
      ),
      length = Math.max(1, Math.hypot(x, y) / Math.max(1, radius));
    setDot({ x: x / length, y: y / length });
    publish();
  };
  const end = (event: React.PointerEvent<HTMLElement>) => {
    event.stopPropagation();
    const held = pointers.current.get(event.pointerId);
    if (!held) return;
    contacts.current.end(event.pointerId, held.generation);
    pointers.current.delete(event.pointerId);
    if (event.currentTarget.classList.contains("rc-pad-drag"))
      setDot({ x: 0, y: 0 });
    publish();
  };
  const key = (
    event: React.KeyboardEvent<HTMLElement>,
    bit: number,
    down: boolean,
  ) => {
    if (!["Enter", " "].includes(event.key)) return;
    const id = -(
      bit * 4 +
      (event.code === "Space" ? 1 : event.code === "NumpadEnter" ? 2 : 3)
    );
    const held = pointers.current.get(id);
    // A release originating on the canvas still belongs to the physical source.
    if (!down && !held) return;
    event.preventDefault();
    event.stopPropagation();
    if (!enabled || draft || event.repeat) return;
    if (down) {
      const generation = contacts.current.begin(id, bit);
      pointers.current.set(id, { generation, x: 0, y: 0 });
    } else {
      if (held) {
        contacts.current.end(id, held.generation);
        pointers.current.delete(id);
      }
    }
    publish();
  };
  const padKey = (event: React.KeyboardEvent<HTMLElement>, down: boolean) => {
    const bit = (
      { ArrowUp: 16, ArrowDown: 32, ArrowLeft: 64, ArrowRight: 128 } as Record<
        string,
        number
      >
    )[event.code];
    if (!bit) {
      if (down && ["Enter", " "].includes(event.key)) {
        event.preventDefault();
        event.stopPropagation();
      }
      return;
    }
    const id = -bit,
      held = pointers.current.get(id);
    if (!down && !held) return;
    event.preventDefault();
    event.stopPropagation();
    if (!enabled || draft || event.repeat) return;
    if (down) {
      const generation = contacts.current.begin(id, bit);
      pointers.current.set(id, { generation, x: 0, y: 0 });
    } else if (held) {
      contacts.current.end(id, held.generation);
      pointers.current.delete(id);
    }
    publish();
  };
  const button = (action: Action) => {
    const bit = 1 << actions.indexOf(action);
    return (
      <button
        type="button"
        className={`rc-nes-button rc-nes-${action}`}
        aria-label={`NES ${labels[action]}`}
        aria-pressed={!!(mask & bit)}
        aria-disabled={!enabled || !!draft}
        onPointerDown={(event) => start(event, bit)}
        onPointerUp={end}
        onPointerCancel={end}
        onLostPointerCapture={end}
        onKeyDown={(event) => key(event, bit, true)}
        onKeyUp={(event) => key(event, bit, false)}
        onClick={(event) => event.stopPropagation()}
      >
        {labels[action]}
      </button>
    );
  };
  const source = controls.device && !inputFallback ? "gamepad" : "keyboard";
  const short: Record<string, string> = {
    ArrowUp: "↑",
    ArrowDown: "↓",
    ArrowLeft: "←",
    ArrowRight: "→",
    AltLeft: "Alt",
    AltRight: "Alt",
    Space: "Space",
  };
  const fullHint = (action: Action) =>
    controls[source][action].map(bindingLabel).join(" / ") || "Unbound";
  const hint = (action: Action) => {
    const primary = controls[source][action][0];
    if (!primary) return "Unbound";
    if (source === "gamepad" && primary.startsWith("button:"))
      return String(Number(primary.split(":")[1]) + 1);
    return short[primary] ?? bindingLabel(primary);
  };
  const directionHint = (["up", "left", "down", "right"] as const)
    .map(action => `${labels[action]}: ${fullHint(action)}`).join("; ");
  const duplicate =
    draft && binding ? conflict(draft.keyboard, capture, binding) : undefined;
  const editor = draft ? (
    <div className="rc-controller-editor" aria-label="Edit controller mappings">
      <label>
        Control
        <select
          disabled={saving}
          value={capture}
          onChange={(event) => {
            setCapture(event.target.value as Action);
            setBinding(null);
          }}
        >
          {actions.slice(0, 8).map((action) => (
            <option key={action} value={action}>
              {labels[action]}
            </option>
          ))}
        </select>
      </label>
      <div
        ref={captureBox}
        tabIndex={0}
        className="rc-controller-capture"
        aria-label="Capture controller key"
        onKeyDown={(event) => {
          if (event.code === "Tab") return;
          event.preventDefault();
          event.stopPropagation();
          if (saving) return;
          if (event.code === "Escape") {
            endEdit();
            return;
          }
          if (
            !event.ctrlKey &&
            !event.metaKey &&
            (!event.altKey ||
              event.code === "AltLeft" ||
              event.code === "AltRight")
          ) {
            setBinding(event.code);
            if (!conflict(draft.keyboard, capture, event.code))
              setDraft({
                ...draft,
                keyboard: { ...draft.keyboard, [capture]: [event.code] },
              });
          }
        }}
      >
        Current:{" "}
        {controls.keyboard[capture].map(bindingLabel).join(" / ") || "Unbound"}{" "}
        · Draft:{" "}
        {binding
          ? bindingLabel(binding)
          : draft.keyboard[capture].map(bindingLabel).join(" / ")}
        . Press a key.
      </div>
      <p role="status">
        {duplicate
          ? `${bindingLabel(binding!)} is used for ${labels[duplicate]}. Choose another.`
          : storageIssue
            ? "Could not save controls. Try Save again."
            : "Tab moves focus. Escape cancels."}
      </p>
      <div>
        <button
          disabled={saving || !!duplicate || !validControls(draft)}
          onClick={() => {
            const generation = editorGeneration.current;
            const current = () => editorGeneration.current === generation;
            setSaving(true);
            void onChange(draft, current).then((saved) => {
              if (!current()) return;
              setSaving(false);
              if (saved) endEdit();
            });
          }}
        >
          Save
        </button>
        <button disabled={saving} onClick={endEdit}>
          Cancel
        </button>
      </div>
    </div>
  ) : null;
  return (
    <div
      ref={root}
      inert={covered}
      aria-hidden={covered}
      className={`rc-controller-band${draft ? " rc-controller-editing" : ""}${phone ? " rc-phone-controller" : ""}`}
      onClick={(event) => event.stopPropagation()}
      onKeyDown={(event) => {
        if (event.key === "Tab") clear();
      }}
    >
      {draft ? (
        phone && editorHost.current ? (
          createPortal(editor, editorHost.current)
        ) : (
          editor
        )
      ) : (
        <>
          <div
            className="rc-nes-controller"
            data-game-input
            aria-label="NES controller"
          >
            <div
              className="rc-thumb-pad"
              role="group"
              aria-label="Direction pad"
            >
              <span
                className="rc-thumb-dot"
                aria-hidden="true"
                style={{ transform: `translate(${dot.x}px,${dot.y}px)` }}
              />
              {(["up", "left", "down", "right"] as const).map((action) => {
                const bit = 1 << actions.indexOf(action);
                return (
                  <span
                    key={action}
                    className={`rc-direction rc-direction-${action}`}
                    data-pressed={!!(mask & bit)}
                    aria-hidden="true"
                  >
                    {directionGlyphs[action]}
                  </span>
                );
              })}
              <button
                className="rc-pad-drag"
                type="button"
                aria-label="Direction pad: use arrow keys or drag"
                aria-disabled={!enabled}
                onPointerDown={(event) => start(event, 0, true)}
                onKeyDown={(event) => padKey(event, true)}
                onKeyUp={(event) => padKey(event, false)}
                onPointerMove={move}
                onPointerUp={end}
                onPointerCancel={end}
                onLostPointerCapture={end}
              />
            </div>
            <div className="rc-nes-system">
              {button("select")}
              {button("start")}
            </div>
            <div className="rc-nes-actions">
              {button("b")}
              {button("a")}
            </div>
          </div>
          {!playing && (
            <div
              className="rc-controller-mappings"
              aria-label={`${source === "keyboard" ? "Keyboard" : "Gamepad"} controls`}
            >
              <div className="rc-connected-hints">
                <span className="rc-connected-move" aria-label={directionHint} title={directionHint}>
                  {source === "gamepad" ? "Gamepad buttons" : "Move"} <i aria-hidden="true" />{" "}
                  {(["up", "left", "down", "right"] as const)
                    .map(action => {const glyph = directionGlyphs[action];const binding = hint(action);return glyph === binding ? glyph : `${glyph}${binding}`;})
                    .join(" ")}
                </span>
                <div>
                  {(["select", "start"] as const).map((action) => (
                    <span key={action} className={`rc-connected-${action}`} aria-label={`${labels[action]}: ${fullHint(action)}`} title={`${labels[action]}: ${fullHint(action)}`}>
                      {labels[action]} <i aria-hidden="true" /> {hint(action)}
                    </span>
                  ))}
                </div>
                <div>
                  {(["b", "a"] as const).map((action) => (
                    <span key={action} className={`rc-connected-${action}`} aria-label={`${labels[action]}: ${fullHint(action)}`} title={`${labels[action]}: ${fullHint(action)}`}>
                      {labels[action]} <i aria-hidden="true" /> {hint(action)}
                    </span>
                  ))}
                </div>
              </div>
              {!controls.device && (
                <button
                  onClick={onRequestEdit}
                >
                  Edit
                </button>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
