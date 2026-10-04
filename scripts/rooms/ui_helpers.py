"""Shared selectors for the current lobby journey in browser checks."""


def choose_section(page, name):
    page.get_by_role('heading', name='Settings', exact=True).wait_for()
    selector = page.get_by_role('combobox', name='Settings section')
    if selector.is_visible():
        assert selector.evaluate('node => {const box = node.getBoundingClientRect(); return node.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2));}'), 'Settings section selector is covered'
        selector.select_option(label=name)
    else:
        page.get_by_role('button', name=name, exact=True).click()


async def choose_section_async(page, name):
    await page.get_by_role('heading', name='Settings', exact=True).wait_for()
    selector = page.get_by_role('combobox', name='Settings section')
    if await selector.is_visible():
        await selector.select_option(label=name)
    else:
        await page.get_by_role('button', name=name, exact=True).click()


def rename_lobby(page, name):
    page.locator('.rc-trail .rc-header-edit').click()
    field = page.get_by_role('textbox', name='Lobby name')
    field.fill(name)
    field.press('Enter')
    page.locator('.rc-trail .rc-header-edit').filter(has_text=name).wait_for()


def protect_lobby(page, password):
    choose_section(page, 'Lobby')
    page.get_by_role('button', name='Require password').click()
    page.get_by_label('New lobby password').fill(password)
    page.get_by_role('button', name='Save password').click()
    page.get_by_text('Password protected', exact=True).wait_for()
