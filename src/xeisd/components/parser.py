"""
Main logic for parsing experimental and back-calculated raw outputs.

Accepts primarily NMR-STAR formatted files for solution data.

USAGE EXAMPLE:
    For NMR-STAR files, it must be the data between the `loop_` and
    `stop_` codes without new lines. The easiest way is to just
    copy the block of data from NMR-STAR file from the BMRB
    to a new text file.
    
    For example an exerpt from entry 4155:
--BEGIN-FILE--
    _Atom_chem_shift.ID
    _Atom_chem_shift.Assembly_atom_ID
    _Atom_chem_shift.Entity_assembly_ID
    _Atom_chem_shift.Entity_assembly_asym_ID
    _Atom_chem_shift.Entity_ID
    _Atom_chem_shift.Comp_index_ID
    _Atom_chem_shift.Seq_ID
    _Atom_chem_shift.Comp_ID
    _Atom_chem_shift.Atom_ID
    _Atom_chem_shift.Atom_type
    _Atom_chem_shift.Atom_isotope_number
    _Atom_chem_shift.Val
    _Atom_chem_shift.Val_err
    1     .   2   .   1   2    2    MET   C    C   13   176.341   .
    2     .   2   .   1   2    2    MET   CA   C   13   55.634    .
    3     .   2   .   1   2    2    MET   CB   C   13   32.613    .
    4     .   2   .   1   3    3    GLU   H    H   1    8.781     .
    5     .   2   .   1   3    3    GLU   C    C   13   176.158   .
    6     .   2   .   1   3    3    GLU   CA   C   13   56.8      .
    7     .   2   .   1   3    3    GLU   CB   C   13   29.905    .
    8     .   2   .   1   3    3    GLU   N    N   15   122.712   .
    9     .   2   .   1   4    4    ALA   H    H   1    8.419     .
    10    .   2   .   1   4    4    ALA   C    C   13   177.602   .
    11    .   2   .   1   4    4    ALA   CA   C   13   52.395    .
--END-OF-FILE--
Currently accepting the following formats for experimental data:
    SAXS: SASBDB (curve .DAT), CUSTOM
    Chemical shift: NMR-STAR, CUSTOM
    FRET: CUSTOM
    J-Couplings: NMR-STAR (coupling constants), CUSTOM
    NOE: NMR-STAR (homonuclear/distances), CUSTOM
    PRE: NMR STAR (changes in R2 or as distance (use NOE)), CUSTOM
    RDC: NMR-STAR, CUSTOM
    Rh: CUSTOM (single values)

CUSTOM format:
    For cases where experimental data is not found on BMRB/SASDB, the
    formatting is delineated by comma (,) and the first line dictates
    what each column represents (i.e. pandas DataFrame format).
    
    Examples for each data-type has been provided in ``/exp_examples``.
    
    SAXS: index,value,error
    CS: index,resnum,atomname,value,error
    FRET: index,res1,res2,value,scale,error
    JC: index,resnum,value,error
    NOE: index,value,lower,upper,error*
    PRE: index,value,lower,upper,error*
    RDC: index,resnum,value,error
    Rh: index,value,error
    
    For NOE and PRE, error* can be provided instead of lower+upper.
    
    !!IMPORTANT!!
    Index is used for alignment purposes. For all modules EXCEPT SAXS,
    where the index is the "X-axis value" of the scattering plot.
    !!IMPORTANT!!
"""
import ast
import json

import pandas as pd

from xeisd.components import (
    cs_name,
    default_bc_errors,
    exp_atmID,
    exp_dist_val,
    exp_err,
    exp_idx,
    exp_max,
    exp_min,
    exp_val,
    fret_name,
    jc_bc_mu,
    jc_name,
    noe_name,
    parse_mode_exp,
    pre_name,
    rdc_name,
    rh_name,
    saxs_name,
    )


class Stack():
    """Custom stack object for conformers and values."""
    
    def __init__(self, name, data, sigma=None, mu=None):
        """
        Initialize stack of experimental or back-calculated data.

        Parameters
        ----------
        name : string
            Name of experimental datatype.
        
        pd.DataFrame
            Containing atoms, values, and errors for the 3 columns
        """
        self.name = name
        self.data = data
        self.sigma = sigma
        self.mu = mu


def parse_saxs_data(fpath):
    """Parse NMR STAR format for SAXS data."""
    index = []
    value = []
    error = []
    
    with open(fpath) as f:
        lines = f.readlines()
        first = lines[0].split(',')
        if first[0] == exp_idx:
            raise TypeError
        
        for line in lines:
            splitted = line.split()
            if type(splitted[0]) is float:
                index.append(splitted[0])
                value.append(splitted[1])
                error.append(splitted[2])
    
    return pd.DataFrame({exp_idx: index, exp_val: value, exp_err: error})


def parse_cs_data(fpath):
    """Parse NMR STAR format for CS data."""
    index = []
    atoms = []
    values = []
    errors = []
    
    with open(fpath) as f:
        lines = f.readlines()
        first = lines[0].split(',')
        if first[0] == exp_idx:
            raise TypeError
        
        for i, line in enumerate(lines):
            if "_" in line:
                dtype = line.split(".")[1].strip()
                if dtype == "Val": data_idx = i  # noqa: E701
                elif dtype == "Val_err": error_idx = i  # noqa: E701
                elif dtype == "Atom_ID": atom_idx = i  # noqa: E701
            else:
                start_idx = i
                break
        
        idx = 1
        for idx in range(start_idx, len(lines)):
            splitted = lines[idx].split()
            
            index.append(idx)
            atoms.append(splitted[atom_idx])
            values.append(float(splitted[data_idx]))
            errors.append(float(splitted[error_idx]))
            idx += 1
            
    return pd.DataFrame({exp_idx: index, exp_atmID: atoms, exp_val: values, exp_err: errors})  # noqa: E501


def parse_nmrstar_data(fpath, type=None):
    """Parse NMR STAR format for JC, RDC, NOE, PRE data."""
    index = []
    values = []
    upper = []
    lower = []
    errors = []
    
    with open(fpath) as f:
        lines = f.readlines()
        first = lines[0].split(',')
        if first[0] == exp_idx:
            raise TypeError
        
        for i, line in enumerate(lines):
            if "_" in line:
                dtype = line.split(".")[1].strip()
                if dtype == "Val": data_idx = i  # noqa: E701
                elif dtype == "Val_err": error_idx = i  # noqa: E701
                if type == noe_name or type == pre_name:  # noqa: E701
                    if dtype == "Val_max": max_idx = i  # noqa: E701
                    elif dtype == "Val_min": min_idx = i  # noqa: E701
            else:
                start_idx = i
                break
        
        idx = 1
        for idx in range(start_idx, len(lines)):
            splitted = lines[idx].split()
            
            index.append(idx)
            values.append(float(splitted[data_idx]))
            errors.append(float(splitted[error_idx]))
            idx += 1
            
            if type == noe_name or type == pre_name:
                max = splitted[max_idx]
                min = splitted[min_idx]
                if max == ".": max = 0.0  # noqa: E701
                if min == ".": min = 0.0  # noqa: E701
                upper.append(float(max))
                lower.append(float(min))
    
    if type == noe_name or type == pre_name:
        return pd.DataFrame({exp_idx: index, exp_dist_val: values, exp_max: upper, exp_min: lower, exp_err: errors})  # noqa: E501
    return pd.DataFrame({exp_idx: index, exp_val: values, exp_err: errors})


def parse_bc_errors(fpath):
    """
    Parse a text file containing customized errors for back-calculators.
    
    FORMATTING:
    In a .TXT file where the first column is the name of the module
    the second column will be the custom error.
    
    For example:
    pre 0.003
    noe 0.0023
    fret 0.004
    cs {'C':1.2,'CA':0.84,'CB':1.11,'H':0.56,'HA':0.10}
    """
    custom_bc_errors = default_bc_errors
    
    with open(fpath, mode='r') as f:
        lines = f.readlines()
        for line in lines:
            splitted = line.split()
            try:
                custom_bc_errors[splitted[0]] = float(splitted[1])
            except ValueError:
                dictconv = ast.literal_eval(splitted[1])
                custom_bc_errors[splitted[0]] = dictconv
    
    return custom_bc_errors
    

def parse_data(filenames, mode, bc_errors=default_bc_errors):
    """
    Parse all experimental and back-calculated files.

    Parameters
    ----------
    filenames : dict
        Dictionary of modules with their relative path
        to the data file. First key-layer has all of the
        different experimental modules eisd can handel.
    
    mode : str
        Parameter must be one of the following:
        - 'exp' = experimental data
        - 'bc' = back-calculated data
        
    Returns
    -------
    parsed : dict
        Dictionary of properties with their pandas dataframe.
    
    errlogs : list
        List of possible messages to display for the user.
    """
    parsed = {}
    errlogs = []
    data = pd.DataFrame(dtype=float)
    
    # Parse experimental data
    if mode == parse_mode_exp:
        for module in filenames:
            # Try to parse NMRStar first
            # otherwise parse CUSTOM formatting
            try:
                if module == saxs_name:
                    data = parse_saxs_data(filenames[module])
                elif module == cs_name:
                    data = parse_cs_data(filenames[module])
                elif module == fret_name:
                    parsed[module] = \
                        Stack(module, pd.read_csv(filenames[module], delimiter=','), None, None)  # noqa: E501
                    continue
                elif module == jc_name:
                    data = parse_nmrstar_data(filenames[module])
                elif module == noe_name:
                    data = parse_nmrstar_data(filenames[module], noe_name)
                elif module == pre_name:
                    data = parse_nmrstar_data(filenames[module], pre_name)
                elif module == rdc_name:
                    data = parse_nmrstar_data(filenames[module])
                elif module == rh_name:
                    parsed[module] = \
                        Stack(module, pd.read_csv(filenames[module], delimiter=','), None, None)  # noqa: E501
                    continue
            except TypeError:
                data = pd.read_csv(filenames[module], delimiter=',')
                     
            parsed[module] = Stack(module, data, None, None)
            
    # Parse back calculated data
    # Made for SPyCi-PDB output formatting in mind
    else:
        for module in filenames:
            try:
                with open(filenames[module], 'r') as f:
                    raw = json.load(f)
                if module == pre_name or module == noe_name:
                    del raw['format']
                if isinstance(list(raw.items())[0][1], float):
                    data = pd.DataFrame(raw, index=[0]).T
                else:
                    data = pd.DataFrame(raw).T
                # assign mu value for JC back-calculations
                if module == jc_name:
                    parsed[module] = \
                        Stack(module, data, bc_errors[module], jc_bc_mu)
                else:
                    parsed[module] = \
                        Stack(module, data, bc_errors[module], None)
            except Exception as e:
                errlogs.append(e)
            
    return parsed, errlogs
