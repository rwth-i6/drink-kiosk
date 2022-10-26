# i6 drink kiosk

Coffee and other drinks.

Designed for our internal use at the [Human Language Technology and Pattern Recognition Group (Chair of Computer Science 6), RWTH Aachen University](https://www-i6.informatik.rwth-aachen.de/).

The GUI is developed using [Kivy](https://kivy.org/).
The drinkers DB and all the configuration is just file-based.
It is expected that the drinkers DB is a directory under Git, and the kiosk app will do git commits frequently.
The drinkers list can be automatically received via LDAP.
The kiosk runs in our environment with a touchpad on a Raspberry Pi
([more Raspberry Pi related info](https://github.com/rwth-i6/drink-kiosk/blob/master/README-pi.md)).

Install dependencies:

    pip3 install --user -r requirements.txt

For a demo, run:

    ./main.py --db demo-db

Or maybe:

    ./main.py --db demo-db --readonly

Screenshot:

![Screenshot](https://raw.githubusercontent.com/rwth-i6/drink-kiosk/master/demo-db/screenshot.png)
