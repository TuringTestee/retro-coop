Retro Coop guests can see the game size before joining, then download and prepare the host's exact game without choosing a file.

Audience: Human

# Lobby wireframe v4: room game download

**Current amendment:** [Approved behavior](room-rom-transfer.md) updates only affected states of [v3](lobby-wireframe-v3.md). References, direction, journeys, and scenarios remain in the linked v3 chain. These are interface sketches, not runtime proof.

## Page 1: public rooms

```text
PUBLIC ROOMS                 Search room, game, host, or code [________]
Lilac Harbor · Guest Lilac 2204 · 1/2 Waiting for guest
Host-shared NES · 2.1 MB download                         [Join]
Super Tilt Bro · No host · 0/2 Waiting for host             [Join as host]
Included game
```

Join reserves Guest and opens Page 3. The size is the host's verified byte count, rounded for reading. Unlisted rooms use the same disclosure on the invitation preview, never a public row.

## Page 3: waiting room

```text
LILAC HARBOR · PUBLIC · JA2V6CFL
Player 1 · Host: Guest Lilac 2204    Player 2 · Guest: You
Downloading game… 1.4 / 2.1 MB                            [Cancel]
Chat [message____________________] [Send]                  [Leave room]

After download: Loading game…
After verified load and peer connection: Game ready here   [Prepare to play]
After Prepare: Ready to play. Waiting for the host.
Failed transfer: Download failed.                         [Retry download]
Storage denied: Available in this tab; download again next time.
Reservation lost: Your room place expired.                [Return to rooms]
```

Cancel releases the guest reservation; Retry applies only to the current reservation. Host sees Guest downloading, loading, prepared, or disconnected near Start. Start still begins solo and releases an unprepared guest. Included games use their existing verified acquisition and Prepare path.

## Settings → Local data

```text
LOCAL DATA
Downloaded games
NES game · 2.1 MB · saved today                           [Delete game]
Saves, battery progress, preferences …
[Delete all local data]                                     [Close local data]
```

Each deletion asks for confirmation. The active game stays in memory; a later Join downloads deleted bytes again. Empty and unavailable storage states appear here, with the in-room fallback notice at the time saving fails.

## Route check

Public row or unlisted invitation → Join → verified cached copy or visible download → load and peer → Prepare → host Start. Cancel, failed download, lost reservation, and Local data deletion each show one relevant recovery action. Keyboard focus remains on the active action after each transition.
