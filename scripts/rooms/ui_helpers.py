"""Shared selectors for the current lobby journey in browser checks."""


def choose_panel(page, name):
    navigation = page.get_by_role('navigation', name='Lobby sections')
    if navigation.is_visible():
        expanded = page.get_by_role('button', name='Return to lobby view', exact=True)
        if expanded.is_visible():
            expanded.click()
        navigation.get_by_role('button', name=name, exact=True).click()


def choose_section(page, name):
    choose_panel(page, 'Settings')
    page.get_by_role('region', name='Game settings', exact=True).wait_for()
    selector = page.get_by_role('combobox', name='Settings section')
    if selector.is_visible():
        assert selector.evaluate('node => {const box = node.getBoundingClientRect(); return node.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2));}'), 'Settings section selector is covered'
        selector.select_option(label=name)
    else:
        page.get_by_role('button', name=name, exact=True).click()


async def choose_section_async(page, name):
    navigation = page.get_by_role('navigation', name='Lobby sections')
    if await navigation.is_visible():
        expanded = page.get_by_role('button', name='Return to lobby view', exact=True)
        if await expanded.is_visible():
            await expanded.click()
        await navigation.get_by_role('button', name='Settings', exact=True).click()
    await page.get_by_role('region', name='Game settings', exact=True).wait_for()
    selector = page.get_by_role('combobox', name='Settings section')
    if await selector.is_visible():
        await selector.select_option(label=name)
    else:
        await page.get_by_role('button', name=name, exact=True).click()


def rename_lobby(page, name):
    if page.get_by_role('navigation', name='Lobby sections').is_visible():
        choose_section(page, 'Profile')
    page.get_by_role('button', name='Edit lobby name:', exact=False).click()
    field = page.get_by_role('textbox', name='Lobby name')
    field.fill(name)
    field.press('Enter')
    page.get_by_role('button', name=f'Edit lobby name: {name}', exact=False).wait_for()


def protect_lobby(page, password):
    choose_section(page, 'Lobby')
    page.get_by_role('button', name='Require password').click()
    page.get_by_label('New lobby password').fill(password)
    page.get_by_role('button', name='Save password').click()
    page.get_by_text('Password protected', exact=True).wait_for()
