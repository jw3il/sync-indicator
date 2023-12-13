from enum import Enum
from typing import Optional
import psutil
import time
import requests
import json
import constants
import subprocess
from datetime import datetime
from dateutil.parser import parse
from dateutil.tz import tzlocal


def proc_names() -> list[str]:
    return list(p.name() for p in psutil.process_iter())


def rsync_is_running() -> bool:
    return "rsync" in proc_names()


def syncthing_api(endpoint="/rest/db/completion"):
    url = f"{constants.SYNCTHING_URL}{endpoint}"
    x = requests.get(
        url,
        headers={"X-API-Key": constants.SYNCTHING_API_KEY},
        verify=constants.SYNCTHING_CERT_FILE,
    )
    return json.loads(x.text)


def syncthing_is_up() -> bool:
    try:
        syncthing_api(endpoint="/rest/system/ping")
        return True
    except RuntimeError as e:
        print(e)
        return False


def syncthing_completion() -> float:
    return float(syncthing_api(endpoint="/rest/db/completion")["completion"])


def syncthing_sync_is_done() -> bool:
    return syncthing_completion() == 100.0


def syncthing_errors() -> Optional[list]:
    return syncthing_api(endpoint="/rest/system/error")["errors"]


def boot_datetime() -> datetime:
    return datetime.fromtimestamp(psutil.boot_time(), tz=tzlocal())


def syncthing_found_errors_since_boot() -> bool:
    errors = syncthing_errors()
    if errors is None:
        return False

    boot_time = boot_datetime()
    errors_since_boot = list(filter(lambda e: parse(e["when"]) > boot_time, errors))
    return len(errors_since_boot) > 0


def syncthing_is_downloading(
    min_delta_bytes=1024, initial_delay=1, tolerance_num_calls=10
) -> bool:
    """
    Checks if syncthing is synchronizing.

    :param min_delta_bytes: Minimum delta in bytes since last function call to classify as synchronizing.
    :param initial_delay: Initial delay in seconds to estimate synchronization speed.
    :param tolerance_num_calls: Max number of subsequent times a negative result is ignored (after a positive result)
    :return: whether syncthing is synchronizing
    """
    # TODO: replace with better API call? We just want to know if the system is currently syncing
    total = syncthing_api("/rest/system/connections")["total"]
    total_sum = total["inBytesTotal"] + total["outBytesTotal"]
    if not hasattr(syncthing_is_downloading, "total_sum") or not hasattr(
        syncthing_is_downloading, "ignore_counter"
    ):
        syncthing_is_downloading.total_sum = total_sum
        # measure download progress for the first time
        time.sleep(initial_delay)
        syncthing_is_downloading.ignore_counter = 0
        return syncthing_is_downloading(min_delta_bytes=min_delta_bytes)

    # min_delta is needed because clients also exchange status bytes
    # that do not count as syncing (included in in/outBytesTotal)
    # We don't care about this status traffic.
    total_changed = total_sum >= syncthing_is_downloading.total_sum + min_delta_bytes
    syncthing_is_downloading.total_sum = total_sum

    if total_changed:
        syncthing_is_downloading.ignore_counter = tolerance_num_calls
        return True
    else:
        syncthing_is_downloading.ignore_counter = max(
            0, syncthing_is_downloading.ignore_counter - 1
        )
        return syncthing_is_downloading.ignore_counter >= 0


class SyncState(Enum):
    # Syncthing is offline
    DOWN = 0
    # Syncthing or rsync are actively syncing
    SYNC = 1
    # Syncthing is done and rsync is not running
    DONE = 2
    # Syncthing idles but is not done
    IDLE = 3
    # Syncthing errors were thrown since boot
    ERROR = 4


def static_rainbow_args(static_color_hex="#00ff00", rainbow_speed=3) -> list[str]:
    return [
        "set",
        "logo",
        "--mode=static",
        f"--color={static_color_hex}",
        "--brightness=4",
        "fan",
        "--mode=static",
        f"--color={static_color_hex}",
        "--brightness=4",
        "ring",
        "--mode=rainbow",
        f"--speed={rainbow_speed}",
        "--brightness=5",
    ]


def static_args(static_color_hex="#00ff00") -> list[str]:
    return [
        "set",
        "logo",
        "--mode=static",
        f"--color={static_color_hex}",
        "--brightness=4",
        "fan",
        "--mode=static",
        f"--color={static_color_hex}",
        "--brightness=4",
        "ring",
        "--mode=static",
        f"--color={static_color_hex}",
        "--speed=1",
        "--brightness=5",
    ]


def down_args() -> list[str]:
    return [
        "set",
        "logo",
        "--mode=static",
        "--color=#ffffff",
        "--speed=1",
        "--brightness=3",
        "fan",
        "--mode=static",
        "--color=#ffffff",
        "--mirage-red-freq=120",
        "--mirage-green-freq=120",
        "--mirage-blue-freq=120",
        "--speed=1",
        "--brightness=4",
        "ring",
        "--mode=static",
        "--color=#ffffff",
        "--speed=1",
        "--brightness=3",
    ]


def set_led(state: SyncState):
    def run_with_args(args: list[str]):
        cmd = [f"{constants.CM_RGB_CLI_PATH}", *args]
        print(f"Executing {' '.join(cmd)}")
        subprocess.run([f"{constants.CM_RGB_CLI_PATH}", *args])

    if state == SyncState.DOWN:
        run_with_args(down_args())
    elif state == SyncState.SYNC:
        run_with_args(static_rainbow_args("#1e99e6", rainbow_speed=3))
    elif state == SyncState.DONE:
        run_with_args(static_rainbow_args("#00ff00", rainbow_speed=1))
    elif state == SyncState.IDLE:
        run_with_args(static_rainbow_args("#a746e8", rainbow_speed=1))
    elif state == SyncState.ERROR:
        run_with_args(static_args("#ff0000"))
    else:
        run_with_args(["restore"])
        print(f"LED: Unknown state {state} -> restore defaults")


def update_state(state: SyncState):
    if not hasattr(update_state, "last_state"):
        update_state.last_state = -1

    if update_state.last_state == state.value:
        return
    update_state.last_state = state.value

    print(f"Updating State to {state}")
    set_led(state)


if __name__ == "__main__":
    while True:
        time.sleep(1)
        if not syncthing_is_up():
            update_state(SyncState.DOWN)
            continue

        if syncthing_found_errors_since_boot():
            update_state(SyncState.ERROR)
            continue

        is_incomplete = syncthing_completion() < 100
        is_syncing = (
            is_incomplete and syncthing_is_downloading()
        ) or rsync_is_running()
        if is_syncing:
            update_state(SyncState.SYNC)
        elif is_incomplete:
            # not syncing but not complete => idle
            update_state(SyncState.IDLE)
        else:
            # not syncing and complete => done
            update_state(SyncState.DONE)
