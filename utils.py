import os
import glob

import numpy as np
from ase import io
from ase.calculators.singlepoint import SinglePointCalculator


def get_all_folders(path):
    all_files = glob.glob(os.path.join(path, "*"))
    return filter(lambda p: os.path.isdir(p), all_files)


def tag_muon(atoms):
    """ Set the tag for a muon in an atoms object

    This currently assumes that the muon is the *last* atom
    in the Atoms object.

    | Args:
    |   atoms (ase.Atoms): an Atoms object to set the tag for
    |
    | Returns:
    |   tags (np.array): an updated array of tags where the muon
    |       is set to 1 and all other atoms are set to 0.
    """
    # this assumes that the LAST element in the file is the muon!
    tags = atoms.get_tags()
    tags[-1] = 1
    return tags


def load_cell(file_name):
    atoms_orig = io.read(file_name.replace("geo_end.xyz", "geo_end.gen"))
    return atoms_orig.cell


def load_dtfb(file_name):
    # Load the final positions from the .xyz file
    atoms = io.read(file_name)
    # Load the unit cell from the input .gen file
    atoms.cell = load_cell(file_name)
    atoms.set_tags(tag_muon(atoms))

    try:
        spcalc = DftbSinglePointCalculator(os.path.dirname(file_name), atoms)
        atoms.set_calculator(spcalc)
    except IOError:
        # if there was no calculator then set it to None
        atoms.set_calculator(None)

    return atoms


class DftbSinglePointCalculator(SinglePointCalculator):
    """Single point calculator for DFTB+

    This loads the results Dftb+. This differs from the standard Dftb
    calculator in that it will not remove the output file on load.
   """

    def __init__(self, directory, atoms):
        self.directory = directory
        self.atoms = atoms
        energy, forces, charges = self.read_results(directory)
        results = {}
        results['energy'] = energy
        results['charges'] = charges
        results['forces'] = forces
        SinglePointCalculator.__init__(self, atoms, **results)

    def read_results(self, directory):
        results_file = os.path.join(self.directory, 'results.tag')
        with open(results_file, 'r') as f_handle:
            lines = f_handle.readlines()

        charges = self.read_charges(directory)
        energy = self.read_energy(lines)
        forces = self.read_forces(lines)

        return energy, forces, charges

    def read_energy(self, lines):
        """Read Energy from dftb output file (results.tag)."""
        from ase.units import Hartree
        # Energy line index
        for iline, line in enumerate(lines):
            estring = 'total_energy'
            if line.find(estring) >= 0:
                index_energy = iline + 1
                break
        try:
            return float(lines[index_energy].split()[0]) * Hartree
        except:
            raise RuntimeError('Problem in reading energy')

    def read_forces(self, lines):
        """Read Forces from dftb output file (results.tag)."""
        from ase.units import Hartree, Bohr

        # Force line indexes
        for iline, line in enumerate(lines):
            fstring = 'forces   '
            if line.find(fstring) >= 0:
                index_force_begin = iline + 1
                line1 = line.replace(':', ',')
                index_force_end = iline + 1 + \
                    int(line1.split(',')[-1])
                break
        try:
            gradients = []
            for j in range(index_force_begin, index_force_end):
                word = lines[j].split()
                gradients.append([float(word[k]) for k in range(0, 3)])
            return np.array(gradients) * Hartree / Bohr
        except:
            raise RuntimeError('Problem in reading forces')

    def read_charges(self, directory):
        """ Get partial charges on atoms
            in case we cannot find charges they are set to None
        """
        detailed_file = os.path.join(self.directory, 'detailed.out')
        with open(detailed_file, 'r') as f_handle:
            lines = f_handle.readlines()

        qm_charges = []
        for n, line in enumerate(lines):
            if ('Atom' and 'Net charge' in line):
                chargestart = n + 1
                break
        else:
            # print('Warning: did not find DFTB-charges')
            # print('This is ok if flag SCC=NO')
            return None
        lines1 = lines[chargestart:(chargestart + len(self.atoms))]
        for line in lines1:
            qm_charges.append(float(line.split()[-1]))

        return np.array(qm_charges)


