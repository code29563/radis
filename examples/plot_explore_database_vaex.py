# -*- coding: utf-8 -*-
"""
.. _example_explore_database_vaex:

================================
Download and Explore Line Database
================================

Databases can be downloaded automatically and edited locally. By default the database
is returned as a :py:mod:`pandas` DataFrame. To explore huge databases (like HITEMP CO2, CH4 or H2O, or ExoMol)
that do not fit in RAM, RADIS allows you to use a :py:mod:`vaex` DataFrame instead (out-of-RAM).

"""

#%% Example with HITRAN and Pandas
from radis.io.hitran import fetch_hitran

df_OH = fetch_hitran("OH")
print(df_OH.columns)


#%%
# Returns:
# ::
# Index(['id', 'iso', 'wav', 'int', 'A', 'airbrd', 'selbrd', 'El', 'Tdpair',
#        'Pshft', 'gp', 'gpp'],
#       dtype='object')

#%% Example with HITEMP and vaex
from radis.io.hitemp import fetch_hitemp

df_CO2 = fetch_hitran(
    "CO2",
    output="pandas",  # default
    load_wavenum_min=2000,
    load_wavenum_max=2500,
)
df_CO2_hitemp = fetch_hitemp(
    "CO2",
    output="vaex",  # return a Vaex DataFrame.
    load_wavenum_min=2000,
    load_wavenum_max=2500,
    columns="jl",  # a specific can be retrieved
)
print(f"{len(df_CO2_hitemp)} lines in HITEMP CO2; 2000 - 2450 cm-1")

#%%
# We can also use Vaex graph functions.
# See Vaex vizualisations : https://vaex.readthedocs.io/en/latest/guides/advanced_plotting.html#
#
# For instance, we plot here (left) the density of lines in the HITRAN and HITEMP databases and (right) the variations of the broadening coefficients with the rotational number.

import matplotlib.pyplot as plt

fig_size = (13, 5)
f = plt.figure(figsize=fig_size)
ax_histo = f.add_subplot(1, 2, 1)
df_CO2.viz.histogram("wav", color="k", label="HITRAN")
df_CO2_hitemp.viz.histogram(
    "wav",
    color="r",
    label="HITEMP",
    xlabel="Wavenumber [cm$^{-1}$]",
    ylabel="Counts",
)
ax_histo.set_ylim(bottom=0)
ax_histo.legend()

#% Figure 2
ax_gamma_J = f.add_subplot(1, 2, 2)
df_CO2_hitemp.viz.heatmap(
    "jl",
    "airbrd",
    f="log",
    limits="90%",
    xlabel="Rotational number, J",
    ylabel="$\gamma_{air}$ [cm$^{-1}$/atm]",
)
