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

Minimum supported Python version: 3.5
(Because our Raspberry Pi Linux only has that...)


# Usage

You need some minimal preparation for the DB.
Create a new directory for the DB, and initialize an empty Git repository in it.
The `demo-db` directory here is an example for the DB directory.
Create the config files, e.g. by copying it from `demo-db/config`.

For the GUI, run `main.py --db <your-db-dir>`.

Currently, the drinkers list is updated via LDAP via the file `config/ldap-opts.txt` in the DB.
The update is done at every startup of the app.
(We restart the app every night.)

The drinkers list update will not delete any drinkers from the DB.
In case some drinker has been added previously, but is not in the active drinker list anymore,
the user will not be shown in the GUI, but the user will still be in the DB.
To remove any inactive drinkers, use `tools/remote-admin.py`
and the `drinker_delete_inactive_non_neg_balance` command.
