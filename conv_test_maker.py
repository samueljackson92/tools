#!/usr/bin/env python
import os
import shutil
import argparse as ap
import yaml
import glob
import re
import subprocess

from ase import io
from _muairss.__main__ import generate_structure_defects, save_dftb_format, save_castep_format, safe_create_folder
from _muairss.input import load_input_file


def generate_single_structure(struct, params, batch_path=''):
    """Generate input files for a single structure and configuration file"""

    atoms = generate_structure_defects(struct, params).structures[0]

    # (Re)Create the output folder
    output_folder = os.path.join(batch_path, params['out_folder'])
    output_folder = safe_create_folder(output_folder)

    # Now save in the appropriate format
    save_funcs = {
        'castep': save_castep_format,
        'dftb+': save_dftb_format
    }

    # Which calculators?
    calcs = map(lambda s: s.strip(), params['calculator'].split(','))
    if 'all' in calcs:
        calcs = save_funcs.keys()

    for cname in calcs:
        try:
            os.mkdir(os.path.join(output_folder, cname))
        except OSError:
            continue

        fold = os.path.join(output_folder,
                            cname,
                            params['name'])
        os.mkdir(fold)
        save_funcs[cname](atoms, fold, params)


def run_dftbconv(path, name, parameter_file, conv_file, mode):
    print ("Running dftbconv.py in {}".format(path))
    command = "dftbconv.py --mode {} {} -p {} -c {}".format(mode, name, parameter_file, conv_file)
    process = subprocess.Popen(command, cwd=path, shell=True)
    process.wait()


def run_castepconv(path, name):
    print ("Running castepconv.py in {}".format(path))
    command = "castepconv.py {}".format(name)
    process = subprocess.Popen(command, cwd=path, shell=True)
    process.wait()


def main():
    parser = ap.ArgumentParser()
    parser.add_argument('structure', type=str, default=None,
                        help="A structure file an ASE readable format")
    parser.add_argument('parameter_file', type=str, default=None, help="""YAML
                        formatted file with generation parameters. """)
    parser.add_argument('conv_file', type=str, default=None, help="""YAML
                        formatted file with convergence parameters.""")
    args = parser.parse_args()

    struct = io.read(args.structure)
    params = load_input_file(args.parameter_file)

    conv_params = yaml.load(open(args.conv_file, 'r'))
    generate_single_structure(struct, params)

    # Create input for dftbconv.py
    path = os.path.join(os.path.curdir, params['out_folder'], "dftb+")
    shutil.copyfile(args.parameter_file, os.path.join(path, args.parameter_file))
    shutil.copyfile(args.conv_file, os.path.join(path, args.conv_file))
    run_dftbconv(path, params['name'], args.parameter_file, args.conv_file, "input")
    shutil.rmtree(os.path.join(path, params['name']))

    # Create input for castepconv.py
    path = os.path.join(os.path.curdir, params['out_folder'], "castep")

    conv_params['running_mode'] = 'PARALLEL'
    conv_params['convergence_task'] = 'INPUT'
    shutil.copyfile(args.parameter_file, os.path.join(path, args.parameter_file))

    sub_path = os.path.join(path, params['name'])
    yaml.dump(conv_params, open(os.path.join(sub_path, args.conv_file), 'w'), default_flow_style=False)
    run_castepconv(sub_path, params['name'])

    for filename in os.listdir(sub_path):
        shutil.move(os.path.join(sub_path, filename), os.path.join(path, filename))
    shutil.rmtree(sub_path)

    cell_files = []
    for root, dirs, files in os.walk(path):
        for f in files:
            if f.endswith(".cell"):
                cell_files.append(os.path.join(root, f))

    for cell_file in cell_files:
        with open(cell_file, "r") as f_handle:
            lines = f_handle.readlines()
        with open(cell_file, "w") as f_handle:
            for line in lines:
                f_handle.write(re.sub(r'H mu', 'H:mu', line))

if __name__ == "__main__":
    main()
