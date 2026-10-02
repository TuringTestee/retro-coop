// Shared keyboard/gamepad mapping from the playable D02 demo.
export const keyMap = {KeyZ:1, KeyC:2, AltLeft:4, AltRight:4, Space:8, ArrowUp:16, ArrowDown:32, ArrowLeft:64, ArrowRight:128};
export const defaultPadBindings = [
  ['button:0'], ['button:1'], ['button:8'], ['button:9'],
  ['button:12','axis:1:-1'], ['button:13','axis:1:1'],
  ['button:14','axis:0:-1'], ['button:15','axis:0:1'],
];
export function gamepadMask(pad) {
  if (!pad) return 0;
  return defaultPadBindings.reduce((mask,bindings,index) => mask | (bindings.some(binding => {
    const [kind,number,direction] = binding.split(':');
    return kind === 'button' ? pad.buttons[Number(number)]?.pressed : pad.axes[Number(number)] * Number(direction) > .5;
  }) ? 1 << index : 0), 0);
}
