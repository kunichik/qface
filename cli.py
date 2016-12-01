#!/usr/bin/env python3
# Copyright (c) Pelagicore AB 2016

import click
from subprocess import call
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from path import Path
import time
import os
import sys
import yaml


CWD = Path(__file__).parent

os.environ['PYTHONPATH'] = os.getcwd()


def sh(cmd, all=False, **kwargs):
    click.echo('$ {0}'.format(cmd))
    return call(cmd, shell=True, **kwargs)


@click.group()
def cli():
    pass


@cli.command()
def antlr():
    """generate a new parser based on the grammar using antlr"""
    cwd = str(Path('qface/idl/parser').abspath())
    sh('antlr4 -Dlanguage=Python3 -Werror -package qface.idl.parser -o . -listener -visitor T.g4', cwd=cwd)


@cli.command()
@click.option('--debug/--nodebug')
def test(debug):
    """run the tests"""
    sh('python3 -m pytest -v -s -l {0}'.format('-pdb' if debug else ''))


@cli.command()
def test_ci():
    """run the tests for CI integration"""
    sh('python3 -m pytest -v -s -l')


class RunTestChangeHandler(FileSystemEventHandler):
    def __init__(self, clickContext):
        super(RunTestChangeHandler).__init__()
        self.clickContext = clickContext

    def on_any_event(self, event):
        if event.is_directory:
            return
        if Path(event.src_path).ext == '.py':
            sh('python3 -m pytest')


@cli.command()
@click.pass_context
def test_monitor(ctx):
    """run the tests and re-run on changes"""
    sh('python3 -m pytest')
    while True:
        event_handler = RunTestChangeHandler(ctx)
        observer = Observer()
        observer.schedule(event_handler, './tests', recursive=True)
        observer.schedule(event_handler, './qface', recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()


class RunScriptChangeHandler(FileSystemEventHandler):
    def __init__(self, script, cwd=None):
        super(RunTestChangeHandler).__init__()
        self.script = script
        self.cwd = cwd

    def on_modified(self, event):
        if event.src_path.endswith('.cache'):
            return
        if event.is_directory:
            return
        self.run()

    def run(self):
        sh('python3 {0}'.format(self.script), cwd=self.cwd)


@cli.command()
@click.option('--runner', type=click.File('r'), help="use the runner YAML file to configure the generation")
@click.option('--reload/--no-reload', default=False, help="if enabled auto-reload the generator on input changes")
@click.option('--generator', help="specifies the generator (either by name or path)")
@click.option('--input', type=click.Path(exists=True), help="specifies the input folder")
@click.option('--output', type=click.Path(exists=False), help="specified the output folder")
@click.option('--list/--no-list', help="lists the available generators")
@click.option('--clean/--no-clean', help="initially cleans the output directory")
def generate(runner, generator, input, output, reload, list, clean):
    if list:
        entries = [str(x.name) for x in Path('generator').dirs()]
        click.echo('generators: {0}'.format(entries))
        sys.exit(0)
    """run the named generator"""
    if runner:
        config = yaml.load(runner)
        generator = config['generator']
        input = config['input']
        output = config['output']
    if not generator or not input or not output:
        print('generator, input and output arguments are required')
        sys.exit(-1)
    # check for embedded generator by name
    generator = CWD / 'generator/{0}'.format(generator)
    if not generator.exists():
        generator = Path(generator).abspath()
    # look if generator points to an external generator
    if not generator.exists():
        print('can not find the specified generator: ' + str(generator))
        sys.exit(-1)
    input = Path(input).abspath()
    output = Path(output).abspath()
    generator = Path(generator).abspath()
    if clean:
        output.rmtree_p()
    output.makedirs_p()
    if not reload:
        _generate_once(generator, input, output)
    else:
        _generate_reload(generator, input, output)


def _generate_once(generator, input, output):
    script = '{0}.py'.format(generator.name)
    sh('python3 {0} --input {1} --output {2}'
        .format(script, input, output),
        cwd=generator)


def _generate_reload(generator, input, output):
    """run the named generator and monitor the input and generator folder"""
    script = generator / '{0}.py --input {1} --output {2}'.format(generator.name, input, output)
    event_handler = RunScriptChangeHandler(script, cwd=generator)
    event_handler.run()  # run always once
    observer = Observer()
    observer.schedule(event_handler, generator, recursive=True)
    observer.schedule(event_handler, input, recursive=True)
    observer.schedule(event_handler, './qface', recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


@click.option('--editable/--no-editable', default=False, help='install editable package')
@cli.command()
def install(editable):
    """install the script onto the system using pip3"""
    script_dir = str(Path(__file__).parent.abspath())
    print(script_dir)
    if editable:
        sh('pip3 install --editable {0} --upgrade'.format(script_dir))
    else:
        sh('pip3 install {0} --upgrade'.format(script_dir))


@cli.command()
def uninstall():
    """uninstall the script from the system using pip3"""
    sh('pip3 uninstall qface')


if __name__ == '__main__':
    cli()