#!/usr/bin/env python
import os
import sys
import argparse as ap
from common import JobBatch, run_dftb, get_all_folders


def do_step(folder, resume=False):
    """Execute DFTB+ on a single job.

    Args:
        folder (str): name of the folder to run DFTB+ in
        resume (bool): whether to skip processing this folder if it has already
            been processed once before.
    """
    if resume and os.path.isfile(os.path.join(folder, 'geo_end.xyz')):
        return
    run_dftb(folder)


def process_single_structure(path, resume=False):
    """Process a collection of configurations for a single structure

    DFTB+ is run asynchronosly on each candidate structure in the folder.

    Args:
        path (str): path to the folder of structures to process.
        resume (bool): whether to start processing from the beginning or skip
            already processed files.
    """
    dftb_files_path = os.path.join(path, "dftb+")
    all_folders = get_all_folders(dftb_files_path)
    num_variations = len(all_folders)

    print("\nProcessing structure {}..."
          .format(path))

    with JobBatch(do_step, all_folders, resume=resume) as batch:
        for i, result in enumerate(batch):
            sys.stdout.write('\rdone {0} of {1}'.format(i+1, num_variations))
            sys.stdout.flush()


def process_batch(path, **kwargs):
    """Process a folder containing a number of different structures

    Args:
        path (str): parent folder containg all the structures DFTB+ needs to be run on.
        kwargs (dict): other keywords to generate a single structure.
    """
    all_folders = get_all_folders(path)
    for folder in all_folders:
        process_single_structure(folder, **kwargs)


def main():
    description = """Run a batch of structures with DFTB+.

    This tool takes either a single structure or a folder full of structures
    and runs DFTB+ in each folder.
    """
    parser = ap.ArgumentParser(description=description,
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
