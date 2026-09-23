"""Enter local play through the public room flow used by the shipped client."""
import hashlib


def start_solo(page, rom):
    expected = hashlib.sha256(rom).hexdigest()
    page.wait_for_function('hash=>document.querySelector("[data-testid=fingerprint]")?.textContent.includes(hash)', arg=expected)
    page.get_by_test_id('room-view').wait_for(state='attached')
    page.wait_for_function('''() => Array.from(document.querySelectorAll('button')).some(button =>
        !button.disabled && (button.textContent.trim()==='Start game' || button.textContent.trim()==='Resume'))''')
    start = page.get_by_role('button', name='Start game', exact=True)
    if start.is_visible():
        start.click()
    else:
        page.get_by_role('button', name='Resume', exact=True).click()
    page.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>5")
