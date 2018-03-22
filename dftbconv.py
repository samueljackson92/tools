#!/usr/bin/env python
import os
import numpy as np
import argparse as ap
import glob

import yaml
from schema import Schema, Optional, SchemaError

from ase import io
from _muairss.__main__ import save_dftb_format, safe_create_folder
from _muairss.input import load_input_file

import matplotlib.pyplot as plt

from common import load_dtfb, run_dftb

# DFTB+ conv file schema and defaults
conv_schema = Schema({
    Optional('running_mode', default='parallel'): str,
    Optional('convergence_task', default='input'): str,
    Optional('kpoint_n_min', default=1): int,
    Optional('kpoint_n_max', default=4): int,
})


def norm_along_row(matrix):
    """Find the Euclidean norm for each row of an nxm matrix

    Args:
      matrix (np.ndarray): matrix with rows to take a norm of

    Returns:
      norms (np.ndarray): The Euclidean norm of each row.
    """
    return np.sum(np.abs(matrix)**2, axis=-1)**(1./2)


def load_conv_file(file_name):
    """Load a .conv file.

    This will check that the supplied parameters match the
    .conv file schema for DFTB+.

    Args:
       file_name (str): name of the .conv file to load

    Returns:
      params (dict): dict of convergence parameters to use.
    """
    params = yaml.load(open(file_name, 'r'))
    try:
        params = conv_schema.validate(params)
    except SchemaError as e:
        raise RuntimeError('Bad formatting in input file {0}\n {1}'
                           .format(file_name, e))
    return params


def write_convergence_tests(args, conv_params):
    """Write convergence tests for each parameter to check

    Args:
        args (dict): arguments passed from the command line.
        conv_params: convergence test parameters red from a .conv file.

    Returns:
        folder_names (list): list of folder paths that were created
            for each of the convergence tests.
    """

    # Get folder containing DFTB+ structure
    if os.path.isdir(args.seedname):
        path = os.path.join(args.seedname, "geo_end.gen")
        struct = io.read(path, format="gen")
    else:
        raise RuntimeError("Input seed must be a folder")

    params = load_input_file(args.parameter_file)
    kpt_range = range(conv_params['kpoint_n_min'],
                      conv_params['kpoint_n_max']+1)

    folder_names = []
    for num_kpts in kpt_range:
        params['k_points_grid'] = np.array([num_kpts]*3)

        ext = "_k{}".format(num_kpts)
        name = os.path.basename(args.seedname) + ext
        folder_name = safe_create_folder(name)

        save_dftb_format(struct, folder_name, params)
        folder_names.append(folder_name)

    return folder_names


def generate_results(folder_names):
    """Generate plots from the results of running convergence tests.

    For each structure this will generate two plots showing how the energy and
    forces vary as the number of k points is changed.

    Args:
        folder_names (str): a list of directory names containing the results
            of each of the convergence tests.
    """
    # Load the ase atoms objects for each result
    file_names = map(lambda x: os.path.join(x, "geo_end.xyz"), folder_names)
    cout_atoms = map(load_dtfb, file_names)
    cout_atoms = filter(lambda x: x.calc is not None, cout_atoms)

    if len(cout_atoms) == 0:
        print("No results to process!")
        return

    # Get energy and max force for each convergence test
    energies = map(lambda s: s.get_potential_energy(), cout_atoms)
    forces = map(lambda s: s.get_forces(), cout_atoms)

    norms = [norm_along_row(f) for f in forces]
    norms = [np.max(n) for n in norms]

    k_range = range(1, len(cout_atoms)+1)

    # Generate plot of the energy
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(k_range, np.array(energies))
    ax.set_xlabel("Num K Points")
    ax.set_ylabel("Energy")
    plt.savefig('energy.png', bbox_inches='tight')

    # Generate plot of the forces
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(k_range, np.array(norms))
    ax.set_xlabel("Num K Points")
    ax.set_ylabel("Force")
    plt.savefig('forces.png', bbox_inches='tight')


def main():
    description = """Run a series of convergence tests with DFTB+ to find the
    optimal hyper parameters to use.

    This tool is roughly the DFTB+ equivilent to castepconv.py and shares a
    similar format at mode of operation.

    Currently only the number of k-points used can be tested.
    """

    parser = ap.ArgumentParser(description)
    parser.add_argument('seedname', type=str, default=None, help="""A structure
                        file or a folder of files in an ASE readable format""")
    parser.add_argument('-p', '--parameter_file', type=str, default=None,
                        required=False, help="""YAML formatted file with
                        parameters.""")
    parser.add_argument('-c', '--conv_file', type=str, default=None,
                        required=False, help="""YAML formatted file with
                        parameters to vary.""")
    parser.add_argument('-m', '--mode', choices=['input', 'output', 'all'],
                        help="Only generate input folders")
    args = parser.parse_args()

    if args.parameter_file is None:
        args.parameter_file = args.seedname + ".yaml"

    if args.conv_file is None:
        args.conv_file = args.seedname + ".conv"

    conv_params = load_conv_file(args.conv_file)
    if args.mode == "input" or args.mode == "all":
        folder_names = write_convergence_tests(args, conv_params)

    if args.mode == "all":
        map(run_dftb, folder_names)

    if args.mode == "output" or args.mode == "all":
        pattern = os.path.basename(args.seedname) + "_k*"
        folder_names = glob.glob(pattern)
        generate_results(folder_names)


if __name__ == "__main__":
    main()
