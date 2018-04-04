# Tools for Running DFTB+ and CASTEP

## batch\_dftb+

The tool `batch_dftb+` can be used to run a folder containing multiple input
files for DFTB+. DFTB+ expects the input parameter file to be specifically
named `dftb_in.hsd`. Also, the output files (`results.out`, `detailed.out`) are
also always call the same thing. Therefore it is expected that each of the
input files existing within there own folder. This tool will glob to find all
`dftb_in.hsd` files.

`batch_dftb+` uses multiprocessing. The tool will run one process of DFTB+ on
each core by default. By default `batch_dftb+` will overwrite any existing
output within a folder. The `--resume` flag will force the tool to check if a
directory contains a `result.out` file. If it does that directory will be
ignored.

## castep\_remote

The tool `castep_remote` can be used to monitor a remote job queue and submit
new jobs when the number of running jobs drops to zero. The tool requires a
host address and folder on the remote sever to monitor for castep input files
to submit. The size of the batch to submit when no other jobs are running can
be controlled with the option `batch-size`. The output of the tool can be
capture to file using the `log-file` option. Optionally, all of the parameters
that can be passed to the exeuctable `castepsub` can also be supplied.

Below is an example of running  `castep_remote`:

```
castep_remote.py submit -b 10 -W 20:00 -n 36 scarf.rl.ac.uk structures/Bithiophene
```

This will monitor the queue at `scarf.rl.ac.uk` and search for `.cell` files in
the folder `structures/Bithiophene`. The `-b` flag tells the tool to submit `10`
jobs whenever the queue is empty. The remaining flags (`-W` and `-n`) are
passed directly to the `castepsub` command.

## dftbconv

`dftbconv` is an analogous to `castepconv` but with much less functionality.
The operation of this tool is very similar to `castepconv`. It can be run in
`input`, `output`, or `all` mode.

 - `input` mode will just create the input files for a convergence test
 - `output` mode will create the output energy and force plots from the results
    of a convergence test.
 - `all` mode will first run input mode, the run DFTB+ on all input files, then
    run output mode.

Like `castepconv` an input seedname is required. The parameter and convergence
file will attempt to be infered from the seedname but can be optional specified
seperately.

To create convergence tests for multiple sets of structures see the section on
`batch_dftbconv`.

## pickle\_structures

`pickle_structures` takes a input folder containing the results from either
DFTB+ or CASTEP and converts the structures to a folder of python pickle files.

## dftb+2castep and castep2dtfb+

This pair of tools can be used to convert DFTB+ input files to CASTEP input
files and CASTEP input to DFTB+ input. They can both be used to convert either
a single file or a folder of input files. In either case an input file or
folder is required along with a parameter file for the structures.

