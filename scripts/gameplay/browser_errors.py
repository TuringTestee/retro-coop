"""Keep recovered Firefox startup diagnostics without hiding later failures."""


def classify_page_errors(errors, socket, established_at, official_firefox):
    messages = {
        f'Firefox can’t establish a connection to the server at {socket}.',
        f'The connection to {socket} was interrupted while the page was loading.',
    }
    recovered, fatal = [], []
    for error in errors:
        elapsed = error.get('elapsed')
        if (official_firefox and error.get('message') in messages
                and isinstance(elapsed, (int, float)) and 0 <= elapsed <= established_at):
            recovered.append(error)
        else:
            fatal.append(error)
    return recovered, fatal
