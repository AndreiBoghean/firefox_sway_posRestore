#!/usr/bin/python3

"""
SYNOPSIS
    i3firefox.py

DESCRIPTION
    Keep Firefox windows on their i3 workspaces.

    When started, if Firefox is not running, load the persistence file.
    If running, collect the current windows.

    When a new Firefox window opens and changes its title,
    move it to the workspace where that title was last seen.

    Otherwise, keep the in-memory state and the persistence file
    synchronized to current running window configuration.

FILES
    $(XDG_STATE_HOME)/i3firefox.json
    ~/.local/state/i3firefox.json
        The persistence file.

BUGS
    The persistence file is written on every change of in-memory state.
    This should probably be debounced a bit.
"""

from contextlib import contextmanager, suppress
from dataclasses import dataclass
import itertools
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, AnyStr, IO, Iterable, Iterator, List, Optional, Set

from i3ipc import Con, Connection  # type: ignore
from i3ipc.events import Event, WindowEvent  # type: ignore


@dataclass
class Window:
    id: Optional[int]
    name: str
    workspace_name: Optional[str]


def xdg_state_dir() -> Path:
    if (path := os.getenv('XDG_STATE_HOME')):
        return Path(path)
    return Path('~/.local/state').expanduser()


@contextmanager
def staging_file(*args: Any, **kwargs: Any) -> Iterator[IO[AnyStr]]:
    with NamedTemporaryFile(*args, **kwargs, delete=False) as f:  # type: ignore
        try:
            yield f
        finally:
            Path(f.name).unlink(missing_ok=True)


class Cache:
    def __init__(self, ws: Iterable[Con]) -> None:
        self._closed_windows: List[Window] = []
        self._active_windows = {
            w.id: Window(
                id=w.id,
                name=w.name, workspace_name=w.workspace().name)
            for w in ws}
        self._unknown_windows: Set[int] = set()
        print(f"{self._active_windows=}")
        print(f"{self._unknown_windows=}")

    def serialize(self) -> str:
        return json.dumps( [
            {'title': w.name, 'workspace': w.workspace_name}
             for w in itertools.chain(self._closed_windows, self._active_windows.values())],
            ensure_ascii=False, indent=2)

    def deserialize(self, state: str) -> None:
        if self._active_windows:
            return
        self._closed_windows = [
            Window(id=None,
                   name=w['title'], workspace_name=w['workspace'])
            for w in json.loads(state)]

    def persist(self) -> None:
        state = self.serialize()
        state_dir = xdg_state_dir()
        state_dir.mkdir(parents=True, exist_ok=True)
        with staging_file(mode='w+', dir=state_dir, prefix='i3firefox', suffix='.json') as tmpjson:
            tmpjson.write(state)
            Path(tmpjson.name).replace(state_dir/'i3firefox.json')

    def restore(self) -> None:
        if self._active_windows:
            return
        state_dir = xdg_state_dir()
        with suppress(FileNotFoundError):
            self.deserialize((state_dir/'i3firefox.json').read_text())

    def on_window_new(self, i3: Connection, e: WindowEvent) -> None:
        if e.container.app_id != 'firefox':
            return

        self._unknown_windows.add(e.container.id)
        print(f'new unknown {e.container.id}')
        self.persist()

    def on_name(self, i3: Connection, e: WindowEvent) -> None:
        con = e.container
        if con.app_id != 'firefox':
            return

        if con.id in self._unknown_windows:
            if (closed := next((w for w in self._closed_windows
                                if w.name == con.name), None)):
                print(f'title {con.name} last seen on {closed.workspace_name}, moving')
                con.command(f'move --no-auto-back-and-forth container to workspace {closed.workspace_name}')
                print(f'removing unknown {con.id}')
                self._unknown_windows.remove(con.id)
            print(f'new active {con.id} titled {con.name}')
            self._active_windows[con.id] = Window(
                id=con.id,
                name=con.name,
                workspace_name=i3.get_tree().find_by_id(con.id).workspace().name)
            self.persist()
            return

        if (active := self._active_windows.get(con.id)):
            print(f'renamed active {con.id} {active.name} to {con.name}')
            active.name = con.name
            self.persist()

    def on_window_move(self, i3: Connection, e: WindowEvent) -> None:
        con = e.container
        if con.app_id != 'firefox':
            return

        if con.id in self._unknown_windows:
            print(f'moved unknown {con.id}')
            return

        if (active := self._active_windows.get(con.id)):
            active.workspace_name = i3.get_tree().find_by_id(con.id).workspace().name
            self.persist()
            print(f'moved active {con.id} to {active.workspace_name}')

    def on_window_close(self, i3: Connection, e: WindowEvent) -> None:
        con = e.container
        if con.app_id != 'firefox':
            return

        if con.id in self._unknown_windows:
            print(f'closed unknown {con.id}')
            self._unknown_windows.remove(con.id)
            self.persist()
            return

        if (was_active := self._active_windows.pop(con.id, None)):
            print(f'closed active {con.id} {con.name} from {was_active.workspace_name}')
            self._closed_windows.append(Window(
                id=None,
                name=con.name, workspace_name=was_active.workspace_name))
            self.persist()


def main() -> None:
    conn = Connection()

    firefoxes = list(filter(lambda x : x.app_id == "firefox", conn.get_tree().descendants()))
    cache = Cache(firefoxes)
    cache.restore()

    conn.on(Event.WINDOW_NEW, cache.on_window_new)
    conn.on(Event.WINDOW_TITLE, cache.on_name)
    conn.on(Event.WINDOW_MOVE, cache.on_window_move)
    conn.on(Event.WINDOW_CLOSE, cache.on_window_close)
    conn.main()


if __name__ == '__main__':
    main()
