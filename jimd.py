#!/usr/bin/env python3

# PYTHON_ARGCOMPLETE_OK

try:
    import argcomplete
    HAVE_ARGCOMPLETE = True
except ImportError:
    print('WARNING: argcomplete not available')
    HAVE_ARGCOMPLETE = False

import argparse
import collections
import configparser
import codecs
import gettext
import http.server
import importlib.machinery
import jinja2
import markdown
import os
import shutil
import socketserver
import subprocess
import webbrowser

from os.path import dirname
from os.path import exists
from os.path import join
from os.path import splitext

try:

    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent
    HAVE_WATCHDOG = True

except:

    print('WARNING: Unable to initialize monitoring system, compile-on-the-fly not available.')
    HAVE_WATCHDOG = False

# Define Page
Page = collections.namedtuple('Page', ['template', 'output_file', 'page_vars'])

class smart_dict(dict):
    def __missing__(self, key):
        return key

class JIMD:


    def __init__(self):

        # Define constant directory entries
        self.OUT_DIR = 'build'
        self.TPL_DIR = 'templates'
        self.CNT_DIR = 'contents'
        self.PLG_DIR = 'plugins'

        self.PRJ_FILE = 'jimd.conf'
        self.MSG_FILE = 'messages.txt'
        self.TRN_FILE = 'translations.txt'

        self.DEF_TPL = 'base.html'

        self.PUB_CMD = None

        #Find working directory
        proj_dir = os.getcwd()

        while True:

            if exists(join(proj_dir, self.PRJ_FILE)):
                break

            parent_dir = dirname(proj_dir)

            if parent_dir == proj_dir:

                proj_dir = None;
                break

            proj_dir = parent_dir

        if proj_dir is None:

            raise Exception('No project directory found.')

        print('Working directory is ' + proj_dir)

        self.PRJ_DIR = proj_dir

        # Read project config file
        prj_file = join(self.PRJ_DIR, self.PRJ_FILE)
        config = configparser.ConfigParser()

        config.read(join(prj_file))
        jimd_config = config['jimd']

        messages = configparser.ConfigParser()
        messages.read(join(self.PRJ_DIR, self.MSG_FILE), encoding='utf-8')
        self.messages = messages['messages']

        translations = configparser.ConfigParser()
        translations.read(join(self.PRJ_DIR, self.TRN_FILE), encoding='utf-8')
        self.translations = translations['translations']

        if 'pub_cmd' in jimd_config:
            self.PUB_CMD = jimd_config['pub_cmd']

        if 'base_url' in jimd_config:
            self.BASE_URL = jimd_config['base_url']

        #Update folders
        self.OUT_DIR = join(proj_dir, self.OUT_DIR)
        self.TPL_DIR = join(proj_dir, self.TPL_DIR)
        self.CNT_DIR = join(proj_dir, self.CNT_DIR)
        self.PLG_DIR = join(proj_dir, self.PLG_DIR)

        #Initialize markdown
        self.md = markdown.Markdown(extensions=['markdown.extensions.meta', 'markdown.extensions.fenced_code'])

        #Set up jinja templates
        self.env = jinja2.Environment(loader=jinja2.FileSystemLoader(self.TPL_DIR))
        # self.env.install_gettext_translations(gettext.translation('jimd', 'locale', ['de']))
        # self.env.install_null_translations()

        self.env.globals.update(zip=zip)

        # Configure plugins
        for plugin in self.get_plugins():
            try:
                plugin.configure(self, config)
            except AttributeError:
                print('{} module has no configure() method'.format(plugin.__name__))

        self.pages = []
        self.trans = smart_dict()



    def create():

        print('Creating jimd project in current folder')

        for d in [JIMD.TPL_DIR, JIMD.CNT_DIR, JIMD.PLG_DIR]:
            if not exists(d):
                os.mkdir(d)

        open(JIMD.PRJ_FILE, 'a').close()

    def read_markdown(self, input_file):

        input_file = codecs.open(input_file, mode="r", encoding="utf-8")

        md_raw = input_file.read()

        html = self.md.convert(md_raw)

        meta = self.md.Meta

        for key in iter(meta.keys()):
            if len(meta[key]) == 1:
                meta[key] = meta[key][0]

        html = jinja2.Markup(html)

        return html, meta


    # TODO: double parameter template
    def render_template(self, tpl, output_file, **page_vars):

        path = output_file.replace(self.OUT_DIR, '')
        # Make it work on windows
        path = path.replace('\\', '/')
        page_vars['path'] = path
        page_vars['jimd'] = jimd

        new_page = Page(tpl, output_file, page_vars.copy())

        self.pages.append(new_page)

    def render_now(self):

        # First pass: update refs

        for page in self.pages:

            if 'translates' in page.page_vars:

                original_page = page.page_vars['translates']
                path = page.page_vars['path']

                # Set translation
                self.trans[path] = original_page

                # And vice versa
                self.trans[original_page] = path

                if path.endswith('index.html'):

                    # Set translation
                    self.trans[path[:path.index('index.html')]] = original_page[:original_page.index('index.html')]

                    # And vice versa
                    self.trans[original_page[:original_page.index('index.html')]] = path[:path.index('index.html')]

        for page in self.pages:

            # Usecase 1: get link or translated link

            translation = 'translates' in page.page_vars
            links = self.trans if translation else smart_dict()
            msgs = self.translations if translation else self.messages

            content = self.env.get_template(page.template).render(links=links, msg=msgs, **page.page_vars, trans=self.trans)

            with open(page.output_file, 'w', encoding='utf-8') as f:
                f.write(content)

    # root is the directory of the file
    def compile_file(self, root, f):

        # Replace content dir with output dir
        output_dir = root.replace(self.CNT_DIR, self.OUT_DIR)

        # Create missing folders, if necessary
        os.makedirs(output_dir, exist_ok=True)

        # Split file into basename and extenstion
        basename, ext = splitext(f)

        input_file = join(root, f)

        # Copy all files that are not markdown files
        if ext != '.md':

            dst_file = join(output_dir, f)
            shutil.copyfile(input_file, dst_file)

            return

        # Else treat as markdown file
        html, meta = self.read_markdown(input_file)

        # Set template
        template = self.DEF_TPL

        if 'template' in meta.keys():
            template = meta['template']

        meta['content'] = html

        dst_file = join(output_dir, basename + '.html')

        # TODO: Instead of rendering right away, we need to cache this stuff
        # But how to deal with page vars from plugins?
        self.render_template(template, dst_file, **meta)

    def compile_content(self):

        for root, dirnames, files in os.walk(self.CNT_DIR):
            for f in files:
                self.compile_file(root, f)

    def get_plugins(self):
        for plugin_file in os.listdir(self.PLG_DIR):
            basename, ext = splitext(plugin_file)

            if ext != '.py':
                continue

            loader = importlib.machinery.SourceFileLoader(basename, join(self.PLG_DIR, plugin_file))
            plugin = loader.load_module()

            yield plugin

    def fetch(self):

        # Run plugins
        for plugin in self.get_plugins():
            try:
                plugin.fetch(self)
            except AttributeError:
                print('{} module has no configure() method'.format(plugin.__name__))


    def build(self):

        print('Deleting output directory')

        #Delete output dir
        if exists(self.OUT_DIR):

            for f in os.listdir(self.OUT_DIR):

                full_file = join(self.OUT_DIR,f)

                if os.path.isdir(full_file):
                    shutil.rmtree(full_file)
                else:
                    os.remove(full_file)

        else:
            os.mkdir(self.OUT_DIR)

        #Compile content

        print('Compiling content')

        self.compile_content()

        print('Executing plugins')

        #Run plugins
        for plugin in self.get_plugins():
            plugin.build(self)


        # Render page tree
        self.render_now()

    def preview(self):

        if HAVE_WATCHDOG:

            class ContentEventHandler(FileSystemEventHandler):

                def on_modified(_, e):

                    if isinstance(e, FileModifiedEvent):

                        print('recompiling', e.src_path)
                        root, f = os.path.split(e.src_path)
                        self.compile_file(root, f)

            class TemplateEventHandler(FileSystemEventHandler):

                def on_modified(_, e):

                    if isinstance(e, FileModifiedEvent):

                        print('template ' + e.src_path + ' changed, building everything')
                        self.build()

            content_handler = ContentEventHandler()
            content_observer = Observer()
            content_observer.schedule(content_handler, self.CNT_DIR, recursive=True)
            content_observer.start()

            template_handler = TemplateEventHandler()
            template_observer = Observer()
            template_observer.schedule(template_handler, self.TPL_DIR, recursive=True)
            template_observer.start()

        #Fire up webserver

        os.chdir(self.OUT_DIR)

        PORT = 8000

        Handler = http.server.SimpleHTTPRequestHandler

        socketserver.TCPServer.allow_reuse_address = True
        httpd = socketserver.TCPServer(("", PORT), Handler)

        print("Opening browser window")
        webbrowser.open(url='http://localhost:8000')

        print("Starting web server at port", PORT)
        httpd.serve_forever()

    def publish(self, skip_build=False):

        if self.PUB_CMD is None:
            print('Error: No publishing command defined')
        else:

            if not skip_build:

                # First build
                self.build()

            # Then publish
            subprocess.run(self.PUB_CMD, cwd=self.PRJ_DIR, shell=True)

if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    parser.add_argument('command', choices=['build', 'create', 'fetch', 'preview', 'publish'])
    parser.add_argument('--skip-build', action='store_true')

    if HAVE_ARGCOMPLETE:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()

    if args.command == 'create':
        JIMD.create()

    jimd = JIMD()

    if args.command == 'build':
        jimd.build()

    if args.command == 'fetch':
        jimd.fetch()

    if args.command == 'preview':
        jimd.preview()

    if args.command == 'publish':
        jimd.publish(args.skip_build)
