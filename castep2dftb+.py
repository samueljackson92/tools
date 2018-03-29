#!/usr/bin/env python
import glob
import os
import yaml
import numpy as np
import argparse as ap

from ase.calculators.dftb import Dftb
from ase import io

from _muairss.input import param_schema
from _muairss.__main__ import safe_create_folder
from _muairss.dftb_pars import DFTBArgs


# List of any parameters we need to copy to DFTB+ and
# what they are called in the general parameter format
CASTEP_to_DFTB_map = {
    'geom_force_tol': 'geom_force_tol',
    'geom_max_iter': 'geom_steps',
}


def convert_single_structure(cell_file, param_file, directory="."):
    atoms = io.read(cell_file)
    io.write(os.path.join(directory, "geo_end.gen"), atoms)

    with open(param_file, 'r') as stream:
        castep_params = yaml.load(stream)

    dftb_params = param_schema.validate({})

    # get castep parameters
    for castep_name, dftb_name in CASTEP_to_DFTB_map.items():
        if castep_name in castep_params:
            dftb_params[dftb_name] = castep_params[castep_name]

    # get k-points from cell file
    k_points = map(int, atoms.calc.cell.kpoints_mp_grid.value.split())

    dargs = DFTBArgs(dftb_params['dftb_set'])

    custom_species = atoms.get_array('castep_custom_species')
    muon_index = np.where(custom_species == dftb_params['mu_symbol'])[0][0]

    # Add muon mass
    args = dargs.args
    args['Driver_'] = 'ConjugateGradient'
    args['Driver_Masses_'] = ''
    args['Driver_Masses_Mass_'] = ''
    args['Driver_Masses_Mass_Atoms'] = '{}'.format(muon_index)
    args['Driver_Masses_Mass_MassPerAtom [amu]'] = '0.1138'
    args['Driver_MaxSteps'] = dftb_params['geom_steps']
    args['Driver_MaxForceComponent [eV/AA]'] = dftb_params['geom_force_tol']

    calc = Dftb(atoms=atoms, kpts=k_points,
                run_manyDftb_steps=True, **args)

    calc.write_dftb_in(os.path.join(directory, "dftb_in.hsd"))



def main():
    description = """Run convert CASTEP .cell files to DFTB+ geo_end.gen
    """
    parser = ap.ArgumentParser(description=description,
                               formatter_class=ap.ArgumentDefaultsHelpFormatter)
    parser.add_argument('input', type=str,
                        help='CASTEP .cell file to convert to DFTB+ .gen file')
    parser.add_argument('param_file', type=str,
                        help='CASTEP .param file to convert to DFTB+ .in file')
    parser.add_argument('--output', type=str, default=".",
                        help='Output folder to save to')
    args = parser.parse_args()
    param_file = args.param_file

    if os.path.isfile(args.input):
        cell_file = args.input
        convert_single_structure(cell_file, param_file, directory=args.output)
    elif os.path.isdir(args.input):
        directory = args.input
        cell_files = glob.glob(os.path.join(directory, "*.cell"))
        base_output = safe_create_folder(args.output)

        for cell_file in cell_files:
            output = os.path.join(base_output, os.path.basename(cell_file.replace(".cell", "")))
            os.mkdir(output)
            convert_single_structure(cell_file, param_file, directory=output)

if __name__ == "__main__":
    main()
