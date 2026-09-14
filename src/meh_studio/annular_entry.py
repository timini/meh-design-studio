"""A supported conical core for exploring annular midrange entry channels."""


def supported_core(design):
    """Local +Z points from the horn toward the diaphragm; units are millimetres.

    The core tapers to a point at the horn end. Two crossing bars create four
    radial supports attached to the port wall. The rear circular face terminates
    at the chamber inlet, leaving the declared front depth to the diaphragm.
    """
    from .cad_runtime import load_cadquery
    cq = load_cadquery()
    radius = design.port_radius_m * 1000
    core = design.port_core_radius_m * 1000
    depth = design.port_length_m * 1000
    width = design.wall_m * 1000
    cone = cq.Solid.makeCone(0, core, depth)
    # Extend supports into the enclosing material so the insert is integral.
    reach = radius + width / 2
    x = cq.Solid.makeBox(2 * reach, width, depth, cq.Vector(-reach, -width / 2, 0))
    y = cq.Solid.makeBox(width, 2 * reach, depth, cq.Vector(-width / 2, -reach, 0))
    result = cone.fuse(x, y).clean()
    if not result.isValid() or len(result.Solids()) != 1:
        raise ValueError('annular entry core and supports are disconnected or invalid')
    return result
