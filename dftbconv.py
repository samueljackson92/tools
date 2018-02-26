#!/usr/bin/env python
import os
import numpy as np
import argparse as ap
import glob

import yaml
import subprocess
from schema import Schema, Optional, SchemaError

from ase import io
from ase.calculators.singlepoint import SinglePointCalculator
from _muairss.__main__ import save_dftb_format, safe_create_folder
from _muairss.input import load_input_file

import matplotlib.pyplot as plt

# Parameter file schema and defaults
conv_schema = Schema({
    Optional('kpoint_n_min', default=1): int,
    Optional('kpoint_n_max', default=4): int,
})


def tag_muon(atoms):
    """ Set the tag for a muon in an atoms object

    This currently assumes that the muon is the *last* atom
    in the Atoms object.

    | Args:
    |   atoms (ase.Atoms): an Atoms object to set the tag for
    |
    | Returns:
    |   tags (np.array): an updated array of tags where the muon
    |       is set to 1 and all other atoms are set to 0.
    """
    # this assumes that the LAST element in the file is the muon!
    tags = atoms.get_tags()
    tags[-1] = 1
    return tags


def load_cell(file_name):
    atoms_orig = io.read(file_name.replace("geo_end.xyz", "geo_end.gen"))
    return atoms_orig.cell


def load_dtfb(file_name):
    # Load the final positions from the .xyz file
    atoms = io.read(file_name)
    # Load the unit cell from the input .gen file
    atoms.cell = load_cell(file_name)
    atoms.set_tags(tag_muon(atoms))

    try:
        spcalc = DftbSinglePointCalculator(os.path.dirname(file_name), atoms)
        atoms.set_calculator(spcalc)
    except IOError:
        # if there was no calculator then set it to None
        atoms.set_calculator(None)

    return atoms


class DftbSinglePointCalculator(SinglePointCalculator):
    """Single point calculator for DFTB+

    This loads the results Dftb+. This differs from the standard Dftb
    calculator in that it will not remove the output file on load.
   """

    def __init__(self, directory, atoms):
        self.directory = directory
        self.atoms = atoms
        energy, forces, charges = self.read_results(directory)
        results = {}
        results['energy'] = energy
        results['charges'] = charges
        results['forces'] = forces
        SinglePointCalculator.__init__(self, atoms, **results)

    def read_results(self, directory):
        results_file = os.path.join(self.directory, 'results.tag')
        with open(results_file, 'r') as f_handle:
            lines = f_handle.readlines()

        charges = self.read_charges(directory)
        energy = self.read_energy(lines)
        forces = self.read_forces(lines)

        return energy, forces, charges

    def read_energy(self, lines):
        """Read Energy from dftb output file (results.tag)."""
        from ase.units import Hartree
        # Energy line index
        for iline, line in enumerate(lines):
            estring = 'total_energy'
            if line.find(estring) >= 0:
                index_energy = iline + 1
                break
        try:
            return float(lines[index_energy].split()[0]) * Hartree
        except:
            raise RuntimeError('Problem in reading energy')

    def read_forces(self, lines):
        """Read Forces from dftb output file (results.tag)."""
        from ase.units import Hartree, Bohr

        # Force line indexes
        for iline, line in enumerate(lines):
            fstring = 'forces   '
            if line.find(fstring) >= 0:
                index_force_begin = iline + 1
                line1 = line.replace(':', ',')
                index_force_end = iline + 1 + \
                    int(line1.split(',')[-1])
                break
        try:
            gradients = []
            for j in range(index_force_begin, index_force_end):
                word = lines[j].split()
                gradients.append([float(word[k]) for k in range(0, 3)])
            return np.array(gradients) * Hartree / Bohr
        except:
            raise RuntimeError('Problem in reading forces')

    def read_charges(self, directory):
        """ Get partial charges on atoms
            in case we cannot find charges they are set to None
        """
        detailed_file = os.path.join(self.directory, 'detailed.out')
        with open(detailed_file, 'r') as f_handle:
            lines = f_handle.readlines()

        qm_charges = []
        for n, line in enumerate(lines):
            if ('Atom' and 'Net charge' in line):
                chargestart = n + 1
                break
        else:
            # print('Warning: did not find DFTB-charges')
            # print('This is ok if flag SCC=NO')
            return None
        lines1 = lines[chargestart:(chargestart + len(self.atoms))]
        for line in lines1:
            qm_charges.append(float(line.split()[-1]))

        return np.array(qm_charges)


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

