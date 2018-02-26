#!/usr/bin/env python
import argparse as ap
from scp import SCPClient
from soprano.hpc.submitter.queues import QueueInterface

if __name__ == "__main__":
    parser = ap.ArgumentParser(description='Run a batch of structures with DFTB+',
                               formatter_class=ap.ArgumentDefaultsHelpFormatter)
    parser.add_argument('host', type=str,
                        help='Host address to connect to')
    parser.add_argument('directory', type=str,
                        help='Directory of structures to submit to server')

    args = parser.parse_args()

    queue = QueueInterface.LSF()
    queue.set_remote_host(args.host)

    with queue._rTarg.context as remote:
        scp = SCPClient(remote._client.get_transport())
        scp.put(args.directory, recursive=True,
                remote_path='~/{}'.format(args.directory))
        scp.close()
