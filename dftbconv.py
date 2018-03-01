#!/usr/bin/env python
import os
import numpy as np
import argparse as ap
import glob

import yaml
import subprocess
from schema import Schema, Optional, SchemaError

from ase import io
from _muairss.__main__ import save_dftb_format, safe_create_folder
from _muairss.input import load_input_file

import matplotlib.pyplot as plt

from tool_utils import load_dtfb

# Parameter file schema and defaults
conv_schema = Schema({
    Optional('kpoint_n_min', default=1): int,
    Optional('kpoint_n_max', default=4): int,
})


def makefig():
    fig = plt.figure()
    return fig, fig.add_subplot(111)


def norm_along_row(x):
    return np.sum(np.abs(x)**2, axis=-1)**(1./2)


def load_conv_file(fname):
    params = yaml.load(open(fname, 'r'))
    try:
        params = conv_schema.validate(params)
    except SchemaError as e:
        raise RuntimeError('Bad formatting in input file {0}\n {1}'
                           .format(fname, e))
    return params


def write_mutiple_parameter(args, conv_params):
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


def run_dftb(path):
    print ("Running dftb+ in {}".format(path))
    # redirect output frm dtfb+
    FNULL = open(os.devnull, 'w')
    process = subprocess.Popen('dftb+', cwd=path, stdout=FNULL,
                               stderr=subprocess.STDOUT)
    process.wait()


def generate_results(folder_names):
    file_names = map(lambda x: os.path.join(x, "geo_end.xyz"), folder_names)
    cout_atoms = map(load_dtfb, file_names)
    cout_atoms = filter(lambda x: x.calc is not None, cout_atoms)

    if len(cout_atoms) == 0:
        print("No results to process!")
        return

    energies = map(lambda s: s.get_potential_energy(), cout_atoms)
    forces = map(lambda s: s.get_forces(), cout_atoms)

    norms = [norm_along_row(f) for f in forces]
    norms = [np.max(n) for n in norms]

    k_range = range(1, len(cout_atoms)+1)
    fig, ax = makefig()
    ax.plot(k_range, -np.array(energies))
    ax.set_xlabel("Num K Points")
    ax.set_ylabel("Energy")
    plt.savefig('energy.png', bbox_inches='tight')

    fig, ax = makefig()
    ax.plot(k_range, -np.array(norms))
    ax.set_xlabel("Num K Points")
    ax.set_ylabel("Force")
    plt.savefig('forces.png', bbox_inches='tight')


if __name__ == "__main__":
    parser = ap.ArgumentParser()
    parser.add_argument('seedname', type=str, default=None,
                        help="A structure file or a folder of files in an ASE "
                        "readable format")
    parser.add_argument('-p', '--parameter_file', type=str, default=None, required=False, help="""YAML
                        formatted file with parameters.""")
    parser.add_argument('-c', '--conv_file', type=str, default=None, required=False, help="""YAML
                        formatted file with parameters to vary.""")
    parser.add_argument('-m', '--mode', choices=['input', 'output', 'all'],
                        help="Only generate input folders")
    args = parser.parse_args()

    if args.parameter_file is None:
        args.parameter_file = args.seedname + ".yaml"

    if args.conv_file is None:
        args.conv_file = args.seedname + ".conv"

    conv_params = load_conv_file(args.conv_file)
    if args.mode == "input" or args.mode == "all":
        folder_names = write_mutiple_parameter(args, conv_params)

    if args.mode == "all":
        map(run_dftb, folder_names)

    if args.mode == "output" or args.mode == "all":
        pattern = os.path.basename(args.seedname) + "_k*"
        folder_names = glob.glob(pattern)
        generate_results(folder_names)

