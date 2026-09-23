Audience: Human

# Room game downloads — proposed change

The host chooses a NES file once when creating a room. Joining players download that exact game into their browsers automatically, then choose **Prepare to play**. They never need to find or upload their own copy.

**Status:** Proposal for the user's 2026-09-23 direction. The running app still requires a guest's matching file for host-provided games. This proposal changes the approved local-file rule in `browser-nes-platform.md`, `lobby-refactor.md`, and the current lobby wireframe; it does not claim that transfer is implemented.

## Decision and pattern

The user reported that a guest in “Lilac Harbor” could connect but could not prepare without the host's NES file, and directed a Warcraft III-style flow: upload once during lobby creation; joining players download and keep the game in their browser. Blizzard's [Warcraft III custom-game description](https://classic.battle.net/war3/faq/bnetfaq.shtml) confirms the useful lobby pattern of choosing a map when creating a public or private custom game. The automatic NES transfer and browser storage are the user's direction for Retro Coop, not a claim taken from that description.

This replaces “file stays only with the host,” “bring your own matching file,” and the guest file picker in a host-provided room. It keeps public/unlisted access, anonymous two-player rooms, exact-file matching, explicit guest **Prepare to play**, host **Start game**, browser-local emulation, and the existing included games. Included games already have a hosted asset and use the same guest acquisition states without a new host upload.

## Journeys

| Journey | Actions and just-in-time information | Outcome and recovery |
| --- | --- | --- |
| Host a personal game | Choose Public or Unlisted, then choose/drop one `.nes` file. Beside that control, say “Guests download this game. The room server keeps it while the room is open.” Validate locally, show upload progress and Cancel, then publish the room only after the server verifies the complete file. | The host sees the waiting room and can play locally or wait. Invalid input or failed/cancelled upload leaves no public room; show the cause and **Retry upload** using the selected file. |
| Join a host-provided game | In the directory, show “Host-shared NES · download size” and one **Join** action. Join reserves the guest place and starts the exact download or uses an already verified browser copy. Show progress and **Cancel** in the room. Verify and save the file in the browser, load it, then show **Prepare to play**. | The guest prepares; the host sees Guest ready and can start shared play. A failed, interrupted, or altered download shows **Retry download**. A lost reservation says **Return to rooms**; retrying cannot silently take another person's place. |
| Start together | Host sees whether the guest is downloading, loading, prepared, or disconnected. Guest sees “Ready; waiting for host” only after the exact bytes and emulator state are ready. Host chooses **Start game**. | Both start from the existing synchronized initial-state barrier. If the host starts while download/preparation is incomplete, the existing solo-start rule releases the guest with a clear notice. |
| Return to the same game | On a later join, check the browser's saved copy by exact SHA-256 before downloading. If absent, evicted, or invalid, download from the current room. | No new file picker. Browser storage may be denied or evicted; if saving fails, allow this tab's verified in-memory copy to play and say it must be downloaded again next time. |
| Manage downloaded games | Open **Local data** from Settings, see saved game bytes and size, and remove an individual copy or clear all local data. | Deletion confirms the copy was removed. Active play keeps its in-memory game; a future join downloads again. |

## Screen states

```text
PUBLIC ROOMS
Lilac Harbor  ·  Guest Lilac 2204  ·  1/2 waiting
Host-shared NES · 2.1 MB download                 [Join]
```

```text
HOST YOUR NES FILE
Access [Public v]  [Choose NES file]
Guests download this game. The room server keeps it while the room is open.

Uploading game… 1.4 / 2.1 MB                    [Cancel]
```

```text
LILAC HARBOR · PUBLIC · JA2V6CFL
Player 1 · Host: Guest Lilac 2204   Player 2 · Guest: You
Downloading game… 1.4 / 2.1 MB                   [Cancel]

After verified load: Game ready in this browser  [Prepare to play]
After Prepare: Ready to play. Waiting for host.   [Leave room]
On failure: Download failed: connection lost.    [Retry download]
```

The directory says what will download before **Join**. The room shows progress when it matters. There is one way forward at each state: choose the file to host, **Join** to enter, **Prepare to play** after download, and **Start game** for the host. Cancel and Retry are recovery actions. The guest's matching-file picker and its old explanation disappear from this journey.

## Scope and acceptance

1. A host-provided public or unlisted room is not joinable or listed until its exact ROM bytes are available to authenticated guests. No filename, local path, raw file, or direct download URL appears in the public directory.
2. A guest in a separate browser session can Join, automatically acquire the exact host file, save a verified browser copy when storage works, Prepare, and reach shared play without opening a file picker. Repeat joining reuses a verified copy.
3. The host can cancel or retry an upload without a ghost room; a guest can cancel or retry a download without a ghost ready state. Membership changes and room closure invalidate old transfers.
4. Downloaded bytes must match the host's published fingerprint before storage or play. A mismatch never becomes “Ready.”
5. Room closure removes the server's temporary copy; each browser owns deletion of its saved copy. Browser quota or eviction produces honest feedback and recovery.
6. Included-game rooms keep their current first-host and replenishment behavior. No new requirement asks that player to upload a file.

**Limits to review:** Hosting now distributes user-provided content and uses server storage and bandwidth. The server needs enforceable capacity and a public-release content policy. Browser storage is normally best-effort and can be evicted or denied; [browser storage behavior](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria) rules out promising permanent storage. The proposed fallback is playable in memory for the current tab with a visible “download again next time” notice.
