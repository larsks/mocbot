#!/usr/bin/python

import argparse
import jinja2
import os
import sys


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('-o', '--output')
    p.add_argument('inputfile')

    return p.parse_args()


def main():
    args = parse_args()

    with open(args.inputfile) as fd:
        template = jinja2.Template(fd.read())

    with (open(args.output, 'w') if args.output else sys.stdout) as fd:
        fd.write(template.render(environ=os.environ))


if __name__ == '__main__':
    main()
