//! Browser-local history: validated sparse checkpoints and recorded controller inputs.
use crate::{local_player::clock_inputs, local_state::Codec};
use serde_json::{Value, json};
use std::{collections::VecDeque, mem::size_of};
use tetanes_core::prelude::*;

pub(crate) const SECONDS: f64 = 10.0;
pub(crate) const BUDGET: usize = 32 * 1024 * 1024;
const CHECKPOINTS: usize = 12;
const INPUTS: usize = 4096;
struct Checkpoint {
    frame: u64,
    cycles: u64,
    bytes: Vec<u8>,
    pixels: Vec<u8>,
}
struct Input {
    frame: u64,
    cycles: u64,
    buttons: u16,
}
pub(crate) struct History {
    checkpoints: VecDeque<Checkpoint>,
    inputs: VecDeque<Input>,
    frame: u64,
    cycles: u64,
    last_cycle: u32,
    rate: f64,
    peak: usize,
}
impl History {
    pub(crate) fn new(deck: &ControlDeck) -> Self {
        Self {
            checkpoints: VecDeque::new(),
            inputs: VecDeque::new(),
            frame: 0,
            cycles: 0,
            last_cycle: deck.bus().cpu.cycle,
            rate: f64::from(deck.clock_rate()),
            peak: 0,
        }
    }
    pub(crate) fn retained_bytes(&self) -> usize {
        size_of::<Self>()
            + self.checkpoints.capacity() * size_of::<Checkpoint>()
            + self.inputs.capacity() * size_of::<Input>()
            + self
                .checkpoints
                .iter()
                .map(|c| c.bytes.capacity() + c.pixels.capacity())
                .sum::<usize>()
    }
    pub(crate) fn info(&self) -> Value {
        let span = self
            .checkpoints
            .front()
            .map_or(0.0, |c| (self.cycles - c.cycles) as f64 / self.rate);
        json!({"availableSeconds": span.min(SECONDS), "spanSeconds":span,
            "maxSeconds":SECONDS,"retainedBytes":self.retained_bytes(),"peakBytes":self.peak,
            "budgetBytes":BUDGET,"frame":self.frame,"cycles":self.cycles,"clockRate":self.rate,
            "checkpoints":self.checkpoints.len(),"inputs":self.inputs.len()})
    }
    pub(crate) fn record(
        &mut self,
        deck: &mut ControlDeck,
        codec: &Codec,
        one: u8,
        two: u8,
    ) -> Result<(), String> {
        if self.checkpoints.is_empty() {
            self.checkpoints.reserve_exact(CHECKPOINTS);
            self.inputs.reserve_exact(INPUTS);
        }
        let now = deck.bus().cpu.cycle;
        if !self.checkpoints.is_empty() {
            let elapsed = now.wrapping_sub(self.last_cycle);
            if elapsed == 0 || f64::from(elapsed) > self.rate {
                return Err("Rewind timing discontinuity; history was cleared".into());
            }
            self.cycles += u64::from(elapsed);
            self.frame += 1;
            if self.inputs.len() == INPUTS {
                return Err("Rewind input budget exceeded".into());
            }
            self.inputs.push_back(Input {
                frame: self.frame,
                cycles: self.cycles,
                buttons: u16::from(one) | (u16::from(two) << 8),
            });
        }
        self.last_cycle = now;
        // Keep an anchor at or before the ten-second horizon, not a rounded frame count.
        while self.checkpoints.len() > 1
            && self.cycles.saturating_sub(self.checkpoints[1].cycles) as f64 >= SECONDS * self.rate
        {
            self.checkpoints.pop_front();
        }
        if let Some(first) = self.checkpoints.front() {
            while self.inputs.front().is_some_and(|i| i.frame <= first.frame) {
                self.inputs.pop_front();
            }
        }
        if self
            .checkpoints
            .back()
            .is_none_or(|c| (self.cycles - c.cycles) as f64 >= self.rate)
        {
            if self.checkpoints.len() == CHECKPOINTS {
                return Err("Rewind checkpoint budget exceeded".into());
            }
            self.checkpoints.push_back(Checkpoint {
                frame: self.frame,
                cycles: self.cycles,
                bytes: codec.export(deck)?,
                pixels: deck.frame_buffer().to_vec(),
            });
        }
        self.peak = self.peak.max(self.retained_bytes());
        if self.peak > BUDGET {
            return Err("Rewind memory budget exceeded".into());
        }
        Ok(())
    }
    pub(crate) fn rewind(
        &mut self,
        deck: &mut ControlDeck,
        codec: &Codec,
        seconds: f64,
    ) -> Result<Vec<u8>, String> {
        let first = self.checkpoints.front().ok_or("No rewind history yet")?;
        if !seconds.is_finite()
            || seconds <= 0.0
            || seconds > SECONDS
            || seconds * self.rate > (self.cycles - first.cycles) as f64
        {
            return Err("Choose a rewind duration within available history".into());
        }
        let desired = (self.cycles as f64 - seconds * self.rate).floor() as u64;
        let (target_frame, target_cycles) = self
            .inputs
            .iter()
            .rev()
            .find(|i| i.cycles <= desired)
            .map_or((first.frame, first.cycles), |i| (i.frame, i.cycles));
        let checkpoint = self
            .checkpoints
            .iter()
            .rev()
            .find(|c| c.frame <= target_frame)
            .unwrap();
        let backup = codec.export(deck)?;
        self.peak = self
            .peak
            .max(self.retained_bytes() + backup.capacity() + deck.frame_buffer().len());
        if self.peak > BUDGET {
            return Err("Rewind restore memory budget exceeded".into());
        }
        let restored = (|| {
            codec.restore(deck, &checkpoint.bytes)?;
            for input in self
                .inputs
                .iter()
                .filter(|i| i.frame > checkpoint.frame && i.frame <= target_frame)
            {
                clock_inputs(deck, input.buttons as u8, (input.buttons >> 8) as u8)?;
            }
            Ok::<_, String>(if target_frame == checkpoint.frame {
                checkpoint.pixels.clone()
            } else {
                deck.frame_buffer().to_vec()
            })
        })();
        match restored {
            Ok(pixels) => {
                self.checkpoints.retain(|c| c.frame <= target_frame);
                self.inputs.retain(|i| i.frame <= target_frame);
                self.frame = target_frame;
                self.cycles = target_cycles;
                self.last_cycle = deck.bus().cpu.cycle;
                deck.clear_audio_samples();
                Ok(pixels)
            }
            Err(error) => {
                codec.restore(deck, &backup)?;
                Err(error)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::{cartridge, change_mapper};
    use sha2::{Digest, Sha256};
    #[test]
    fn regions_changed_banks_ram_partial_serial_and_irq_rewind_exactly_with_real_capacity_accounting() {
        for region in [NesRegion::Ntsc, NesRegion::Pal, NesRegion::Dendy] {
            for mapper in [0, 1, 4] {
                let (rom, mut deck) = cartridge(mapper, region);
                let codec = Codec::new(&deck, &Sha256::digest(&rom).into(), &[9; 32]).unwrap();
                clock_inputs(&mut deck, 0, 0).unwrap();
                change_mapper(&mut deck, mapper);
                deck.bus_mut().memory.ram_mut()[0] = 0x79;
                let first = codec.export(&deck).unwrap();
                let mut history = History::new(&deck);
                history.record(&mut deck, &codec, 0, 0).unwrap();
                let mut trace = vec![(0u64, 0u8, 0u8)];
                let mut total = 0u64;
                let mut previous = deck.bus().cpu.cycle;
                while total as f64 <= f64::from(deck.clock_rate()) * 12.5 {
                    let frame = trace.len() as u32;
                    let (one, two) = (((frame / 7) % 256) as u8, ((frame / 13) % 256) as u8);
                    clock_inputs(&mut deck, one, two).unwrap();
                    total += u64::from(deck.bus().cpu.cycle.wrapping_sub(previous));
                    previous = deck.bus().cpu.cycle;
                    trace.push((total, one, two));
                    history.record(&mut deck, &codec, one, two).unwrap();
                }
                let original = codec.export(&deck).unwrap();
                let desired = total as f64 - 10.0 * f64::from(deck.clock_rate());
                let target = trace
                    .iter()
                    .rposition(|(cycles, _, _)| *cycles as f64 <= desired)
                    .unwrap();
                let pixels = history.rewind(&mut deck, &codec, 10.0).unwrap();
                let restored = codec.export(&deck).unwrap();
                assert_eq!(history.frame, target as u64);
                assert!(history.inputs.iter().all(|i| i.frame <= target as u64));
                assert!(history.checkpoints.iter().all(|c| c.frame <= target as u64));
                let (_, mut reference) = cartridge(mapper, region);
                codec.restore(&mut reference, &first).unwrap();
                for &(_, one, two) in &trace[1..=target] {
                    clock_inputs(&mut reference, one, two).unwrap();
                }
                assert_eq!(
                    restored,
                    codec.export(&reference).unwrap(),
                    "{mapper} {region:?} target"
                );
                assert_eq!(pixels, reference.frame_buffer(), "target presentation");
                for &(_, one, two) in &trace[target + 1..] {
                    clock_inputs(&mut deck, one, two).unwrap();
                    history.record(&mut deck, &codec, one, two).unwrap();
                }
                assert_eq!(
                    original,
                    codec.export(&deck).unwrap(),
                    "{mapper} {region:?} replay"
                );
                assert!(history.info()["spanSeconds"].as_f64().unwrap() >= 10.0);
                assert!(history.retained_bytes() <= BUDGET && history.peak <= BUDGET);
                assert!(
                    history.retained_bytes()
                        > history
                            .checkpoints
                            .iter()
                            .map(|c| c.bytes.len())
                            .sum::<usize>(),
                    "actual capacities include pixels, inputs and metadata"
                );
                eprintln!(
                    "rewind qualification mapper={mapper} region={region:?} trace_frames={} target={target} info={}",
                    trace.len() - 1,
                    history.info()
                );
            }
        }
    }
    #[test]
    fn actual_capacity_at_the_shared_file_limit_leaves_room_for_restore_scratch() {
        let (_, mut deck) = cartridge(0, NesRegion::Ntsc);
        let pixels = deck.frame_buffer().len();
        let mut history = History::new(&deck);
        history.inputs.reserve_exact(INPUTS);
        history.checkpoints.reserve_exact(CHECKPOINTS);
        for frame in 0..CHECKPOINTS {
            history.checkpoints.push_back(Checkpoint {
                frame: frame as u64,
                cycles: 0,
                bytes: vec![0xa5; crate::local_file::LIMIT],
                pixels: vec![0x79; pixels],
            });
        }
        let backup = vec![0x51; crate::local_file::LIMIT];
        let presentation = vec![0x29; pixels];
        let actual = history.retained_bytes() + backup.capacity() + presentation.capacity();
        assert!(
            actual <= BUDGET,
            "actual retained and restore buffers {actual} exceed {BUDGET}"
        );
        assert!(history.retained_bytes() > CHECKPOINTS * crate::local_file::LIMIT);
        eprintln!(
            "rewind maximum-file capacity history={} restore_peak={actual} budget={BUDGET}",
            history.retained_bytes()
        );
    }
    #[test]
    fn wrapped_cpu_cycles_short_history_and_invalid_targets_preserve_state() {
        let (rom, mut deck) = cartridge(0, NesRegion::Ntsc);
        clock_inputs(&mut deck, 0, 0).unwrap();
        deck.bus_mut().cpu.cycle = u32::MAX - 100;
        let codec = Codec::new(&deck, &Sha256::digest(&rom).into(), &[9; 32]).unwrap();
        let mut history = History::new(&deck);
        history.record(&mut deck, &codec, 0, 0).unwrap();
        clock_inputs(&mut deck, 1, 2).unwrap();
        history.record(&mut deck, &codec, 1, 2).unwrap();
        assert!(deck.bus().cpu.cycle < 100_000);
        assert!(history.cycles > 100 && history.cycles < 100_000);
        let before = codec.export(&deck).unwrap();
        let first = history.checkpoints.front().unwrap().bytes.clone();
        let pixels = history.checkpoints.front().unwrap().pixels.clone();
        for seconds in [0.0, -1.0, f64::NAN, f64::INFINITY, 1.0, 11.0] {
            assert!(history.rewind(&mut deck, &codec, seconds).is_err());
            assert_eq!(before, codec.export(&deck).unwrap());
        }
        assert_eq!(history.frame, 1);
        let duration = history.info()["availableSeconds"].as_f64().unwrap();
        assert_eq!(history.rewind(&mut deck, &codec, duration).unwrap(), pixels);
        assert_eq!(codec.export(&deck).unwrap(), first);
        assert_eq!(history.frame, 0);
    }
}
