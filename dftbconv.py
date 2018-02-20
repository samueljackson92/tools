#!/usr/bin/env python
import os
import numpy as np
import argparse as ap

import yaml
import subprocess
from schema import Schema, Optional, SchemaError

from ase import io
from _muairss.__main__ import save_dftb_format, safe_create_folder
from _muairss.input import load_input_file
from _muairss.dftb import load_dtfb

import matplotlib.pyplot as plt

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

    kpt_range = range(conv_params['kpoint_n_min'], conv_params['kpoint_n_max']+1)

    folder_names = []
    for num_kpts in kpt_range:
        params['k_points_grid'] = np.array([num_kpts]*3)

        name = os.path.basename(args.seedname) + "_k{}".format(num_kpts)
        folder_name = os.path.join(args.seedname, name)
        folder_name = safe_create_folder(folder_name)

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
    parser.add_argument('parameter_file', type=str, default=None, help="""YAML
                        formatted file with parameters.""")
    parser.add_argument('conv_file', type=str, default=None, help="""YAML
                        formatted file with parameters to vary.""")
    args = parser.parse_args()

    conv_params = load_conv_file(args.conv_file)
    folder_names = write_mutiple_parameter(args, conv_params)

    map(run_dftb, folder_names)
    generate_results(folder_names)

