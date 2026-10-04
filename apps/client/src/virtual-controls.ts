/** Independent contacts share a mask; stale releases cannot end a newer hold. */
export class VirtualContacts {
  private next = 0;
  private contacts = new Map<number, { generation: number; mask: number }>();
  begin(id: number, mask: number) {
    const generation = ++this.next;
    this.contacts.set(id, { generation, mask });
    return generation;
  }
  update(id: number, generation: number, mask: number) {
    const contact = this.contacts.get(id);
    if (contact?.generation === generation) contact.mask = mask;
  }
  end(id: number, generation: number) {
    if (this.contacts.get(id)?.generation === generation)
      this.contacts.delete(id);
  }
  clear() {
    this.contacts.clear();
  }
  mask() {
    let result = 0;
    for (const contact of this.contacts.values()) result |= contact.mask;
    return result;
  }
}
/** Eight directions around a neutral center, using existing NES mask bits. */
export function directionMask(x: number, y: number, deadzone = 10) {
  if (Math.hypot(x, y) <= deadzone) return 0;
  const sector = (Math.round(Math.atan2(y, x) / (Math.PI / 4)) + 8) % 8;
  return [128, 128 | 32, 32, 32 | 64, 64, 64 | 16, 16, 16 | 128][sector];
}
export function boundedOrigin(value: number, center: number, radius = 16) {
  return Math.max(center - radius, Math.min(center + radius, value));
}
