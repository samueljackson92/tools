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


def pickle_structures(atoms, out_folder):
    """Pickle a list of atoms objects.

    Args:
      atoms (list): list atoms objects pickle.
    """
    if len(atoms) == 0:
        return

    os.mkdir(out_folder)

    file_names = NameGenerator("structure_{}.pkl", len(atoms))

    for file_name, atoms in zip(file_names, atoms):
        out_file = os.path.join(out_folder, file_name)
        with open(out_file, 'wb') as handle:
            pickle.dump(atoms, handle)


def main():
    description = """Convert a folder containing the output of CASTEP and/or
    DFTB+ results to a folder of pickled ase.Atoms objects"""

    parser = ap.ArgumentParser(description=description)
    parser.add_argument('input', type=str, default=None,
                        help="""Input folder containing castep and
                        DFTB+ results""")
    parser.add_argument('output', type=str, default=None,
                        help="Output folder to store pickled structures in")
    args = parser.parse_args()

    args.output = safe_create_folder(args.output)

    # Find all files in the input directory
    path = args.input
    all_files = [os.path.join(p, f)
                 for p, folders, files in os.walk(path) for f in files]

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
