import fnmatch
import functools
import glob
import json
import os
import shutil
import subprocess
import sys
from multiprocessing import Pool

import numpy as np

from ase import io
from ase.calculators.dftb import Dftb
from ase.calculators.singlepoint import SinglePointCalculator


class JobBatch:
    """A class to create and manage a job pool

    Accepts a function, a collection of items to
    map over and any additional parameters to pass
    to the function.
    """

    def __init__(self, func, items, ncores=None, **params):
        """Create a new job batch run

        Args:
            func (function): function to execute on every item
            items (list): list of items to call func on in parallel
            ncores (int): max number of processes to run in parallel
            params (dict): dict of keyword parameters to be passed to func
        """
        self._func = functools.partial(func, **params)
        self._items = items
        self._ncores = ncores

    def __enter__(self):
        """Create the job pool and jobs to run"""
        self._pool = Pool(processes=self._ncores)
        self._jobs = self._pool.imap_unordered(self._func, self._items)
        return self

    def __iter__(self):
        """Return the iterator to the jobs"""
        return self

    def __next__(self):
        """Get the next job to be executed in the queue"""
        # Setting a timeout here works around this bug:
        # https://bugs.python.org/issue8296
        # which prevents the user from killing all processes with Ctrl+C
        result = self._jobs.next(timeout=sys.maxint)
        return result

    def next(self):
        """Get the next job to be executed in the queue

        This method is implemented for python2 support
        """
        return self.__next__()

    def __exit__(self, type, value, traceback):
        """Close the job pool when finished"""
        self._pool.close()


class NameGenerator:
    """Generator to create names matching a pattern with
    zero padded numbers appended.
    """

    def __init__(self, pattern, size):
        self._pattern = pattern
        self._num_format = self._get_padded_number_format(size)
        self._count = 0

    def _get_padded_number_format(self, size):
        return '{{0:0{0}n}}'.format(int(np.floor(np.log10(size))+1))

    def __iter__(self):
        return self

    def __next__(self):
        self._count += 1
        ext = self._num_format.format(self._count)
        return self._pattern.format(ext)

    def next(self):
        return self.__next__()


class BackupFile():
    """Backup a file before performing an operation

    A class to make a copy of a file before performing some
    potentially unsafe operation on it. In either succes or failure
    the copy of the original file it restored.
    """

    def __init__(self, file_name, backup_file):
        """Create a temporary backup file while executing some
        potentially unsafe operation.

        Args:
          file_name (str): path of the file to backup.
          backup_file (str): path to backup the file to.
        """
        self._file_name = file_name
        self._backup_file = backup_file

    def __enter__(self):
        """Copy the file to the backup location"""
        shutil.copyfile(self._file_name, self._backup_file)
        return self

    def __exit__(self, type, value, traceback):
        """Replace and overwrite the file to the original location"""
        shutil.move(self._backup_file, self._file_name)


def run_dftb(path):
    """Run DFTB+

    This will run DFTB+ as a seperate process but will block and wait for the
    program to finished executing.

    Args:
        path (str): directory to run DFTB+ in.
    """
    # redirect output from dtfb+
    log_file = open(os.path.join(path, "dftb+.log"), 'w')
    process = subprocess.Popen('dftb+', cwd=path, stdout=log_file,
                               stderr=subprocess.STDOUT)
    process.wait()


def get_all_folders(path):
    """Get all directories within a file path

    Args:
      file_name (str): path to search for directories in.
    """
    all_files = glob.glob(os.path.join(path, "*"))
    return filter(lambda p: os.path.isdir(p), all_files)


def get_all_folders_containing_pattern(pattern, directory):
    """Get all directories containing a file matching pattern

    Args:
      pattern (str): pattern to match file names against
      directory (str): path to search for directories in.

    Return:
        matches (list) list of matches folder paths
    """
    matches = []
    for root, dirnames, filenames in os.walk(directory):
        for filename in fnmatch.filter(filenames, pattern):
            matches.append(root)
    return matches


def tag_muon(atoms):
    """ Set the tag for a muon in an atoms object

    This currently assumes that the muon is the *last* atom
    in the Atoms object.

    Args:
      atoms (ase.Atoms): an Atoms object to set the tag for

    Returns:
      tags (np.array): an updated array of tags where the muon
          is set to 1 and all other atoms are set to 0.
    """
    # this assumes that the LAST element in the file is the muon!
    tags = atoms.get_tags()
    tags[-1] = 1
    return tags


def load_dftb_calculator(directory, atoms):
    """ Set the tag for a muon in an atoms object

    Args:
      directory (str): path to a directory to load DFTB+ results

    Returns:
      calculator (ase.calculator.SinglePointCalculator): a single
        point calculator for the results of the DFTB+ calculation
    """
    results_file = os.path.join(directory, "results.tag")
    temp_file = os.path.join(directory, "results.tag.bak")

    # We need to backup the results file here because
    # .read_results() will remove the results file
    with BackupFile(results_file, temp_file):
        calc = Dftb(atoms=atoms)
        calc.atoms_input = atoms
        calc.directory = directory
        calc.read_results()

    return SinglePointCalculator(atoms, energy=calc.get_potential_energy(),
                                 forces=calc.get_forces(),
                                 charges=calc.get_charges(atoms),
                                 stress=calc.get_stress(atoms))


def load_dtfb(file_name):
    """Load the results of a DFTB+ calculation

    Unlike the calculator in ase this loader is not destructive and
    and will not remove the results.out file after loading it.

    Args:
      file_name (str): the name of the .xyz file to load a structure from

    Returns:
      atoms (ase.Atoms): the loaded ase atoms object with a DFTB+
        single point calculator containing thr results of the computation
        attached.
    """
    file_name = file_name.replace('results.tag', 'geo_end.xyz')
    # Load the final positions from the .xyz file
    atoms = io.read(file_name)
    # Load the unit cell from the input .gen file
    original_file_name = file_name.replace("geo_end.xyz", "geo_end.gen")
    atoms_orig = io.read(original_file_name)
    atoms.cell = atoms_orig.cell
    atoms.set_tags(tag_muon(atoms))

    directory = os.path.dirname(file_name)

    try:
        spcalc = load_dftb_calculator(directory, atoms)
        atoms.set_calculator(spcalc)
    except IOError, e:
        # if there was no calculator then set it to None
        print ("Warning: Could not load calculator for {}".format(file_name))
        print (e)
        atoms.set_calculator(None)

    atoms.info['original_file'] = original_file_name
    atoms.set_tags(tag_muon(atoms))
    return atoms


def load_castep(file_name):
    """Load the results of a CASTEP calculation

    Args:
      file_name (str): name of the `*-out.cell` file to load.

    Returns:
      atoms (ase.Atoms): the loaded ase atoms object with a CASTEP
        single point calculator containing thr results of the computation
        attached.
    """
    atoms = io.read(file_name)
    try:
        # Create a calculator to store the energy & forces
        atoms_cast = io.read(file_name.replace('-out.cell', '.castep'))
        energy = atoms_cast.get_potential_energy()
        forces = atoms_cast.get_forces()
        spcalc = SinglePointCalculator(atoms, energy=energy, forces=forces)
        atoms.set_calculator(spcalc)
    except:
        # Something is wrong. The run didn't finish executing or failed to
        # converge
        print("Failed to load -out.cell file")
    atoms.set_tags(tag_muon(atoms))
    atoms.info['original_file'] = file_name.replace('-out.cell', '.cell')
    return atoms


def load_dftb_precon(file_name):
    """Load the results of a DFTB+ calculation that was run
    with the ASE preconditioned optimizer

    Args:
        file_name (str): name of the `results.json` file to load.

    Returns:
      atoms (ase.Atoms): the loaded ase atoms object with a DFTB+
        single point calculator containing the results of the computation
        attached.
    """

    def load_file(file_name):
        atoms = io.read(file_name)
        atoms_orig = io.read(file_name.replace(".xyz", ".gen"))
        atoms.cell = atoms_orig.cell
        return atoms

    results = json.load(open(file_name, 'r'))
    atoms_file = 'geo_end.xyz'
    atoms = load_file(os.path.join(os.path.dirname(file_name), atoms_file))

    calc = SinglePointCalculator(atoms, energy=results['energy'],
                                 forces=results['forces'])
    atoms.set_calculator(calc)
    atoms.set_tags(tag_muon(atoms))

    return atoms

