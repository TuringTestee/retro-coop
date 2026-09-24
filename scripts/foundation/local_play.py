"""Enter local play through the public Create Game flow used by the shipped client."""
import hashlib


def enter_create(page):
    """Use the same entry button a player uses before adding a new cartridge."""
    page.get_by_role('button', name='Create game', exact=True).click()
    page.get_by_test_id('create-game').wait_for()


def read_fingerprint(page, expected=None):
    """Read the technical identity through Game help, then return to play."""
    page.get_by_role('button', name='Game help', exact=True).click()
    page.get_by_text('Technical details', exact=True).click()
    details = page.get_by_test_id('fingerprint')
    if expected is not None:
        details.filter(has_text=expected).wait_for()
    value = details.inner_text()
    page.get_by_role('button', name='Back', exact=True).click()
    return value


def start_solo(page, rom, *, require_start=False):
    """Leave Create Game for local play, then start the loaded cartridge."""
    expected = hashlib.sha256(rom).hexdigest()
    local = page.get_by_role('button', name='Play locally', exact=True)
    if local.is_visible():
        local.click()
    else:
        page.get_by_test_id('player-status').filter(has_text='Game loaded').wait_for()
    assert expected in read_fingerprint(page, expected)
    if require_start:
        start = page.get_by_role('button', name='Resume', exact=True)
        start.wait_for()
        frames = page.get_by_test_id('frames')
        assert frames.inner_text() == '0 frames', 'Replacement ran before local Resume'
        page.wait_for_timeout(200)
        assert frames.inner_text() == '0 frames', 'Loaded game advanced before Resume'
        start.click()
        page.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>5")
        return
    page.get_by_role('button', name='Resume', exact=True).click()
    page.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>5")
