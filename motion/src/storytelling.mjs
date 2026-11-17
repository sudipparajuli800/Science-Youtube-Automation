// Motion is derived from the spoken cues and frame, including out-of-order seeks.
export function beatState(frame, index, cues, frames, count, treatment = 'draw') {
  const starts = Array.from({length: count}, (_, i) => Math.max(0, Math.min(frames - 2,
    Number.isFinite(cues[i]) ? cues[i] : i * frames * .6 / Math.max(1, count))));
  const start = starts[index];
  const entrance = Math.min(16, Math.max(1, frames - 1 - start));
  const p = Math.max(0, Math.min(1, (frame - start) / entrance));
  const ease = 1 - Math.pow(1 - p, 3);
  const active = frame >= start && !starts.slice(index + 1).some(cue => frame >= cue);
  return {
    visible: p,
    draw: treatment === 'draw' ? p : 1,
    opacity: treatment === 'focus' && frame >= start ? (active ? 1 : .65) : p,
    shift: treatment === 'assemble' ? (1 - ease) * 65 : 0,
    rotation: treatment === 'assemble' ? (1 - ease) * (index % 2 ? 7 : -7) : 0,
    active,
  };
}
