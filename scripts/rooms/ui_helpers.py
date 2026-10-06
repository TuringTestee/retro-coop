"""Shared selectors for the current lobby journey in browser checks."""

from playwright.sync_api import expect


def choose_panel(page, name):
    expect(page.locator('.rc-stage')).not_to_have_attribute('inert', '')
    navigation = page.get_by_role('navigation', name='Lobby sections')
    if navigation.is_visible():
        expanded = page.get_by_role('button', name='Return to lobby view', exact=True)
        if expanded.is_visible():
            expanded.click()
        button = navigation.get_by_role('button', name=name, exact=True)
        if button.get_attribute('aria-current') != 'page':
            button.click()


def choose_section(page, name):
    choose_panel(page, 'Settings')
    try:
        page.get_by_role('region', name='Game settings', exact=True).wait_for()
    except Exception:
        print(page.evaluate('''()=>({active:{tag:document.activeElement?.tagName,label:document.activeElement?.getAttribute('aria-label')},
          dialogs:[...document.querySelectorAll('[role=dialog],[role=alertdialog]')].map(n=>n.textContent),
          blockers:[...document.querySelectorAll('[inert],[aria-hidden=true]')].map(n=>({class:n.className,text:n.textContent?.slice(0,140)})),
          panels:[...document.querySelectorAll('.rc-phone-panels button')].map(n=>({text:n.textContent,current:n.getAttribute('aria-current')}))})'''),flush=True)
        raise
    selector = page.get_by_role('combobox', name='Settings section')
    if selector.is_visible():
        assert selector.evaluate('node => {const box = node.getBoundingClientRect(); return node.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2));}'), 'Settings section selector is covered'
        selector.select_option(label=name)
    else:
        page.get_by_role('button', name=name, exact=True).click()


async def choose_section_async(page, name):
    from playwright.async_api import expect as expect_async
    await expect_async(page.locator('.rc-stage')).not_to_have_attribute('inert', '')
    navigation = page.get_by_role('navigation', name='Lobby sections')
    if await navigation.is_visible():
        expanded = page.get_by_role('button', name='Return to lobby view', exact=True)
        if await expanded.is_visible():
            await expanded.click()
        button = navigation.get_by_role('button', name='Settings', exact=True)
        if await button.get_attribute('aria-current') != 'page':
            await button.click()
    await page.get_by_role('region', name='Game settings', exact=True).wait_for()
    selector = page.get_by_role('combobox', name='Settings section')
    if await selector.is_visible():
        await selector.select_option(label=name)
    else:
        await page.get_by_role('button', name=name, exact=True).click()


def choose_audio(page, name):
    choose_section(page, 'Audio')
    page.get_by_role('combobox', name='Audio setting').select_option(label=name)


async def choose_audio_async(page, name):
    await choose_section_async(page, 'Audio')
    await page.get_by_role('combobox', name='Audio setting').select_option(label=name)


def open_access(page):
    page.get_by_role('button', name='Set Password', exact=True).click()
    page.get_by_role('dialog', name='Lobby access', exact=True).wait_for()


def capture_binding(page, name='A'):
    choose_section(page, 'Controls')
    page.get_by_role('button', name=f'Map {name}:', exact=False).click()
    dialog = page.get_by_role('dialog', name=f'Map {name}', exact=True)
    dialog.wait_for()
    return dialog, dialog.get_by_label('Capture input', exact=True)


async def open_access_async(page):
    await page.get_by_role('button', name='Set Password', exact=True).click()
    await page.get_by_role('dialog', name='Lobby access', exact=True).wait_for()


def rename_lobby(page, name):
    page.get_by_role('button', name='Edit lobby name:', exact=False).click()
    field = page.get_by_role('textbox', name='Lobby name')
    field.fill(name)
    field.press('Enter')
    page.get_by_role('button', name=f'Edit lobby name: {name}', exact=False).wait_for()


def protect_lobby(page, password):
    open_access(page)
    page.get_by_role('button', name='Require password').click()
    page.get_by_label('New lobby password').fill(password)
    page.get_by_role('button', name='Save password').click()
    page.get_by_text('Password protected', exact=True).wait_for()
    page.get_by_role('dialog', name='Lobby access', exact=True).get_by_role('button', name='Done', exact=True).click()
