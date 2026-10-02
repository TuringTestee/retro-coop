"""Shared selectors for the current lobby journey in synchronous browser checks."""


def rename_lobby(page, name):
    page.locator('.rc-trail .rc-header-edit').click()
    field = page.get_by_role('textbox', name='Lobby name')
    field.fill(name)
    field.press('Enter')
    page.locator('.rc-trail .rc-header-edit').filter(has_text=name).wait_for()


def protect_lobby(page, password):
    page.get_by_role('button', name='Lobby', exact=True).click()
    page.get_by_role('button', name='Require password').click()
    page.get_by_label('New lobby password').fill(password)
    page.get_by_role('button', name='Save password').click()
    page.get_by_text('Password protected', exact=True).wait_for()
