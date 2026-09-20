Audience: Agent

Shared play now preserves elapsed frame debt during packet waits and negotiates six frames of input delay. A 30-second production probe completed in 29.74 active seconds with identical checkpoints and final state; this is short qualification evidence, not the required ten-minute browser matrix.

The initial RAF scheduler moved its clock anchor before input admission and discarded elapsed debt. Under the existing D02 kernel profile (100 ms RTT, 20 ms jitter, 1% packet loss), [the observed run](raf-before.json) needed 40.34 active seconds for 1,800 frames, including approximately 10.4 seconds of input waits. Workers needed approximately 2.2 ms per frame, so native emulation cost did not explain the missing throughput.

The shared player now follows D02's absolute wall-time target and one-in-flight-worker pattern. Every frame still requires both inputs; no frame is skipped or predicted. The existing one-second stall budget bounds accumulated debt. With three frames of lookahead, [the next run](delay3-debt.json) exhausted that bound and correctly paused both players at frame 1,318. The native frame workload remained fast, but the minimum lookahead could not sustain this impaired route.

With the fixed offered delay changed to six, within the approved negotiated 3–8 range, [the same workload passed](paced-delay6.json): 29.74 active seconds, 39.13 seconds including preparation and common pause barriers. Both controller ports were independently observed in the diagnostic cartridge's CPU WRAM as `[128,64]`; all epoch/frame hash packets agree, and final pause states agree. Different per-peer wait totals reflect asynchronous input arrival, while absolute scheduling catches up without changing emulation order.

The evidence includes exact browser version, timing histograms and a unique run identity bound to packet capture, routing and qdisc sidecars by the existing D02 binder. The common setup and verifier remain single owners shared by both probes. The original PR50 policy-change timeout remains causally unproven; PR54's host-first challenge repair and its observed native-send boundary do not constitute proof of that original cause.

At the time of this development run, the remaining checks were: long Chrome/Firefox matrix, shared failure and focus/device recovery journeys, integrated voice/persistence testing, screenshots, final pre-flight and independent review. This document does not claim delivery acceptance.
