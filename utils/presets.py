"""The five challenge targets. Each position has a reference epoch; proper motion (mas/yr) is
applied where known. WISE 0855's coordinate epoch is approximate."""

PRESETS = {
    "Barnard's Star": dict(
        ra="17h57m48.5s", dec="+04d41m36s", fov=12.0, pm=(-802.8, 10362.4), epoch=2000.0,
        tip="One of the fastest-moving stars in the sky (about 10 arcseconds a year). "
            "Follow the dotted line: the star should travel along it."),
    "Epsilon Indi B": dict(
        ra="22h04m10.5s", dec="-56d46m58s", fov=8.0, pm=(3966.0, -2536.0), epoch=2000.0,
        tip="Two brown dwarfs too close to tell apart at SPHEREx resolution, drifting about 4.7 arcseconds a year."),
    "WISE 0855": dict(
        ra="08h55m10.831s", dec="-07d14m42.53s", fov=8.0, pm=(-8123.7, 673.2), epoch=2010.5,
        tip="One of the coldest known brown dwarfs: extremely faint and fast. Try the reddest colors and "
            "combine many images; it may be too faint to see."),
    "RW Aurigae": dict(
        ra="05h07m49.6s", dec="+30d24m05s", fov=6.0, pm=(0.0, 0.0), epoch=2000.0,
        tip="A young variable star. It stays put, but its brightness changes."),
    "R Draconis": dict(
        ra="16h32m42.6s", dec="+66d45m17s", fov=6.0, pm=(0.0, 0.0), epoch=2000.0,
        tip="A pulsating variable star. Look for brightness changes, not motion."),
}
DEFAULT = "Barnard's Star"
