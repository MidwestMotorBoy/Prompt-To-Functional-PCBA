"""cpdl.py: second half of cpd (team C integration): moves the stage input sense resistors next to the PD chips once
cpower has placed the stages. Use HOOKS=cpd,cpower,cpdl,ccorr (PD chips before the stages, resistor after)."""
import cpd


def pre_place(ctx):
    cpd.place_rin(ctx)
