"""
The AdBKurucz class below is inspired by an Exojax class developed by Hiroyuki Tako ISHIKAWA.
It allows loading data from the Kurucz database and performing several calculations on it.
https://github.com/HajimeKawahara/exojax.git

Author: Racim Menasria
Date: June 2023
"""

import io
import os
import pkgutil
from contextlib import closing
from io import BytesIO

import numpy as np
import pandas as pd
import periodictable
import requests
from tqdm import tqdm

from radis.misc.utils import getProjectRoot
from radis.phys.air import air2vacuum

def load_ionization_energies():
    #based on https://github.com/HajimeKawahara/exojax/blob/78466cef0170ee1a2768b6a6f7b7c911d715c1bd/src/exojax/spec/atomllapi.py#L308; the file 'NIST_Atomic_Ionization_Energies.txt' is taken from https://github.com/HajimeKawahara/exojax/blob/78466cef0170ee1a2768b6a6f7b7c911d715c1bd/src/exojax/data/atom/NIST_Atomic_Ionization_Energies.txt; 
    # Not used for now but will probably be for NIST database
    """Load atomic ionization energies.

    Returns:
        df_ionE (pd.DataFrame): table of ionization energies

    """
    fn_IonE = os.path.join(getProjectRoot(), "db", "NIST_Atomic_Ionization_Energies.txt") #pkgutil.get_data(
    #     "exojax", "data/atom/NIST_Atomic_Ionization_Energies.txt"
    # )
    df_ionE = pd.read_csv(fn_IonE, sep="|", skiprows=6, header=0)
    return df_ionE

def pick_ionE(ielem, iion, df_ionE):
    """Pick up ionization energy of a specific atomic species.

    This method was extracted from exojax/src/exojax/spec/atomllapi.py
    (https://github.com/HajimeKawahara/exojax.git)

    Args:
        ielem (int): atomic number (e.g., Fe=26)
        iion (int): ionized level (e.g., neutral=1, singly ionized=2, etc.)
        df_ionE (pd.DataFrame): table of ionization energies

    Returns:
        ionE (float): ionization energy

    Note:
        NIST_iE is for now is .NIST_iE.txt
    """

    def f_droppare(x):
        return (
            x.str.replace("\(", "", regex=True)
            .str.replace("\)", "", regex=True)
            .str.replace("\[", "", regex=True)
            .str.replace("\]", "", regex=True)
            .str.replace("                                      ", "0", regex=True)
        )

    ionE = f_droppare(
            df_ionE[
                (df_ionE["At. num "] == ielem)
                & (df_ionE[" Ion Charge "] == iion - 1)
            ]["      Ionization Energy (a) (eV)      "]
        )
    return ionE

def get_atomic_number(species):
    """
    Extracts the atomic_number from the species id
    """
    atomic_symbol = species.split("_")[0]
    el = getattr(periodictable, atomic_symbol)

    atomic_number = el.number
    return atomic_number

def get_ionization_state(species):
    """
    Extracts the ionization_state from the species id
    """
    ionization_str = species.split("_")[1]
    roman_to_int = {"I": 0, "II": 1, "III": 2, "IV": 3, "V": 4, "VI": 5}
    ionization_int = roman_to_int.get(ionization_str, -1)
    #formatted_str = f"{ionization_int:02}"

    return ionization_int#formatted_str

def get_element_symbol(species):
    atomic_symbol = species.split("_")[0]
    el = getattr(periodictable, atomic_symbol)
    return el

#Initially from Exojax but no longer needed since pressure is handled by SpectrumFactory; Update: from https://github.com/HajimeKawahara/exojax/blob/78466cef0170ee1a2768b6a6f7b7c911d715c1bd/src/exojax/atm/atmprof.py#L10
def pressure_layer(logPtop=-8.,
                logPbtm=2.,
                NP=20,
                mode='ascending',
                reference_point=0.5):
    """generating the pressure layer.

    Args:
        logPtop: log10(P[bar]) at the top layer
        logPbtm: log10(P[bar]) at the bottom layer
        NP: the number of the layers
        mode: ascending or descending
        reference_point: reference point in the layer. 0.5:center, 1.0:lower boundary, 0.0:upper boundary
        numpy: if True use numpy array instead of jnp array

    Returns:
        Parr: pressure layer
        dParr: delta pressure layer
        k: k-factor, P[i-1] = k*P[i]

    Note:
        dParr[i] = Parr[i] - Parr[i-1], dParr[0] = (1-k) Parr[0] for ascending mode
    """
    dlog10P = (logPbtm - logPtop) / (NP - 1)
    k = 10**-dlog10P
    
    Parr = np.logspace(logPtop, logPbtm, NP)
    
    dParr = (k ** (reference_point - 1.0) - k**reference_point) * Parr
    if mode == 'descending':
        Parr = Parr[::-1]
        dParr = dParr[::-1]

    return Parr, dParr, k

def load_pf_Barklem2016():
    """Load a table of the partition functions for 284 atomic species.

    Returns
    -------
    pfTdat:  pd.DataFrame
        Steps of temperature (K)
    pfdat:  pd.DataFrame
        Partition functions for 284 atomic species

    References
    ----------
    `Barklem & Collet (2016), Table 8 <https://doi.org/10.1051/0004-6361/201526961>`_

    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "./../levels/pfTKurucz_values.txt")
    with open(file_path, "r") as file:
        pfT_str = file.read()
    #     lines = file.readlines()
    # pfT_values_line = [line for line in lines if "pfT_str" in line][0]
    # pfT_values_line = pfT_values_line.strip()
    # pfT_str = pfT_values_line.replace('"', "")  # Removing quotation marks.
    pfTdat = pd.read_csv(io.StringIO(pfT_str), sep='\s+')
    pfTdat = pd.Series(pfTdat.columns[1:]).astype(
        "float64"
    )  # Converts the values to float64, skipping the first value

    with open(os.path.join(getProjectRoot(), "db", "kuruczpartfn.txt"), "r") as f:
        pfdat = pd.read_csv(f, sep="\s+", comment="#", names=pfTdat.index)

    return pfTdat, pfdat

class AdBKurucz:
    from radis.phys.constants import c_CGS, ecgs, mecgs

    def __init__(self, species):
        self.kurucz_url_base = "http://kurucz.harvard.edu/linelists/gfall/gf"
        self.hdf5_file = None
        self.data = None
        self.pfTdat, self.pfdat = load_pf_Barklem2016()
        self.populations = None
        self.species = species
        self.atomic_number = get_atomic_number(species)
        self.ionization_state = get_ionization_state(species)
        self.element_symbol = get_element_symbol(species)

    def get_url(self, atomic_number, ionization_state):
        ionization_state = str(ionization_state).zfill(2)
        code = f'{atomic_number}{ionization_state}'
        return "http://kurucz.harvard.edu/atoms/" + code + "/gf" + code + ".all"
        #return f"http://kurucz.harvard.edu/linelists/gfall/gf{atomic_number}{ionization_state}.all"

    def download_file(self):
        """Download a file from an url to a specified output path."""

        # extracts the file's name from l'URL
        filename = self.url.split("/")[-1]

        # Verify if the file exists already
        if os.path.exists(filename):
            print("File already exists, skipping download.")
            return filename

        with closing(requests.get(self.url, stream=True)) as r:
            total_size = int(r.headers.get("content-length", 0))
            block_size = 1024
            with open(filename, "wb") as f, tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc=filename,
            ) as pbar:
                for data in r.iter_content(block_size):
                    f.write(data)
                    pbar.update(len(data))
        return filename

    def Sij0(self, A, g, nu_lines, elower, QTref):
        # The int column of the df can be computed using this method but the default option rather uses Radis linestrength_from_Einstein
        """Reference Line Strength in Tref=296K, S0.

        Note:
        Tref=296K

        Args:
        A: Einstein coefficient (s-1)
        g: the upper state statistical weight
        nu_lines: line center wavenumber (cm-1)
        elower: elower
        QTref: partition function Q(Tref)
        Mmol: molecular mass (normalized by m_u)

        Returns:
        Sij(T): Line strength (cm)
        """
        hcperk = 1.4387773538277202  # hc/kB (cm K)
        ccgs = 29979245800.0
        Tref = 296.0
        S0 = (
            -A
            * g
            * np.exp(-hcperk * elower / Tref)
            * np.expm1(-hcperk * nu_lines / Tref)
            / (8.0 * np.pi * ccgs * nu_lines**2 * QTref)
        )
        return S0

    def read_kurucz(self, kuruczf):
        """
        This method was adapted from the original read_kurucz method in exojax/src/exojax/spec/atomllapi.py
        (https://github.com/HajimeKawahara/exojax.git)
        Input Kurucz line list (http://kurucz.harvard.edu/linelists/)

        Args:
            kuruczf: file path

        Returns:
            A:  Einstein coefficient in [s-1]
            nu_lines:  transition waveNUMBER in [cm-1] (#NOT frequency in [s-1])
            elower: lower excitation potential [cm-1] (#converted from eV)
            eupper: upper excitation potential [cm-1] (#converted from eV)
            gupper: upper statistical weight
            jlower: lower J (rotational quantum number, total angular momentum)
            jupper: upper J
            ielem:  atomic number (e.g., Fe=26)
            iion:  ionized level (e.g., neutral=1, singly)
            gamRad: log of gamma of radiation damping (s-1) #(https://www.astro.uu.se/valdwiki/Vald3Format)
            gamSta: log of gamma of Stark damping (s-1)
            gamvdW:  log of (van der Waals damping constant / neutral hydrogen number) (s-1)
        """
        with open(kuruczf) as f:
            lines = f.readlines()
        num_lines = len(lines)
        (
            wlnmair,
            loggf,
            species,
            elower,
            jlower,
            labellower,
            eupper,
            jupper,
            labelupper,
            gamRad,
            gamSta,
            gamvdW,
            ref,
            NLTElower,
            NLTEupper,
            isonum,
            hyperfrac,
            isonumdi,
            isofrac,
            hypershiftlower,
            hypershiftupper,
            hyperFlower,
            hypernotelower,
            hyperFupper,
            hypternoteupper,
            strenclass,
            auto,
            landeglower,
            landegupper,
            isoshiftmA,
        ) = (
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.array([""] * num_lines, dtype=object),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
            np.zeros(num_lines),
        )
        ielem, iion = np.zeros(num_lines, dtype=int), np.zeros(num_lines, dtype=int)

        for i, line in enumerate(lines):
            wlnmair[i] = float(line[0:11])
            loggf[i] = float(line[11:18])
            species[i] = str(line[18:24])
            ielem[i] = int(species[i].split(".")[0])
            iion[i] = int(species[i].split(".")[1])
            elower[i] = float(line[24:36])
            jlower[i] = float(line[36:41])
            eupper[i] = float(line[52:64])
            jupper[i] = float(line[64:69])
            gamRad[i] = float(line[80:86])
            gamSta[i] = float(line[86:92])
            gamvdW[i] = float(line[92:98])
            isonum[i] = int(line[106:109])

        ielem = np.unique(ielem)
        assert len(ielem) == 1
        ielem = ielem[0]

        iion = np.unique(iion)
        assert len(iion) == 1
        iion = iion[0] + 1
        
        # Invert elower, eupper, and jlower, jupper where eupper - elower <= 0
        elower_inverted = np.where((eupper-elower) > 0,  elower,  eupper)
        eupper_inverted = np.where((eupper-elower) > 0,  eupper,  elower)
        jlower_inverted = np.where((eupper-elower) > 0,  jlower,  jupper)
        jupper_inverted = np.where((eupper-elower) > 0,  jupper,  jlower)
        elower = elower_inverted
        eupper = eupper_inverted
        jlower = jlower_inverted
        jupper = jupper_inverted

        wlaa = np.where(wlnmair < 200, wlnmair * 10, air2vacuum(wlnmair * 10))
        nu_lines = 1e8 / wlaa[::-1]  # [cm-1]<-[AA]
        wlnmair = wlnmair[::-1]
        loggf = loggf[::-1]
        elower = elower[::-1]
        eupper = eupper[::-1]
        jlower = jlower[::-1]
        jupper = jupper[::-1]
        gupper = jupper * 2 + 1
        A = (
            10**loggf
            / gupper
            * (self.c_CGS * nu_lines) ** 2
            * (8 * np.pi**2 * self.ecgs**2)
            / (self.mecgs * self.c_CGS**3)
        )
        gamRad = gamRad[::-1]
        gamSta = gamSta[::-1]
        gamvdW = gamvdW[::-1]
        isonum = isonum[::-1]

        ionE = pick_ionE(ielem, iion, load_ionization_energies())
        assert ionE.size == 1
        ionE = float(ionE.iloc[0])

        data_dict = {
            "A": A,
            'orig_wavelen': wlnmair,
            "wav": nu_lines,
            "El": elower,
            "eupper": eupper,
            "gu": gupper,
            "jlower": jlower,
            "ju": jupper,
            "id": ielem,
            "ionE": ionE,
            "iso": isonum,
            "gamRad": gamRad,
            "gamSta": gamSta,
            "gamvdW": gamvdW,
            "Tdpair": 0.68,  # placeholder to adjust
            "wlnmair": wlnmair,
            "loggf": loggf,
            "species": species,
            "labellower": labellower,
            "labelupper": labelupper,
            "ref": ref,
            "NLTElower": NLTElower,
            "NLTEupper": NLTEupper,
            "isonum": isonum,
            "hyperfrac": hyperfrac,
            "isonumdi": isonumdi,
            "isofrac": isofrac,
            "hypershiftlower": hypershiftlower,
            "hypershiftupper": hypershiftupper,
            "hyperFlower": hyperFlower,
            "hypernotelower": hypernotelower,
            "hyperFupper": hyperFupper,
            "hypternoteupper": hypternoteupper,
            "strenclass": strenclass,
            "auto": auto,
            "landeglower": landeglower,
            "landegupper": landegupper,
            "isoshiftmA": isoshiftmA,
            "shft": 0
            # "int":self.Sij0(A,gupper,nu_lines,elower,self.partfcn(self.species,296))
            # if int parameter is used, calc_linestrength_eq will also use it
        }

        self.data = pd.DataFrame(data_dict)
        return self.data

    def add_airbrd(self, data):
        if "airbrd" not in data.columns:
            # placeholder for neutral_hydrogen_number and atomic_coeff
            # TODO: adjust the coefficient to the atoms and adjust the value for neutral_hydrogen_number

            neutral_hydrogen_number = 1
            atomic_coeff = 1

            if self.element_symbol == "H":
                airbrd = (
                    (10 ** data["gamvdW"]) * data["Tdpair"] * neutral_hydrogen_number
                )
            elif self.element_symbol == "He":
                airbrd = (
                    (10 ** data["gamvdW"])
                    * data["Tdpair"]
                    * neutral_hydrogen_number
                    * 0.42
                )
            else:
                airbrd = (
                    (10 ** data["gamvdW"])
                    * data["Tdpair"]
                    * neutral_hydrogen_number
                    * atomic_coeff
                )

            data["airbrd"] = airbrd

    def partfcn(self, key, T):
        # So far ielem is used for id and iion for iso in eq_spectrum so this method is used when the linestrength is computed for data_dict
        """Partition function from Barklem & Collet (2016).

        Args:
        key: the atom name
        T: temperature

        Returns:
        partition function Q
        """
        try:
            #print(f"Temperature: {T}")
            pfdat = self.pfdat

            # Locate the row for the specific atom and ionization state
            pf_atom = pfdat.loc[f"{key}"]
            # Extract temperature and partition function values
            pfT_values = self.pfTdat.values.flatten()
            pf_values = pf_atom.values

            pfT_values = pfT_values.astype(float)
            pf_values = pf_values.astype(float)

            # print("pfT_values:", pfT_values)
            # print("pf_values:", pf_values)

            # Interpolate to find the partition function at the desired temperature
            Q = np.interp(T, pfT_values, pf_values)
            # print(f"Partition function: {Q}")

            return Q
        except KeyError:
            print("pfdat", pfdat)
            print(
                f"Key {key} not found in pfdat. Available keys: {pfdat.index.tolist()}"
            )
            raise

    def calculate_populations(self, atom, temperature, data):
        # Select the partition function for the specific atom
        # atom_pf = self.pfdat.loc[f'{atom}_I']

        # Calculate the partition function at a certain temperature
        #print(type(self.partfn))
        QT_atom = self.partfcn(atom, temperature)
        #print("QT_atom",QT_atom)

        # Calculate energy/temperature ratio
        energy_temp_ratio = data["El"] / (0.695 * temperature)
        # print(f'Energy/temp ratio: {energy_temp_ratio}')   # print the energy to temperature ratio for debugging

        # Calculate level populations using Boltzmann statistics
        self.populations = np.exp(-energy_temp_ratio) / QT_atom

        return self.populations