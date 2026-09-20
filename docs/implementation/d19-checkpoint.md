Audience: Agent

# Included-game implementation checkpoint

This branch preserves unfinished From Below download and UI groundwork. It is not a completed two-game catalog and is not ready for acceptance. The user's later request adds Super Tilt Bro first and license placeholders for both; planning PR #65 must finish review, actual reviewed-version approval and merge before that changed behavior is implemented.

## Preserved work

A pinned From Below identity module, exact bounded download verifier, build-time artifact verification, static packaging and catalog classification are drafted. The UI draft reuses the existing player and room selection flow, with cancellation guards through worker acceptance, directory filtering and an included entry. A private original stays outside Git; the branch holds the exact verified distributable copy. No new runtime qualification or Internet deployment is claimed.

Three focused download tests pass (exact identity/fixed path; bad size/hash/network responses; late canceled response), and TypeScript checking passes. Full preflight, actual browser journeys, screenshots, accessibility/cancellation audit, two-game generalization, license placeholders and fresh independent review remain unperformed. Do not use this checkpoint as release evidence.

## Resume

1. Read current epic #2, issue #23 and PR #65, plus the latest user direction. Do not restore the earlier no-license-placeholder instruction.
2. Integrate the approved two-game plan, then replace the single-game manifest/downloader/UI with one ordered catalog owner. Preserve arbitrary local NES admission and hosting without title gates.
3. Qualify the supplied Super Tilt Bro artifact exactly: 524,304 bytes, SHA-256 `847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d`, NES 2.0 mapper 2/submapper 1 PAL. Its runtime and exact release version are unverified.
4. Reconcile D12/D15 interfaces after their accepted integration. D12 adds timeline RPCs, D15 changes controller/room wording. The catalog's optional LocalPlayer.load cancellation predicate was coordinated with D12; no new scheduler or state-transfer owner is intended.
5. Audit catalog request ownership across room membership, manual reselection, worker approval/battery awaits, cancellation, timeout and in-tab reuse. Test and inspect actual configured/unconfigured UI before a draft PR handoff. The current patch has not had this runtime audit.

Root owns this worktree/branch. Main's user-requested Vaseline submodule change must remain untouched. GKE staging is a separate D24 workstream, with credit/cost verification pending and no cloud mutation performed.
