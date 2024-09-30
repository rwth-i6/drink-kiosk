
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
    # XAUTHORITY not necessarily needed with xhost, see below.
    # export XAUTHORITY=/home/pi/.Xauthority
    cd /kaffee/kiosk

    while true; do
      python3 ./main.py --db ../db
      sleep 5
    done

This assumes that `pi` is the main user which automatically logs in to the graphical desktop.
For the user `pi`, it is probably necessary to give permission for the X access.
For a newer Debian 12.5, we did that via `/home/pi/.config/wayland.ini`:

    [autostart]
    xauth_coffee = $HOME/bin/auth_coffee.sh

And `/home/pi/bin/auth_coffee.sh`:

    #!/bin/bash
    sleep 10  # make sure X is available
    xhost +local:kaffee-user  # give permission


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
    # mtdev_%(name)s = probesysfs,provider=mtdev  # try enabling on older Pis?
    hid_%(name)s = probesysfs,provider=hidinput

    [modules]
    touchring =


To rotate the touchscreen, probably the easy solution is to add this to `~/.kivy/config.ini`:

    [graphics]
    ...
    rotation = 270

Another alternative option to do it for the whole system, which however **does not fully work yet**:

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


## ntpdate

It seems that the local clock/time is not so good/accurate.
Running `sudo ntpdate-debian` frequently will fix this.
You might need to edit `/etc/default/ntpdate`.
Or it actually seems to use `systemd-timesyncd`, thus edit `/etc/systemd/timesyncd.conf`.
In our case, the default NTP servers (0.debian.pool.ntp.org etc) did not seem to work,
and we had to use `services-0.informatik.rwth-aachen.de` instead.


## Remote admin access

For the tool `remote-admin.py`:

It seems that `/etc/hosts` has a weird entry for the hostname (127.0.1.1).
The IPython/Jupyter server will bind to this IP, and thus not be accessible from the network.
Just remove this entry from `/etc/hosts`.
Then it should bind to the correct ethernet IP for the hostname.


## Shell environment

We need UTF8 encoding support in the terminal.
Edit `/etc/locale.gen` and uncomment the line with `en_US.UTF-8`.
Then run `sudo locale-gen` and `sudo update-locale LANG=en_US.UTF-8`.
Reboot.
Check that `locale` now shows `en_US.UTF-8`.


## Stability

The kiosk software runs fine for 1-2 weeks or so but then becomes laggish.
Probably there is some resource leakage, by our kiosk, by Kivy, or by any of the used libraries.
This is hard to debug, and also hard to fix (esp if not in our code), so as a simple work around,
we installed an automatic restart of the kiosk software during the night (see `kill_at_night` in the code).

The Pi itself ran fine for about 3 months, after which we also hit probably some OOM
(it mostly froze; we had to hard restart).
