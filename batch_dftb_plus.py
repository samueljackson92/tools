#!/usr/bin/env python
import os
import sys
import glob
import subprocess
import argparse as ap


def get_all_folders(path):
    all_files = glob.glob(os.path.join(path, "*"))
    return filter(lambda p: os.path.isdir(p), all_files)


def run_dftb(path):
    # redirect output frm dtfb+
    FNULL = open(os.devnull, 'w')
    process = subprocess.Popen('dftb+', cwd=path, stdout=FNULL, stderr=subprocess.STDOUT)
    process.wait()


def process_single_structure(path, resume=False):
    dftb_files_path = os.path.join(path, "dftb+")
    all_folders = get_all_folders(dftb_files_path)
    num_variations = len(all_folders)

    print("Processing structure {}..."
          .format(path))

    for i, folder in enumerate(all_folders):
        if resume and os.path.isfile(os.path.join(folder, 'detailed.out')):
            continue
        sys.stdout.write("\r running variation {} of {}"
                         .format(i, num_variations))
        sys.stdout.flush()
        run_dftb(folder)


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
