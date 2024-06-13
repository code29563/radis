# -*- coding: utf-8 -*-
"""
================================
Calculate a spectrum from Kurucz
================================

Auto-download and compute an atomic spectra from the Kurucz database

Naming Conventions:
- You can use either the conventional naming or its simplified form.
- For instance, 'Mg_I' can be used for 'Mg' and 'Ca_II' for 'Ca+'.

"""

from radis import calc_spectrum, plot_diff
from radis.lbl.factory import SpectrumFactory
from radis.lbl.broadening import gamma_vald3
import numpy as np

wlim = (12850, 13120)
truncation = 50
mole_fraction = 0.01

def func1(**kwargs):
    """An example implementing the default broadening formula and values in SpectraPlot"""
    # print(kwargs.keys())
    # print(kwargs['df'].columns)
    return 1.0*(296/kwargs['Tgas'])**0.8, None

def func2(**kwargs):
    """An example changing the value of the van der Waals broadening parameter for a particular line"""
    df = kwargs['df']
    Tgas = kwargs['Tgas']
    pressure_atm = kwargs['pressure_atm']
    diluent = kwargs['diluent']
    #print(df.loc[df['orig_wavelen'] == 777.5388, 'gamvdW'])
    df.loc[df['orig_wavelen'] == 777.5388, 'gamvdW'] = -7
    #print(df.loc[df['orig_wavelen'] == 777.5388, 'gamvdW'])
    # copied from default code in RADIS:
    gammma_rad, gamma_stark, gamma_vdw = gamma_vald3(Tgas, pressure_atm*1.01325, df['wav'], df['El'], df['ionE'], df['gamRad'], df['gamSta'], df['gamvdW'], diluent)
    shift = (1.0/3.0)*2*gamma_vdw #Konjević et al. 2012 §4.1.3.2
    wl = gammma_rad + gamma_stark + gamma_vdw
    return wl, shift

def func3(**kwargs):
    """An example scaling the Stark broadening parameter by (T/10000)**(1.0/6.0)"""
    df = kwargs['df']
    Tgas = kwargs['Tgas']
    pressure_atm = kwargs['pressure_atm']
    diluent = kwargs['diluent']
    df['gamSta'].replace(0., -99)
    df['gamSta'] += (1.0/6.0)*(np.log10(Tgas) - 4)
    # copied from default code in RADIS:
    gammma_rad, gamma_stark, gamma_vdw = gamma_vald3(Tgas, pressure_atm*1.01325, df['wav'], df['El'], df['ionE'], df['gamRad'], df['gamSta'], df['gamvdW'], diluent)
    shift = (1.0/3.0)*2*gamma_vdw #Konjević et al. 2012 §4.1.3.2
    wl = gammma_rad + gamma_stark + gamma_vdw
    return wl, shift

class CustomSpectrumFactory(SpectrumFactory):
    def _add_Lorentzian_broadening_HWHM(
        self,
        df,
        pressure_atm,
        mole_fraction,
        Tgas,
        Tref,
        diluent,
        diluent_broadening_coeff,
    ):

        print('testing')
        wl, shift = func1(
            Tgas=Tgas,
        )
        if shift:
            df['shft'] = shift

        # Update dataframe
        df["hwhm_lorentz"] = wl

        #####

        return

s = calc_spectrum(
    wlim[0],
    wlim[1]+truncation,  # cm-1
    species="O_I",  # Enter species name
    Tgas=4000,  # K
    databank="kurucz",
    pressure=1.01325,
    # optimization=None,
    truncation=truncation,
    diluent={'H':1-mole_fraction-1e-3, 'e-': 1e-3},
    mole_fraction=mole_fraction,
    path_length=15,
    # lbfunc=func2,
    # CustomSpectrumFactory=CustomSpectrumFactory,
    warnings={"AccuracyError": "ignore", "AccuracyWarning": "ignore"},
)

s.crop(*wlim)
s.plot("radiance_noslit", wunit="cm-1")