Retro Coop shows one action at each stage of joining a host's game: Join, wait or Cancel, then Prepare after verified load.

Audience: Human

# Lobby wireframe v6: preparation exits

**Current room-preparation sketch:** Revises [v5](lobby-wireframe-v5.md) after its [critique](lobby-critique-v5.md). Approved behavior remains [room game downloads](room-rom-transfer.md); unaffected room pages remain in [v3](lobby-wireframe-v3.md). The proposed [Create Game v2](create-game-library-wireframe-v2.md) becomes the current public-browser and host-setup sketch after reviewed approval; this page continues to own guest preparation and waiting-room recovery.

## Public directory and unlisted invitation

```text
PUBLIC ROOMS                         Search [_______________]
Lilac Harbor · Guest Lilac 2204 · 1/2 Waiting for guest
Host-shared NES · 2.1 MB download                       [Join]

UNLISTED INVITATION · Lilac Harbor · Guest Lilac 2204
Host-shared NES · 2.1 MB download                       [Join room]
```

Each entry has one Join. Its next state is the waiting room. The public list never shows the unlisted row. A full, playing, or expired room has no Join.

## Guest waiting room, while acquiring

```text
LILAC HARBOR · PUBLIC · JA2V6CFL
Player 1 · Host: Guest Lilac 2204    Player 2 · Guest: You
Checking saved game…                                [Cancel preparation]
or: Downloading game… 1.4 / 2.1 MB                  [Cancel preparation]
or: Loading game…                                   [Cancel preparation]
Chat [message____________________] [Send]
```

Cancel preparation is the same exit while checking a saved game, downloading, or loading. It aborts and releases this reservation, then shows the public directory with focus on its search box. The host's room status follows the guest's room-scoped downloading or loading report; it never guesses a phase from a missing file. The initial cached state says “Checking saved game…” then “Loading game…”.

## Guest success and recovery

```text
Game ready in this browser. Waiting for peer connection… [Leave room]
After peer connects: Game ready in this browser.       [Prepare to play]
After Prepare: Ready to play. Waiting for host.        [Leave room]
If saving failed: Available in this tab; download again next time.

Download or local load failed: [reason]                [Retry download]
                                                     [Leave room]
Reservation lost: Your room place expired.            [Return to rooms]
```

Retry rechecks the current reservation and reacquires the exact bytes. Leave exits. A failed or interrupted transfer never enables Prepare. The host sees “Guest downloading,” “Guest loading,” “Guest prepared,” or “Guest disconnected” alongside Start, reflecting a current room membership.

## Settings → Local data

```text
LOCAL DATA
Downloaded games
NES game · 2.1 MB · saved today                        [Delete game]
If empty: No downloaded games saved in this browser.
Saves, battery progress, preferences …
[Delete all local data]                                [Close local data]
```

Delete game and Delete all ask for confirmation and return focus to Local data. The current tab's loaded game stays in memory; a future join downloads deleted bytes.
