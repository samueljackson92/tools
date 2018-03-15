#!/usr/bin/env python
import pickle
import os
import glob
import shutil
import numpy as np
import argparse as ap
from ase import io
from _muairss.__main__ import safe_create_folder
from ase.calculators.dftb import Dftb
from ase.calculators.singlepoint import SinglePointCalculator


class NameGenerator:
    """Generator to create names matching a pattern with
    zero padded numbers appended.
    """

    def __init__(self, pattern, size):
        self._pattern = pattern
        self._num_format = self._get_padded_number_format(size)
        self._count = 0

    def _get_padded_number_format(self, size):
        return '{{0:0{0}n}}'.format(int(np.floor(np.log10(size))+1))

    def __iter__(self):
        return self

    def __next__(self):
        self._count += 1
        ext = self._num_format.format(self._count)
        return self._pattern.format(ext)

    def next(self):
        return self.__next__()


class BackupFile():
    """Backup a file before performing an operation

    A class to make a copy of a file before performing some
    potentially unsafe operation on it. In either succes or failure
    the copy of the original file it restored.
    """
    def __init__(self, file_name, backup_file):
        self._file_name = file_name
        self._backup_file = backup_file

    def __enter__(self):
        shutil.copyfile(self._file_name, self._backup_file)
        return self

    def __exit__(self, type, value, traceback):
        shutil.move(self._backup_file, self._file_name)


def get_all_folders(path):
    all_files = glob.glob(os.path.join(path, "*"))
    return filter(lambda p: os.path.isdir(p), all_files)


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


def load_dftb_calculator(directory, atoms):
    results_file = os.path.join(directory, "results.tag")
    temp_file = os.path.join(directory, "results.tag.bak")

    # We need to backup the results file here because
    # .read_results() will remove the results file
    with BackupFile(results_file, temp_file):
        calc = Dftb(atoms=atoms)
        calc.atoms_input = atoms
        calc.directory = directory
        calc.read_results()

    return SinglePointCalculator(atoms, energy=calc.get_potential_energy(),
                                 forces=calc.get_forces())


def load_dtfb(file_name):
    # Load the final positions from the .xyz file
    atoms = io.read(file_name)
    # Load the unit cell from the input .gen file
    atoms.cell = load_cell(file_name)
    atoms.set_tags(tag_muon(atoms))

    directory = os.path.dirname(file_name)

    try:
        spcalc = load_dftb_calculator(directory, atoms)
        atoms.set_calculator(spcalc)
    except IOError:
        # if there was no calculator then set it to None
        atoms.set_calculator(None)

    return atoms


def load_castep(fname):
    atoms = io.read(fname)
    # Create a calculator to store the energy
    try:
        atoms_cast = io.read(fname.replace('-out.cell', '.castep'))
        spcalc = SinglePointCalculator(atoms,
                                       energy=atoms_cast.get_potential_energy(),
                                       forces=atoms_cast.get_forces())
        atoms.set_calculator(spcalc)
    except:
        print("Failed to load -out.cell file")
    atoms.set_tags(tag_muon(atoms))
    return atoms


def load_structures(all_files, ext, func):
    files = filter(lambda x: x.endswith(ext), all_files)
    return map(func, files)


def pickle_structures(atoms, out_folder):
    if len(atoms) == 0:
        return

    os.mkdir(out_folder)

    file_names = NameGenerator("structure_{}.pkl", len(atoms))

    for file_name, atoms in zip(file_names, atoms):
        out_file = os.path.join(out_folder, file_name)
        with open(out_file, 'wb') as handle:
            pickle.dump(atoms, handle)


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
