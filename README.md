# Sync(thing) Indicator
Visualizes the synchronization status of [Syncthing](https://syncthing.net/) and [rsync](https://rsync.samba.org/) by changing the leds of an [AMD Wraith Prism](https://www.amd.com/en/technologies/cpu-cooler-solution) cooler using [cm-rgb](https://github.com/gfduszynski/cm-rgb).

Overview of considered states and their meaning:

| Down | Sync | Done | Idle | Error|
|:----:|:----:|:----:|:----:|:----:|
| Syncthing is not running (also shown on startup) | Syncthing is syncing or rsync is running | Syncthing is done and rsync is not running | Syncthing is running but not done (e.g., remote device down) | Syncthing error since boot | 
| ![](doc/down.jpg) | ![](doc/sync.jpg) | ![](doc/done.jpg) | ![](doc/idle.jpg) | ![](doc/error.jpg) |

*Disclaimer: The error state was tested superficially, as we do not have access to errors thrown by Synching (yet).*

## Requirements

This project requires that...
1. `Syncthing` is installed and running on the device
2.  An AMD Wraith Prism cooler is connected via USB (check `lsusb | grep 2516:0051`)

## Setup

This script has been tested on Ubuntu 22.04 with Python 3.10.12.

Steps
1. Install requirements 
    ```
    $ pip install -r requirements.txt
    ```
2. Setting RGB colors without root permissions can be enabled by creating an udev rule file `/etc/udev/rules.d/60-cm-rgb.rules` with the following content:
    ```
    SUBSYSTEM=="usb", ATTR{idVendor}=="2516", ATTR{idProduct}=="0051", MODE="0666", TAG+="uaccess", TAG+="udev-acl"
    ```

2. Set the required environment variables (see `env.conf`). It is recommended to use the provided configuration file. As this includes the Syncthing API key, make sure that the file has restrictive permissions (i.e. can only be read by the current user and root).

## Run

To run and debug the script, you can manually set the environment variables or load the configuration file like
```
$ env $(cat env.conf | grep -e '^[^#]' | xargs) python3 sync-indicator/src/main.py
```

## Systemd Service

Sync indicator is intended to be run as a (systemd) service.

Create a service file at `~/.config/systemd/user/sync-indicator.service` with the following content and adjust `ExecStart` and `EnvironmentFile` according to your setup.
```
[Unit]
Description=Sync Indicator Service
After=multi-user.target
StartLimitIntervalSec=500
StartLimitBurst=5

[Service]
ExecStart=python3 -O -u /home/led/sync-indicator/src/main.py run
EnvironmentFile=/home/led/sync-indicator.conf
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=default.target
```

Test the service with
```
$ systemctl --user daemon-reload && systemctl --user restart sync-indicator && sleep 2 && systemctl --user status -n 100 sync-indicator
```

Enable the service and user lingering (allows running user services without login) with
```
$ systemctl --user enable sync-indicator
$ loginctl enable-linger
```
