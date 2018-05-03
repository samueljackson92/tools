#!/usr/bin/env python
import pickle
import os
import argparse as ap

from itertools import imap
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


def pickle_structures(func, files, output):
    """Pickle a list of atoms objects.

    Args:
      atoms (list): list atoms objects pickle.
      out_folder (str): name of the folder to pickle structures to
    """
    atoms = map(func, files)

    if len(atoms) == 0:
        return

    out_folders = map(os.path.dirname, files)
    out_folders = map(lambda folder: os.path.join(output, folder), out_folders)
    for folder in out_folders:
        os.makedirs(folder)

    pattern = "structures{}.pkl"
    file_names = NameGenerator(pattern, len(atoms))
    file_names = imap(os.path.join, out_folders, file_names)
    for item in zip(file_names, atoms):
        pickle_structure(*item)


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
    all_files = [os.path.join(dir_name, file_name)
                 for dir_name, folders, files in os.walk(args.input)
                 for file_name in files]

    cell_files = filter(lambda x: x.endswith("-out.cell"), all_files)
    json_files = filter(lambda x: x.endswith(".json"), all_files)
    tag_files = filter(lambda x: x.endswith(".tag"), all_files)

    pickle_structures(load_castep, cell_files, args.output)
    pickle_structures(load_dftb_precon, json_files, args.output)
    pickle_structures(load_dtfb, tag_files, args.output)


if __name__ == "__main__":
    main()
