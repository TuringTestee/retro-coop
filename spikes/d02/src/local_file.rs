//! Shared local-file allocation budget and exact compatibility identity.
use sha2::{Digest, Sha256};
use tetanes_core::prelude::*;

pub(crate) const LIMIT: usize = 2 * 1024 * 1024;
pub(crate) fn identity(
    schema: &[u8; 8],
    deck: &ControlDeck,
    rom: &[u8; 32],
    core: &[u8; 32],
    layout: &[u8],
) -> [u8; 32] {
    let mut identity = Sha256::new();
    identity.update(schema);
    identity.update(rom);
    identity.update(core);
    identity.update(serde_json::to_vec(&deck.region()).unwrap());
    identity.update(b"zero-ram;48000hz;1x;standard-p1-p2;default-mapper-revisions");
    identity.update(layout);
    identity.finalize().into()
}
