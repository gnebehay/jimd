#!/usr/bin/env python3

# PYTHON_ARGCOMPLETE_OK

import argcomplete
import argparse
import codecs
import http.server
import importlib.machinery
import jinja2
import markdown
import os
import shutil
import socketserver
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

    print('Unable to initialize monitoring system, compile-on-the-fly not available.')
    HAVE_WATCHDOG = False


class JIMD:

    OUT_DIR = 'build'
    TPL_DIR = 'templates'
    CNT_DIR = 'contents'
    PLG_DIR = 'plugins'

    PRJ_FILE = 'jimd.conf'

    DEF_TPL = 'base.html'

    def __init__(self):

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

        self.PROJ_DIR = proj_dir

        #Update folders
        self.OUT_DIR = join(proj_dir, self.OUT_DIR)
        self.TPL_DIR = join(proj_dir, self.TPL_DIR)
        self.CNT_DIR = join(proj_dir, self.CNT_DIR)
        self.PLG_DIR = join(proj_dir, self.PLG_DIR)

        #Initialize markdown
        self.md = markdown.Markdown(extensions = ['markdown.extensions.meta', 'markdown.extensions.fenced_code'])

        #Set up jinja templates
        self.env = jinja2.Environment(loader=jinja2.FileSystemLoader(self.TPL_DIR))
        self.env.globals.update(zip=zip)

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

    def compile_file(self, root, f):

        basename, ext = splitext(f)

        output_dir = root.replace(self.CNT_DIR, self.OUT_DIR)
        os.makedirs(output_dir, exist_ok = True)

        input_file = join(root, f)

        if ext != '.md':

            #copy file
            dst_file = join(output_dir, f)
            shutil.copyfile(input_file, dst_file)

            return

        #Else treat as markdown file
        html, meta = self.read_markdown(input_file)

        #Set template
        tpl = self.DEF_TPL
        if 'template' in meta.keys():
            tpl = meta['template']

        url = root.replace(self.CNT_DIR, '') + '/' + basename + '.html'

        meta['url'] = url

        content = self.env.get_template(tpl).render(content=html, **meta)

        dst_file = join(output_dir, basename + '.html')

        with open(dst_file, 'w', encoding='utf-8') as f:
            f.write(content)

    def compile_content(self):

        for root, dirnames, files in os.walk(self.CNT_DIR):
            for f in files:
                self.compile_file(root, f)

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
        for plugin_file in os.listdir(self.PLG_DIR):
            basename, ext = splitext(plugin_file)

            if ext != '.py':
                continue

            loader = importlib.machinery.SourceFileLoader(basename, join(self.PLG_DIR, plugin_file))
            plugin = loader.load_module()

            plugin.execute(self)

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

if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    parser.add_argument('command', choices=['build', 'create', 'preview'])

    argcomplete.autocomplete(parser)

    args =  parser.parse_args()

    if args.command == 'create':
        JIMD.create()

    jimd = JIMD()

    if args.command == 'build':
        jimd.build()

    if args.command == 'preview':
        jimd.preview()
