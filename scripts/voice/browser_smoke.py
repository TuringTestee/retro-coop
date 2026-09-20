import argparse, contextlib, json, os, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--chrome", action="store_true")
parser.add_argument(
    "--pair",
    choices=["Chrome-Chrome", "Chrome-Firefox", "Firefox-Firefox"],
    default="Chrome-Chrome",
)
parser.add_argument("--output", default="voice.local.json")
parser.add_argument("--relay", action="store_true")
parser.add_argument("--turnserver", default="turnserver")
args = parser.parse_args()
started = time.monotonic()
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "scripts/peer"))
from fixture import LocalTurn

fixture = LocalTurn(args.turnserver) if args.relay else contextlib.nullcontext()
stack = contextlib.ExitStack()
server = None
pages = []
try:
    turn = stack.enter_context(fixture)
    server = subprocess.Popen(
        ["node", "scripts/rooms/browser-server.ts"],
        cwd=root,
        env={
            **os.environ,
            **(turn.environment() if turn else {"TURN_URLS": "", "TURN_SECRET": ""}),
        },
        stdout=subprocess.PIPE,
        text=True,
    )
    url = json.loads(server.stdout.readline())["url"]
    rom = (root / "apps/client/dist/generated/diagnostic.nes").read_bytes()
    p = sync_playwright().start()
    stack.callback(p.stop)
    browsers = {}
    for kind in set(args.pair.split("-")):
        browsers[kind] = (
            p.chromium.launch(
                **({"channel": "chrome"} if args.chrome else {}),
                ignore_default_args=["--mute-audio"],
                args=[
                    "--use-fake-device-for-media-stream",
                    "--use-fake-ui-for-media-stream",
                ]
            )
            if kind == "Chrome"
            else p.firefox.launch(
                firefox_user_prefs={
                    "media.navigator.streams.fake": True,
                    "media.navigator.permission.disabled": True,
                    **(
                        {"media.peerconnection.ice.loopback": True}
                        if args.relay
                        else {}
                    ),
                }
            )
        )
    errors = []
    kinds = iter(args.pair.split("-"))

    def page(url):
        tab = browsers[next(kinds)].new_page()
        pages.append(tab)
        tab.on("pageerror", lambda e: errors.append(str(e)))
        tab.add_init_script(
            (root / "scripts/peer/diagnostics.js").read_text()
            + (root / "scripts/voice/fixtures.js").read_text()
        )
        tab.goto(url)
        return tab

    host = page(url)
    host.locator(".room-panel").get_by_label(
        "Connection privacy", exact=True
    ).select_option("relay" if args.relay else "standard")
    host.set_input_files(
        "input[type=file]",
        {"name": "fixture.nes", "mimeType": "application/octet-stream", "buffer": rom},
    )
    host.get_by_test_id("room-view").wait_for()
    guest = page(host.get_by_label("Room invitation", exact=True).input_value())
    guest.get_by_role("button", name="Retry join / Join", exact=True).click()
    guest.get_by_test_id("room-view").wait_for()
    timeline_before = host.evaluate("timelineWrites")
    for tab in [host, guest]:
        tab.wait_for_function(
            "route=>document.querySelector('[data-testid=connection-status]').textContent.includes('Route: '+route)",
            arg="relay" if args.relay else "direct",
        )
        if args.relay:
            assert tab.evaluate(
                "async()=>{const stats=await pcs.at(-1).getStats();return [...stats.values()].some(s=>(s.type==='transport'&&s.selectedCandidatePairId&&stats.get(stats.get(s.selectedCandidatePairId).localCandidateId)?.candidateType==='relay')||(s.type==='candidate-pair'&&s.selected===true&&stats.get(s.localCandidateId)?.candidateType==='relay'))}"
            )
        assert tab.evaluate("captures.length") == 0
        tab.locator(".room-panel").get_by_label(
            "Remote voice volume", exact=False
        ).fill("0")
        tab.get_by_role("button", name="Enable voice", exact=True).click()
        tab.locator(".room-panel").get_by_text(
            "Transmitting microphone audio", exact=True
        ).wait_for()
    for tab in [host, guest]:
        tab.wait_for_function(
            """async()=>{const stats=await pcs.at(-1).getStats();return [...stats.values()].some(s=>s.type==='inbound-rtp'&&s.kind==='audio'&&s.totalAudioEnergy>0&&s.packetsReceived>0)}"""
        )
    panel = host.locator(".room-panel")
    frame_before = host.get_by_test_id("frames").inner_text()
    panel.get_by_label("Voice mode", exact=True).select_option("push")
    host.get_by_label("Local game screen", exact=True).focus()
    host.keyboard.down("KeyV")
    host.wait_for_function("captures.at(-1).getAudioTracks().every(t=>t.enabled)")
    host.keyboard.up("KeyV")
    host.wait_for_function("captures.at(-1).getAudioTracks().every(t=>!t.enabled)")
    panel.get_by_role("button", name="Hold to talk", exact=True).focus()
    host.keyboard.down("Space")
    host.wait_for_function("captures.at(-1).getAudioTracks().every(t=>t.enabled)")
    host.keyboard.up("Space")
    host.wait_for_function("captures.at(-1).getAudioTracks().every(t=>!t.enabled)")
    host.get_by_label("Room invitation", exact=True).focus()
    host.keyboard.down("KeyV")
    host.evaluate(
        "()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))"
    )
    assert host.evaluate("captures.at(-1).getAudioTracks().every(t=>!t.enabled)")
    host.keyboard.up("KeyV")
    # Synthetic gamepad input goes through the real Settings selection and shared mapping.
    host.evaluate(
        """() => { window.voicePad={index:0,id:'Voice fixture controller',connected:true,buttons:Array.from({length:16},()=>({pressed:false,value:0})),axes:[0,0]};Object.defineProperty(navigator,'getGamepads',{configurable:true,value:()=>voicePad.connected?[voicePad]:[]}); }"""
    )
    host.get_by_role("button", name="Settings", exact=True).click()
    host.get_by_label("Input device", exact=True).select_option("0")
    host.get_by_role("button", name="Close settings", exact=True).click()
    host.get_by_label("Local game screen", exact=True).focus()
    host.evaluate(
        "()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))"
    )
    host.evaluate("voicePad.buttons[10]={pressed:true,value:1}")
    host.wait_for_function("captures.at(-1).getAudioTracks().every(t=>t.enabled)")
    host.evaluate("voicePad.connected=false")
    panel.get_by_text("Microphone muted", exact=True).wait_for()
    assert host.evaluate("captures.at(-1).getAudioTracks().every(t=>!t.enabled)")
    host.get_by_role("button", name="Settings", exact=True).click()
    host.get_by_label("Input device", exact=True).select_option("keyboard")
    host.get_by_role("button", name="Close settings", exact=True).click()
    panel.get_by_role("button", name="Unmute microphone", exact=True).click()
    panel.get_by_label("Voice mode", exact=True).select_option("open")
    panel.get_by_role("button", name="Mute remote voice", exact=True).click()
    assert host.evaluate("voiceAudio.at(-1).muted")
    panel.get_by_role("button", name="Unmute remote voice", exact=True).click()
    assert not host.evaluate("voiceAudio.at(-1).muted")
    # Permission and device failures do not replace the peer or reset local emulation.
    pc_count = host.evaluate("pcs.length")
    panel.get_by_role("button", name="Disable microphone", exact=True).click()
    host.evaluate("window.denyCapture=true")
    panel.get_by_role("button", name="Enable voice", exact=True).click()
    panel.get_by_text("Microphone access was denied.", exact=False).wait_for()
    host.evaluate("window.denyCapture=false;window.missingDevice=true")
    panel.get_by_role("button", name="Try microphone again", exact=True).click()
    panel.get_by_text(
        "Microphone unavailable. Choose another device", exact=False
    ).wait_for()
    host.evaluate("window.missingDevice=false;window.rejectAttachment=true")
    panel.get_by_role("button", name="Try microphone again", exact=True).click()
    panel.get_by_text("Voice could not start.", exact=False).wait_for()
    assert host.evaluate("pcs.length") == pc_count
    host.evaluate("window.rejectAttachment=false;window.blockPlayback=true")
    panel.get_by_role("button", name="Try microphone again", exact=True).click()
    panel.get_by_role("button", name="Enable voice sound", exact=True).wait_for()
    host.evaluate("window.blockPlayback=false")
    panel.get_by_role("button", name="Enable voice sound", exact=True).click()
    panel.get_by_text("Transmitting microphone audio", exact=True).wait_for()
    assert host.evaluate("pcs.length") == pc_count
    assert int(host.get_by_test_id("frames").inner_text().split()[0]) >= int(
        frame_before.split()[0]
    )
    # Select another actual fake-device input after permission; replacement starts muted.
    devices = (
        panel.get_by_label("Microphone device", exact=True)
        .locator("option")
        .evaluate_all("options=>options.map(o=>o.value).filter(v=>v!=='default')")
    )
    assert devices
    panel.get_by_label("Microphone device", exact=True).select_option(devices[0])
    panel.get_by_text("Microphone muted", exact=True).wait_for()
    assert host.evaluate(
        "captures.slice(0,-1).every(s=>s.getTracks().every(t=>t.readyState==='ended'))"
    )
    panel.get_by_role("button", name="Unmute microphone", exact=True).click()
    # Model device removal: keep the missing selection visible so Default is an actual new choice.
    host.evaluate(
        "hideMicrophoneDevices=true;captures.at(-1).getAudioTracks()[0].dispatchEvent(new Event('ended'));navigator.mediaDevices.dispatchEvent(new Event('devicechange'))"
    )
    panel.get_by_text(
        "Microphone disconnected. Choose a device and try again.", exact=True
    ).wait_for()
    host.wait_for_function(
        "id=>[...document.querySelector('.room-panel select[id$=device]').options].every(o=>o.value!==id || o.textContent.includes('unavailable'))",
        arg=devices[0],
    )
    host.screenshot(
        path=str(Path(args.output).with_suffix(".missing-device.png")), full_page=True
    )
    assert (
        panel.get_by_label("Microphone device", exact=True).input_value() == devices[0]
    ), "missing selection silently displays Default instead of its unavailable state"
    panel.get_by_label("Microphone device", exact=True).select_option("default")
    panel.get_by_role("button", name="Try microphone again", exact=True).click()
    panel.get_by_text("Transmitting microphone audio", exact=True).wait_for()
    host.evaluate("hideMicrophoneDevices=false")
    panel.get_by_role("button", name="Refresh microphones", exact=True).click()
    # Pending permission can be cancelled; a later result must stop all its tracks.
    panel.get_by_role("button", name="Disable microphone", exact=True).click()
    host.evaluate("window.holdCapture=true")
    panel.get_by_role("button", name="Enable voice", exact=True).click()
    host.wait_for_function("!!window.releaseCapture")
    panel.get_by_role("button", name="Cancel microphone request", exact=True).click()
    count = host.evaluate("captures.length")
    host.evaluate("releaseCapture();window.holdCapture=false")
    host.wait_for_function("(count)=>captures.length>count", arg=count)
    host.wait_for_function(
        "captures.every(s=>s.getTracks().every(t=>t.readyState==='ended'))"
    )
    panel.get_by_role("button", name="Enable voice", exact=True).click()
    panel.get_by_text("Transmitting microphone audio", exact=True).wait_for()
    host.screenshot(
        path=str(Path(args.output).with_suffix(".voice.png")), full_page=True
    )
    host.set_viewport_size({"width": 400, "height": 1000})
    assert host.evaluate("document.documentElement.scrollWidth<=innerWidth")
    host.screenshot(
        path=str(Path(args.output).with_suffix(".mobile.png")), full_page=True
    )
    host.evaluate("window.dispatchEvent(new Event('blur'))")
    host.locator(".room-panel").get_by_text("Microphone muted", exact=True).wait_for()
    assert host.evaluate("captures.at(-1).getAudioTracks().every(t=>!t.enabled)")
    host.evaluate("window.dispatchEvent(new Event('focus'))")
    assert host.evaluate("captures.at(-1).getAudioTracks().every(t=>!t.enabled)")
    panel.get_by_role("button", name="Unmute microphone", exact=True).click()
    panel.get_by_label("Voice mode", exact=True).select_option("push")
    host.get_by_label("Local game screen", exact=True).focus()
    host.keyboard.down("KeyV")
    host.wait_for_function("captures.at(-1).getAudioTracks().every(t=>t.enabled)")
    guest.get_by_role("button", name="Cancel join", exact=True).click()
    guest.get_by_test_id("room-view").wait_for(state="detached")
    for tab in [host, guest]:
        tab.wait_for_function(
            "captures.every(s=>s.getTracks().every(t=>t.readyState==='ended'))"
        )
    # Rejoining must not retain a held push-to-talk key from the previous peer.
    capture_count = host.evaluate("captures.length")
    guest.get_by_role("button", name="Retry join / Join", exact=True).click()
    for tab in [host, guest]:
        tab.wait_for_function(
            "document.querySelector('[data-testid=connection-status]').textContent.includes('Route:')"
        )
    assert host.evaluate("captures.length") == capture_count
    panel.get_by_role("button", name="Enable voice", exact=True).click()
    host.wait_for_function(
        "n=>captures.length>n && document.querySelector('[data-testid=microphone-status]').textContent!=='Microphone permission pending…'",
        arg=capture_count,
    )
    host.evaluate(
        "()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))"
    )
    assert host.evaluate(
        "captures.at(-1).getAudioTracks().every(t=>!t.enabled)"
    ), "replaced peer retained old push-to-talk input"
    host.keyboard.up("KeyV")
    host.get_by_label("Local game screen", exact=True).focus()
    host.keyboard.down("KeyV")
    host.wait_for_function("captures.at(-1).getAudioTracks().every(t=>t.enabled)")
    host.keyboard.up("KeyV")
    guest.get_by_role("button", name="Cancel join", exact=True).click()
    host.wait_for_function(
        "captures.every(s=>s.getTracks().every(t=>t.readyState==='ended'))"
    )
    assert (
        host.evaluate("timelineWrites") == timeline_before
    ), "voice changed the local emulator timeline"
    assert not errors, errors
    result = {
        "pair": args.pair,
        "versions": {name: browser.version for name, browser in browsers.items()},
        "route": "relay" if args.relay else "direct",
        "firefox_local_turn_loopback_enabled": args.relay and "Firefox" in args.pair,
        "two_way_decoded_audio_energy": True,
        "no_capture_before_enable": True,
        "blur_mutes_focus_does_not_unmute": True,
        "leave_stops_both_tracks": True,
        "missing_device_selection_allows_default_retry": True,
        "timeline_mutating_worker_commands_unchanged": timeline_before,
        "rejoin_requires_opt_in_and_new_push_to_talk_input": True,
        "remote_volume_zero_via_setting": True,
        "page_errors": errors,
        "push_to_talk_key_button_and_typing_isolation": True,
        "permission_device_and_playback_retry_preserve_peer_and_frames": True,
        "late_cancelled_capture_stops": True,
        "device_replacement_muted_until_deliberate_unmute": True,
        "failed_sender_attachment_retries_without_peer_reset": True,
        "mobile_no_overflow": True,
        "selected_gamepad_push_to_talk_and_unplug_mute": True,
        "seconds": round(time.monotonic() - started, 2),
    }
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    for browser in browsers.values():
        browser.close()
except BaseException:
    failure = []
    for tab in pages:
        try:
            failure.append(
                tab.evaluate(
                    """async()=>({diagnostics:peerDiagnostics(),peerErrors,iceErrors,candidateShapes,focus:document.hasFocus(),hidden:document.hidden,microphone:document.querySelector('[data-testid=microphone-status]')?.textContent,connection:document.querySelector('[data-testid=connection-status]')?.textContent,tracks:captures.map(s=>s.getTracks().map(t=>({state:t.readyState,enabled:t.enabled}))),peers:await Promise.all(pcs.map(async pc=>({state:pc.connectionState,stats:[...(await pc.getStats().catch(()=>new Map())).values()].filter(s=>['transport','candidate-pair','local-candidate','remote-candidate','inbound-rtp','outbound-rtp'].includes(s.type)).map(s=>({type:s.type,kind:s.kind,candidateType:s.candidateType,selected:s.selected,nominated:s.nominated,state:s.state,dtls:s.dtlsState,packetsReceived:s.packetsReceived,packetsSent:s.packetsSent,totalAudioEnergy:s.totalAudioEnergy}))})))})"""
                )
            )
        except Exception as error:
            failure.append({"diagnostics_error": str(error)[:500]})
    Path(args.output).write_text(
        json.dumps(
            {
                "failure": failure,
                "page_errors": errors,
                "turn_error_codes": turn.error_codes() if turn else {},
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "failure": failure,
                "page_errors": errors,
                "turn_error_codes": turn.error_codes() if turn else {},
            }
        ),
        flush=True,
    )
    raise
finally:
    if server:
        server.terminate()
        server.wait(timeout=5)
    stack.close()
