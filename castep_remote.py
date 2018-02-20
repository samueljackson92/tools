import os
import paramiko
import argparse as ap
from soprano.hpc.submitter.queues import QueueInterface

if __name__ == "__main__":
    parser = ap.ArgumentParser(description='Run a batch of structures with DFTB+',
                               formatter_class=ap.ArgumentDefaultsHelpFormatter)
    parser.add_argument('location', type=str,
                        help='Username and host address to connect to')
    args = parser.parse_args()
    user, host = args.location.split("@")

    queue = QueueInterface.LSF()
    queue.set_remote_host(host)
    print (queue.list())

    # c = paramiko.SSHClient()
    # c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # c.connect(hostname=host, username=user, look_for_keys=True)
    # print("Connected to {}@{}".format(user, host))
    # stdin, stdout, stderr = c.exec_command("bjobs")
    # print (stdout.read())
    # c.close()
