#!/usr/bin/env python
import os
import re
import shutil
import sys
import argparse as ap
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from itertools import islice
from common import get_all_folders_containing_pattern


def read_geom_steps(paths):
    values = []
    for path in paths:
        with open(os.path.join(path, "detailed.out"), 'r') as f_handle:
            head = list(islice(f_handle, 3))
            value = int(head[2].strip().split(':')[1])
            values.append(value)

    return pd.Series(values)


def read_energy_conv(path):
    pattern = re.compile(r'Total Energy:\s+([-+]?\d*\.\d+|\d+)\s+H\s+([-+]?\d*\.\d+|\d+)')
    energy = []

    file_name = os.path.join(path, "dftb+.log")
    if not os.path.isfile(file_name):
        return pd.Series()

    with open(file_name, 'r') as f_handle:
        for line in f_handle:
            matches = pattern.findall(line)
            if len(matches) > 0:
                energy.append(float(matches[0][1]))

    return pd.Series(energy)


def read_max_force_conv(path):
    pattern = re.compile(r'Maximal force component:\s+(\d*\.?\d*([Ee][+-]?\d+)?)')
    max_force = []

    file_name = os.path.join(path, "dftb+.log")
    if not os.path.isfile(file_name):
        return pd.Series()

    with open(file_name, 'r') as f_handle:
        for line in f_handle:
            matches = pattern.findall(line)
            if len(matches) > 0:
                max_force.append(float(matches[0][0]))

    return pd.Series(max_force)


def color_fill_plot(df, file_name):
    X = df.columns.values
    Y = df.index.values
    Z = df.values
    Xi, Yi = np.meshgrid(X, Y)
    plt.contourf(Xi, Yi, Z, alpha=0.7, cmap=plt.cm.jet)
    plt.savefig(file_name)


def line_plot(df, file_name):
    df = df.T
    df.plot()
    plt.savefig(file_name)


def histogram_plot(series, file_name):
    plt.figure()
    series.plot(kind='hist', bins=20)
    plt.savefig(file_name)


def safe_remove_folder(path):
    if os.path.isdir(path):
        answer = raw_input("Are you sure you want to overwrite {}? [y/n]".format(path))
        if answer != "y":
            sys.exit()
        else:
            shutil.rmtree(path)

    return


def main():
    description = """
    Generate a set of convergence data and plots for a folder
    of DFTB+ structures.

    This will produce a folder containing the following output files:
        - energy.csv: a csv file containing the energies for every iteration of
            every structure.
        - max_force.csv: a csv file containing the max forces for every
            iteration of every structure.
        - max_geom_steps.csv: a csv file containing the number of geom steps
            that were required for convergence for each structure.
        - energy_cf.png: a contour plot of the energy for each structure and
            iteration.
        - max_force_cf.png: a contour plot of the energy for each structure and
            iteration.
        - energy_lp.png: a line plot of the energy for each structure and
            iteration.
        - max_force_lp.png: a line plot of the energy for each structure and
            iteration.
        - max_geom_steps_hist.png: a histogram plot of the number of geom steps
            for each all structures.
    """
    parser = ap.ArgumentParser(description=description,
                               formatter_class=ap.RawDescriptionHelpFormatter)
    parser.add_argument('input', type=str,
                        help="""A folder containing detailed.out files and
                        dftb+.log files""")
    parser.add_argument('output', type=str,
                        help="""Name of an output folder to write data and
                        plots to.""")

    args = parser.parse_args()
    directory = args.input

    if not os.path.isdir(directory):
        raise RuntimeError("Input should be a directory")

    paths = get_all_folders_containing_pattern("*detailed.out", directory)
    energy_conv = pd.DataFrame([read_energy_conv(path) for path in paths])
    max_force_conv = pd.DataFrame([read_max_force_conv(path) for path in paths])
    max_geom_steps = read_geom_steps(paths)

    safe_remove_folder(args.output)
    os.mkdir(args.output)

    energy_conv.to_csv(os.path.join(args.output, "energy.csv"))
    max_force_conv.to_csv(os.path.join(args.output, "max_force.csv"))
    max_geom_steps.to_csv(os.path.join(args.output, "max_geom_steps.csv"))

    color_fill_plot(energy_conv, os.path.join(args.output, "energy_cf.png"))
    color_fill_plot(max_force_conv, os.path.join(args.output, "max_force_cf.png"))

    line_plot(energy_conv, os.path.join(args.output, "energy_lp.png"))
    line_plot(max_force_conv, os.path.join(args.output, "max_force_lp.png"))

    histogram_plot(max_geom_steps, os.path.join(args.output, "max_geom_steps_hist.png"))

if __name__ == "__main__":
    main()
