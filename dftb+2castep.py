#!/usr/bin/env python
import glob
import os
import numpy as np
import argparse as ap

from ase.io.castep import read_param, write_param
from ase.calculators.castep import Castep
from ase import io

from _muairss.__main__ import safe_create_folder
from _muairss.input import load_input_file
from _muairss.utils import list_to_string

from common import get_all_folders_containing_pattern

# List of any parameters we need to copy to DFTB+ and
# what they are called in the general parameter format
CASTEP_to_DFTB_map = {
    'geom_force_tol': 'geom_force_tol',
    'geom_max_iter': 'geom_steps',
}


def convert_single_structure(gen_file, param_file, directory="."):
    atoms = io.read(gen_file)
    params = load_input_file(param_file)

    # Muon mass and gyromagnetic ratio
    mass_block = 'AMU\n{0}       0.1138'
    gamma_block = 'radsectesla\n{0}        851586494.1'

    ccalc = Castep(castep_command=params['castep_command'])
    ccalc.cell.kpoint_mp_grid.value = list_to_string(params['k_points_grid'])
    ccalc.cell.species_mass = mass_block.format(params['mu_symbol']
                                                ).split('\n')
    ccalc.cell.species_gamma = gamma_block.format(params['mu_symbol']
                                                  ).split('\n')
    ccalc.cell.fix_all_cell = True  # To make sure for older CASTEP versions

    atoms.set_calculator(ccalc)

    symbols = atoms.get_chemical_symbols()
    symbols[-1] = params['mu_symbol']
    atoms.set_array('castep_custom_species', np.array(symbols))

    name = "{}.cell".format(params['name'])
    cell_file = os.path.join(directory, name)
    io.write(cell_file, atoms)

    # Param file?
    if params['castep_param'] is not None:
        p = read_param(params['castep_param']).param
        # Set up task and geometry optimization steps
        p.task.value = 'GeometryOptimization'
        p.geom_max_iter.value = params['geom_steps']
        p.geom_force_tol.value = params['geom_force_tol']

        param_file = os.path.join(directory, "{}.param".format(params['name']))
        write_param(param_file, p, force_write=True)


def main():
    description = """Run convert DFTB+ files to CASTEP input files"""
    parser = ap.ArgumentParser(description=description,
                               formatter_class=ap.ArgumentDefaultsHelpFormatter)
    parser.add_argument('input', type=str,
                        help='DFTB+ .gen file to convert to CASTEP .cell file')
    parser.add_argument('param_file', type=str,
                        help='YAML file with parameters to convert to CASTEP params')
    parser.add_argument('--output', type=str, default=".",
                        help='Output directory to place generated files')
    args = parser.parse_args()
    param_file = args.param_file

    if os.path.isfile(args.input):
        gen_file = args.input
        convert_single_structure(gen_file, param_file, args.output)
    elif os.path.isdir(args.input):
        directory = args.input
        gen_files = get_all_folders_containing_pattern("*.gen", directory)
        base_output = safe_create_folder(args.output)

        for gen_file in gen_files:
            output = os.path.join(base_output, os.path.basename(gen_file))
            os.mkdir(output)
            gen_file = os.path.join(gen_file, "geo_end.gen")
            convert_single_structure(gen_file, param_file, directory=output)

if __name__ == "__main__":
    main()
