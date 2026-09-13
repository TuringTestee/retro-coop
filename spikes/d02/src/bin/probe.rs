use retro_coop_d02::{canonical, checkpoint::Codec, deck, snapshot, step};
use sha2::{Digest, Sha256};
fn main() {
    let path = std::env::args_os()
        .nth(1)
        .expect("local authorized ROM path");
    let rom = std::fs::read(path).unwrap();
    let mut d = deck(&rom);
    let codec = Codec::new(&d, &rom).unwrap();
    let started = std::time::Instant::now();
    let mut largest = 0;
    for frame in 0..36000 {
        step(&mut d, frame);
        if frame % 600 == 599 {
            let bytes = codec
                .encode(&d)
                .unwrap_or_else(|e| panic!("frame {}: {e}", frame + 1));
            largest = largest.max(bytes.len());
            let _ = codec.decode(&bytes).unwrap();
        }
    }
    let elapsed = started.elapsed().as_secs_f64();
    let checkpoint = codec.encode(&d).unwrap();
    let raw = snapshot(&d);
    for frame in 36000..36600 {
        step(&mut d, frame);
    }
    let expected = canonical(&d);
    let expected_audio = d.audio_samples().to_vec();
    codec.restore(&mut d, &checkpoint).unwrap();
    for frame in 36000..36600 {
        step(&mut d, frame);
    }
    let resumed = canonical(&d);
    let resumed_audio = d.audio_samples().to_vec();
    // Different preceding timeline; same checkpoint must start identical new audio epoch.
    for frame in 36600..36737 {
        step(&mut d, frame);
    }
    codec.restore(&mut d, &checkpoint).unwrap();
    assert!(d.audio_samples().is_empty());
    for frame in 36000..36600 {
        step(&mut d, frame);
    }
    let result = serde_json::json!({"rom_sha256":format!("{:x}",Sha256::digest(&rom)),
        "frames":36000,"seconds":elapsed,"max_checkpoint_bytes":largest,
        "raw_snapshot_bytes":raw.len(),"canonical_restore_equal":expected==resumed,
        "new_epoch_canonical_equal":resumed==canonical(&d),
        "new_epoch_audio_equal":resumed_audio==d.audio_samples(),
        "uninterrupted_pcm_equal":expected_audio==resumed_audio,
        "final_audio_samples":d.audio_samples().len()});
    println!("{result}");
    std::fs::write(
        "native.local.json",
        serde_json::to_vec_pretty(&result).unwrap(),
    )
    .unwrap();
}
