The Create Game page must stay usable when local storage, a selected file, or the room upload fails. Each control below has an entry state and a visible result.

Audience: Human

# Create Game scenarios

| ID / journey | Trigger and expected visible state | Recovery |
| --- | --- | --- |
| C01 / J1 | Open home with live public directory. **Create game** is separate from rows' Join actions. | Directory load/error shows Retry; creating remains reachable if local setup is possible. |
| C02 / J2 | Open Create Game with a saved last-used game. Preview shows its name, source, size and a real captured frame or “No preview yet.” | If metadata/preview missing, text remains; no blank image. |
| C03 / J2,J4 | A ROM arrives by local import and later by guest download, or vice versa. Your games has one row keyed by SHA-256; last used moves it to the top. | Hash/byte mismatch marks the row unusable; selecting it never publishes a room. |
| C04 / J3 | Add or drop one valid `.nes` file. Validation progress and selected game appear on Create Game; Save locally succeeds or explains tab-only availability. | Invalid/multiple files keep the prior selection and show one actionable error. |
| C05 / J2,J3 | Change Public/Unlisted with a verified selection. **Create room** shows the chosen access and starts upload/claim. | No selection disables Create with a nearby reason; changing access alone does nothing remotely. |
| C06 / J3 | Upload begins, advances, then confirms. Waiting room appears only after server verification. | Cancel aborts; timeout/error offers Retry upload or Back to Create Game with selection preserved. |
| C07 / J2,J4 | Open saved entry after reload. Bytes are rehashed before enabling Create; guest download bytes use the same gate. | Eviction, corruption or IndexedDB denial shows unavailable and Add NES file. |
| C08 / J2,J3 | Browser storage quota/permission denies writing. Current validated bytes remain in tab; Create can continue with “Available in this tab only.” | Reload loses the entry; Add NES file is required again. |
| C09 / J5 | Delete one saved game or all Local data in Settings. Create page updates on return, including the preview fallback. | Confirm/cancel works by keyboard; failed deletion keeps item and error. Current loaded game remains in memory. |
| C10 / J6 | Back to rooms or browser Back from Create before upload. Directory regains focus and remains current. | During upload, Cancel first prevents a hidden pending room. |
| C11 / J2,J3 | Keyboard/assistive user tabs through saved choices, file picker, access, Create and Back. Selection/status are announced and focus lands on page heading or relevant error. | Escape from a modal returns focus; no drag-only path. |
| C12 / J2,J3 | Narrow screen shows one column with preview above Your games and Create action after access. | No horizontal scroll or hidden primary action. |

## Feature support check

| Feature | Entry and usable state | Feedback and exit/failure |
| --- | --- | --- |
| Create game | Public rooms header, no active room | Opens Create Game; Back returns to rooms. |
| Recent preview | Create Game, last-used metadata available | Actual image or text fallback; updates after use/deletion. |
| Your games | Create Game, saved records loaded | One row per hash; loading/error/empty states; selecting re-verifies bytes. |
| Add NES file | Create Game | Validates and selects; invalid input reports reason without replacing selection. |
| Public/Unlisted | Create Game with a selected game | Choice visibly selected; applied only at Create room. |
| Create room | Selected verified game and no active room | Progress, waiting room or Retry/Cancel; no duplicate creation. |
| Delete saved game | Settings → Local data | Confirmation, refreshed list, or retained row plus error. |

Defects to remove from the current UI: inline Host bar on directory; a second file-selection action on the player panel while setting up; duplicate locally imported/downloaded bytes; blank preview imagery. File size and upload notice belong on Create Game, not the Public rooms list except the guest's download size next to Join.
