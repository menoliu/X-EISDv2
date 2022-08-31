"""
Main interface for scoring module of X-EISD.

Please note that if you provide a path to PDB structures AND
back-calculated files, X-EISD will attempt to parse the back-calculated
files first and if they're not in the right format, we will back-calculate
the information for you using SPyCi-PDB.

For `--exp-files`, please name all your experimental files
ending with the extension(s) corresponding to the experiment
of interest and starting with `exp_`.
    
    For example:
    exp_*.saxs, exp_*.cs, exp_*.fret, exp_*.jc,
    exp_*.noe, exp_*.pre, exp_*.rdc, exp_*.rh
    
For back-calculated files (if they're already in the correct format),
please start them with the `back_` prefix, ending with the same file extensions as seen above.
    
    For example:
    back_*.saxs, back_*.cs, back_*.fret, etc.

USAGE:
    $ xeisd score [--exp-files] [--back-files] [--epochs]
    $ xeisd score [--exp-files] [--pdb-structures] [--epochs] [--output] [--ncores]

OUTPUT:

"""
import argparse
import os
import shutil
from functools import partial

from xeisd import Path, log
from xeisd.libs import libcli
from xeisd.logger import S, T, init_files, report_on_crash

from xeisd.components import (
    default_bc_errors,
    parse_mode_exp,
    parse_mode_back,
    meta_data,
    )
from xeisd.components.optimizer import XEISD
from xeisd.components.parser import parse_data

from idpconfgen.libs.libstructure import Structure
from idpconfgen.libs.libio import extract_from_tar, read_path_bundle
from idpconfgen.libs.libmulticore import pool_function

LOGFILESNAME = '.xeisd_score'
TMPDIR = '__tmpscore__'

_name = 'score'
_help = 'Score conformational ensembles against experimental data.'

_prog, _des, _usage = libcli.parse_doc_params(__doc__)

ap = libcli.CustomParser(
    prog=_prog,
    description=libcli.detailed.format(_des),
    usage=_usage,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    )

libcli.add_argument_exp_files(ap)
libcli.add_argument_pdb_files(ap)
libcli.add_argument_back_files(ap)
libcli.add_argument_epochs(ap)
libcli.add_argument_output(ap)
libcli.add_argument_ncores(ap)

ap.add_argument(
    '--tmpdir',
    help=(
    'Temporary directory to store data during calculation '
    'if needed.'
    ),
    type=Path,
    default=TMPDIR,
    )


def main(
        exp_files,
        epochs,
        pdb_files=None,
        back_files=None,
        output=None,
        ncores=1,
        tmpdir=TMPDIR,
        func=None,
    ):
    """
    Process and score ensembles.

    Parameters
    ----------
    pdb_files : str or Path, required
        Path to PDB files on the disk. Accepts TAR file.
    
    exp_files : str or Path, required
        Path to the folder containing experimental
        data files.
        
    back_files : str or Path, optional
        Path to the folder containing experimental
        data files.
    
    epochs : int, required
        Number of times to run main optimization.
    
    output : str or Path, optional
        Path to the folder to store eisd outputs.
        Defaults to working directory.
        
    ncores : int, optional
        Number of workers to use for multiprocessing.
        Defaults to 1.   
    """
    init_files(log, LOGFILESNAME)
    
    if pdb_files == None and back_files == None:
        log.info(S('WARNING: you must provide either PDB files or back-calculated files.'))
        return
    
    log.info(T('Reading conformer ensemble paths'))
    _istarfile = False
    if pdb_files:
        try:
            pdbs2operate = extract_from_tar(pdb_files, output=tmpdir, ext='.pdb')
            _istarfile = True
        except (OSError, FileNotFoundError, TypeError):
            pdbs2operate = list(read_path_bundle(pdb_files, ext='pdb'))
            _istarfile = False
        log.info(S('done'))
        
        ens_size = len(pdbs2operate)
        
        s = Structure(pdbs2operate[0])
        s.build()
        nres = len(s.residues)
    
    log.info(T('Checking experimental data files'))
    filenames, errs = meta_data(exp_files)
    if errs:
        for e in errs:
            log.info(S(e))
        if filenames == {}:
            log.info(S('done'))
            return
    log.info(S('done'))
    exp_paths = parse_data(filenames[parse_mode_exp], mode=parse_mode_exp)
    
    if back_files:
        back_paths = parse_data(filenames[parse_mode_back], parse_mode_back, default_bc_errors)
    #TODO: perform back-calculation via SPyCi-PDB
    
    eisd_ens = XEISD(exp_paths, back_paths, ens_size, nres)
    log.info(T(f'Starting X-EISD Scoring'))
    execute = partial (
        report_on_crash,
        eisd_ens.calc_scores,
        epochs=epochs,
        ens_size=ens_size,        
        )
    execute_pool = pool_function(execute, ncores=ncores)
    #TODO: print output to stdout or save to disk
    
    log.info(S('done'))
    
    if _istarfile:
        shutil.rmtree(tmpdir)
        
    log.info(S('done'))
    
    return


if __name__ == '__main__':
    libcli.maincli(ap, main)
