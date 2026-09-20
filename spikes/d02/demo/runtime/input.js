// Shared keyboard/gamepad mapping from the playable D02 demo.
export const keyMap = {KeyX:1, KeyZ:2, ShiftLeft:4, ShiftRight:4, Enter:8, ArrowUp:16, ArrowDown:32, ArrowLeft:64, ArrowRight:128};
export function gamepadMask(pad) {
  if (!pad) return 0;
  let mask = 0;
  for (const [index, bit] of [[0,1],[1,2],[8,4],[9,8],[12,16],[13,32],[14,64],[15,128]]) if (pad.buttons[index]?.pressed) mask |= bit;
  if (pad.axes[0] < -.5) mask |= 64;
  if (pad.axes[0] > .5) mask |= 128;
  if (pad.axes[1] < -.5) mask |= 16;
  if (pad.axes[1] > .5) mask |= 32;
  return mask;
}
