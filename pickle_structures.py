#!/usr/bin/env python
import pickle
import os
import argparse as ap
from _muairss.__main__ import safe_create_folder

from common import NameGenerator, load_dtfb, load_castep, load_dftb_precon


def load_structures(all_files, ext, func):
    """Load all files matching a given file extension

    Args:
      all_files (list): list of file paths.
      ext (str): file extension to match against

    Returns:
      atoms ([ase.Atoms]): a list of loaded ase atoms objects.
    """
    files = filter(lambda x: x.endswith(ext), all_files)
    return map(func, files)


def pickle_structure(file_name, atoms):
    """Pickle a single ase Atoms object

    Args:
        file_name (str): the name of the file to pickle the atoms object to.
        atoms (ase.Atoms): the atoms object (with calculator) to pickle.
    """
    with open(file_name, 'wb') as handle:
        pickle.dump(atoms, handle)


def pickle_structures(atoms, out_folder):
    """Pickle a list of atoms objects.

    Args:
      atoms (list): list atoms objects pickle.
      out_folder (str): name of the folder to pickle structures to
    """
    if len(atoms) == 0:
        return

    os.mkdir(out_folder)

    pattern = os.path.join(out_folder, "structures{}.pkl")
    file_names = NameGenerator(pattern, len(atoms))
    for file_name, a in zip(file_names, atoms):
        pickle_structure(file_name, a)


def main():
    description = """Convert a folder containing the raw output files of CASTEP
    and/or DFTB+ results to a folder of pickled ase.Atoms objects.

    The output folder will mimic the folder structure of the input folder, but
    will contain only *.pkl files. Each pickle file is a ASE atoms object with
    a single point calculator attached to it.
    """

    parser = ap.ArgumentParser(description=description)
    parser.add_argument('input', type=str, default=None,
                        help="""Folder containing castep and DFTB+ result
                        files. For CASTEP the program will search for
                        *-out.cell files to load. For DFTB+ it will search for
                        either result.tag files or for *.json files. The former
                        is that standard outpt of DFTB+. The latter is output
                        from batch_dftb+ when run with the --precon option.""")
    parser.add_argument('output', type=str, default=None,
                        help="Output folder to store pickled structures in")
    args = parser.parse_args()

    args.output = safe_create_folder(args.output)

    # Find all files in the input directory
    path = args.input
    all_files = [os.path.join(dir_name, file_name)
                 for dir_name, folders, files in os.walk(path)
                 for file_name in files]

    # Look for CASTEP folder and pickle the structures
    atoms = load_structures(all_files, "-out.cell", load_castep)
    path = os.path.join(args.output, "castep")
    pickle_structures(atoms, path)

    # Look for DFTB+ folder and pickle the structures from preconditioned runs
    atoms = load_structures(all_files, ".json", load_dftb_precon)
    path = os.path.join(args.output, "dftb+")
    pickle_structures(atoms, path)

    # Look for DFTB+ folder and pickle the structures
    path = os.path.join(args.output, "dftb+")
    atoms = load_structures(all_files, ".tag", load_dtfb)
    pickle_structures(atoms, path)


if __name__ == "__main__":
    main()
