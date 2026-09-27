"""Shared across Gunicorn and systemd on a single LXC. No pickle or secrets."""
import fcntl
import json
import os
import time
from pathlib import Path
from django.conf import settings


class SyncBusy(Exception):
    pass


def state_path(name):
    directory = Path(settings.SYNC_STATE_DIR)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    return directory / name


def read_state(name):
    try:
        return json.loads(state_path(name).read_text())
    except FileNotFoundError:
        return {}


def write_state(name, value):
    target = state_path(name)
    temporary = target.with_suffix(f'.{os.getpid()}.tmp')
    with open(temporary, 'w', encoding='utf-8') as output:
        os.chmod(temporary, 0o600)
        json.dump(value, output)
    os.replace(temporary, target)


def lock(name):
    handle = open(state_path(name + '.lock'), 'a+')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise SyncBusy('已有同步工作執行中。') from None
    return handle


def reserve_sync():
    handle = lock('sync')
    try:
        state = read_state('sync.json')
        if time.time() < state.get('next_allowed', 0):
            raise SyncBusy('同步冷卻中，請稍後再試。')
        write_state('sync.json', {'state': 'running', 'next_allowed': time.time() + 900})
    except Exception:
        handle.close()
        raise
    return handle


def finish_sync(**result):
    state = read_state('sync.json')
    state.update(result)
    write_state('sync.json', state)


def sync_status():
    state = read_state('sync.json') or {'state': 'idle'}
    if state.get('state') == 'running':
        try:
            handle = lock('sync')
        except SyncBusy:
            return state
        with handle:
            state = read_state('sync.json')
            if state.get('state') == 'running':
                state.update(state='error', error='上次同步已中斷，請稍後重試。')
                write_state('sync.json', state)
    return state
