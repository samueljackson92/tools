#!/usr/bin/env python
import os
import sys
import json
import argparse as ap

from ase import io
from ase.calculators.dftb import Dftb
from ase.optimize.precon import Exp, PreconLBFGS
from common import JobBatch, run_dftb, get_all_folders_containing_pattern
from _muairss.dftb_pars import DFTBArgs
from _muairss.input import load_input_file


def make_dftb_calc(atoms, folder, params):
    """Make a DFTB+ calculator with the supplied parameters

    Args:
        atoms (ase.Atoms): an atoms object to create the DFTB+ calculator for
        folder (str): directory where the structure files are located.
        params (dict): dictionary of parameters to pass to the calculator

    Returns:
        dcalc (ase.calculators.dftb.Dftb): DFTB+ calculator setup with the
            provided parameters
    """
    name = os.path.split(folder)[-1]
    atoms.set_pbc(params['dftb_pbc'])

    dargs = DFTBArgs(params['dftb_set'])

    # Add muon mass
    args = dargs.args
    args['Driver_'] = 'ConjugateGradient'
    args['Driver_Masses_'] = ''
    args['Driver_Masses_Mass_'] = ''
    args['Driver_Masses_Mass_Atoms'] = '{}'.format(len(atoms.positions))
    args['Driver_Masses_Mass_MassPerAtom [amu]'] = '0.1138'

    if 'geom_force_tol' in params:
        args['Driver_MaxForceComponent [eV/AA]'] = params['geom_force_tol']

    # Max steps is zero because we don't want to optimize with DFTB+. Instead
    # we just evaluate using DFTB+ let the ASE LBFGS optimizer do the work.
    args['Driver_MaxSteps'] = '0'

    # The run_manyDftb_steps option is required here to prevent DFTB+
    # overwriting some of the options we set.
    if params['dftb_pbc']:
        dcalc = Dftb(label=name, atoms=atoms,
                     kpts=params['k_points_grid'],
                     run_manyDftb_steps=True, **args)
    else:
        dcalc = Dftb(label=name, atoms=atoms, run_manyDftb_steps=True, **args)

    dcalc.directory = folder
    return dcalc


def run_dftb_precon(folder, param_file):
    """ Run DFTB+ using a preconditioned optimizer

    Unlike a regular DFTB+ run a result.tag file is not produced because ASE
    deletes the file. Instead we dump the energy and forces to a json file so
    we cna load it back in later.

    Args:
        folder (str): directory containing a structure to optimize
        param_file (str): path to the parameter file for this structure.
    """

    if param_file is None:
        raise RuntimeError("A parameter file must be supplied to run \
                           batch_dftb+ in precon mode")

    hsd_file = os.path.join(folder, 'dftb_pin.hsd')
    file_name = 'dftb_pin.hsd' if os.path.isfile(hsd_file) else 'geo_end.gen'
    atoms = io.read(os.path.join(folder, file_name))
    params = load_input_file(param_file)
    calc = make_dftb_calc(atoms, folder, params)
    atoms.set_calculator(calc)

    try:
        opt = PreconLBFGS(atoms, precon=Exp(A=3), use_armijo=True,
                          logfile=None)
        opt.run(steps=int(params['geom_steps']))
    except:
        return

    results = {
        'energy': calc.get_potential_energy(),
        'forces': calc.get_forces().tolist()
    }

    json.dump(results, open(os.path.join(folder, "results.json"), 'w'))


def do_step(folder, param_file=None, precon=False):
    """Execute DFTB+ on a single job.

    Args:
        folder (str): name of the folder to run DFTB+ in
    """
    if not precon:
        run_dftb(folder)
    else:
        run_dftb_precon(folder, param_file)


def process_structures(all_folders, **kwargs):
    """Process a collection of configurations for a single structure

    DFTB+ is run asynchronosly on each candidate structure in the folder.

    Args:
        path (str): path to the folder of structures to process.
    """
    num_variations = len(all_folders)

    print("Processing {} structures".format(num_variations))
    with JobBatch(do_step, all_folders, **kwargs) as batch:
        for i, result in enumerate(batch):
            sys.stdout.write('\rdone {0} of {1}'.format(i+1, num_variations))
            sys.stdout.flush()


def main():
    description = """Run a batch of structures with DFTB+.

    This tool takes a folder full of structures
    and runs DFTB+ in each folder.
    """
    parser = ap.ArgumentParser(description=description,
                               formatter_class=ap.ArgumentDefaultsHelpFormatter)

    parser.add_argument('structures', type=str,
                        help="""Folder of structures to run dtfb+ on. Each
                        folder should contain a dftb_in.hsd file containing the
                        parameters to use and a geo_end.gen file containing a
                        description of the structure.""")

    parser.add_argument('-j', '--ncores', type=int, required=False,
                        default=None,
                        help="""Number of jobs to run in parallel""")

    parser.add_argument('--param-file', type=str, required=False, default=None,
                        help="""Parameter file for the runs. This should be the
                        same parameter file use to generate the structures.
                        This is only required when runinng in precon mode.""")

    parser.add_argument('--precon', required=False, default=False,
                        action='store_true',
                        help="""Run batch_dftb+ in precon mode. This will run
                        DFTB+ with a preconditioned LBFGS optimizer instead of
                        the default Conjugate Gradient. To use this mode the
                        user MUST supply a parameter file.""")

    args = parser.parse_args()

    if not os.path.isdir(os.path.join(args.structures)):
        raise RuntimeError("First argument must be a file or a folder")

    all_folders = get_all_folders_containing_pattern("dftb_in.hsd",
                                                     args.structures)
    params = vars(args)
    params.pop('structures')
    process_structures(all_folders, **params)

if __name__ == "__main__":
    main()
