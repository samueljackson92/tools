#!/usr/bin/env python
import os
import sys
import glob
import subprocess
import argparse as ap


def get_all_folders(path):
    all_files = glob.glob(os.path.join(path, "*"))
    return filter(lambda p: os.path.isdir(p), all_files)


def submit_structure(folder, ncores=32, walltime='12:00', dryrun=False):
    name = os.path.basename(folder)
    cell_file = os.path.join(folder, "{0}.cell".format(name))

    # if no cell file then skip this folder
    if not os.path.isfile(cell_file):
        return

    dry_run_flag = '-d' if dryrun else ''
    command = ['castepsub', dry_run_flag, '-n', str(ncores), '-W', str(walltime), name]
    command = ' '.join(command)
    print(command)
    process = subprocess.Popen(command, cwd=folder, shell=True)
    process.wait()


def submit_structure_group(folder, lower, upper, **kwargs):
    all_folders = get_all_folders(folder)
    all_folders = sorted(all_folders)

    for folder in all_folders[lower:upper]:
        submit_structure(folder, **kwargs)


def main():
    parser = ap.ArgumentParser(description='Run a batch of structures with CASTEP',
                               formatter_class=ap.ArgumentDefaultsHelpFormatter)
    parser.add_argument('folder', type=str,
                        help='File or folder of structures to run CASTEP on')
    parser.add_argument('lower', type=int,
                        help='Lower bound of structures to run')
    parser.add_argument('upper', type=int,
                        help='Upper bound of structures to run')
    parser.add_argument('-d', '--dryrun', required=False, action='store_true',
                        help='Pass dryrun option to castep')
    parser.add_argument('-n', '--ncores', required=False, type=int, default=36,
                        help='Number of cores to use')
    parser.add_argument('-W', '--walltime', required=False, type=str, default='12:00',
                        help='Walltime for the jobs')
    args = parser.parse_args()

    
    if os.path.isdir(args.folder):
        submit_structure_group(**vars(args))
    else:
        raise RuntimeError("First argument must be a file or a folder")


if __name__ == "__main__":
    main()
