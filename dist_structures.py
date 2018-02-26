#!/usr/bin/env python
import pickle
import os
import numpy as np
import argparse as ap
from ase import io
from _muairss.__main__ import safe_create_folder
from ase.calculators.singlepoint import SinglePointCalculator

from utils import tag_muon, load_dtfb


def load_castep(fname):
    atoms = io.read(fname)
    # Create a calculator to store the energy
    atoms_cast = io.read(fname.replace('-out.cell', '.castep'))
    spcalc = SinglePointCalculator(atoms,
                                   energy=atoms_cast.get_potential_energy(),
                                   forces=atoms_cast.get_forces())
    atoms.set_calculator(spcalc)
    atoms.set_tags(tag_muon(atoms))
    return atoms


def load_structures(all_files, ext, func):
    files = filter(lambda x: x.endswith(ext), all_files)
    return map(func, files)


def pickle_structures(atoms, out_folder):
    if len(atoms) == 0:
        return

    os.mkdir(out_folder)

    num_format = get_padded_number_format(len(atoms))
    for i, atoms in enumerate(atoms):
        ext = num_format.format(i+1)
        out_file = os.path.join(out_folder, "structure_{}.pkl".format(ext))
        with open(out_file, 'wb') as handle:
            pickle.dump(atoms, handle)


def get_padded_number_format(size):
    return '{{0:0{0}n}}'.format(int(np.floor(np.log10(size))+1))


def main():
    parser = ap.ArgumentParser()
    parser.add_argument('input', type=str, default=None,
                        help="Input folder to prepare for ditribution")
    parser.add_argument('output', type=str, default=None,
                        help="Output folder to store data in")
    args = parser.parse_args()

    args.output = safe_create_folder(args.output)

    path = args.input
    all_files = [os.path.join(p, f)
                 for p, folders, files in os.walk(path) for f in files]

    path = os.path.join(args.output, "castep")
    atoms = load_structures(all_files, "-out.cell", load_castep)
    pickle_structures(atoms, path)

    path = os.path.join(args.output, "dftb+")
    atoms = load_structures(all_files, ".xyz", load_dtfb)
    pickle_structures(atoms, path)


if __name__ == "__main__":
    main()
