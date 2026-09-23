The Create Game page must stay usable when local storage, a selected file, or the room upload fails. Each control below has an entry state and a visible result.

Audience: Human

# Create Game scenarios

| ID / journey | Trigger and expected visible state | Recovery |
| --- | --- | --- |
| C01 / J1 | Open home with live public directory. **Create game** is separate from rows' Join actions. | Directory load/error shows Retry; creating remains reachable if local setup is possible. |
| C02 / J2 | Open Create Game with a saved last-used game. Preview shows its name, source, size and a real captured frame or “No preview yet.” | If metadata/preview missing, text remains; no blank image. |
| C03 / J2,J4 | A ROM arrives by local import and later by guest download, or vice versa. Your games has one row keyed by SHA-256; last used moves it to the top. | Hash/byte mismatch marks the row unusable; selecting it never publishes a room. |
| C04 / J3 | Add or drop one valid `.nes` file. Validation progress and selected game appear on Create Game; Save locally succeeds or explains tab-only availability. | Invalid/multiple files keep the prior selection and show one actionable error. |
| C05 / J1–J3 | Change Standard/Relay-only beside public Join, invitation Join, or Create room. Change Public/Unlisted on Create Game with a verified, locally loaded selection. **Create room** uses both choices; Join uses the selected connection policy. | Neither change starts a room or peer contact by itself. Relay-only failure never silently falls back to Standard; no selection/failed local load disables Create with a nearby reason. |
| C06 / J3 | Upload begins, advances, then confirms. Waiting room appears only after server verification. | Cancel aborts; timeout/error offers Retry upload or Back to Create Game with selection preserved. |
| C07 / J2,J4 | Open saved entry after reload. Bytes are rehashed and loaded through the same local player path before enabling Create; the selected hash, fingerprint and File stay bound to one generation. Guest download bytes use the same verification gate. | Eviction, corruption, load failure or IndexedDB denial shows unavailable and Add NES file. A late load from a previous choice cannot create a room. |
| C08 / J2,J3 | Browser storage quota/permission denies writing. Current validated bytes remain in tab; Create can continue with “Available in this tab only.” | Reload loses the entry; Add NES file is required again. |
| C09 / J5 | Delete one saved game or all Local data in Settings. Create page updates on return, including the preview fallback. | Confirm/cancel works by keyboard; failed deletion keeps item and error. Current loaded game remains in memory. |
| C10 / J6 | Back to rooms or browser Back from Create before upload. Directory regains focus and remains current. | During upload, Cancel first prevents a hidden pending room. |
| C11 / J2,J3,J10 | Keyboard/assistive user tabs through saved choices, file picker, access, Create and Back. Selection/status are announced and focus lands on page heading or relevant error. | Escape from inline confirmation restores the prior action; no drag-only path. |
| C12 / J2,J3,J10 | Wide Create Game has internally scrolling game list left and selected preview right, both in stable regions. Narrow/zoomed views stack regions in page flow. | No overlapping content, horizontal scroll or hidden primary action. Reduced motion has no decorative slide to disable. |
| C13 / J7,J9 | Waiting room opens with Guest place Open. Host closes empty place; public row and invite show Closed and suppress Join. Host reopens; Join returns. | Stale Join is rejected atomically with visible Closed status. Mutation failure preserves actual state and offers Retry. |
| C14 / J7,J8 | Guest occupies P2; Close is absent. Host selects Remove guest, sees inline reason/confirm/cancel, confirms, then may Close the now empty place. | Cancel keeps guest; failed kick keeps occupied state. Concurrent guest reconnect cannot bypass Closed after a successful close. |
| C15 / J7,J8,J9 | Host starts with slot Open or Closed, alone or with prepared guest. | Slot controls disappear at Start. Late Join fails under the existing playing-room rule; no misleading Open label remains. |
| C16 / J10 | Open Settings, Local data, Saves, Rewind, Help, invitation and play room status. Each occupies a stable page region or whole content page. | Back returns focus; any confirmation/error appears inline. No dialog backdrop, floating drawer, toast, browser confirm or obscured canvas. |
| C17 / J10 | Leave or change room, publish, delete local data or change visibility when confirmation is needed. | Relevant page action area shows exact effect, Confirm and Cancel. Confirmation is never a separate overlay; failed action preserves state. |

## Feature support check

| Feature | Entry and usable state | Feedback and exit/failure |
| --- | --- | --- |
| Create game | Public rooms header, no active room | Opens Create Game; Back returns to rooms. |
| Recent preview | Create Game, last-used metadata available | Actual image or text fallback; updates after use/deletion. |
| Your games | Create Game, saved records loaded | One row per hash; loading/error/empty states; selecting re-verifies bytes. |
| Add NES file | Create Game | Validates and selects; invalid input reports reason without replacing selection. |
| Public/Unlisted | Create Game with a selected game | Choice visibly selected; applied only at Create room. |
| Standard/Relay-only | Public rooms beside Join; invitation beside Join room; Create Game beside Create room | Choice visibly selected; connection failure reports Retry without privacy fallback. |
| Create room | Selected verified and locally loaded game, no active room | Progress, waiting room or Retry/Cancel; no duplicate creation. |
| Delete saved game | Settings → Local data | Confirmation, refreshed list, or retained row plus error. |
| Guest place | Waiting room host, before Start | Open/Closed status updates directory/invite; Close only when empty; failure leaves actual state and Retry. |
| Remove guest | Occupied waiting room host | Inline confirmation, then empty Open place or intact guest plus error; Cancel exits confirmation. |
| Secondary page navigation | Settings, Local data, Saves, Rewind, Help, invitation and playing room control | Page heading and one Back path; focus return, inline error/confirmation and no covered content. |

Defects to remove from the current UI: inline Host bar on directory; a second file-selection action on the player panel while setting up; duplicate locally imported/downloaded bytes; blank preview imagery. File size and upload notice belong on Create Game, not the Public rooms list except the guest's download size next to Join.

Further current-UI defects: `<dialog>` overlays in Settings, Local data, Saves, Rewind and Help; floating room drawer, invitation, selection status and release notice; browser `window.confirm` for leave/remove/visibility. Replace each with the page state or an inline action-state named in C16–C17. Do not leave hidden duplicate routes in the DOM focus order.
