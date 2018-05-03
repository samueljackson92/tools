#!/usr/bin/env python
import socket
import os
import argparse as ap
from paramiko.ssh_exception import SSHException
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


def submit(*args, **kwargs):
    SECS_IN_MIN = 60.0
    wait_time = kwargs.pop("wait_time")

    hdlr = logging.FileHandler(kwargs.pop('log_file'))
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    host = kwargs.pop('host')

    finished = False
    while not finished:
        try:
            logger.info("Running castep_submitter")
            queue = connect_to_host(host)

            with queue._rTarg.context as remote:
                finished = submit_job(remote, **kwargs)

            if not finished:
                logger.info("Waiting for {} mins"
                            .format(wait_time/SECS_IN_MIN))
                time.sleep(wait_time)
        except socket.timeout:
            logger.error("Connection timeout, retrying...")
            time.sleep(5)
        except SSHException:
            logger.error("SSH exception, retrying...")
            time.sleep(5)


def run_command(remote, command, **kwargs):
    failed = True

    while failed:
        try:
            stdout, stderr = remote.run_cmd(command, **kwargs)
            failed = False
        except:
            logger.error("Failed to execute command, retrying...")
            time.sleep(5)

    return stdout, stderr


def cleanup_files(remote, directory):
    logger.info("Removing large output files")
    cleanup_files = ['castep_bin', 'check', 'check_bak', 'cst_esp']
    for file_ext in cleanup_files:
        run_command(remote, 'find {0} -name "*.{1}" | xargs -L1 rm'.format(directory, file_ext))


def submit_job(remote, directory, batch_size, walltime, ncores, dry_run):
    if not check_directory_exists(remote, directory):
        logger.info("Directory does not exist! Cannot submit jobs")
        return True

    # Get list of files for each file type from server
    stdout, _ = run_command(remote, 'find {} -name "*.cell"'.format(directory))
    cell_files = stdout.split()
    cell_files = filter(lambda c: not c.endswith('-out.cell'), cell_files)

    stdout, _ = run_command(remote, 'find {} -name "*-out.cell"'.format(directory))
    out_cell_files = stdout.split()

    stdout, _ = run_command(remote, 'find {} -name "*.err"'.format(directory))
    error_files = stdout.split()

    # Work out how many structures have been processed, how many have failed,
    # and how many still need to be run.
    cell_dirs = map(os.path.dirname, cell_files)
    out_cell_dirs = map(os.path.dirname, out_cell_files)
    error_dirs = map(os.path.dirname, error_files)

    unprocessed = filter(lambda name: name not in out_cell_dirs, cell_dirs)
    unprocessed = filter(lambda name: name not in error_dirs, unprocessed)

    unprocessed_cell_files = filter(lambda name: os.path.dirname(name) not
                                    in out_cell_dirs, cell_files)
    unprocessed_cell_files = filter(lambda name: os.path.dirname(name) not
                                    in error_dirs, unprocessed_cell_files)

    total_num_structures = len(cell_files)
    total_unprocessed = len(unprocessed_cell_files)
    total_processed = total_num_structures - total_unprocessed

    logger.info("Number of structures: {}".format(total_num_structures))
    logger.info("Number of processed structures: {}".format(total_processed))
    logger.info("Number of unprocessed structures: {}".format(total_unprocessed))

    # Quit if there are no more stuctures left to process
    if total_unprocessed == 0:
        logger.info("No structures are currently unprocessed for this structure!")
        cleanup_files(remote, directory)  # clean up the last batch of files
        return True

    # Check how many jobs are currently running. If there are no jobs running then
    # we can submit some more jobs.
    logger.info("Finding current job names")
    stdout, stderr = run_command(remote, "bjobs -o 'job_name' | awk 'NR > 1 {print $1}'")
    stack_names = stdout.split("\n")

    num_unprocessed = len(unprocessed)

    unprocessed = filter(lambda name: os.path.basename(name) not in
                         stack_names, unprocessed)
    unprocessed_cell_files = filter(lambda name:
                                    os.path.basename(name).replace(".cell", "")
                                    not in stack_names, unprocessed_cell_files)

    num_queued_jobs = num_unprocessed - len(unprocessed)

    logger.info("Number of pending or running jobs: {}".format(num_queued_jobs))

    # Give up submitting jobs, but don't quit the program if we have more
    # structures to run but the queue is full
    if num_queued_jobs >= num_unprocessed:
        logger.info("There are already too many running/pending jobs. Quiting")
        return False

    cleanup_files(remote, directory)

    # Submit new jobs is the queue is empty
    num_new_jobs = batch_size - num_queued_jobs
    logger.info("Submitting {} jobs".format(num_new_jobs))

    batch_dirs = unprocessed[:num_new_jobs]
    batch_cell_files = unprocessed_cell_files[:num_new_jobs]

    dry_run = '-d' if dry_run else ''

    for cell_file, path in zip(batch_cell_files, batch_dirs):
        logger.info(cell_file)
        seed_name = os.path.basename(os.path.splitext(cell_file)[0])
        command = "castepsub {} -n {} -W {} {}".format(dry_run, ncores,
                                                       walltime, seed_name)
        stdout, _ = run_command(remote, command, cwd=path)
        logger.info(stdout)

    return False


if __name__ == "__main__":
    description = """Submit CASTEP jobs to a remote queue.

    This tool automates the process of submitting jobs to a remote job queue.
    The tool will submit a batch of structures to a remote job queue, then
    watch the queue until space becomes available to submit another job. The
    limit of the number of jobs to be submitted at any one time is determined
    by the batch_size argument.
    """

    parser = ap.ArgumentParser(description=description,
                               formatter_class=ap.ArgumentDefaultsHelpFormatter)

    parser.add_argument('host', type=str,
                        help='Host address to connect to. e.g. scarf.rl.ac.uk')
    parser.add_argument('directory', type=str,
                        help='Directory of structures to monitor.')
    parser.add_argument('-b', '--batch-size', type=int,
                        default=10, required=False,
                        help='Batch size to submit to the server.')
    parser.add_argument('-W', '--walltime', type=str,
                        default='5:00', required=False,
                        help="""Approximate walltime required from the job.
                        This option will be passed directly to CASTEP""")
    parser.add_argument('-n', '--ncores', type=str, default=36, required=False,
                        help="""Number of cores. This option will be passed
                        directly to CASTEP.""")
    parser.add_argument('-d', '--dry-run', action='store_true',
                        default=False, required=False,
                        help="""Dry run flag. No jobs will actually be
                        submitted with this option. This option will be passed
                        directly to CASTEP""")
    parser.add_argument('--wait-time', type=int, default=600, required=False,
                        help="""Number of seconds to wait before reattempting a failed command.""")
    parser.add_argument('-l', '--log-file', type=str,
                        default='/var/tmp/castep_submitter.log',
                        required=False,
                        help='Location to direct logging output to')

    kwargs = vars(parser.parse_args())
    submit(**kwargs)

