I needed to change `~/.kivy/config.ini`:

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

