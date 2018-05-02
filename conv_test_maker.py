#!/usr/bin/env python
import os
import shutil
import argparse as ap
import yaml
import re
import glob
import subprocess
import castep_keywords

from ase import io
from _muairss.__main__ import (generate_structure_defects, save_dftb_format,
                               save_castep_format, safe_create_folder)
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
    print command
    process = subprocess.Popen(command, cwd=path, shell=True)
    process.wait()


def create_dftb_test(params, parameter_file, conv_file):
    path = os.path.join(os.path.curdir, params['out_folder'], "dftb+")
    new_param_file = os.path.abspath(os.path.join(path, params['name']+".yaml"))
    new_conv_file = os.path.abspath(os.path.join(path, params['name']+".conv"))

    shutil.copyfile(parameter_file, new_param_file)
    shutil.copyfile(conv_file, new_conv_file)
    run_dftbconv(path, params['name'], new_param_file, new_conv_file, "input")
    shutil.rmtree(os.path.join(path, params['name']))


def create_castep_test(params, conv_params, parameter_file, conv_file):
    path = os.path.join(os.path.curdir, params['out_folder'], "castep")
    name = params['name']
    new_param_file = os.path.abspath(os.path.join(path, name, name+".yaml"))
    new_conv_file = os.path.abspath(os.path.join(path, name, name+".conv"))
    new_castep_file = os.path.abspath(os.path.join(path, name, name+".param"))

    shutil.copyfile(parameter_file, new_param_file)
    shutil.copyfile(params['castep_param'], new_castep_file)
    # Overwrite these to parameters if present in the file.
    # We need parallel mode so that one run does not depend on the other
    # and we need input mode so that we just generate input files
    conv_params['running_mode'] = 'PARALLEL'
    conv_params['convergence_task'] = 'INPUT'
    with open(new_conv_file, 'w') as f_handle:
        yaml.dump(conv_params, f_handle, default_flow_style=False)

    sub_path = os.path.join(path, name)
    run_castepconv(sub_path, params['name'])

    for filename in os.listdir(sub_path):
        shutil.move(os.path.join(sub_path, filename),
                    os.path.join(path, filename))

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

    cell_file = os.path.join(path, name+".cell")
    shutil.move(cell_file, cell_file + ".orig")


def create_convergence_test(struct, params, conv_params, parameter_file, conv_file):
    generate_single_structure(struct, params)

    if params['calculator'] == 'dftb+' or params['calculator'] == 'all':
        create_dftb_test(params, parameter_file, conv_file)
    if params['calculator'] == 'castep' or params['calculator'] == 'all':
        create_castep_test(params, conv_params, parameter_file, conv_file)


def create_batch_tests(args):
    pattern = os.path.join(os.path.abspath(args.structure), "*.cif")
    structure_files = glob.glob(pattern)

    params = load_input_file(args.parameter_file)
    conv_params = yaml.load(open(args.conv_file, 'r'))

    if 'castep_param' in params:
        params['castep_param'] = os.path.abspath(params['castep_param'])

    batch_path = safe_create_folder(params['batch_name'])
    os.chdir(batch_path)

    for file_name in structure_files:
        struct = io.read(file_name)
        params['out_folder'] = os.path.basename(file_name)[:-4]
        params['name'] = os.path.basename(file_name)[:-4]
        create_convergence_test(struct, params, conv_params,
                                args.parameter_file, args.conv_file)


def main():
    description ="""Make a convergence test case for a particular structure

    This tool takes an input structure file (e.g. a CIF) and a YAML parameter
    file. It also takes a convegence file which should be in the same format as
    expected by the castepconv.py tool supplied with CASTEP. The tool generates
    a series of convergence tests for the criteria in the .conv file. Note: for
    DFTB+ only testing convergence over the number of k-points is currently
    supported by the dftbconv tool.
    """
    parser = ap.ArgumentParser(description=description)
    parser.add_argument('structure', type=str,
                        help="""A structure file an ASE readable format. e.g. a
                        CIF""")
    parser.add_argument('-p', '--parameter-file', type=str, default=None,
                        help="""YAML formatted file parameter file. This is
                        used to generate a candidate structure for the
                        convergence test.  """)
    parser.add_argument('-c', '--conv-file', type=str, default=None,
                        help="""YAML formatted file with convergence
                        parameters. This should be the same format as expected
                        by the castepconv.py tool.""")
    args = parser.parse_args()

    name = os.path.splitext(os.path.basename(args.structure))[0]
    if args.parameter_file is None:
        args.parameter_file = os.path.basename(name) + ".yaml"
    if args.conv_file is None:
        args.conv_file = os.path.basename(name) + ".conv"

    args.parameter_file = os.path.abspath(args.parameter_file)
    args.conv_file = os.path.abspath(args.conv_file)

    if os.path.isfile(args.structure):
        struct = io.read(args.structure)
        params = load_input_file(args.parameter_file)
        conv_params = yaml.load(open(args.conv_file, 'r'))
        create_convergence_test(struct, params, conv_params,
                                args.parameter_file, args.conv_file)
    elif os.path.isdir(args.structure):
        create_batch_tests(args)
    else:
        raise RuntimeError("{} is not a file or folder".format(args.structure))

if __name__ == "__main__":
    main()
