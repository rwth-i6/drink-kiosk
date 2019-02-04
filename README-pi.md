
# Raspberry Pi related information

You want to minimize the write access to the SD card.
This kiosk and its DB should live on NFS (or another network mount).

## Automatic startup

We created a custom user (`kaffee-user` in this example).

X server startup file `/etc/X11/Xsession.d/96kaffee-tmux`:

    sudo -u kaffee-user bash /kaffee/start-tmux.sh &

I have this file `/kaffee/start-tmux.sh`:

    #!/bin/bash

    set -x

    tmux new-session -d -s kaffee
    tmux send-keys /kaffee/start-kiosk.sh C-m

And this file `/kaffee/start-kiosk.sh`:

    #!/bin/bash

    set -x

    export DISPLAY=:0
    export XAUTHORITY=/home/pi/.Xauthority
    cd /kaffee/kiosk

    while true; do
      python3 ./main.py --db ../db
      sleep 5
    done


## Logging

Either the log files should go also on the NFS, or you want to disable them.
Edit `~/.kivy/config.ini`:

    [kivy]
    ...
    log_enable = 0

## Touchscreen

I needed to change `~/.kivy/config.ini` to allow the touchscreen input:

    [input]
    mouse = mouse
    %(name)s = probesysfs,provider=hidinput
    # https://github.com/kivy/kivy/issues/3640
    mtdev_%(name)s = probesysfs,provider=mtdev
    hid_%(name)s = probesysfs,provider=hidinput

    [modules]
    touchring =


To rotate the touchscreen, probably the easy solution is to add this to `~/.kivy/config.ini`:

    [graphics]
    ...
    rotation = 270

Another alternative option to do it for the whole system:

I modified `/boot/config.txt` to rotate our touchscreen:

    # https://elinux.org/RPiconfig
    # default is 64
    gpu_mem=128
    # 90 degrees
    display_rotate=1

I created a new file `/etc/X11/Xsession.d/90rotatetouch` to also rotate the input:

    # https://wiki.ubuntu.com/X/InputCoordinateTransformation
    xinput set-prop "ELAN Touchscreen" "Coordinate Transformation Matrix" 0 1 0 -1 0 1 0 0 1

However, mtdev seems to ignore this.
Probably there is a way to also tell mtdev to rotate, but I don't know how, and I just use the other option via the Kivy option now.

