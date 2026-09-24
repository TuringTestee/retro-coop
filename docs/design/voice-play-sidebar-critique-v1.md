# Voice and play sidebar: page critique of v1

The first pass places the right tasks near play, but its voice states need clearer recovery and its controls need a faithful device label.

| Page | Supports | Missing / consequence | Remove or revise |
|---|---|---|---|
| P1 shared | V1 entry, C1 readout, E1 leave | `P1` alone implies the host owns P1; a guest needs `Player 2` and current local input source. Long key names can break the narrow card. | Show `Your controls · Player N`, truncate no binding; wrap each binding value. Move room status below voice. |
| P2 request/live | V1 permission, V2 mute | Push mode is only prose outside the actual box; a player cannot see the exact hold action or binding. `Voice settings` competes with header Settings unless its role is explicit. | Draw the push state as its own card. Label `Voice settings` for device/remote controls only; header Settings remains general. |
| P3 error | V1 recovery | `Permission denied` may be wrong for no device or attachment failure. Remote playback failure has no actual screen. | Use precise error text; draw a separate remote playback state with `Enable voice sound`. |
| P4 narrow | C3 access | A single row may overflow with remapped labels; `Room status / Leave / Chat` is a placeholder, not a usable state. | Use stacked action/value rows and actual room controls; keep cards within viewport. |

| Rule | P1 | P2 | P3 | P4 |
|---|---|---|---|---|
| Complete journeys | Failed: guest role absent | Failed: push state absent | Failed: remote recovery absent | Failed: room actions placeholder |
| Feature support | Failed: long binding behavior unproven | Failed: hold entry missing | Failed: error variants merged | Failed: chat control undefined |
| Information just in time | Met: bindings/voice at play | Failed: mapped talk key not visible | Failed: generic permission text | Met: cards after game |
| One clear forward path | Met: one opt-in | Failed: Settings names ambiguous | Met: one retry | Met: no overlay |
| Concise and consistent | Failed: `P1` ambiguous | Failed: detail name inconsistent | Met: short error | Failed: placeholder labels |
| Borrow before inventing | Met: mapped action readout | Met: visible voice state | Met: recoverable error | Unproven: narrow geometry |

The revised screen set must show the guest role, push-to-talk, remote playback recovery, and a concrete narrow room section. Geometry remains implementation evidence to gather in a browser.
