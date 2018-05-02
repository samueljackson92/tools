#!/usr/bin/env python
import glob
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
    pattern = re.compile(r'Final energy, E\s+=\s+([+-]?\d*\.?\d*([Ee][+-]?\d+)?)\s+eV')
    energy = []

    files = glob.glob(os.path.join(path, "*.castep"))
    if len(files) == 0:
        return pd.Series()

    file_name = os.path.join(path, files[0])
    if not os.path.isfile(file_name):
        return pd.Series()

    with open(file_name, 'r') as f_handle:
        for line in f_handle:
            matches = pattern.findall(line)
            if len(matches) > 0:
                energy.append(float(matches[0][0]))

    return pd.Series(energy)


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
    parser = ap.ArgumentParser(description="""Plot the convergence of a set of
                               structures""",
                               formatter_class=ap.ArgumentDefaultsHelpFormatter)
    parser.add_argument('input', type=str, help='')
    parser.add_argument('output', type=str, help='')

    args = parser.parse_args()
    directory = args.input

    if not os.path.isdir(directory):
        raise RuntimeError("Input should be a directory")

    paths = get_all_folders_containing_pattern("*.castep", directory)
    energy_conv = pd.DataFrame([read_energy_conv(path) for path in paths])

    safe_remove_folder(args.output)
    os.mkdir(args.output)

    energy_conv.to_csv(os.path.join(args.output, "energy.csv"))

    color_fill_plot(energy_conv, os.path.join(args.output, "energy_cf.png"))

    line_plot(energy_conv, os.path.join(args.output, "energy_lp.png"))


if __name__ == "__main__":
    main()
