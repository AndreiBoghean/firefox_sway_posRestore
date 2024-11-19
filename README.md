# Keep Firefox windows on their ~~i3~~ sway workspaces

Context: I am using ~~[i3]~~ sway and multiple Firefox windows across many workspaces,
and have Firefox automatically restore the previous session’s windows and tabs.

[i3]: https://i3wm.org/

Issue: When I quit and restart Firefox, all the windows are dumped on the current workspace
and I have to spend a minute sending each of them to where they belong.

There is code in Firefox that attempts to restore each window to the desktop it was closed on,
but this code does not work on ~~i3~~ sway and specifically disabled.

There are general tools for ~~i3~~ sway to restore window configuration,
but it’s not easy to identify Firefox windows
in order to swallow them to their respective workspaces.
In particular, a Firefox window first opens with a generic `Mozilla Firefox` title,
and changes that to the current tab’s title a few milliseconds later.
This throws off the ~~i3~~ sway swallowing logic.

This script is tailored specifically for Firefox.
It maintains a list of currently open Firefox windows and recently closed windows
both in memory and in a disk file.
When a new window opens and first changes its title,
it will be moved to the workspace that title was last seen on.

If the script is started while Firefox is already running,
it will skip loading the window configuration file
and just rebuild its state from the current window configuration.

The state is kept in `$XDG_STATE_HOME/i3firefox.json`
(or `$HOME/.local/state/i3firefox.json` if `$XDG_STATE_HOME` is not set).


# Installation

`apt-get install python3-i3ipc`
^ note: this package supports both i3 and wayland :D

and arrange for this script to run on ~~i3~~ sway startup.
