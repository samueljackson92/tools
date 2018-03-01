#!/usr/bin/env python
import os
import sys
import subprocess
import argparse as ap
import functools
from multiprocessing import Pool

from tool_utils import get_all_folders


def run_dftb(path):
    # redirect output frm dtfb+
    FNULL = open(os.devnull, 'w')
    process = subprocess.Popen('dftb+', cwd=path, stdout=FNULL,
                               stderr=subprocess.STDOUT)
    process.wait()


def do_step(folder, resume=False):
    if resume and os.path.isfile(os.path.join(folder, 'detailed.out')):
        return
    run_dftb(folder)


def process_single_structure(path, resume=False):
    dftb_files_path = os.path.join(path, "dftb+")
    all_folders = get_all_folders(dftb_files_path)
    num_variations = len(all_folders)

    print("Processing structure {}..."
          .format(path))

    pool = Pool()
    func = functools.partial(do_step, **{'resume': resume})
    for i, _ in enumerate(pool.imap_unordered(func, all_folders), 1):
        sys.stdout.write('\rdone {0} of {1}'.format(i, num_variations))
        sys.stdout.flush()

def process_batch(path, **kwargs):
    all_folders = get_all_folders(path)
    for folder in all_folders:
        process_single_structure(folder, **kwargs)


def main():
    parser = ap.ArgumentParser(description='Run a batch of structures with DFTB+',
                               formatter_class=ap.ArgumentDefaultsHelpFormatter)
    parser.add_argument('structures', type=str,
                        help='File or folder of structures to run dtfb+ on')
    parser.add_argument('--resume', required=False, action='store_true',
                        help="Whether to start from where we left off")
    args = parser.parse_args()

    if args.resume:
        print ("Resuming!")
 
    if os.path.isdir(os.path.join(args.structures, "dftb+")):
        # Looks like we're trying to run dftb+ on a single structure
        process_single_structure(args.structures, resume=args.resume)
    elif os.path.isdir(args.structures):
        # Looks like we're trying to run dftb+ on a batch of structures
        process_batch(args.structures, resume=args.resume)
    else:
        raise RuntimeError("First argument must be a file or a folder")


if __name__ == "__main__":
    main()
