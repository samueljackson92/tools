#!/usr/bin/env python
import os
import numpy as np
import argparse as ap

from ase import io
from _muairss.__main__ import generate_structure_defects, save_dftb_format, safe_create_folder
from _muairss.input import load_input_file


class FolderNameGenerator:

    def __init__(self, parent, name, size):
        self._parent = parent
        self._size = size
        self._name = name
        self._num_format = '{{0:0{0}n}}'.format(int(np.floor(np.log10(size))+1))
        self._index = 0

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        struct_folder = os.path.join(self._parent, self._name + '_' +
                                     self._num_format.format(self._index + 1))
        try:
            os.mkdir(struct_folder)
        except OSError:
            pass

        self._index += 1
        return struct_folder


def write_mutiple_parameter(args):
    struct = io.read(args.structure)
    params = load_input_file(args.parameter_file)

    defect_collection = generate_structure_defects(struct, params)

    for i in range(1, 5):
        params['k_points_grid'] = np.array([i, i, i])

        output_folder = os.path.dirname(params['out_folder'])
        folder_name = params['out_folder'] + '_kpts{}'.format(i)
        folder = os.path.join(output_folder, folder_name)
        safe_create_folder(folder)

        name_gen = FolderNameGenerator(folder, params['name'],
                                       len(defect_collection))

        for i, atoms in enumerate(defect_collection):
            struct_folder = next(name_gen)
            save_dftb_format(atoms, struct_folder, params)


if __name__ == "__main__":
    parser = ap.ArgumentParser()
    parser.add_argument('structure', type=str, default=None,
                        help="A structure file or a folder of files in an ASE "
                        "readable format")
    parser.add_argument('parameter_file', type=str, default=None, help="""YAML
                        formatted file with generation parameters. This is
                        ignored if a folder is passed as the first argument""")
    args = parser.parse_args()
    write_mutiple_parameter(args)

