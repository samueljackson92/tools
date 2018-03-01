#!/usr/bin/env python
import glob
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
    stdout, stderr = run_command(remote, 'if test -d "{}"; then echo True; else echo False; fi'.format(directory))
    return "True" in stdout


def upload(host, directory):
    queue = connect_to_host(host)
    
    with queue._rTarg.context as remote:
        dir_exists = check_directory_exists(remote, directory)

        if not dir_exists or check_overwrite():
            if dir_exists:
                remote.run_cmd('rm -R {}'.format(directory))

            print("Uploading {}".format(directory))
            scp = SCPClient(remote._client.get_transport())
            scp.put(directory, recursive=True,
                    remote_path='~/{}'.format(directory))
            scp.close()

    print("Done!")


def submit(*args, **kwargs):
    wait_time = kwargs.pop("wait_time")

    hdlr = logging.FileHandler(kwargs.pop('log_file'))
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)

    finished = False
    while not finished:
        finished = submit_job(*args, **kwargs)
        if not finished:
            logger.info("Waiting for {} mins".format(wait_time/60.0))
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
            pass

    return stdout, stderr


def submit_job(host, directory, batch_size, walltime, ncores, dry_run):

    logger.info("Running castep_submitter")
    queue = connect_to_host(host)
    
    with queue._rTarg.context as remote:
        dir_exists = check_directory_exists(remote, directory)
        if not dir_exists:
            logger.info("Directory does not exist! Cannot submit jobs")
            return True

        directory = os.path.join(directory, "castep")
        stdout, _ = run_command(remote, 'find {} -type d'.format(directory))
        dir_names = stdout.split()[1:]

        stdout, _ = run_command(remote, 'find {} -name "*-out.cell"'.format(directory))
        cell_files = stdout.split() 
        cell_dirs = map(lambda name: os.path.dirname(name), cell_files)
        unprocessed = filter(lambda name: not name in cell_dirs, dir_names)

        total_num_structures = len(dir_names)
        total_unprocessed = len(unprocessed)
        total_processed = total_num_structures - total_unprocessed

        if total_unprocessed == 0:
            logger.info ("No structures are currently unprocessed for this structure!")
            return True

        logger.info("Number of structures: {}".format(total_num_structures))
        logger.info("Number of processed structures: {}".format(total_processed))
        logger.info("Number of unprocessed structures: {}".format(total_unprocessed))

        logger.info("Removing any .check and .castep_bin files")
        run_command(remote, 'find {} -name "*.castep_bin" | xargs -L1 rm'.format(directory))
        run_command(remote, 'find {} -name "*.check" | xargs -L1 rm'.format(directory))

    jobs = queue.list().values()
    pending_jobs = filter(lambda job: job['job_status'] == 'PEND', jobs)
    num_pending_jobs = len(pending_jobs)

    logger.info("Number of pending jobs: {}".format(num_pending_jobs))

    batch_dirs = unprocessed[:batch_size]
    dry_run = '-d' if dry_run else ''

    if num_pending_jobs > 0:
        logger.info("There are already pending jobs. Quiting")
        return False
    
    logger.info("Submitting {} jobs".format(batch_size))

    with queue._rTarg.context as remote:
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

