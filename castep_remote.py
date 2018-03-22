#!/usr/bin/env python
import sys
import socket
import os
import argparse as ap
from scp import SCPClient
from soprano.hpc.submitter.queues import QueueInterface
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("castep_submitter")


def check_overwrite():
    text = ''
    while text not in ['y', 'n']:
        print("Directory already exists. Do you wish to overwrite? (y/n)")
        text = raw_input()

    return text == 'y'


def connect_to_host(host):
    queue = QueueInterface.LSF()
    queue.set_remote_host(host)
    return queue


def check_directory_exists(remote, directory):
    command = 'if test -d "{}"; then echo True; else echo False; fi'.format(directory)
    stdout, stderr = run_command(remote, command)
    return "True" in stdout


def progress(filename, size, sent):
    sys.stdout.write("Uploading {}\r".format(filename))


def upload(host, directory):
    queue = connect_to_host(host)

    with queue._rTarg.context as remote:
        dir_exists = check_directory_exists(remote, directory)

        if not dir_exists or check_overwrite():
            if dir_exists:
                remote.run_cmd('rm -R {}'.format(directory))

            print("Uploading {}".format(directory))
            scp = SCPClient(remote._client.get_transport(), progress=progress)
            scp.put(directory, recursive=True,
                    remote_path='~/{}'.format(directory))
            scp.close()

    print("Done!")


def submit(*args, **kwargs):
    SECS_IN_MIN = 60.0
    wait_time = kwargs.pop("wait_time")

    hdlr = logging.FileHandler(kwargs.pop('log_file'))
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)

    finished = False
    while not finished:
        try:
            finished = submit_job(*args, **kwargs)
        except socket.timeout:
            logger.error("Connection timeout, retrying...")
            time.sleep(5)

        if not finished:
            logger.info("Waiting for {} mins".format(wait_time/SECS_IN_MIN))
            time.sleep(wait_time)


def run_command(remote, command, **kwargs):
    failed = True

    while failed:
        try:
            stdout, stderr = remote.run_cmd(command, **kwargs)
            failed = False
        except:
            logger.error("Failed to connect, retrying...")
            time.sleep(5)

    return stdout, stderr


def submit_job(host, directory, batch_size, walltime, ncores, dry_run):

    logger.info("Running castep_submitter")
    queue = connect_to_host(host)

    with queue._rTarg.context as remote:
        dir_exists = check_directory_exists(remote, directory)
        if not dir_exists:
            logger.info("Directory does not exist! Cannot submit jobs")
            return True

        stdout, _ = run_command(remote, 'find {} -name "*.cell"'.format(directory))
        cell_files = stdout.split()

        stdout, _ = run_command(remote, 'find {} -name "*-out.cell"'.format(directory))
        out_cell_files = stdout.split()

        stdout, _ = run_command(remote, 'find {} -name "*.err"'.format(directory))
        error_files = stdout.split()

        cell_dirs = map(lambda name: os.path.dirname(name), cell_files)
        out_cell_dirs = map(lambda name: os.path.dirname(name), out_cell_files)
        error_dirs = map(lambda name: os.path.dirname(name), error_files)
        unprocessed = filter(lambda name: name not in out_cell_dirs, cell_dirs)
        unprocessed = filter(lambda name: name not in error_dirs, unprocessed)

        total_num_structures = len(cell_files)
        total_unprocessed = total_num_structures - len(out_cell_files)
        total_processed = total_num_structures - total_unprocessed

        logger.info("Number of structures: {}".format(total_num_structures))
        logger.info("Number of processed structures: {}".format(total_processed))
        logger.info("Number of unprocessed structures: {}".format(total_unprocessed))

        if total_unprocessed == 0:
            logger.info ("No structures are currently unprocessed for this structure!")
            return True

        logger.info("Finding current job names")
        stdout, stderr = run_command(remote, "bjobs -o 'job_name' | awk 'NR > 1 {print $1}'")
        stack_names = stdout.split("\n")

        num_unprocessed = len(unprocessed)
        unprocessed = filter(lambda name: os.path.basename(name) not in stack_names, unprocessed)
        num_queued_jobs = num_unprocessed - len(unprocessed)

        logger.info("Number of pending or running jobs: {}".format(num_queued_jobs))

        batch_dirs = unprocessed[:batch_size]
        dry_run = '-d' if dry_run else ''

        if num_queued_jobs > 0:
            logger.info("There are already running/pending jobs. Quiting")
            return False

        logger.info("Removing large output files")
        run_command(remote, 'find {} -name "*.castep_bin" | xargs -L1 rm'.format(directory))
        run_command(remote, 'find {} -name "*.check_bak" | xargs -L1 rm'.format(directory))
        run_command(remote, 'find {} -name "*.check" | xargs -L1 rm'.format(directory))
        run_command(remote, 'find {} -name "*.cst_esp" | xargs -L1 rm'.format(directory))

        logger.info("Submitting {} jobs".format(batch_size))

        for path in batch_dirs:
            stdout, _ = run_command(remote, "castepsub {} -n {} -W {} {}".format(
                dry_run, ncores, walltime, os.path.basename(path)), cwd=path)
            logger.info(stdout)

    return False


if __name__ == "__main__":
    parser = ap.ArgumentParser(description='Run a batch of structures with DFTB+',
                               formatter_class=ap.ArgumentDefaultsHelpFormatter)

    subparsers = parser.add_subparsers(dest='subparser')

    parser_upload = subparsers.add_parser('upload')
    parser_upload.add_argument('host', type=str,
                               help='Host address to connect to')
    parser_upload.add_argument('directory', type=str,
                               help='Directory of structures to submit to server')

    parser_upload = subparsers.add_parser('submit')
    parser_upload.add_argument('host', type=str,
                               help='Host address to connect to')
    parser_upload.add_argument('directory', type=str,
                               help='Directory of structures to submit to server')
    parser_upload.add_argument('-b', '--batch-size', type=int, default=10, required=False,
                               help='Batch size to submit to the server')
    parser_upload.add_argument('-W', '--walltime', type=str, default='5:00', required=False,
                               help='Approximate walltime to pass to CASTEP')
    parser_upload.add_argument('-n', '--ncores', type=str, default=36, required=False,
                               help='Number of cores to pass to CASTEP')
    parser_upload.add_argument('-d', '--dry-run', action='store_true', default=False, required=False,
                               help='Dry run flag to pass to CASTEP')
    parser_upload.add_argument('-l', '--log-file', type=str, default='/var/tmp/castep_submitter.log', required=False,
                               help='Logging file to output to')
    parser_upload.add_argument('--wait-time', type=int, default=600, required=False,
                               help='Number of seconds to wait before attempting submission')

    kwargs = vars(parser.parse_args())
    globals()[kwargs.pop('subparser')](**kwargs)

